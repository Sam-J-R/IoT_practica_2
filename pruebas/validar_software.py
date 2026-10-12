"""Ejecuta comprobaciones y guarda las salidas originales, sin editar resultados."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def principal():
    opciones = argparse.ArgumentParser(description="Validar software y guardar evidencias")
    ncat_local = Path(__file__).resolve().parents[1] / ".herramientas/ncat/ncat.exe"
    opciones.add_argument("--ncat", default=shutil.which("ncat") or str(ncat_local))
    pio_local = Path.home() / ".platformio/penv/Scripts/platformio.exe"
    pio = shutil.which("pio") or shutil.which("platformio")
    if not pio and pio_local.is_file():
        pio = str(pio_local)
    opciones.add_argument("--platformio", default=pio, help="Ruta del ejecutable PlatformIO")
    argumentos = opciones.parse_args()
    raiz = Path(__file__).resolve().parents[1]
    evidencias = raiz / "documentacion" / "evidencias" / "software"
    evidencias.mkdir(parents=True, exist_ok=True)
    resultados = []
    entorno = os.environ.copy()
    entorno["PYTHONUTF8"] = "1"
    entorno["PYTHONIOENCODING"] = "utf-8"
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz,
                            capture_output=True, text=True, check=True).stdout.strip()
    # Las huellas identifican el código probado, incluso antes de crear un commit.
    archivos = [raiz / "platformio.ini", raiz / "sensor/platformio.ini", raiz / "actuador/platformio.ini"]
    for carpeta in ("sensor/src", "sensor/include", "actuador/src", "actuador/include", "comun", "servidor", "pruebas"):
        archivos.extend(ruta for ruta in (raiz / carpeta).rglob("*")
                        if ruta.suffix in (".py", ".cpp", ".h") and ruta.name != "ConfiguracionRed.h")
    huellas = {ruta.relative_to(raiz).as_posix(): sha256(ruta.read_bytes()).hexdigest()
               for ruta in sorted(archivos)}

    def pendiente(nombre, motivo):
        (evidencias / f"{nombre}.txt").write_text(f"PENDIENTE: {motivo}\n", encoding="utf-8")
        resultados.append({"prueba": nombre, "estado": "PENDIENTE", "motivo": motivo})
        print(f"{nombre}: PENDIENTE ({motivo})", flush=True)

    def ejecutar(nombre, comando, admite_pendiente=False):
        print(f"Verificando {nombre}...", flush=True)
        inicio = datetime.now(timezone.utc).isoformat()
        proceso = subprocess.run(comando, cwd=raiz, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                 errors="replace", env=entorno)
        (evidencias / f"{nombre}.txt").write_text(proceso.stdout, encoding="utf-8")
        estado = "APROBADO" if proceso.returncode == 0 else "FALLIDO"
        if admite_pendiente and proceso.returncode == 2:
            estado = "PENDIENTE"
        resultados.append({"prueba": nombre, "inicio_utc": inicio, "comando": comando,
                           "codigo_salida": proceso.returncode, "estado": estado})
        print(f"{nombre}: {estado}", flush=True)
        return proceso.returncode

    ejecutar("pruebas_python", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "pruebas", "-v"])
    pio = argumentos.platformio
    comando_pio = [pio] if pio else [sys.executable, "-m", "platformio"]
    if (pio and Path(pio).is_file()) or (not pio and importlib.util.find_spec("platformio") is not None):
        ejecutar("pruebas_unity", comando_pio + ["test", "-e", "native"])
        for proyecto in ("sensor", "actuador"):
            ejecutar(f"compilacion_{proyecto}", comando_pio + ["run", "--project-dir", proyecto])
    else:
        for nombre in ("pruebas_unity", "compilacion_sensor", "compilacion_actuador"):
            pendiente(nombre, "No se encontró PlatformIO; indicar --platformio RUTA")
    registro_ncat = evidencias / "sesiones_ncat.jsonl"
    registro_ncat.unlink(missing_ok=True)
    comando_ncat = [sys.executable, "-B", "pruebas/verificar_ncat.py",
                   "--registro", str(registro_ncat)]
    if argumentos.ncat:
        comando_ncat += ["--ncat", argumentos.ncat]
    ejecutar("pruebas_ncat", comando_ncat, admite_pendiente=True)
    if any(fila["estado"] == "FALLIDO" for fila in resultados):
        estado_final, codigo_salida = "FALLIDO", 1
    elif any(fila["estado"] == "PENDIENTE" for fila in resultados):
        estado_final, codigo_salida = "INCOMPLETO", 2
    else:
        estado_final, codigo_salida = "APROBADO", 0
    (evidencias / "resumen.json").write_text(
        json.dumps({"tipo": "SOFTWARE_SIN_PLACAS", "estado": estado_final,
                    "commit_base": commit, "codigo_sha256": huellas, "python": sys.version,
                    "resultados": resultados}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Validación de software: {estado_final}", flush=True)
    return codigo_salida


if __name__ == "__main__":
    sys.exit(principal())
