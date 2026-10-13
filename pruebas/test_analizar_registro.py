"""Regresiones esenciales para no presentar evidencia mezclada o incompleta."""
import json
import unittest

from pruebas.analizar_registro import analizar_registro


def evento(nombre, tiempo=0, **datos):
    return json.dumps({"evento": nombre, "tiempo_monotonico": tiempo, **datos})


def lectura(numero, tiempo, sensor_ms, distancia=5):
    return evento("LECTURA", tiempo, sesion=1, numero=numero,
                  tiempo_sensor_ms=sensor_ms, distancia_cm=distancia)


class PruebasAnalizador(unittest.TestCase):
    def test_separa_ejecuciones_y_frecuencias(self):
        filas = [evento("SERVIDOR_INICIADO"), lectura(1, 1, 100),
                 lectura(2, 2, 200, None), lectura(3, 3, 300, 40), lectura(4, 4, 400),
                 evento("APLICADO", 4, latencia_confirmacion_ms=20),
                 evento("SERVIDOR_DETENIDO", 5), evento("SERVIDOR_INICIADO"),
                 lectura(1, 1, 100), lectura(2, 1.5, 600),
                 evento("APLICADO", 2, latencia_confirmacion_ms=100),
                 evento("SERVIDOR_DETENIDO", 3)]
        resumen = analizar_registro(filas)
        primera, segunda = resumen["ejecuciones"]
        sesion = primera["sesiones_sensor"][0]
        self.assertEqual((sesion["lecturas"], sesion["validas"], sesion["sin_eco"],
                          sesion["fuera_de_rango"]), (4, 2, 1, 1))
        self.assertEqual(sesion["frecuencia_adquisicion_hz"], 10)
        self.assertEqual(sesion["frecuencia_recepcion_hz"], 1)
        self.assertAlmostEqual(sesion["frecuencia_validas_recepcion_hz"], 1 / 3)
        self.assertEqual(segunda["sesiones_sensor"][0]["frecuencia_adquisicion_hz"], 2)
        self.assertEqual(primera["latencia_confirmacion_media_ms"], 20)
        self.assertEqual(segunda["latencia_confirmacion_media_ms"], 100)
        self.assertEqual(resumen["advertencias"] + primera["advertencias"]
                         + segunda["advertencias"] + sesion["advertencias"], [])

    def test_advierte_evidencia_incompleta_y_no_infiere_muestreo_con_huecos(self):
        resumen = analizar_registro([
            lectura(2, 1, 100), lectura(4, 2, 300),
            evento("REGISTROS_DESCARTADOS", 2, cantidad=2, total=2),
            '{"evento":', evento("LECTURA", 3),
            evento("SERVIDOR_INICIADO", 4), lectura(1, 5, 500)])
        primera, segunda = resumen["ejecuciones"]
        sesion = primera["sesiones_sensor"][0]
        self.assertEqual(len(resumen["advertencias"]), 2)
        self.assertEqual(len(primera["advertencias"]), 3)  # Sin inicio/cierre y descartes.
        self.assertEqual(len(sesion["advertencias"]), 2)  # Inicio perdido y salto 2→4.
        self.assertIsNone(sesion["frecuencia_adquisicion_hz"])
        self.assertEqual(sesion["frecuencia_recepcion_hz"], 1)
        self.assertTrue(segunda["advertencias"])
        self.assertIsNone(segunda["sesiones_sensor"][0]["frecuencia_recepcion_hz"])
        self.assertTrue(analizar_registro([])["advertencias"])

    def test_reloj_sensor_desbordado_o_discontinuo(self):
        for inicio, fin, esperado in ((2 ** 32 - 50, 50, 10), (200, 100, None),
                                      (100, 100, None)):
            with self.subTest(inicio=inicio, fin=fin):
                resumen = analizar_registro([evento("SERVIDOR_INICIADO"),
                    lectura(1, 1, inicio), lectura(2, 1.1, fin),
                    evento("SERVIDOR_DETENIDO", 2)])
                sesion = resumen["ejecuciones"][0]["sesiones_sensor"][0]
                self.assertEqual(sesion["frecuencia_adquisicion_hz"], esperado)
                self.assertEqual(bool(sesion["advertencias"]), esperado is None)


if __name__ == "__main__":
    unittest.main()
