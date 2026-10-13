"""Ejecuta la validación reproducible de la arquitectura con hilos.

Conserva salidas reales (sin inventar métricas) y un resumen JSON con
huellas SHA-256 de los archivos probados. No requiere placas para las
pruebas Python y C++ nativas. El firmware ESP32 necesita PlatformIO.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

RAIZ = Path(__file__).resolve().parents[1]
EVIDENCIAS = RAIZ / "documentacion/evidencias/hilos"


def ejecutar(nombre, comando, resultados, salida=EVIDENCIAS):
    inicio = datetime.now(timezone.utc).isoformat()
    proceso = subprocess.run([str(x) for x in comando], cwd=RAIZ,
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", env={**os.environ, "PYTHONUTF8": "1"})
    texto = proceso.stdout + proceso.stderr
    (salida / f"{nombre}.txt").write_text(texto, encoding="utf-8")
    estado = "APROBADO" if proceso.returncode == 0 else "FALLIDO"
    resultados.append({"nombre": nombre, "comando": [str(x) for x in comando],
                       "fecha_utc": inicio, "codigo_salida": proceso.returncode,
                       "estado": estado})
    print(f"{nombre}: {estado}", flush=True)


def pendiente(nombre, motivo, resultados):
    (EVIDENCIAS / f"{nombre}.txt").write_text("NO EJECUTADO: " + motivo + "\n", encoding="utf-8")
    resultados.append({"nombre": nombre, "estado": "NO_EJECUTADO", "motivo": motivo})
    print(f"{nombre}: NO EJECUTADO ({motivo})", flush=True)


def principal():
    parser = argparse.ArgumentParser(description="Pruebas de proyecto IoT unificado")
    parser.add_argument("--platformio", default=shutil.which("pio") or shutil.which("platformio"))
    parser.add_argument("--ncat", default=shutil.which("ncat"))
    args = parser.parse_args()
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    resultados = []

    ejecutar("pruebas_python", [sys.executable, "-B", "-m", "unittest",
                                "discover", "-s", "pruebas", "-p", "test_*.py", "-v"], resultados)

    compilador = shutil.which("g++")
    if compilador:
        with tempfile.TemporaryDirectory(prefix="iot_tests_") as carpeta:
            binario = Path(carpeta) / ("componentes.exe" if os.name == "nt" else "componentes")
            banderas = ["-std=c++11", "-Wall", "-Wextra", "-I", "pruebas/dobles",
                        "-I", "firmware/include/sensor", "-I", "firmware/include/actuador",
                        "-I", "comun"]
            ejecutar("compilacion_cpp_nativa", [compilador, *banderas,
                "pruebas/nativo_compilador/test_componentes.cpp",
                "firmware/src/sensor/SensorUltrasonico.cpp",
                "firmware/src/actuador/IndicadorLeds.cpp", "-o", binario], resultados)
            if resultados[-1]["estado"] == "APROBADO":
                ejecutar("pruebas_cpp_nativas", [binario], resultados)
            else:
                pendiente("pruebas_cpp_nativas", "La compilación C++ falló", resultados)
            for rol in ("sensor", "actuador"):
                fuentes = sorted((RAIZ / "firmware/src" / rol).glob("*.cpp"))
                ejecutar(f"sintaxis_{rol}", [compilador, *banderas, "-fsyntax-only",
                                               *(p.relative_to(RAIZ) for p in fuentes)], resultados)
    else:
        for nombre in ("compilacion_cpp_nativa", "pruebas_cpp_nativas", "sintaxis_sensor", "sintaxis_actuador"):
            pendiente(nombre, "No está disponible g++", resultados)

    plataforma = args.platformio
    if not plataforma:
        candidato = Path.home() / ".platformio" / "penv" / "Scripts" / "platformio.exe"
        if candidato.is_file():
            plataforma = str(candidato)
    if plataforma:
        ejecutar("pruebas_unity", [plataforma, "test", "-e", "native"], resultados)
        for entorno in ("esp32_sensor", "esp32_actuador"):
            ejecutar(f"compilacion_{entorno}", [plataforma, "run", "-e", entorno], resultados)
    else:
        for nombre in ("pruebas_unity", "compilacion_esp32_sensor", "compilacion_esp32_actuador"):
            pendiente(nombre, "PlatformIO no disponible en esta computadora", resultados)

    if args.ncat:
        ejecutar("pruebas_ncat", [sys.executable, "-B", "pruebas/verificar_ncat.py",
                "--ncat", args.ncat, "--registro", EVIDENCIAS / "sesiones_ncat.jsonl"], resultados)
    else:
        pendiente("pruebas_ncat", "Ncat no disponible", resultados)

    archivos = [RAIZ / "platformio.ini"]
    for carpeta in ("firmware", "comun", "servidor", "pruebas"):
        archivos.extend(p for p in (RAIZ/carpeta).rglob("*")
                        if p.is_file() and p.suffix in (".py", ".h", ".cpp", ".ini"))
    huellas = {p.relative_to(RAIZ).as_posix(): sha256(p.read_bytes()).hexdigest()
               for p in sorted(archivos)}
    if any(x["estado"] == "FALLIDO" for x in resultados):
        estado, codigo = "FALLIDO", 1
    elif any(x["estado"] == "NO_EJECUTADO" for x in resultados):
        estado, codigo = "PARCIAL", 2
    else:
        estado, codigo = "APROBADO", 0
    resumen = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
               "tipo": "SOFTWARE_LOCAL_Y_COMPILACION", "arquitectura": "HILOS",
               "estado": estado, "python": sys.version, "resultados": resultados,
               "sha256_codigo": huellas,
               "nota": "No acredita funcionamiento, exactitud o tiempos físicos de los ESP32."}
    (EVIDENCIAS / "resumen.json").write_text(json.dumps(resumen, indent=2,
        ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"VALIDACION: {estado}")
    return codigo


if __name__ == "__main__":
    sys.exit(principal())
