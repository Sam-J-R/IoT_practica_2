"""Resume JSONL por ejecución; sus promedios no certifican métricas físicas."""
import argparse
import json
from math import isfinite
from pathlib import Path
from statistics import mean


def _numero(valor):
    return type(valor) in (int, float) and isfinite(valor)


def _evento_valido(fila):
    """Descarta filas dañadas sin perder el resto de la evidencia recuperable."""
    if not isinstance(fila, dict) or not isinstance(fila.get("evento"), str):
        return False
    if not _numero(fila.get("tiempo_monotonico")):
        return False
    if fila["evento"] == "LECTURA":
        for clave in ("sesion", "numero", "tiempo_sensor_ms"):
            valor = fila.get(clave)
            if type(valor) is not int or not 0 <= valor <= 4294967295:
                return False
        distancia = fila.get("distancia_cm")
        return (fila["sesion"] > 0 and fila["numero"] > 0 and "distancia_cm" in fila
                and (distancia is None or (_numero(distancia) and 0 <= distancia <= 400)))
    if fila["evento"] == "APLICADO":
        return (_numero(fila.get("latencia_confirmacion_ms"))
                and fila["latencia_confirmacion_ms"] >= 0)
    return True


def _resumir_sesion(sesion, lecturas):
    advertencias = []
    duracion = lecturas[-1]["tiempo_monotonico"] - lecturas[0]["tiempo_monotonico"]
    intervalos = len(lecturas) - 1
    validas = [fila["distancia_cm"] is not None and 2 <= fila["distancia_cm"] <= 30
               for fila in lecturas]
    if lecturas[0]["numero"] != 1:
        advertencias.append("Faltan lecturas iniciales de esta sesión.")
    secuencia_correcta = True
    reloj_correcto = True
    tiempo_sensor_ms = 0
    for anterior, actual in zip(lecturas, lecturas[1:]):
        if actual["numero"] != anterior["numero"] + 1:
            secuencia_correcta = False
        # millis() es uint32. Un salto >= media vuelta es ambiguo: no inferir un reinicio.
        delta = (actual["tiempo_sensor_ms"] - anterior["tiempo_sensor_ms"]) % (2 ** 32)
        if not 0 < delta < 2 ** 31:
            reloj_correcto = False
        tiempo_sensor_ms += delta
    if not secuencia_correcta:
        advertencias.append("Secuencia discontinua: faltan lecturas o están desordenadas.")
    if not reloj_correcto:
        advertencias.append("Reloj del sensor repetido o discontinuo; adquisición no calculable.")
    recepcion_correcta = intervalos > 0 and all(
        b["tiempo_monotonico"] > a["tiempo_monotonico"]
        for a, b in zip(lecturas, lecturas[1:]))
    if not recepcion_correcta:
        advertencias.append("Recepción insuficiente o reloj no creciente; frecuencia no calculable.")
    adquisicion_correcta = intervalos > 0 and secuencia_correcta and reloj_correcto
    return {
        "sesion": sesion, "lecturas": len(lecturas), "validas": sum(validas),
        "sin_eco": sum(fila["distancia_cm"] is None for fila in lecturas),
        "fuera_de_rango": sum(fila["distancia_cm"] is not None and not valida
                              for fila, valida in zip(lecturas, validas)),
        "duracion_recepcion_s": duracion,
        "duracion_sensor_s": tiempo_sensor_ms / 1000 if adquisicion_correcta else None,
        "frecuencia_adquisicion_hz": intervalos * 1000 / tiempo_sensor_ms
        if adquisicion_correcta else None,
        "frecuencia_recepcion_hz": intervalos / duracion if recepcion_correcta else None,
        "frecuencia_validas_recepcion_hz": sum(validas[1:]) / duracion
        if recepcion_correcta else None,
        "advertencias": advertencias,
    }


def _resumir_ejecucion(numero, eventos):
    advertencias = []
    if eventos[0]["evento"] != "SERVIDOR_INICIADO":
        advertencias.append("Falta SERVIDOR_INICIADO: no se puede asegurar el origen del tramo.")
    if eventos[-1]["evento"] != "SERVIDOR_DETENIDO":
        advertencias.append("Falta SERVIDOR_DETENIDO: registro abierto o cierre incompleto.")
    incidencias = [fila for fila in eventos if fila["evento"] in
                   ("REGISTROS_DESCARTADOS", "FALLO_REGISTRO", "FALLO_HILO")]
    if incidencias:
        advertencias.append("Hay descartes o fallos registrados; revisar incidencias.")
    sesiones = {}
    for fila in eventos:
        if fila["evento"] == "LECTURA":
            sesiones.setdefault(fila["sesion"], []).append(fila)
    resumen = [_resumir_sesion(sesion, filas) for sesion, filas in sesiones.items()]
    latencias = [fila["latencia_confirmacion_ms"] for fila in eventos
                 if fila["evento"] == "APLICADO"]
    return {
        "ejecucion": numero, "inicio_utc": eventos[0].get("fecha_utc"),
        "sesiones_sensor": resumen, "incidencias": incidencias,
        "desconexiones": [fila for fila in eventos if fila["evento"] == "DESCONEXION"],
        "confirmaciones": len(latencias),
        "latencia_confirmacion_media_ms": mean(latencias) if latencias else None,
        "latencia_confirmacion_maxima_ms": max(latencias) if latencias else None,
        "advertencias": advertencias,
    }


def analizar_registro(lineas):
    """Segmenta por inicio/cierre; no mezcla sesiones ni latencias de ensayos distintos."""
    ejecuciones = []
    eventos = []
    advertencias = []
    for numero, linea in enumerate(lineas, 1):
        if not linea.strip():
            continue
        try:
            fila = json.loads(linea)
        except (ValueError, RecursionError):
            fila = None
        if not _evento_valido(fila):
            advertencias.append(f"Línea {numero} inválida o incompleta; se omitió.")
            continue
        if fila["evento"] == "SERVIDOR_INICIADO" and eventos:
            ejecuciones.append(_resumir_ejecucion(len(ejecuciones) + 1, eventos))
            eventos = []
        eventos.append(fila)
        if fila["evento"] == "SERVIDOR_DETENIDO":
            ejecuciones.append(_resumir_ejecucion(len(ejecuciones) + 1, eventos))
            eventos = []
    if eventos:
        ejecuciones.append(_resumir_ejecucion(len(ejecuciones) + 1, eventos))
    if not ejecuciones:
        advertencias.append("No hay eventos utilizables.")
    return {
        "ejecuciones": ejecuciones, "advertencias": advertencias,
        "limites": [
            "Separación por marcadores de inicio/cierre: si ambos se pierden, no puede garantizarse.",
            "Frecuencias medias entre primera y última lectura; no acreditan una frecuencia mínima.",
            "Adquisición usa el reloj del sensor y exige números consecutivos; incluye SIN_ECO.",
            "Recepción usa el reloj del servidor. Válidas: 2–30 cm en el intervalo (primera, última].",
            "Confirmación mide ORDEN→APLICADO, no sensor→LED ni exactitud o estabilidad física.",
            "Un fallo de escritura puede dejar avisos solo en consola: revisar también FALLO_REGISTRO.",
        ],
    }


def principal():
    opciones = argparse.ArgumentParser(description="Resumir un registro JSONL por ejecución")
    opciones.add_argument("archivo", type=Path)
    argumentos = opciones.parse_args()
    with argumentos.archivo.open(encoding="utf-8", errors="replace") as archivo:
        resumen = analizar_registro(archivo)
    print(json.dumps(resumen, ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
    principal()
