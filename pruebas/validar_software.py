"""Validación esencial: servidor, firmware simulado y compilación de las placas."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

RAIZ = Path(__file__).resolve().parents[1]


def ejecutar(nombre, comando, resultados, salida):
    inicio = datetime.now(timezone.utc).isoformat()
    proceso = subprocess.run([str(x) for x in comando], cwd=RAIZ,
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", env={**os.environ, "PYTHONUTF8": "1"})
    (salida / f"{nombre}.txt").write_text(proceso.stdout + proceso.stderr, encoding="utf-8")
    estado = "APROBADO" if proceso.returncode == 0 else "FALLIDO"
    resultados.append({"nombre": nombre, "comando": [str(x) for x in comando],
                       "fecha_utc": inicio, "codigo_salida": proceso.returncode,
                       "estado": estado})
    print(f"{nombre}: {estado}", flush=True)


def principal():
    parser = argparse.ArgumentParser(description="Validación esencial del proyecto IoT")
    parser.add_argument("--platformio", default=shutil.which("pio") or shutil.which("platformio"))
    parser.add_argument("--salida", type=Path, default=Path("documentacion/evidencias/esenciales") /
                        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
    args = parser.parse_args()
    salida = args.salida if args.salida.is_absolute() else RAIZ / args.salida
    salida.mkdir(parents=True, exist_ok=True)
    resultados = []

    ejecutar("pruebas_python", [sys.executable, "-B", "-m", "unittest",
                                "discover", "-s", "pruebas", "-p", "test_*.py", "-v"],
             resultados, salida)

    plataforma = args.platformio
    if not plataforma:
        candidato = Path.home() / ".platformio/penv/Scripts/pio.exe"
        if candidato.is_file():
            plataforma = str(candidato)
    pasos = [("pruebas_unity", ["test", "-e", "native"]),
             ("compilacion_esp32_sensor", ["run", "-e", "esp32_sensor"]),
             ("compilacion_esp32_actuador", ["run", "-e", "esp32_actuador"])]
    for nombre, argumentos in pasos:
        if plataforma:
            ejecutar(nombre, [plataforma, *argumentos], resultados, salida)
        else:
            motivo = "PlatformIO no disponible; indicar --platformio"
            (salida / f"{nombre}.txt").write_text("NO EJECUTADO: " + motivo + "\n", encoding="utf-8")
            resultados.append({"nombre": nombre, "estado": "NO_EJECUTADO", "motivo": motivo})
            print(f"{nombre}: NO EJECUTADO", flush=True)

    archivos = [RAIZ / "platformio.ini"]
    for carpeta in ("firmware", "comun", "servidor", "pruebas"):
        archivos.extend(p for p in (RAIZ / carpeta).rglob("*")
                        if p.is_file() and p.suffix in (".py", ".h", ".cpp", ".ini")
                        and p.name != "ConfiguracionRed.h")
    huellas = {p.relative_to(RAIZ).as_posix(): sha256(p.read_bytes()).hexdigest()
               for p in sorted(archivos)}
    if any(x["estado"] == "FALLIDO" for x in resultados):
        estado, codigo = "FALLIDO", 1
    elif any(x["estado"] == "NO_EJECUTADO" for x in resultados):
        estado, codigo = "PARCIAL", 2
    else:
        estado, codigo = "APROBADO", 0
    resumen = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
               "tipo": "SOFTWARE_ESENCIAL_Y_COMPILACION", "estado": estado,
               "python": sys.version, "resultados": resultados, "sha256_codigo": huellas,
               "nota": "No acredita funcionamiento, exactitud o tiempos físicos de los ESP32. "
                       "La configuración privada de red se excluye de las huellas."}
    (salida / "resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    print(f"VALIDACION: {estado}\nEvidencias: {salida}")
    return codigo


if __name__ == "__main__":
    sys.exit(principal())
