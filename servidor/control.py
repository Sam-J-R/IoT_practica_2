"""Aquí están los rangos de distancia y el filtro de tres lecturas."""
from enum import StrEnum
from math import isfinite
from typing import Optional


class ConfiguracionServidor:
    def __init__(self, direccion: str = "0.0.0.0", puerto: int = 5000) -> None:
        self.direccion: str = direccion
        self.puerto: int = puerto
        self.espera_registro: float = 3.0
        self.inactividad_sensor: float = 5.0
        self.espera_confirmacion: float = 1.0
        self.espera_cierre: float = 0.5
        self.intervalo_refresco: float = 1.0
        self.distancia_minima: float = 2.0
        self.umbral_rojo: float = 10.0
        self.umbral_amarillo: float = 20.0
        self.distancia_maxima: float = 30.0
        self.maximo_clientes: int = 8
        if not 0 <= puerto <= 65535:
            raise ValueError("Puerto fuera de rango")


# Estados representados mediante StrEnum para tipado fuerte y compatibilidad de texto.
class EstadoLed(StrEnum):
    APAGADO = "APAGADO"
    ROJO = "ROJO"
    AMARILLO = "AMARILLO"
    VERDE = "VERDE"


class ControlDistancia:
    def __init__(self, configuracion: Optional[ConfiguracionServidor] = None) -> None:
        self.configuracion: ConfiguracionServidor = configuracion or ConfiguracionServidor()
        self.lecturas: list[float] = []
        self.distancia_filtrada: Optional[float] = None
        self.estado: EstadoLed = EstadoLed.APAGADO

    def clasificar(self, distancia: Optional[float]) -> EstadoLed:
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

    def invalidar(self) -> EstadoLed:
        self.lecturas.clear()
        self.distancia_filtrada = None
        self.estado = EstadoLed.APAGADO
        return self.estado

    def procesar(self, distancia: Optional[float]) -> EstadoLed:
        """Guarda las tres últimas lecturas válidas y toma la del medio."""
        if self.clasificar(distancia) == EstadoLed.APAGADO:
            return self.invalidar()
        if distancia is not None:
            self.lecturas.append(distancia)
        if len(self.lecturas) > 3:
            self.lecturas.pop(0)
        if len(self.lecturas) == 3:
            ordenadas = sorted(self.lecturas)
            self.distancia_filtrada = ordenadas[1]
            self.estado = self.clasificar(self.distancia_filtrada)
        return self.estado
