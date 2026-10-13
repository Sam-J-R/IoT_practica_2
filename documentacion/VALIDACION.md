# Validación del proyecto unificado con hilos

## 1. Qué versión se está evaluando

El código actual sustituye el servidor `select` por un **servidor Python con hilos** y agrupa el firmware de las dos placas en **un único proyecto PlatformIO**. Se conservan los mensajes de la versión 1 del protocolo, los GPIO existentes y la clasificación por mediana.

Las pruebas anteriores de los ESP32 y los registros del servidor anterior se consideran **históricos**: el funcionamiento físico comunicado por el grupo se realizó con la implementación anterior a esta modificación. Es necesario comprobar las placas nuevamente después de cargar la nueva organización del proyecto.

## 2. Resultados ejecutados con la arquitectura nueva

Se han generado resultados reproducibles mediante el archivo `pruebas/validar_software.py`. Los archivos auténticos se encuentran en [evidencias/hilos/](evidencias/hilos/).

| Verificación | Resultado observado en el entorno de revisión | Evidencia |
|---|---|---|
| Python: lógica, protocolo y TCP concurrente | **24/24 aprobadas** | [pruebas_python.txt](evidencias/hilos/pruebas_python.txt) |
| Robustez de Python (cinco ejecuciones consecutivas) | **5/5 suites aprobadas, 24 casos por ejecución** | [pruebas_python_repetibilidad.txt](evidencias/hilos/pruebas_python_repetibilidad.txt); repetir en las laptops según el comando inferior |
| C++ nativo con dobles de Arduino | **9 verificaciones aprobadas** | [pruebas_cpp_nativas.txt](evidencias/hilos/pruebas_cpp_nativas.txt) |
| Compilación/sintaxis C++ del firmware de sensor y actuador con `g++` y dobles | **Correcta** | [sintaxis_sensor.txt](evidencias/hilos/sintaxis_sensor.txt), [sintaxis_actuador.txt](evidencias/hilos/sintaxis_actuador.txt) y [resumen.json](evidencias/hilos/resumen.json) |
| PlatformIO Unity | **NO EJECUTADO en este entorno:** no hay PlatformIO instalado | [pruebas_unity.txt](evidencias/hilos/pruebas_unity.txt) |
| Compilación para DOIT ESP32 real | **NO EJECUTADA en este entorno:** no hay PlatformIO instalado | [sensor](evidencias/hilos/compilacion_esp32_sensor.txt) / [actuador](evidencias/hilos/compilacion_esp32_actuador.txt) |
| Ncat | **NO EJECUTADO en este entorno:** binario no disponible | [pruebas_ncat.txt](evidencias/hilos/pruebas_ncat.txt) |
| Conexión física, exactitud, Wi-Fi, latencia sensor→LED | **PENDIENTE de nueva demostración** | No se presentan resultados no medidos |

El archivo [resumen.json](evidencias/hilos/resumen.json) conserva comandos, códigos de salida, hora UTC y huellas SHA-256 para identificar exactamente qué fuentes se probaron. La falta de herramientas se distingue explícitamente de un fallo de ejecución.

## 3. Qué validan las pruebas Python

La suite incluye pruebas de lógica, gramática y sockets TCP reales contra la implementación multihilo:

- Rangos `2–10`, `10–20`, `20–30`, fuera de rango y distancias decimales.
- Mediana de tres lecturas y recuperación de filtrado después de `SIN_ECO`.
- `REGISTRO`, `LECTURA`, `RECIBIDO`, `ORDEN`, `APLICADO` y mensajes `ERROR`.
- Recepción fragmentada o concatenada; control del límite de 128 bytes.
- Concurrencia real entre dos conexiones y presencia de los hilos supervisor/aceptador.
- Inactividad del sensor y apagado lógico del actuador, pérdida de socket, reconexión, reemplazo de rol y uso del estado más reciente.
- Confirmación incorrecta o ausente, roles no autorizados y secuencias repetidas.

Las pruebas de inactividad utilizan tiempos **reales acortados mediante configuración de prueba** para completar la suite rápidamente; la configuración de producción conserva **5 segundos**. No se certifica un error de tiempo de 0 ms por haberlas superado.

## 4. Qué validan las pruebas C++

El programa nativo (`pruebas/nativo_compilador/test_componentes.cpp`) prueba el parser de mensajes, detección de argumentos repetidos, enteros de 32 bits, conversión de eco a centímetros, ausencia de eco, rechazo fuera del rango representable, selección exclusiva de colores y apagado.

Se compila el código C++ real contra dobles locales de las funciones de Arduino, sin simular las salidas de una compilación para ESP32. La verificación de sintaxis de `main.cpp` de ambas placas es independiente de la prueba física del hardware. El test Unity original se conserva como un ensayo adicional reproducible con PlatformIO.

## 5. Cómo reproducir en las laptops

Desde la raíz del repositorio, con Python 3.11 o posterior:

```powershell
python -B pruebas/validar_software.py
```

Este comando guarda registros bajo `documentacion/evidencias/hilos/` y produce `resumen.json`. Para pruebas individuales:

```powershell
python -B -m unittest discover -s pruebas -p "test_*.py" -v
pio test -e native
pio run -e esp32_sensor
pio run -e esp32_actuador
python -m servidor --direccion 0.0.0.0 --puerto 5000
```

Para Ncat (si está instalado):

```powershell
python -B pruebas/verificar_ncat.py --ncat "C:\RUTA\ncat.exe"
```

El validador verifica si está disponible Ncat y ejecuta el escenario automáticamente; su salida debe guardarse **después** de probar el nuevo servidor por hilos.

## 6. Verificaciones físicas pendientes

| Propiedad | Objetivo declarado | Cómo documentarla |
|---|---|---|
| Integración real | Sensor→servidor→actuador por TCP Wi-Fi | Fotografía general, monitores serie y registro JSONL con identificadores y horas |
| Exactitud | Error máximo ≤ 3 cm entre 2 y 30 cm | Al menos cinco medidas por punto, referencia con cinta métrica y error absoluto sin signo |
| Estabilidad | Operación continua ≥ 10 minutos | Inicio/fin, registros originales, conteo de lecturas y ausencia de reinicios |
| Muestreo | ≥ 2 lecturas/s | Diferencias de tiempos del sensor y recepciones del servidor |
| Respuesta extremo a extremo | ≤ 1 s como referencia | Video de 60 fps o instrumentos sincronizados; no usar `APLICADO` como equivalente a LED físico |
| Tolerancia a fallos | Apagado y recuperación controlada | Desconectar sensor/actuador/laptop e identificar plazos y estados observados |

Los requisitos y métricas definitivos deben coincidir con la consigna del docente. No se transfieren cifras experimentales de la Práctica 1 a esta nueva implementación.

## 7. Trazabilidad del requisito al código

| Requisito | Código | Prueba disponible |
|---|---|---|
| RF1 Medición HC-SR04 | [SensorUltrasonico](../firmware/src/sensor/SensorUltrasonico.cpp) | Verificación C++ con eco simulado; falta ensayo físico |
| RF2 Tres rangos | [ControlDistancia](../servidor/control.py) | `test_control.py`, integración TCP |
| RF3 Actuar según distancia | [IndicadorLeds](../firmware/src/actuador/IndicadorLeds.cpp) | Prueba de GPIO simulado y `ORDEN`/`APLICADO` |
| RF4 Sockets TCP/Wi-Fi | [ServidorTcp](../servidor/servidor.py), [ClienteTcp](../comun/ClienteTcp.h) | `test_integracion.py` TCP local; falta Wi-Fi físico con versión nueva |

## 8. Evidencia histórica

Los archivos bajo `documentacion/evidencias/software/` pertenecen a ejecuciones anteriores. No se deben citar como prueba de que la versión con hilos y único PlatformIO se ejecutó físicamente o compiló para ESP32. Se conservaron para trazabilidad, y los nuevos resultados están separados en `evidencias/hilos/`.
