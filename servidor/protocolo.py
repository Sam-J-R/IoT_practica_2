"""Gramática compartida y reconstrucción de líneas de un flujo TCP."""
from math import isfinite
from typing import Any, Iterator, Union

MAXIMO_MENSAJE: int = 128  # Incluye LF o CRLF, en bytes.
MAXIMO_ENTERO: int = 4294967295


class ErrorProtocolo(ValueError):
    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo: str = codigo


class ReceptorLineas:
    """Búfer acotado, también para líneas sin terminador."""

    def __init__(self) -> None:
        self.pendiente: bytearray = bytearray()

    def recibir(self, datos: Union[bytes, bytearray]) -> Iterator[str]:
        # Generador: procesa las líneas anteriores aunque una posterior falle.
        for byte in datos:
            if byte > 127 or (byte < 32 and byte not in (10, 13)):
                raise ErrorProtocolo("FORMATO")
            self.pendiente.append(byte)
            if len(self.pendiente) > MAXIMO_MENSAJE:
                raise ErrorProtocolo("LONGITUD")
            if byte == 10:
                linea = bytes(self.pendiente[:-1])
                self.pendiente.clear()
                if linea.endswith(b"\r"):
                    linea = linea[:-1]
                if b"\r" in linea or not linea:
                    raise ErrorProtocolo("FORMATO")
                yield linea.decode("ascii")
            elif len(self.pendiente) == MAXIMO_MENSAJE:
                # No cabe el LF obligatorio: rechazar sin esperar más datos.
                raise ErrorProtocolo("LONGITUD")


class Mensaje:
    def __init__(self, comando: str, argumentos: dict[str, Any]) -> None:
        self.comando: str = comando
        self.argumentos: dict[str, Any] = argumentos


class ProtocoloAplicacion:
    """Valida sintaxis y dominios; el servidor valida permisos y secuencia."""

    CAMPOS: dict[str, list[str]] = {
        "REGISTRO": ["tipo", "version"],
        "LECTURA": ["numero", "tiempo_ms", "distancia_cm"],
        "ORDEN": ["numero", "estado"],
        "APLICADO": ["numero"],
        "RECIBIDO": ["numero"],
        "ERROR": ["codigo"],
    }

    @staticmethod
    def entero(texto: str) -> int:
        if not texto or not texto.isascii() or not texto.isdigit():
            raise ErrorProtocolo("VALOR")
        valor = int(texto)
        if valor > MAXIMO_ENTERO:
            raise ErrorProtocolo("VALOR")
        return valor

    @classmethod
    def interpretar(cls, linea: str) -> Mensaje:
        if linea == "ACEPTADO REGISTRO":
            return Mensaje("ACEPTADO", {})
        comando, separador, texto = linea.partition(" ")
        if comando not in cls.CAMPOS:
            raise ErrorProtocolo("COMANDO")
        if not separador or not texto:
            raise ErrorProtocolo("FORMATO")
        argumentos: dict[str, Any] = {}
        for indice, campo in enumerate(texto.split(",")):
            # Solo la coma admite un espacio opcional; el comando exige uno.
            if indice > 0 and campo.startswith(" "):
                campo = campo[1:]
            if campo.count("=") != 1:
                raise ErrorProtocolo("FORMATO")
            clave, valor = campo.split("=")
            if not clave or not valor:
                raise ErrorProtocolo("FORMATO")
            for letra in clave:
                if not ("a" <= letra <= "z" or letra == "_"):
                    raise ErrorProtocolo("FORMATO")
            for letra in valor:
                if not ("a" <= letra <= "z" or "A" <= letra <= "Z"
                        or "0" <= letra <= "9" or letra in "_."):
                    raise ErrorProtocolo("FORMATO")
            if clave in argumentos:
                raise ErrorProtocolo("DUPLICADO")
            if clave not in cls.CAMPOS[comando]:
                raise ErrorProtocolo("ARGUMENTO")
            argumentos[clave] = valor
        for clave in cls.CAMPOS[comando]:
            if clave not in argumentos:
                raise ErrorProtocolo("FALTANTE")
        if "numero" in argumentos:
            argumentos["numero"] = cls.entero(argumentos["numero"])
            if argumentos["numero"] == 0:
                raise ErrorProtocolo("VALOR")
        if comando == "REGISTRO":
            if argumentos["tipo"] not in ("sensor", "actuador"):
                raise ErrorProtocolo("VALOR")
            if argumentos["version"] != "1":
                raise ErrorProtocolo("VERSION")
        elif comando == "LECTURA":
            argumentos["tiempo_ms"] = cls.entero(argumentos["tiempo_ms"])
            valor = argumentos["distancia_cm"]
            if valor == "SIN_ECO":
                argumentos["distancia_cm"] = None
            else:
                if valor.count(".") > 1:
                    raise ErrorProtocolo("VALOR")
                for parte in valor.split("."):
                    if not parte.isdigit():
                        raise ErrorProtocolo("VALOR")
                distancia = float(valor)
                if not isfinite(distancia) or not 0 <= distancia <= 400:
                    raise ErrorProtocolo("VALOR")
                argumentos["distancia_cm"] = distancia
        elif comando == "ORDEN" and argumentos["estado"] not in (
                "APAGADO", "ROJO", "AMARILLO", "VERDE"):
            raise ErrorProtocolo("VALOR")
        elif comando == "ERROR":
            for letra in argumentos["codigo"]:
                if not ("A" <= letra <= "Z" or letra == "_"):
                    raise ErrorProtocolo("VALOR")
        return Mensaje(comando, argumentos)

    @staticmethod
    def codificar(linea: str) -> bytes:
        datos = (linea + "\n").encode("ascii")
        if len(datos) > MAXIMO_MENSAJE:
            raise ErrorProtocolo("LONGITUD")
        return datos
