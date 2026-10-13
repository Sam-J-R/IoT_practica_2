"""Regresiones de fallos y recursos con transporte y reloj controlados."""
import unittest
import time

from servidor.control import EstadoLed
from servidor.servidor import ServidorTcp, SesionCliente
from servidor.protocolo import ErrorProtocolo


class RegistroMemoria:
    def registrar(self, evento, **datos):
        pass

    def cerrar(self):
        pass


class SocketDoble:
    def __init__(self):
        self.cerrado = False

    def shutdown(self, _):
        pass

    def close(self):
        self.cerrado = True


class PruebasRobustezServidor(unittest.TestCase):
    def setUp(self):
        self.ahora = 0.0
        self.servidor = ServidorTcp(registro=RegistroMemoria(), reloj=lambda: self.ahora)
        self.addCleanup(self.servidor.cerrar)

    def sesion(self, rol):
        sesion = SesionCliente(SocketDoble(), "doble", len(self.servidor.sesiones) + 1,
                               self.ahora)
        sesion.rol = rol
        self.servidor.sesiones[sesion.conexion] = sesion
        self.servidor.roles[rol] = sesion
        return sesion

    def test_cierre_total_a_medio_segundo_aunque_escritor_no_avance(self):
        sensor = self.sesion("sensor")
        self.servidor._rechazar(sensor, "FORMATO")
        self.ahora = 0.499
        self.servidor._temporizadores()
        self.assertFalse(sensor.cerrada)
        self.ahora = 0.5
        self.servidor._temporizadores()
        self.assertTrue(sensor.cerrada)
        self.assertTrue(sensor.conexion.cerrado)

    def interrumpir_color(self, actuador):
        self.servidor.control.estado = EstadoLed.ROJO
        self.servidor._solicitar_estado()
        actuador.salida.get_nowait()
        color = actuador.numero_pendiente
        self.servidor.control.estado = EstadoLed.APAGADO
        self.servidor._solicitar_estado()
        actuador.salida.get_nowait()
        return color, actuador.numero_pendiente

    def test_confirmacion_interrumpida_tardia_no_renueva_el_plazo(self):
        actuador = self.sesion("actuador")
        color, _ = self.interrumpir_color(actuador)
        self.ahora = self.servidor.configuracion.espera_confirmacion
        with self.assertRaises(ErrorProtocolo) as error:
            self.servidor._procesar(actuador, f"APLICADO numero={color}")
        self.assertEqual(error.exception.codigo, "CONFIRMACION_TARDIA")
        self.servidor._temporizadores()
        self.assertTrue(actuador.cerrada)
        self.assertEqual(actuador.numero_interrumpido, 0)

    def esperar_hilos(self):
        limite = time.monotonic() + 2
        while time.monotonic() < limite:
            with self.servidor.bloqueo:
                if not self.servidor.hilos:
                    return
            time.sleep(0.005)
        self.fail("Quedaron hilos registrados después de terminar")

    def test_fallo_inesperado_de_hilo_cierra_servicio_y_libera_sesiones(self):
        sensor = self.sesion("sensor")
        actuador = self.sesion("actuador")

        def fallar():
            raise RuntimeError("Fallo simulado del supervisor")

        self.servidor._iniciar_hilo(fallar, "supervisor-prueba")
        self.esperar_hilos()
        self.assertTrue(self.servidor.detener.is_set())
        self.assertIn("Fallo simulado", self.servidor.error_hilo)
        self.assertTrue(sensor.conexion.cerrado)
        self.assertTrue(actuador.conexion.cerrado)
        self.assertEqual(self.servidor.sesiones, {})
        self.assertEqual(self.servidor.roles, {})


if __name__ == "__main__":
    unittest.main()
