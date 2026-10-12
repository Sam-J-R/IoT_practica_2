"""Ejecuta comprobaciones y guarda las salidas originales, sin editar resultados."""
import argparse
from datetime import datetime, timezone
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
    argumentos = opciones.parse_args()
    raiz = Path(__file__).resolve().parents[1]
    evidencias = raiz / "documentacion" / "evidencias" / "software"
    evidencias.mkdir(parents=True, exist_ok=True)
    resultados = []
    entorno = os.environ.copy()
    entorno["PYTHONUTF8"] = "1"
    entorno["PYTHONIOENCODING"] = "utf-8"

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
    pio = shutil.which("pio") or shutil.which("platformio")
    comando_pio = [pio] if pio else [sys.executable, "-m", "platformio"]
    if pio or importlib.util.find_spec("platformio") is not None:
        ejecutar("pruebas_unity", comando_pio + ["test", "-e", "native"])
        for proyecto in ("sensor", "actuador"):
            ejecutar(f"compilacion_{proyecto}", comando_pio + ["run", "--project-dir", proyecto])
    else:
        resultados.append({"prueba": "unity_y_compilacion_esp32", "estado": "PENDIENTE", "motivo": "No se encontró PlatformIO"})
    registro_ncat = evidencias / "sesiones_ncat.jsonl"
    registro_ncat.unlink(missing_ok=True)
    comando_ncat = [sys.executable, "-B", "pruebas/verificar_ncat.py",
                   "--registro", str(registro_ncat)]
    if argumentos.ncat:
        comando_ncat += ["--ncat", argumentos.ncat]
    ejecutar("pruebas_ncat", comando_ncat, admite_pendiente=True)
    (evidencias / "resumen.json").write_text(
        json.dumps({"tipo": "SOFTWARE_SIN_PLACAS", "python": sys.version,
                    "resultados": resultados}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if any(fila["estado"] == "FALLIDO" for fila in resultados) else 0


if __name__ == "__main__":
    sys.exit(principal())
