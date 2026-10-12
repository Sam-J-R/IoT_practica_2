"""Aquí están los rangos de distancia y el filtro de tres lecturas."""
from math import isfinite


class ConfiguracionServidor:
    def __init__(self, direccion="0.0.0.0", puerto=5000):
        self.direccion = direccion
        self.puerto = puerto
        self.espera_registro = 3
        self.inactividad_sensor = 5
        self.espera_confirmacion = 1
        self.intervalo_refresco = 1
        self.distancia_minima = 2
        self.umbral_rojo = 10
        self.umbral_amarillo = 20
        self.distancia_maxima = 30
        self.maximo_clientes = 8
        if not 0 <= puerto <= 65535:
            raise ValueError("Puerto fuera de rango")


# Los estados son textos comunes, no enumeraciones especiales.
class EstadoLed:
    APAGADO = "APAGADO"
    ROJO = "ROJO"
    AMARILLO = "AMARILLO"
    VERDE = "VERDE"


class ControlDistancia:
    def __init__(self, configuracion=None):
        self.configuracion = configuracion or ConfiguracionServidor()
        self.lecturas = []
        self.distancia_filtrada = None
        self.estado = EstadoLed.APAGADO

    def clasificar(self, distancia):
        """Recibe centímetros y devuelve el nombre del color."""
        c = self.configuracion
        if distancia is None or not isfinite(distancia):
            return EstadoLed.APAGADO
        if distancia < c.distancia_minima or distancia > c.distancia_maxima:
            return EstadoLed.APAGADO
        if distancia <= c.umbral_rojo:
            return EstadoLed.ROJO
        if distancia <= c.umbral_amarillo:
            return EstadoLed.AMARILLO
        return EstadoLed.VERDE

    def invalidar(self):
        self.lecturas = []
        self.distancia_filtrada = None
        self.estado = EstadoLed.APAGADO
        return self.estado

    def procesar(self, distancia):
        """Guarda las tres últimas lecturas válidas y toma la del medio."""
        if self.clasificar(distancia) == EstadoLed.APAGADO:
            return self.invalidar()
        self.lecturas.append(distancia)
        if len(self.lecturas) > 3:
            self.lecturas.pop(0)
        if len(self.lecturas) == 3:
            ordenadas = sorted(self.lecturas)
            self.distancia_filtrada = ordenadas[1]
            self.estado = self.clasificar(self.distancia_filtrada)
        return self.estado
