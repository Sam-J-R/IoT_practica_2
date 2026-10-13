"""Pruebas de integración TCP reales contra el servidor con hilos.

Usan localhost y tiempos cortos para no requerir ESP32. Se comprueba
el comportamiento observable; las pruebas no modifican el reloj interno.
"""
import socket
import threading
import time
import unittest
from unittest.mock import patch

from servidor.control import ConfiguracionServidor, EstadoLed
from servidor.servidor import RegistroPruebas, ServidorTcp


class RegistroMemoria:
    def __init__(self):
        self.eventos = []
        self.bloqueo = threading.Lock()

    def registrar(self, evento, **datos):
        with self.bloqueo:
            self.eventos.append((evento, datos))

    def cerrar(self):
        pass


class ClientePrueba:
    def __init__(self, puerto):
        self.conexion = socket.create_connection(("127.0.0.1", puerto), timeout=1)
        self.conexion.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.pendiente = b""

    def enviar(self, mensaje):
        self.conexion.sendall((mensaje + "\n").encode("ascii"))

    def leer(self, plazo=0.7):
        limite = time.monotonic() + plazo
        while b"\n" not in self.pendiente:
            restante = limite - time.monotonic()
            if restante <= 0:
                raise AssertionError("No llegó un mensaje TCP dentro del plazo")
            self.conexion.settimeout(restante)
            try:
                datos = self.conexion.recv(4096)
            except socket.timeout as exc:
                raise AssertionError("Se agotó el tiempo de recepción TCP") from exc
            if not datos:
                raise AssertionError("El cliente se desconectó antes del mensaje esperado")
            self.pendiente += datos
        linea, self.pendiente = self.pendiente.split(b"\n", 1)
        return linea.rstrip(b"\r").decode("ascii")

    def esperar_cierre(self, plazo=1):
        limite = time.monotonic() + plazo
        while time.monotonic() < limite:
            self.conexion.settimeout(max(0.01, limite - time.monotonic()))
            try:
                if self.conexion.recv(1024) == b"":
                    return True
            except (OSError, socket.timeout):
                continue
        return False

    def cerrar(self):
        self.conexion.close()


class PruebasIntegracionHilos(unittest.TestCase):
    def setUp(self):
        self.config = ConfiguracionServidor(direccion="127.0.0.1", puerto=0)
        self.config.espera_registro = 0.5
        self.config.espera_confirmacion = 0.6
        self.config.inactividad_sensor = 5.0
        self.config.intervalo_refresco = 5.0
        self.registro = RegistroMemoria()
        self.servidor = ServidorTcp(self.config, self.registro)
        self.servidor.iniciar()
        self.clientes = []

    def tearDown(self):
        self.servidor.cerrar()
        for cliente in self.clientes:
            cliente.cerrar()

    def esperar(self, predicado, plazo=0.8):
        limite = time.monotonic() + plazo
        while time.monotonic() < limite:
            with self.servidor.bloqueo:
                if predicado():
                    return True
            time.sleep(0.005)
        return False

    def nuevo(self):
        cliente = ClientePrueba(self.servidor.puerto)
        self.clientes.append(cliente)
        return cliente

    def registrar(self, rol):
        cliente = self.nuevo()
        cliente.enviar(f"REGISTRO tipo={rol}, version=1")
        self.assertEqual(cliente.leer(), "ACEPTADO REGISTRO")
        if rol == "actuador":
            self.assertEqual(cliente.leer(), "ORDEN numero=1, estado=APAGADO")
            cliente.enviar("APLICADO numero=1")
            self.assertTrue(self.esperar(lambda: self.servidor.roles.get('actuador') is not None
                                        and self.servidor.roles['actuador'].numero_pendiente == 0))
        return cliente

    def lectura(self, cliente, numero, distancia):
        cliente.enviar(f"LECTURA numero={numero}, tiempo_ms={numero*100}, distancia_cm={distancia}")
        self.assertEqual(cliente.leer(), f"RECIBIDO numero={numero}")

    def tres_lecturas(self, sensor, desde, distancia):
        for numero in range(desde, desde + 3):
            self.lectura(sensor, numero, distancia)

    def test_colores_decimales_y_sin_eco(self):
        actuador = self.registrar("actuador")
        sensor = self.registrar("sensor")
        for i, (distancia, color) in enumerate(((5.25, "ROJO"), (15.2, "AMARILLO"),
                                                (25.1, "VERDE"))):
            self.tres_lecturas(sensor, 1 + 3*i, distancia)
            orden = i + 2
            self.assertEqual(actuador.leer(), f"ORDEN numero={orden}, estado={color}")
            actuador.enviar(f"APLICADO numero={orden}")
            self.assertTrue(self.esperar(lambda: self.servidor.roles['actuador'].numero_pendiente == 0))
        self.lectura(sensor, 10, "SIN_ECO")
        self.assertEqual(actuador.leer(), "ORDEN numero=5, estado=APAGADO")

    def test_inactividad_sensor_apaga_leds(self):
        self.config.inactividad_sensor = 0.35
        actuador = self.registrar("actuador")
        sensor = self.registrar("sensor")
        self.tres_lecturas(sensor, 1, 5.2)
        self.assertEqual(actuador.leer(), "ORDEN numero=2, estado=ROJO")
        actuador.enviar("APLICADO numero=2")
        self.assertTrue(self.esperar(lambda: self.servidor.roles['actuador'].numero_pendiente == 0))
        time.sleep(0.12)
        self.assertIn("sensor", self.servidor.roles)
        self.assertEqual(actuador.leer(plazo=0.75), "ORDEN numero=3, estado=APAGADO")
        self.assertNotIn("sensor", self.servidor.roles)

    def test_desconexion_sensor_apaga_leds(self):
        actuador = self.registrar("actuador")
        sensor = self.registrar("sensor")
        self.tres_lecturas(sensor, 1, 5.2)
        self.assertEqual(actuador.leer(), "ORDEN numero=2, estado=ROJO")
        actuador.enviar("APLICADO numero=2")
        self.assertTrue(self.esperar(lambda: self.servidor.roles['actuador'].numero_pendiente == 0))
        sensor.cerrar()
        self.assertEqual(actuador.leer(), "ORDEN numero=3, estado=APAGADO")
        self.assertTrue(self.esperar(lambda: 'sensor' not in self.servidor.roles))

    def test_confirmacion_agotada(self):
        self.config.espera_confirmacion = 0.18
        cliente = self.nuevo()
        cliente.enviar("REGISTRO tipo=actuador, version=1")
        self.assertEqual(cliente.leer(), "ACEPTADO REGISTRO")
        self.assertEqual(cliente.leer(), "ORDEN numero=1, estado=APAGADO")
        self.assertTrue(self.esperar(lambda: "actuador" not in self.servidor.roles, 0.5))
        self.assertTrue(cliente.esperar_cierre())
        nuevo = self.registrar("actuador")
        self.assertIsNotNone(nuevo)

    def test_confirmacion_incorrecta_rechazada(self):
        actuador = self.nuevo()
        actuador.enviar("REGISTRO tipo=actuador, version=1")
        self.assertEqual(actuador.leer(), "ACEPTADO REGISTRO")
        actuador.leer()
        actuador.enviar("APLICADO numero=999")
        self.assertEqual(actuador.leer(), "ERROR codigo=CONFIRMACION")
        self.assertTrue(self.esperar(lambda: "actuador" not in self.servidor.roles))

    def test_reemplazo_de_sensor(self):
        anterior = self.registrar("sensor")
        sesion = self.servidor.roles['sensor']
        nuevo = self.registrar("sensor")
        self.assertTrue(self.esperar(lambda: sesion.cerrada))
        self.assertTrue(anterior.esperar_cierre())
        self.lectura(nuevo, 1, 15.2)

    def test_reconexion_actuador_conserva_color(self):
        sensor = self.registrar("sensor")
        self.tres_lecturas(sensor, 1, 25)
        primer_actuador = self.nuevo()
        primer_actuador.enviar("REGISTRO tipo=actuador, version=1")
        self.assertEqual(primer_actuador.leer(), "ACEPTADO REGISTRO")
        self.assertEqual(primer_actuador.leer(), "ORDEN numero=1, estado=VERDE")
        primer_actuador.enviar("APLICADO numero=1")
        self.assertTrue(self.esperar(lambda: self.servidor.roles['actuador'].numero_pendiente == 0))
        primer_actuador.cerrar()
        self.assertTrue(self.esperar(lambda: 'actuador' not in self.servidor.roles))
        otro = self.nuevo()
        otro.enviar("REGISTRO tipo=actuador, version=1")
        self.assertEqual(otro.leer(), "ACEPTADO REGISTRO")
        self.assertEqual(otro.leer(), "ORDEN numero=1, estado=VERDE")

    def test_refresco_sin_nuevas_lecturas(self):
        self.config.intervalo_refresco = 0.20
        actuador = self.registrar("actuador")
        self.assertEqual(actuador.leer(plazo=0.5), "ORDEN numero=2, estado=APAGADO")

    def test_secuencia_repetida_y_rol_equivocado(self):
        sin_registro = self.nuevo()
        sin_registro.enviar("LECTURA numero=1, tiempo_ms=0, distancia_cm=15")
        self.assertEqual(sin_registro.leer(), "ERROR codigo=SIN_REGISTRO")
        sensor = self.registrar("sensor")
        self.lectura(sensor, 1, 15)
        sensor.enviar("LECTURA numero=1, tiempo_ms=100, distancia_cm=15")
        self.assertEqual(sensor.leer(), "ERROR codigo=SECUENCIA")
        actuador = self.registrar("actuador")
        actuador.enviar("LECTURA numero=1, tiempo_ms=0, distancia_cm=15")
        self.assertEqual(actuador.leer(), "ERROR codigo=ROL")

    def test_sensor_rechazado_apaga_antes_de_confirmar_color(self):
        actuador = self.registrar("actuador")
        sensor = self.registrar("sensor")
        self.tres_lecturas(sensor, 1, 5)
        self.assertEqual(actuador.leer(), "ORDEN numero=2, estado=ROJO")
        sensor.enviar("LECTURA numero=3, tiempo_ms=400, distancia_cm=5")
        # No se confirma ROJO hasta después de recibir APAGADO.
        self.assertEqual(actuador.leer(), "ORDEN numero=3, estado=APAGADO")
        self.assertEqual(sensor.leer(), "ERROR codigo=SECUENCIA")
        self.assertTrue(sensor.esperar_cierre())
        actuador.enviar("APLICADO numero=2")
        actuador.enviar("APLICADO numero=3")
        self.assertTrue(self.esperar(lambda: self.servidor.roles['actuador'].numero_pendiente == 0))
        self.assertEqual(self.servidor.roles['actuador'].estado_confirmado, EstadoLed.APAGADO)
        # Tras confirmar APAGADO ya no se acepta el color sustituido.
        actuador.enviar("APLICADO numero=2")
        self.assertEqual(actuador.leer(), "ERROR codigo=CONFIRMACION")

    def test_reconexiones_liberan_hilos_lectores_y_escritores(self):
        for _ in range(30):
            sensor = self.registrar("sensor")
            sensor.cerrar()
            self.assertTrue(self.esperar(lambda: not self.servidor.sesiones
                                        and len(self.servidor.hilos) == 2))
        self.assertIsNone(self.servidor.error_hilo)

    def test_consola_bloqueada_no_detiene_tcp_ni_supervision(self):
        entra = threading.Event()
        continuar = threading.Event()

        def consola_lenta(*_):
            entra.set()
            if not continuar.wait(3):
                raise TimeoutError("La prueba no liberó la consola")

        registro = RegistroPruebas(capacidad=4)
        with self.servidor.bloqueo:
            self.servidor.registro = registro
            self.config.inactividad_sensor = 0.15
        try:
            with patch("servidor.registro.logging.info", side_effect=consola_lenta):
                registro.registrar("INICIO_PRUEBA")
                self.assertTrue(entra.wait(1))
                sensor = self.registrar("sensor")
                self.lectura(sensor, 1, 15)
                self.assertTrue(sensor.esperar_cierre())
                self.assertTrue(self.esperar(lambda: not self.servidor.sesiones))
                self.assertGreater(registro.descartados, 0)
                self.assertEqual(registro.cola.qsize(), 4)
                self.assertIsNone(self.servidor.error_hilo)
                continuar.set()
                registro.cerrar()
        finally:
            continuar.set()
            registro.cerrar()


if __name__ == "__main__":
    unittest.main()
