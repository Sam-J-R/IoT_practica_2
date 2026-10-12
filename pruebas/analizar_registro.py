"""Resume evidencia de adquisición; no infiere exactitud o reinicios físicos."""
import argparse
import json
from pathlib import Path
from statistics import mean


def principal():
    opciones = argparse.ArgumentParser(description="Resumir un registro JSONL de la práctica")
    opciones.add_argument("archivo", type=Path)
    argumentos = opciones.parse_args()
    eventos = [json.loads(linea) for linea in argumentos.archivo.read_text(encoding="utf-8").splitlines() if linea]
    sesiones = {}
    for evento in eventos:
        if evento["evento"] == "LECTURA":
            sesiones.setdefault(evento["sesion"], []).append(evento)
    resumen = []
    for sesion, lecturas in sesiones.items():
        duracion = lecturas[-1]["tiempo_monotonico"] - lecturas[0]["tiempo_monotonico"]
        validas = sum(fila["distancia_cm"] is not None and 2 <= fila["distancia_cm"] <= 30
                      for fila in lecturas)
        resumen.append({"sesion": sesion, "lecturas": len(lecturas), "validas": validas,
            "duracion_observada_s": duracion,
            "frecuencia_recibida_hz": (len(lecturas) - 1) / duracion if duracion > 0 else None})
    latencias = [fila["latencia_confirmacion_ms"] for fila in eventos if fila["evento"] == "APLICADO"]
    print(json.dumps({"sesiones_sensor": resumen,
        "desconexiones": [fila for fila in eventos if fila["evento"] == "DESCONEXION"],
        "confirmaciones": len(latencias),
        "latencia_confirmacion_media_ms": mean(latencias) if latencias else None,
        "latencia_confirmacion_maxima_ms": max(latencias) if latencias else None,
        "advertencia": "Frecuencia recibida incluye SIN_ECO. Confirmación desde ORDEN encolada, incluida su cola; no tiempo físico de respuesta."},
        ensure_ascii=False, indent=2))


if __name__ == "__main__":
    principal()
