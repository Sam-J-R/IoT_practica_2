"""Registro con destinos lentos o fallidos, sin bloquear el productor."""
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from servidor.registro import RegistroPruebas


class ArchivoLento:
    def __init__(self, fallar=False):
        self.entra = threading.Event()
        self.continuar = threading.Event()
        self.fallar = fallar
        self.cerrado = False

    def write(self, texto):
        self.entra.set()
        if not self.continuar.wait(3):
            raise TimeoutError("La prueba no liberó el archivo")
        if self.fallar:
            raise OSError("Disco lleno simulado")

    def flush(self):
        pass

    def close(self):
        self.cerrado = True


class PruebasRegistro(unittest.TestCase):
    def registro_doble(self, archivo, capacidad=2):
        with patch.object(Path, "open", return_value=archivo):
            registro = RegistroPruebas("doble.jsonl", capacidad=capacidad)
        self.addCleanup(registro.cerrar)
        self.addCleanup(archivo.continuar.set)
        return registro

    def test_error_de_disco_no_sale_al_productor_y_cierra_el_archivo(self):
        archivo = ArchivoLento(fallar=True)
        registro = self.registro_doble(archivo)
        archivo.continuar.set()
        with patch("servidor.registro.logging.error") as aviso:
            registro.registrar("LECTURA", distancia_cm=15)
            registro.cerrar()
        self.assertIn("Disco lleno", registro.error)
        self.assertFalse(registro.hilo.is_alive())
        self.assertTrue(archivo.cerrado)
        aviso.assert_called_once()

    def test_cierre_no_espera_indefinidamente_al_disco(self):
        archivo = ArchivoLento()
        registro = self.registro_doble(archivo)
        registro.registrar("LECTURA")
        self.assertTrue(archivo.entra.wait(1))
        terminado = threading.Event()
        cerrador = threading.Thread(target=lambda: (registro.cerrar(), terminado.set()), daemon=True)
        cerrador.start()
        try:
            self.assertTrue(terminado.wait(1.5))
            self.assertIn("destino bloqueado", registro.error)
        finally:
            archivo.continuar.set()
            cerrador.join(timeout=1)
            registro.cerrar()


if __name__ == "__main__":
    unittest.main()
