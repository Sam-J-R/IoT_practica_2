"""Registro asíncrono: un destino lento no detiene el control TCP."""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from queue import Empty, Full, Queue
import threading
import time
from typing import Any, Optional, Union


class RegistroPruebas:
    """Cola acotada; descarta eventos nuevos si se llena y deja constancia.

    Los errores de un destino lo deshabilitan sin interrumpir el servidor.
    `error` conserva el último fallo y `descartados` cuenta la saturación.
    """

    def __init__(self, ruta: Optional[Union[Path, str]] = None,
                 capacidad: int = 1024) -> None:
        if capacidad < 1:
            raise ValueError("La capacidad del registro debe ser positiva")
        self.bloqueo = threading.Lock()
        self.cola: Queue[dict[str, Any]] = Queue(maxsize=capacidad)
        self.detener = threading.Event()
        self.error: Optional[str] = None
        self.descartados = 0
        self.archivo = None
        if ruta:
            ruta_path = Path(ruta)
            ruta_path.parent.mkdir(parents=True, exist_ok=True)
            # Un error al abrir impide iniciar, antes de aceptar clientes.
            self.archivo = ruta_path.open("a", encoding="utf-8")
        self.archivo_activo = self.archivo is not None
        self.consola_activa = True
        self.hilo = threading.Thread(target=self._escribir, name="registro-eventos", daemon=True)
        self.hilo.start()

    @staticmethod
    def _fila(evento: str, **datos: Any) -> dict[str, Any]:
        return {"fecha_utc": datetime.now(timezone.utc).isoformat(),
                "tiempo_monotonico": time.monotonic(), "evento": evento, **datos}

    def registrar(self, evento: str, **datos: Any) -> None:
        fila = self._fila(evento, **datos)
        with self.bloqueo:
            if self.detener.is_set():
                return
            try:
                self.cola.put_nowait(fila)
            except Full:
                self.descartados += 1

    def _fallo(self, destino: str, error: Exception) -> None:
        with self.bloqueo:
            self.error = f"{destino}: {error}"
        if self.consola_activa:
            try:
                logging.error("FALLO_REGISTRO %s", self.error)
            except Exception:
                self.consola_activa = False

    def _guardar(self, fila: dict[str, Any]) -> None:
        if self.consola_activa:
            try:
                logging.info("%s %s", fila["evento"], fila)
            except Exception as error:
                self.consola_activa = False
                self._fallo("consola", error)
        if self.archivo_activo:
            try:
                texto = json.dumps(fila, ensure_ascii=False, allow_nan=False)
                self.archivo.write(texto + "\n")
                self.archivo.flush()
            except Exception as error:
                self.archivo_activo = False
                self._fallo("archivo", error)

    def _escribir(self) -> None:
        informados = 0
        try:
            while not self.detener.is_set() or not self.cola.empty():
                try:
                    fila = self.cola.get(timeout=0.1)
                except Empty:
                    continue
                self._guardar(fila)
                with self.bloqueo:
                    descartados = self.descartados
                if descartados > informados:
                    self._guardar(self._fila("REGISTROS_DESCARTADOS",
                                              cantidad=descartados - informados,
                                              total=descartados))
                    informados = descartados
        finally:
            if self.archivo:
                try:
                    self.archivo.close()
                except Exception as error:
                    self._fallo("cierre_archivo", error)

    def cerrar(self) -> None:
        with self.bloqueo:
            self.detener.set()
        # Un destino bloqueado no debe impedir detener el servidor.
        if self.hilo is not threading.current_thread():
            self.hilo.join(timeout=0.6)
        if self.hilo.is_alive():
            with self.bloqueo:
                self.error = "Cierre del registro incompleto: destino bloqueado"
