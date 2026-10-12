"""La gramática se prueba independientemente de los sockets."""
import unittest

from servidor.protocolo import ErrorProtocolo, ProtocoloAplicacion, ReceptorLineas


class PruebasProtocolo(unittest.TestCase):
    def test_distancias_decimales_y_sin_eco(self):
        mensaje = ProtocoloAplicacion.interpretar(
            "LECTURA numero=42, tiempo_ms=12500, distancia_cm=15.20")
        self.assertEqual(mensaje.argumentos["distancia_cm"], 15.2)
        mensaje = ProtocoloAplicacion.interpretar(
            "LECTURA numero=43,tiempo_ms=12600,distancia_cm=SIN_ECO")
        self.assertIsNone(mensaje.argumentos["distancia_cm"])

    def test_catalogo_y_respuestas(self):
        for linea in ("REGISTRO tipo=sensor, version=1", "REGISTRO tipo=actuador, version=1",
                      "ACEPTADO REGISTRO", "RECIBIDO numero=1", "APLICADO numero=1",
                      "ORDEN numero=1, estado=ROJO", "ERROR codigo=FORMATO"):
            with self.subTest(linea=linea):
                ProtocoloAplicacion.interpretar(linea)

    def test_datos_rechazados(self):
        casos = {
            "POST distance=15": "COMANDO",
            "REGISTRO tipo=sensor, version=2": "VERSION",
            "REGISTRO tipo=robot, version=1": "VALOR",
            "REGISTRO tipo=sensor": "FALTANTE",
            "APLICADO numero=1, numero=2": "DUPLICADO",
            "APLICADO otra=1": "ARGUMENTO",
            "APLICADO numero=0": "VALOR",
            "APLICADO numero=4294967296": "VALOR",
            "ORDEN numero=1, estado=AZUL": "VALOR",
            "APLICADO numero=1,": "FORMATO",
            "APLICADO numero= 1": "FORMATO",
        }
        for linea, codigo in casos.items():
            with self.subTest(linea=linea):
                with self.assertRaises(ErrorProtocolo) as error:
                    ProtocoloAplicacion.interpretar(linea)
                self.assertEqual(error.exception.codigo, codigo)
        for valor in ("nan", "inf", "1e2", "401", "-1", "15.2.3"):
            with self.subTest(valor=valor), self.assertRaises(ErrorProtocolo):
                ProtocoloAplicacion.interpretar(
                    f"LECTURA numero=1, tiempo_ms=0, distancia_cm={valor}")

    def test_fragmentacion_concatenacion_y_crlf(self):
        receptor = ReceptorLineas()
        self.assertEqual(list(receptor.recibir(b"REGIS")), [])
        self.assertEqual(list(receptor.recibir(b"TRO tipo=sensor, version=1\r\nAPLICADO numero=1\n")),
                         ["REGISTRO tipo=sensor, version=1", "APLICADO numero=1"])

    def test_limite_incluye_terminador(self):
        self.assertEqual(list(ReceptorLineas().recibir(b"a" * 127 + b"\n")), ["a" * 127])
        self.assertEqual(list(ReceptorLineas().recibir(b"a" * 126 + b"\r\n")), ["a" * 126])
        with self.assertRaises(ErrorProtocolo):
            list(ReceptorLineas().recibir(b"a" * 128))
        with self.assertRaises(ErrorProtocolo):
            list(ReceptorLineas().recibir(b"a" * 127 + b"\r\n"))

    def test_rechaza_codificacion_y_controles(self):
        for datos in (b"\xff", b"\x00", b"\n", b"a\rb\n"):
            with self.subTest(datos=datos), self.assertRaises(ErrorProtocolo):
                list(ReceptorLineas().recibir(datos))

    def test_linea_valida_antes_de_error_se_procesa(self):
        generador = ReceptorLineas().recibir(b"APLICADO numero=1\n" + b"x" * 128)
        self.assertEqual(next(generador), "APLICADO numero=1")
        with self.assertRaises(ErrorProtocolo):
            next(generador)


if __name__ == "__main__":
    unittest.main()
