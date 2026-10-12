"""Servidor TCP con un único bucle de eventos y sesiones por conexión."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import logging
import select
import socket
import time
from typing import Any, Callable, Optional, Union

from .control import ConfiguracionServidor, ControlDistancia, EstadoLed
from .protocolo import ErrorProtocolo, ProtocoloAplicacion, ReceptorLineas


class RegistroPruebas:
    """Muestra eventos en consola y conserva su evidencia original en JSONL."""

    def __init__(self, ruta: Optional[Union[Path, str]] = None) -> None:
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
        logging.info("%s %s", evento, datos)
        if self.archivo:
            self.archivo.write(json.dumps(fila, ensure_ascii=False, allow_nan=False) + "\n")
            self.archivo.flush()

    def cerrar(self) -> None:
        if self.archivo:
            self.archivo.close()
            self.archivo = None


class SesionCliente:
    """Datos de un cliente: su socket, su rol y sus mensajes pendientes."""

    def __init__(
        self, conexion: socket.socket, direccion: Any, identificador: int, creada: float
    ) -> None:
        self.conexion: socket.socket = conexion
        self.direccion: Any = direccion
        self.identificador: int = identificador
        self.creada: float = creada
        self.rol: str = ""
        self.receptor: ReceptorLineas = ReceptorLineas()
        self.salida: bytearray = bytearray()
        self.ultima_lectura: float = 0.0
        self.numero_lectura: int = 0
        self.numero_orden: int = 0
        self.numero_pendiente: int = 0  # Cero significa que no se espera confirmación.
        self.estado_pendiente: Union[EstadoLed, str] = EstadoLed.APAGADO
        self.inicio_orden: float = 0.0
        self.estado_confirmado: Optional[Union[EstadoLed, str]] = None
        self.ultimo_envio: float = 0.0
        self.cerrada: bool = False
        self.cerrar_tras_envio: bool = False
        self.limite_cierre: float = 0.0


class ServidorTcp:
    """Coordina los mismos pasos del servidor inicial, agrupados en una clase.

    iniciar -> ejecutar_paso -> _recibir -> _procesar -> _solicitar_estado.
    _temporizadores revisa los plazos y _transmitir entrega los bytes pendientes.
    Un solo bucle modifica los clientes y el filtro; no necesita un lock.
    """

    def __init__(
        self,
        configuracion: Optional[ConfiguracionServidor] = None,
        registro: Optional[RegistroPruebas] = None,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self.configuracion: ConfiguracionServidor = configuracion or ConfiguracionServidor()
        self.registro: RegistroPruebas = registro or RegistroPruebas()
        self.reloj: Callable[[], float] = reloj
        self.escucha: Optional[socket.socket] = None
        self.sesiones: dict[socket.socket, SesionCliente] = {}  # Todas las conexiones, incluso sin registro.
        self.roles: dict[str, SesionCliente] = {}  # Equivale al diccionario clientes del ejemplo inicial.
        self.control: ControlDistancia = ControlDistancia(self.configuracion)
        self.siguiente_sesion: int = 0

    @property
    def puerto(self) -> int:
        if self.escucha is None:
            raise RuntimeError("Servidor no iniciado")
        return self.escucha.getsockname()[1]

    def iniciar(self) -> None:
        conexion = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conexion.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            conexion.bind((self.configuracion.direccion, self.configuracion.puerto))
            conexion.listen(self.configuracion.maximo_clientes)
            conexion.setblocking(False)
        except Exception:
            conexion.close()
            raise
        self.escucha = conexion
        self.registro.registrar("SERVIDOR_INICIADO", puerto=self.puerto)

    def _aceptar(self) -> None:
        if self.escucha is None:
            return
        conexion, direccion = self.escucha.accept()
        if len(self.sesiones) >= self.configuracion.maximo_clientes:
            conexion.close()
            self.registro.registrar("CLIENTE_RECHAZADO", motivo="LIMITE_CLIENTES")
            return
        conexion.setblocking(False)
        conexion.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.siguiente_sesion += 1
        sesion = SesionCliente(conexion, direccion, self.siguiente_sesion, self.reloj())
        self.sesiones[conexion] = sesion
        self.registro.registrar("CONEXION", sesion=sesion.identificador, direccion=str(direccion))

    def _cerrar_si_error_enviado(self, sesion: SesionCliente) -> None:
        if sesion.cerrar_tras_envio and not sesion.salida and not sesion.cerrada:
            self._cerrar_sesion(sesion, "ERROR_ENVIADO")

    def _enviar(self, sesion: SesionCliente, linea: str) -> None:
        """Guarda una línea para transmitir sin bloquear a los otros clientes."""
        if sesion.cerrada or sesion.cerrar_tras_envio:
            return
        datos = ProtocoloAplicacion.codificar(linea)
        if len(sesion.salida) + len(datos) > 4096:
            self._cerrar_sesion(sesion, "CLIENTE_NO_LEE")
            return
        sesion.salida.extend(datos)
        self._cerrar_si_error_enviado(sesion)
        self.registro.registrar("MENSAJE_ENCOLADO", sesion=sesion.identificador, mensaje=linea)

    def _rechazar(self, sesion: SesionCliente, codigo: str) -> None:
        self.registro.registrar("ERROR_PROTOCOLO", sesion=sesion.identificador, codigo=codigo)
        # Descartar órdenes aún no enviadas antes de entregar el error final.
        sesion.salida.clear()
        self._enviar(sesion, f"ERROR codigo={codigo}")
        if not sesion.cerrada:
            sesion.cerrar_tras_envio = True
            sesion.limite_cierre = self.reloj() + 0.5
            if self.roles.get(sesion.rol) is sesion and sesion.rol == "sensor":
                self.control.invalidar()
                self._solicitar_estado()
            self._cerrar_si_error_enviado(sesion)

    def _cerrar_sesion(self, sesion: SesionCliente, motivo: str) -> None:
        if sesion.cerrada:
            return
        sesion.cerrada = True
        self.sesiones.pop(sesion.conexion, None)
        sesion.conexion.close()
        if self.roles.get(sesion.rol) is sesion:
            del self.roles[sesion.rol]
            if sesion.rol == "sensor":
                self.control.invalidar()
                self._solicitar_estado()
        self.registro.registrar("DESCONEXION", sesion=sesion.identificador,
                                rol=sesion.rol, motivo=motivo)

    def _solicitar_estado(self, forzar: bool = False) -> None:
        """Como actualizar_leds: solicita el estado vigente si no hay orden pendiente."""
        actuador = self.roles.get("actuador")
        if actuador is None or actuador.cerrada or actuador.cerrar_tras_envio or actuador.numero_pendiente != 0:
            return
        if not forzar and actuador.estado_confirmado == self.control.estado:
            return
        actuador.numero_orden += 1
        actuador.numero_pendiente = actuador.numero_orden
        actuador.estado_pendiente = self.control.estado
        # El segundo de espera incluye la cola de salida; no es latencia física.
        actuador.inicio_orden = self.reloj()
        actuador.ultimo_envio = self.reloj()
        self._enviar(actuador, f"ORDEN numero={actuador.numero_orden}, estado={self.control.estado}")
        self.registro.registrar("ORDEN", sesion=actuador.identificador,
                                numero=actuador.numero_orden, estado=str(self.control.estado))

    def _procesar(self, sesion: SesionCliente, linea: str) -> None:
        """Como procesar_mensaje: interpreta registro, lectura o confirmación."""
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
            self.registro.registrar("LECTURA", sesion=sesion.identificador, numero=numero,
                tiempo_sensor_ms=argumentos["tiempo_ms"], distancia_cm=argumentos["distancia_cm"],
                filtrada_cm=self.control.distancia_filtrada, estado=str(estado))
            self._solicitar_estado()
        elif mensaje.comando == "APLICADO" and sesion.rol == "actuador":
            if sesion.numero_pendiente == 0 or argumentos["numero"] != sesion.numero_pendiente:
                raise ErrorProtocolo("CONFIRMACION")
            if self.reloj() - sesion.inicio_orden >= self.configuracion.espera_confirmacion:
                raise ErrorProtocolo("CONFIRMACION_TARDIA")
            sesion.estado_confirmado = sesion.estado_pendiente
            self.registro.registrar("APLICADO", sesion=sesion.identificador,
                numero=sesion.numero_pendiente, estado=str(sesion.estado_pendiente),
                latencia_confirmacion_ms=(self.reloj() - sesion.inicio_orden) * 1000)
            sesion.numero_pendiente = 0
            self._solicitar_estado()
        elif mensaje.comando == "ERROR":
            # Un ERROR recibido se registra y cierra; nunca se responde con otro ERROR.
            self._cerrar_sesion(sesion, "ERROR_CLIENTE_" + argumentos["codigo"])
        else:
            raise ErrorProtocolo("ROL")

    def _recibir(self, sesion: SesionCliente) -> None:
        """Recibe bytes, reconstruye líneas y las entrega a _procesar."""
        datos = sesion.conexion.recv(1024)
        if not datos:
            self._cerrar_sesion(sesion, "CIERRE_TCP")
            return
        try:
            for linea in sesion.receptor.recibir(datos):
                self._procesar(sesion, linea)
                if sesion.cerrada or sesion.cerrar_tras_envio:
                    break
        except ErrorProtocolo as error:
            self._rechazar(sesion, error.codigo)

    def _transmitir(self, sesion: SesionCliente) -> None:
        enviados = sesion.conexion.send(sesion.salida)
        if enviados == 0:
            self._cerrar_sesion(sesion, "ENVIO_CERRADO")
            return
        del sesion.salida[:enviados]
        self._cerrar_si_error_enviado(sesion)

    def _temporizadores(self) -> None:
        """Revisa los plazos de registro, actividad y confirmación sin detener el bucle."""
        ahora = self.reloj()
        c = self.configuracion
        for sesion in list(self.sesiones.values()):
            if sesion.cerrar_tras_envio:
                if ahora >= sesion.limite_cierre:
                    self._cerrar_sesion(sesion, "ERROR_TIEMPO_AGOTADO")
            elif not sesion.rol and ahora - sesion.creada >= c.espera_registro:
                self._cerrar_sesion(sesion, "REGISTRO_TIEMPO_AGOTADO")
            elif sesion.rol == "sensor" and ahora - sesion.ultima_lectura >= c.inactividad_sensor:
                self._cerrar_sesion(sesion, "SENSOR_INACTIVO")
            elif sesion.numero_pendiente != 0 and ahora - sesion.inicio_orden >= c.espera_confirmacion:
                self._cerrar_sesion(sesion, "CONFIRMACION_TIEMPO_AGOTADO")
        actuador = self.roles.get("actuador")
        if actuador and ahora - actuador.ultimo_envio >= c.intervalo_refresco:
            self._solicitar_estado(forzar=True)

    def ejecutar_paso(self, espera: float = 0.05) -> None:
        """Una vuelta: revisar plazos, recibir mensajes y enviar respuestas."""
        if self.escucha is None:
            return
        self._temporizadores()
        para_leer = [self.escucha]
        para_enviar = []
        for sesion in self.sesiones.values():
            if not sesion.cerrar_tras_envio:
                para_leer.append(sesion.conexion)
            if sesion.salida:
                para_enviar.append(sesion.conexion)
        listas = select.select(para_leer, para_enviar, [], espera)
        for conexion in listas[0]:
            if conexion == self.escucha:
                self._aceptar()
            else:
                self._atender(conexion, recibir=True)
        for conexion in listas[1]:
            self._atender(conexion, recibir=False)
        self._temporizadores()

    def _atender(self, conexion: socket.socket, recibir: bool) -> None:
        # Un cliente pudo cerrar o ser reemplazado durante esta misma vuelta.
        sesion = self.sesiones.get(conexion)
        if sesion is None:
            return
        try:
            if recibir:
                self._recibir(sesion)
            elif sesion.salida:
                self._transmitir(sesion)
        except BlockingIOError:
            pass  # No hay datos disponibles todavía; revisar en otra vuelta.
        except OSError as error:
            self._cerrar_sesion(sesion, "SOCKET_" + str(error.errno))

    def cerrar(self) -> None:
        # Primero actuador: evita encolar nuevas órdenes durante el cierre.
        actuador = self.roles.get("actuador")
        if actuador:
            self._cerrar_sesion(actuador, "SERVIDOR_DETENIDO")
        sesiones = list(self.sesiones.values())
        for sesion in sesiones:
            self._cerrar_sesion(sesion, "SERVIDOR_DETENIDO")
        if self.escucha:
            self.escucha.close()
            self.escucha = None
        self.registro.registrar("SERVIDOR_DETENIDO")
        self.registro.cerrar()


def principal() -> None:
    argumentos = argparse.ArgumentParser(description="Servidor TCP de control de distancia")
    argumentos.add_argument("--direccion", default="0.0.0.0")
    argumentos.add_argument("--puerto", type=int, default=5000)
    argumentos.add_argument("--registro", type=Path, default=Path("registros/ejecucion.jsonl"))
    opciones = argumentos.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    servidor = ServidorTcp(ConfiguracionServidor(direccion=opciones.direccion, puerto=opciones.puerto),
                           RegistroPruebas(opciones.registro))
    try:
        servidor.iniciar()
        while True:
            servidor.ejecutar_paso()
    except KeyboardInterrupt:
        logging.info("Detención solicitada")
    finally:
        servidor.cerrar()
