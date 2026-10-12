"""TCP real en localhost con reloj controlado para probar plazos sin esperas."""
import socket
import unittest

from servidor.control import ConfiguracionServidor
from servidor.control import EstadoLed
from servidor.protocolo import ReceptorLineas
from servidor.servidor import ServidorTcp


class RegistroMemoria:
    def __init__(self):
        self.eventos = []
    def registrar(self, evento, **datos):
        self.eventos.append((evento, datos))
    def cerrar(self):
        pass


class PruebasIntegracion(unittest.TestCase):
    def setUp(self):
        self.ahora = 100.0
        self.registro = RegistroMemoria()
        self.servidor = ServidorTcp(ConfiguracionServidor(direccion="127.0.0.1", puerto=0),
                                   self.registro, lambda: self.ahora)
        self.servidor.iniciar()
        self.conexiones = []
        self.receptores = {}

    def tearDown(self):
        self.servidor.cerrar()
        for conexion in self.conexiones:
            conexion.close()

    def procesar_red(self):
        for _ in range(8):
            self.servidor.ejecutar_paso(0.001)

    def conectar(self):
        conexion = socket.create_connection(("127.0.0.1", self.servidor.puerto), timeout=1)
        conexion.setblocking(False)
        self.conexiones.append(conexion)
        self.receptores[conexion] = ReceptorLineas()
        self.procesar_red()
        return conexion

    def enviar(self, conexion, linea):
        conexion.sendall((linea + "\n").encode("ascii"))
        self.procesar_red()

    def leer(self, conexion):
        self.procesar_red()
        lineas = []
        while True:
            try:
                datos = conexion.recv(4096)
            except BlockingIOError:
                break
            if not datos:
                break
            lineas.extend(self.receptores[conexion].recibir(datos))
        return lineas

    def registrar(self, rol):
        conexion = self.conectar()
        self.enviar(conexion, f"REGISTRO tipo={rol}, version=1")
        lineas = self.leer(conexion)
        self.assertEqual(lineas[0], "ACEPTADO REGISTRO")
        if rol == "actuador":
            self.assertTrue(lineas[1].startswith("ORDEN numero=1, estado="))
            self.enviar(conexion, "APLICADO numero=1")
            self.assertEqual(self.leer(conexion), [])  # No bucle de respuestas.
        return conexion

    def lectura(self, conexion, numero, distancia):
        self.enviar(conexion,
                    f"LECTURA numero={numero}, tiempo_ms={numero * 100}, distancia_cm={distancia}")
        self.assertEqual(self.leer(conexion), [f"RECIBIDO numero={numero}"])

    def test_recorrido_tres_rangos_y_sin_eco(self):
        actuador = self.registrar("actuador")
        sensor = self.registrar("sensor")
        numero = 0
        orden = 1
        for distancia, estado in ((5.25, "ROJO"), (15.2, "AMARILLO"), (25.1, "VERDE")):
            for _ in range(3):
                numero += 1
                self.lectura(sensor, numero, distancia)
            orden += 1
            self.assertEqual(self.leer(actuador), [f"ORDEN numero={orden}, estado={estado}"])
            self.enviar(actuador, f"APLICADO numero={orden}")
        self.lectura(sensor, numero + 1, "SIN_ECO")
        self.assertEqual(self.leer(actuador), [f"ORDEN numero={orden + 1}, estado=APAGADO"])

    def test_inactividad_exactamente_cinco_segundos(self):
        sensor = self.registrar("sensor")
        self.lectura(sensor, 1, "SIN_ECO")
        self.ahora += 4.99
        self.procesar_red()
        self.assertIn("sensor", self.servidor.roles)
        self.ahora += 0.01
        self.procesar_red()
        self.assertNotIn("sensor", self.servidor.roles)
        self.assertEqual(self.servidor.control.estado, EstadoLed.APAGADO)
        self.assertTrue(any(datos.get("motivo") == "SENSOR_INACTIVO"
                            for _, datos in self.registro.eventos))

    def test_sin_eco_demuestra_actividad(self):
        sensor = self.registrar("sensor")
        self.ahora += 4.0
        self.lectura(sensor, 1, "SIN_ECO")
        self.ahora += 4.0
        self.procesar_red()
        self.assertIn("sensor", self.servidor.roles)

    def test_confirmacion_agotada_y_reconexion(self):
        actuador = self.conectar()
        self.enviar(actuador, "REGISTRO tipo=actuador, version=1")
        self.leer(actuador)
        self.ahora += 1.0
        self.procesar_red()
        self.assertNotIn("actuador", self.servidor.roles)
        nuevo = self.registrar("actuador")
        self.assertIsNotNone(nuevo)
        self.assertEqual(self.servidor.roles["actuador"].numero_orden, 1)

    def test_confirmacion_incorrecta_se_rechaza(self):
        actuador = self.conectar()
        self.enviar(actuador, "REGISTRO tipo=actuador, version=1")
        self.leer(actuador)
        self.enviar(actuador, "APLICADO numero=999")
        self.assertEqual(self.leer(actuador), ["ERROR codigo=CONFIRMACION"])
        self.assertNotIn("actuador", self.servidor.roles)

    def test_estado_mas_reciente_sin_cola_de_ordenes(self):
        actuador = self.registrar("actuador")
        sensor = self.registrar("sensor")
        for numero in range(1, 4):
            self.lectura(sensor, numero, 5)
        self.assertEqual(self.leer(actuador), ["ORDEN numero=2, estado=ROJO"])
        for numero in range(4, 7):
            self.lectura(sensor, numero, 25)
        self.assertEqual(self.leer(actuador), [])
        self.lectura(sensor, 7, "SIN_ECO")
        self.enviar(actuador, "APLICADO numero=2")
        self.assertEqual(self.leer(actuador), ["ORDEN numero=3, estado=APAGADO"])

    def test_reemplazo_cierra_antiguo_y_preserva_nueva_sesion(self):
        antiguo = self.registrar("sensor")
        sesion_antigua = self.servidor.roles["sensor"]
        nuevo = self.registrar("sensor")
        self.assertTrue(sesion_antigua.cerrada)
        self.assertIsNot(self.servidor.roles["sensor"], sesion_antigua)
        self.assertEqual(antiguo.recv(1), b"")
        self.lectura(nuevo, 1, 15.2)

    def test_reconexion_del_actuador_recibe_estado_vigente(self):
        sensor = self.registrar("sensor")
        for numero in range(1, 4):
            self.lectura(sensor, numero, 25)
        actuador = self.registrar("actuador")
        self.assertEqual(self.servidor.roles["actuador"].estado_confirmado, EstadoLed.VERDE)
        actuador.close()
        self.procesar_red()
        self.registrar("actuador")
        self.assertEqual(self.servidor.roles["actuador"].estado_confirmado, EstadoLed.VERDE)

    def test_refresco_independiente_de_nuevas_lecturas(self):
        actuador = self.registrar("actuador")
        self.ahora += 1.0
        self.procesar_red()
        self.assertEqual(self.leer(actuador), ["ORDEN numero=2, estado=APAGADO"])

    def test_roles_y_secuencia(self):
        conexion = self.conectar()
        self.enviar(conexion, "LECTURA numero=1, tiempo_ms=0, distancia_cm=15")
        self.assertEqual(self.leer(conexion), ["ERROR codigo=SIN_REGISTRO"])
        sensor = self.registrar("sensor")
        self.lectura(sensor, 1, 15)
        self.enviar(sensor, "LECTURA numero=1, tiempo_ms=0, distancia_cm=15")
        self.assertEqual(self.leer(sensor), ["ERROR codigo=SECUENCIA"])

    def test_error_del_cliente_no_produce_otro_error(self):
        actuador = self.registrar("actuador")
        self.enviar(actuador, "ERROR codigo=FORMATO")
        self.assertEqual(self.leer(actuador), [])
        self.assertNotIn("actuador", self.servidor.roles)

    def test_registro_con_plazo_y_linea_excesiva(self):
        conexion = self.conectar()
        self.ahora += 3.0
        self.procesar_red()
        self.assertEqual(conexion.recv(1), b"")
        conexion = self.conectar()
        conexion.sendall(b"x" * 128)
        self.assertEqual(self.leer(conexion), ["ERROR codigo=LONGITUD"])

    def test_fragmentos_tcp_reales(self):
        sensor = self.conectar()
        sensor.sendall(b"REGIS")
        self.assertEqual(self.leer(sensor), [])
        sensor.sendall(b"TRO tipo=sensor, version=1\r\n"
                       b"LECTURA numero=1, tiempo_ms=0, distancia_cm=15.2\n"
                       b"LECTURA numero=2, tiempo_ms=100, distancia_cm=15.2\n")
        self.assertEqual(self.leer(sensor), ["ACEPTADO REGISTRO", "RECIBIDO numero=1", "RECIBIDO numero=2"])


if __name__ == "__main__":
    unittest.main()
