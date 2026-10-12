"""Pruebas de los límites declarados y del filtro de tres muestras."""
import unittest

from servidor.control import ControlDistancia, EstadoLed


class PruebasControl(unittest.TestCase):
    def test_fronteras_y_datos_no_confiables(self):
        control = ControlDistancia()
        casos = [(None, "APAGADO"), (float("nan"), "APAGADO"),
                 (float("inf"), "APAGADO"), (-1, "APAGADO"),
                 (0, "APAGADO"), (1.99, "APAGADO"), (2, "ROJO"),
                 (9.99, "ROJO"), (10, "ROJO"), (10.01, "AMARILLO"),
                 (19.99, "AMARILLO"), (20, "AMARILLO"), (20.01, "VERDE"),
                 (29.99, "VERDE"), (30, "VERDE"), (30.01, "APAGADO"),
                 (400, "APAGADO")]
        for distancia, esperado in casos:
            with self.subTest(distancia=distancia):
                self.assertEqual(control.clasificar(distancia), esperado)

    def test_espera_tres_lecturas_y_rechaza_un_pico(self):
        control = ControlDistancia()
        self.assertEqual(control.procesar(15), EstadoLed.APAGADO)
        self.assertEqual(control.procesar(29), EstadoLed.APAGADO)
        self.assertEqual(control.procesar(15), EstadoLed.AMARILLO)
        self.assertEqual(control.distancia_filtrada, 15)
        self.assertEqual(control.procesar(9), EstadoLed.AMARILLO)
        self.assertEqual(control.procesar(9), EstadoLed.ROJO)

    def test_error_vacia_el_filtro_y_exige_tres_nuevas(self):
        control = ControlDistancia()
        for _ in range(3):
            control.procesar(25)
        self.assertEqual(control.procesar(None), EstadoLed.APAGADO)
        self.assertIsNone(control.distancia_filtrada)
        for _ in range(2):
            self.assertEqual(control.procesar(5), EstadoLed.APAGADO)
        self.assertEqual(control.procesar(5), EstadoLed.ROJO)
        self.assertEqual(control.procesar(31), EstadoLed.APAGADO)


if __name__ == "__main__":
    unittest.main()
