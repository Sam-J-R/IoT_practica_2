"""Servidor TCP con hilos para clientes y supervisión de seguridad.

Un hilo acepta clientes, cada conexión tiene un hilo lector y un hilo
supervisor controla los tiempos. Un RLock protege roles, filtro y órdenes.
"""
import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import socket
import threading
import time
from typing import Any, Callable, Optional, Union

from .control import ConfiguracionServidor, ControlDistancia, EstadoLed
from .protocolo import ErrorProtocolo, ProtocoloAplicacion, ReceptorLineas


class RegistroPruebas:
    """Registra eventos JSONL sin mezclar escrituras entre hilos."""

    def __init__(self, ruta: Optional[Union[Path, str]] = None) -> None:
        self.bloqueo = threading.Lock()
        self.archivo = None
        if ruta:
            ruta_path = Path(ruta)
            ruta_path.parent.mkdir(parents=True, exist_ok=True)
            self.archivo = ruta_path.open("a", encoding="utf-8")

    def registrar(self, evento: str, **datos: Any) -> None:
        fila = {
            "fecha_utc": datetime.now(timezone.utc).isoformat(),
            "tiempo_monotonico": time.monotonic(),
            "evento": evento,
            **datos,
        }
        with self.bloqueo:
            logging.info("%s %s", evento, datos)
            if self.archivo:
                self.archivo.write(json.dumps(fila, ensure_ascii=False, allow_nan=False) + "\n")
                self.archivo.flush()

    def cerrar(self) -> None:
        with self.bloqueo:
            if self.archivo:
                self.archivo.close()
                self.archivo = None


class SesionCliente:
    """Datos del socket, rol y confirmación pendiente de un cliente."""

    def __init__(self, conexion: socket.socket, direccion: Any, identificador: int,
                 creada: float) -> None:
        self.conexion = conexion
        self.direccion = direccion
        self.identificador = identificador
        self.creada = creada
        self.rol = ""
        self.receptor = ReceptorLineas()
        self.ultima_lectura = creada
        self.numero_lectura = 0
        self.numero_orden = 0
        self.numero_pendiente = 0
        self.estado_pendiente: EstadoLed = EstadoLed.APAGADO
        self.inicio_orden = 0.0
        self.estado_confirmado: Optional[EstadoLed] = None
        self.ultimo_envio = creada
        self.cerrada = False


class ServidorTcp:
    """Coordina sensor y actuador usando un hilo lector por cliente.

    La lectura de sockets se realiza fuera del bloqueo; solo la modificación
    del estado compartido y los envíos breves se hacen bajo el RLock.
    """

    def __init__(self, configuracion: Optional[ConfiguracionServidor] = None,
                 registro: Optional[RegistroPruebas] = None,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        self.configuracion = configuracion or ConfiguracionServidor()
        self.registro = registro or RegistroPruebas()
        self.reloj = reloj
        self.escucha: Optional[socket.socket] = None
        self.sesiones: dict[socket.socket, SesionCliente] = {}
        self.roles: dict[str, SesionCliente] = {}
        self.control = ControlDistancia(self.configuracion)
        self.siguiente_sesion = 0
        self.bloqueo = threading.RLock()
        self.detener = threading.Event()
        self.hilos: list[threading.Thread] = []

    @property
    def puerto(self) -> int:
        if self.escucha is None:
            raise RuntimeError("Servidor no iniciado")
        return self.escucha.getsockname()[1]

    def iniciar(self) -> None:
        if self.escucha is not None:
            raise RuntimeError("Servidor ya iniciado")
        conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conexion.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            conexion.bind((self.configuracion.direccion, self.configuracion.puerto))
            conexion.listen(self.configuracion.maximo_clientes)
            conexion.settimeout(0.2)
        except Exception:
            conexion.close()
            raise
        self.escucha = conexion
        self.detener.clear()
        self.registro.registrar("SERVIDOR_INICIADO", puerto=self.puerto, modo="HILOS")
        self._iniciar_hilo(self._aceptar, "tcp-aceptador")
        self._iniciar_hilo(self._supervisar, "tcp-supervisor")

    def _iniciar_hilo(self, tarea: Callable[..., None], nombre: str,
                      *args: Any) -> None:
        hilo = threading.Thread(target=tarea, args=args, name=nombre, daemon=True)
        self.hilos.append(hilo)
        hilo.start()

    def _aceptar(self) -> None:
        while not self.detener.is_set():
            try:
                if self.escucha is None:
                    return
                conexion, direccion = self.escucha.accept()
            except socket.timeout:
                continue
            except OSError:
                if not self.detener.is_set():
                    logging.exception("Error aceptando conexiones")
                return
            conexion.settimeout(0.25)
            conexion.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self.bloqueo:
                if self.detener.is_set() or len(self.sesiones) >= self.configuracion.maximo_clientes:
                    conexion.close()
                    self.registro.registrar("CLIENTE_RECHAZADO", motivo="LIMITE_CLIENTES")
                    continue
                self.siguiente_sesion += 1
                sesion = SesionCliente(conexion, direccion, self.siguiente_sesion, self.reloj())
                self.sesiones[conexion] = sesion
                self.registro.registrar("CONEXION", sesion=sesion.identificador,
                                        direccion=str(direccion))
                self._iniciar_hilo(self._leer_cliente, f"tcp-cliente-{sesion.identificador}", sesion)

    def _leer_cliente(self, sesion: SesionCliente) -> None:
        while not self.detener.is_set() and not sesion.cerrada:
            try:
                datos = sesion.conexion.recv(1024)
            except socket.timeout:
                continue
            except OSError:
                with self.bloqueo:
                    self._cerrar_sesion(sesion, "ERROR_SOCKET")
                break
            if not datos:
                with self.bloqueo:
                    self._cerrar_sesion(sesion, "CIERRE_TCP")
                break
            try:
                for linea in sesion.receptor.recibir(datos):
                    with self.bloqueo:
                        if sesion.cerrada:
                            break
                        self._procesar(sesion, linea)
            except ErrorProtocolo as error:
                with self.bloqueo:
                    if not sesion.cerrada:
                        self._rechazar(sesion, error.codigo)
                break

    def _enviar(self, sesion: SesionCliente, mensaje: str) -> bool:
        """El bloqueo del servidor serializa los envíos y preserva su orden."""
        if sesion.cerrada:
            return False
        try:
            sesion.conexion.sendall(ProtocoloAplicacion.codificar(mensaje))
            self.registro.registrar("MENSAJE_ENVIADO", sesion=sesion.identificador,
                                    mensaje=mensaje)
            return True
        except (OSError, socket.timeout):
            self._cerrar_sesion(sesion, "FALLO_ENVIO")
            return False

    def _rechazar(self, sesion: SesionCliente, codigo: str) -> None:
        self.registro.registrar("ERROR_PROTOCOLO", sesion=sesion.identificador, codigo=codigo)
        self._enviar(sesion, f"ERROR codigo={codigo}")
        self._cerrar_sesion(sesion, "ERROR_PROTOCOLO")

    def _cerrar_sesion(self, sesion: SesionCliente, motivo: str) -> None:
        if sesion.cerrada:
            return
        sesion.cerrada = True
        self.sesiones.pop(sesion.conexion, None)
        if self.roles.get(sesion.rol) is sesion:
            del self.roles[sesion.rol]
            if sesion.rol == "sensor":
                self.control.invalidar()
                self._solicitar_estado()
        try:
            sesion.conexion.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sesion.conexion.close()
        self.registro.registrar("DESCONEXION", sesion=sesion.identificador,
                                rol=sesion.rol, motivo=motivo)

    def _solicitar_estado(self, forzar: bool = False) -> None:
        actuador = self.roles.get("actuador")
        if actuador is None or actuador.cerrada or actuador.numero_pendiente:
            return
        if not forzar and actuador.estado_confirmado == self.control.estado:
            return
        actuador.numero_orden += 1
        actuador.numero_pendiente = actuador.numero_orden
        actuador.estado_pendiente = self.control.estado
        actuador.inicio_orden = self.reloj()
        actuador.ultimo_envio = self.reloj()
        enviado = self._enviar(
            actuador, f"ORDEN numero={actuador.numero_orden}, estado={self.control.estado}")
        if enviado:
            self.registro.registrar("ORDEN", sesion=actuador.identificador,
                                    numero=actuador.numero_orden, estado=str(self.control.estado))

    def _procesar(self, sesion: SesionCliente, linea: str) -> None:
        mensaje = ProtocoloAplicacion.interpretar(linea)
        argumentos = mensaje.argumentos
        self.registro.registrar("MENSAJE_RECIBIDO", sesion=sesion.identificador, mensaje=linea)
        if mensaje.comando == "REGISTRO":
            if sesion.rol:
                raise ErrorProtocolo("YA_REGISTRADO")
            rol = argumentos["tipo"]
            anterior = self.roles.get(rol)
            if anterior:
                self._cerrar_sesion(anterior, "REEMPLAZO")
            sesion.rol = rol
            sesion.ultima_lectura = self.reloj()
            self.roles[rol] = sesion
            self._enviar(sesion, "ACEPTADO REGISTRO")
            self.registro.registrar("REGISTRO", sesion=sesion.identificador, rol=rol)
            if rol == "actuador":
                self._solicitar_estado(forzar=True)
            return
        if not sesion.rol:
            raise ErrorProtocolo("SIN_REGISTRO")
        if mensaje.comando == "LECTURA" and sesion.rol == "sensor":
            numero = argumentos["numero"]
            if numero <= sesion.numero_lectura:
                raise ErrorProtocolo("SECUENCIA")
            sesion.numero_lectura = numero
            sesion.ultima_lectura = self.reloj()
            estado = self.control.procesar(argumentos["distancia_cm"])
            self._enviar(sesion, f"RECIBIDO numero={numero}")
            self.registro.registrar(
                "LECTURA", sesion=sesion.identificador, numero=numero,
                tiempo_sensor_ms=argumentos["tiempo_ms"],
                distancia_cm=argumentos["distancia_cm"],
                filtrada_cm=self.control.distancia_filtrada, estado=str(estado))
            self._solicitar_estado()
        elif mensaje.comando == "APLICADO" and sesion.rol == "actuador":
            if (sesion.numero_pendiente == 0 or
                    argumentos["numero"] != sesion.numero_pendiente):
                raise ErrorProtocolo("CONFIRMACION")
            if self.reloj() - sesion.inicio_orden >= self.configuracion.espera_confirmacion:
                raise ErrorProtocolo("CONFIRMACION_TARDIA")
            sesion.estado_confirmado = sesion.estado_pendiente
            self.registro.registrar("APLICADO", sesion=sesion.identificador,
                                    numero=sesion.numero_pendiente,
                                    estado=str(sesion.estado_pendiente),
                                    latencia_confirmacion_ms=(self.reloj() - sesion.inicio_orden) * 1000)
            sesion.numero_pendiente = 0
            self._solicitar_estado()
        elif mensaje.comando == "ERROR":
            self._cerrar_sesion(sesion, "ERROR_CLIENTE_" + argumentos["codigo"])
        else:
            raise ErrorProtocolo("ROL")

    def _temporizadores(self) -> None:
        ahora = self.reloj()
        c = self.configuracion
        for sesion in list(self.sesiones.values()):
            if not sesion.rol and ahora - sesion.creada >= c.espera_registro:
                self._cerrar_sesion(sesion, "REGISTRO_TIEMPO_AGOTADO")
            elif sesion.rol == "sensor" and ahora - sesion.ultima_lectura >= c.inactividad_sensor:
                self._cerrar_sesion(sesion, "SENSOR_INACTIVO")
            elif sesion.numero_pendiente and ahora - sesion.inicio_orden >= c.espera_confirmacion:
                self._cerrar_sesion(sesion, "CONFIRMACION_TIEMPO_AGOTADO")
        actuador = self.roles.get("actuador")
        if actuador and ahora - actuador.ultimo_envio >= c.intervalo_refresco:
            self._solicitar_estado(forzar=True)

    def _supervisar(self) -> None:
        while not self.detener.wait(0.025):
            with self.bloqueo:
                self._temporizadores()

    def cerrar(self) -> None:
        self.detener.set()
        with self.bloqueo:
            # Cerrar primero el actuador impide generar órdenes durante el cierre.
            actuador = self.roles.get("actuador")
            if actuador:
                self._cerrar_sesion(actuador, "SERVIDOR_DETENIDO")
            for sesion in list(self.sesiones.values()):
                self._cerrar_sesion(sesion, "SERVIDOR_DETENIDO")
            if self.escucha:
                self.escucha.close()
                self.escucha = None
        for hilo in self.hilos:
            if hilo is not threading.current_thread():
                hilo.join(timeout=0.6)
        self.hilos.clear()
        self.registro.registrar("SERVIDOR_DETENIDO")
        self.registro.cerrar()


def principal() -> None:
    opciones = argparse.ArgumentParser(description="Servidor TCP con hilos")
    opciones.add_argument("--direccion", default="0.0.0.0")
    opciones.add_argument("--puerto", type=int, default=5000)
    opciones.add_argument("--registro", type=Path, default=Path("registros/ejecucion.jsonl"))
    argumentos = opciones.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    servidor = ServidorTcp(
        ConfiguracionServidor(direccion=argumentos.direccion, puerto=argumentos.puerto),
        RegistroPruebas(argumentos.registro))
    try:
        servidor.iniciar()
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        logging.info("Detención solicitada")
    finally:
        servidor.cerrar()
