"""Prueba reproducible con Ncat real; no requiere placas ni servidor externo."""
import argparse
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from servidor.control import ConfiguracionServidor
from servidor.protocolo import ProtocoloAplicacion
from servidor.servidor import RegistroPruebas
from servidor.servidor import ServidorTcp


class ConexionNcat:
    """Ncat transporta los bytes; Python automatiza entradas y verificaciones."""

    def __init__(self, ejecutable, puerto, rol=None, confirmar=False):
        self.confirmar = confirmar
        self.lineas = queue.Queue()
        self.bloqueo = threading.Lock()
        self.proceso = subprocess.Popen(
            [ejecutable, "127.0.0.1", str(puerto)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.lector = threading.Thread(target=self._leer, daemon=True)
        self.lector.start()
        if rol:
            self.enviar(f"REGISTRO tipo={rol}, version=1")
            self.esperar("ACEPTADO REGISTRO")

    def enviar(self, linea):
        with self.bloqueo:
            self.proceso.stdin.write((linea + "\n").encode("ascii"))
            self.proceso.stdin.flush()

    def _leer(self):
        for datos in iter(self.proceso.stdout.readline, b""):
            linea = datos.decode("ascii").rstrip("\r\n")
            if linea.startswith("ORDEN ") and self.confirmar:
                mensaje = ProtocoloAplicacion.interpretar(linea)
                self.enviar(f"APLICADO numero={mensaje.argumentos['numero']}")
            self.lineas.put(linea)
        self.lineas.put(None)

    def esperar(self, esperado, plazo=2):
        linea = self.lineas.get(timeout=plazo)
        if linea != esperado:
            raise AssertionError(f"Esperado {esperado!r}, recibido {linea!r}")
        return linea

    def esperar_estado(self, estado, plazo=2):
        linea = self.lineas.get(timeout=plazo)
        if linea is None or not linea.startswith("ORDEN "):
            raise AssertionError(f"Se esperaba orden, recibido {linea!r}")
        mensaje = ProtocoloAplicacion.interpretar(linea)
        if mensaje.argumentos["estado"] != estado:
            raise AssertionError(f"Se esperaba {estado}, recibido {linea}")
        return linea

    def esperar_cierre(self, plazo=6):
        limite = time.monotonic() + plazo
        while time.monotonic() < limite:
            linea = self.lineas.get(timeout=max(0.01, limite - time.monotonic()))
            if linea is None:
                return
        raise AssertionError("No se recibió cierre de la conexión")

    def cerrar(self):
        if self.proceso.poll() is None:
            self.proceso.terminate()
        self.proceso.wait(timeout=3)
        self.lector.join(timeout=1)
        for archivo in (self.proceso.stdin, self.proceso.stdout, self.proceso.stderr):
            archivo.close()


def principal():
    opciones = argparse.ArgumentParser(description="Verificar protocolo usando Ncat en localhost")
    ncat_local = Path(__file__).resolve().parents[1] / ".herramientas/ncat/ncat.exe"
    opciones.add_argument("--ncat", default=shutil.which("ncat") or str(ncat_local))
    opciones.add_argument("--registro", default="registros/ncat.jsonl")
    argumentos = opciones.parse_args()
    if not argumentos.ncat or not Path(argumentos.ncat).is_file():
        print("PENDIENTE: no se encontró Ncat. Indicar --ncat con la ruta de ncat.exe.")
        return 2
    version = subprocess.run([argumentos.ncat, "--version"], capture_output=True, text=True, check=True)
    print((version.stdout + version.stderr).strip())
    servidor = ServidorTcp(ConfiguracionServidor(direccion="127.0.0.1", puerto=0),
                           RegistroPruebas(argumentos.registro))
    servidor.iniciar()
    detener = threading.Event()
    errores = []

    def atender():
        try:
            while not detener.is_set():
                servidor.ejecutar_paso(0.01)
        except Exception as error:
            errores.append(error)
        finally:
            servidor.cerrar()

    hilo = threading.Thread(target=atender)
    hilo.start()
    conexiones = []

    def conectar(rol=None, confirmar=False):
        conexion = ConexionNcat(argumentos.ncat, servidor.puerto, confirmar=confirmar)
        conexiones.append(conexion)
        if rol:
            conexion.enviar(f"REGISTRO tipo={rol}, version=1")
            conexion.esperar("ACEPTADO REGISTRO")
        return conexion

    try:
        actuador = conectar("actuador", True)
        actuador.esperar_estado("APAGADO")
        sensor = conectar("sensor")
        numero = 0
        for distancia, estado in (("5.25", "ROJO"), ("15.20", "AMARILLO"), ("25.10", "VERDE")):
            for _ in range(3):
                numero += 1
                sensor.enviar(f"LECTURA numero={numero}, tiempo_ms={numero * 100}, distancia_cm={distancia}")
                sensor.esperar(f"RECIBIDO numero={numero}")
            actuador.esperar_estado(estado)
        print("APROBADO: registro, decimales, tres rangos y confirmaciones correlacionadas.")
        numero += 1
        sensor.enviar(f"LECTURA numero={numero}, tiempo_ms=1000, distancia_cm=SIN_ECO")
        sensor.esperar(f"RECIBIDO numero={numero}")
        actuador.esperar_estado("APAGADO")
        print("APROBADO: SIN_ECO apaga y mantiene actividad.")
        inicio = time.monotonic()
        sensor.esperar_cierre(6)
        duracion = time.monotonic() - inicio
        if not 4.5 <= duracion <= 6:
            raise AssertionError(f"Plazo de inactividad inesperado: {duracion:.3f} s")
        print(f"APROBADO: sensor inactivo cerrado tras aproximadamente {duracion:.3f} s reales.")
        nuevo = conectar("sensor")
        nuevo.enviar("LECTURA numero=1, tiempo_ms=0, distancia_cm=15.20")
        nuevo.esperar("RECIBIDO numero=1")
        print("APROBADO: reconexión, nuevo registro y secuencia reiniciada.")
        reemplazo = conectar("sensor")
        nuevo.esperar_cierre(1)
        reemplazo.enviar("LECTURA numero=1, tiempo_ms=0, distancia_cm=15.20")
        reemplazo.esperar("RECIBIDO numero=1")
        print("APROBADO: reemplazo cierra la sesión anterior y conserva la nueva.")
        incorrecto = conectar()
        incorrecto.enviar("LECTURA numero=1, tiempo_ms=0, distancia_cm=15.20")
        incorrecto.esperar("ERROR codigo=SIN_REGISTRO")
        incorrecto.esperar_cierre(1)
        sin_confirmar = conectar("actuador")
        sin_confirmar.esperar_estado("APAGADO")
        sin_confirmar.esperar_cierre(2)
        print("APROBADO: mensaje sin registro y orden sin confirmación cierran la conexión.")
        confirmacion_incorrecta = conectar("actuador")
        confirmacion_incorrecta.esperar_estado("APAGADO")
        confirmacion_incorrecta.enviar("APLICADO numero=2")
        confirmacion_incorrecta.esperar("ERROR codigo=CONFIRMACION")
        confirmacion_incorrecta.esperar_cierre(1)
        print("APROBADO: confirmación con número distinto rechazada.")
        repetido = conectar("sensor")
        lectura = "LECTURA numero=1, tiempo_ms=0, distancia_cm=15.20"
        repetido.enviar(lectura)
        repetido.esperar("RECIBIDO numero=1")
        repetido.enviar(lectura)
        repetido.esperar("ERROR codigo=SECUENCIA")
        repetido.esperar_cierre(1)
        excesivo = conectar()
        excesivo.enviar("a" * 128)
        excesivo.esperar("ERROR codigo=LONGITUD")
        excesivo.esperar_cierre(1)
        print("APROBADO: secuencia repetida y línea excesiva rechazadas.")
        if errores:
            raise errores[0]
        print("Todas las verificaciones Ncat finalizaron; no son pruebas físicas de los ESP32.")
        return 0
    finally:
        for conexion in conexiones:
            conexion.cerrar()
        detener.set()
        hilo.join(timeout=3)


if __name__ == "__main__":
    sys.exit(principal())
