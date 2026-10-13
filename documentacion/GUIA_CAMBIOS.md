# Cambios realizados y cómo aplicarlos

Este paquete se creó **a partir del ZIP `IoT_practica_2(2).zip`**, sin editar el repositorio de GitHub del grupo.

## 1. Cambios en el servidor

- `servidor/servidor.py`: se sustituye el bucle `select` por `threading` (aceptador, lector por cliente y supervisor), con un `RLock` que protege las estructuras compartidas.
- Se conservan el filtro `ControlDistancia`, el protocolo en español, los roles, la confirmación `APLICADO`, los tiempos declarados y los archivos JSONL.
- Se limita a 250 ms el tiempo de las operaciones de socket de cada cliente. Los envíos cortos ocurren bajo el bloqueo global; para dos ESP32 es simple, pero un cliente de red muy lento puede retrasar brevemente a los demás.
- Se eliminó el servidor antiguo `server/server.py` de la copia entregable para no tener dos implementaciones activas.

## 2. Un único proyecto PlatformIO

- `platformio.ini` en la raíz contiene **tres** entornos: `esp32_sensor`, `esp32_actuador` y `native` (solo pruebas).
- Las fuentes se trasladaron a `firmware/src/sensor/` y `firmware/src/actuador/`; las cabeceras están en `firmware/include/sensor/` y `firmware/include/actuador/`.
- Los archivos repetidos `sensor/platformio.ini` y `actuador/platformio.ini` desaparecen. Se conserva `comun/` con las clases TCP y parser para ambos firmware.
- Los dos `main.cpp` **siguen siendo distintos** porque cada placa tiene una tarea diferente. No es apropiado cargar un solo binario idéntico a ambos sin seleccionar el rol, ya que eso añade configuración innecesaria.
- Se actualizaron las rutas de las pruebas C++ para apuntar a la nueva estructura.

## 3. Pruebas actualizadas

- `pruebas/test_integracion.py`: 15 ensayos TCP con servidor real multihilo, sin reloj simulado.
- `pruebas/test_control.py` y `pruebas/test_protocolo.py`: continúan verificando rangos y formato.
- `pruebas/nativo_compilador/test_componentes.cpp`: ensayo C++ independiente compilable con `g++` y dobles de Arduino.
- `pruebas/validar_software.py`: guarda salidas y hashes SHA-256 de código en `documentacion/evidencias/hilos/`. Detecta explícitamente herramientas que faltan.
- `pruebas/verificar_ncat.py`: se adaptó al nuevo servidor, que inicia y atiende sus propios hilos.

## 4. Cambios que deben verificar en las laptops

Desde la raíz, con PlatformIO instalado:

```powershell
python -B pruebas/validar_software.py
pio run -e esp32_sensor
pio run -e esp32_actuador
pio test -e native
```

**No** presentar los archivos antiguos en `documentacion/evidencias/software/` como una validación de la nueva versión con hilos. Las evidencias de esta versión están en `documentacion/evidencias/hilos/`.

## 5. Subir los cambios a GitHub

1. Descomprimir el ZIP en una carpeta de trabajo temporal.
2. Hacer una copia de seguridad de la rama actual antes de reemplazar archivos.
3. Trasladar la nueva estructura a la rama de trabajo del equipo.
4. Comparar (`git diff`) los cambios. Comprobar que **no** se sube `comun/ConfiguracionRed.h` con claves Wi-Fi ni archivos `.pio/`.
5. Compilar, ejecutar las pruebas en las dos laptops y probar físicamente ambos ESP32.
6. Cada integrante puede crear commits de su contribución con su propia cuenta, según pide la consigna.

El paquete no crea commits ni toca GitHub. El código y los comentarios conservan el idioma español del proyecto del equipo.
