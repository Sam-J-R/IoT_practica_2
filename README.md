# Práctica 2 — Integración de Objetos Inteligentes con TCP/IP

Sistema distribuido de Internet de las Cosas (IoT) basado en la arquitectura cliente-servidor sobre la suite de protocolos TCP/IP y red Wi-Fi IEEE 802.11. Dos microcontroladores **DOIT ESP32 DevKit v1** desacoplan las funciones de sensado ultrasónico y actuación lumínica bajo el mando coordinado de un servidor central multihilo implementado en Python.

---

## Información del Proyecto

- **Asignatura:** Internet de las Cosas (SIS-234) — Semestre 2-2026.
- **Institución:** Universidad Católica Boliviana "San Pablo".
- **Equipo de desarrollo:**
  - María Jesús Lozada Peralta (Arquitectura de servidor TCP, concurrencia y protocolo).
  - Samuel Jarro Rodriguez (Firmware embebido en C++, PlatformIO y pruebas Unity).
  - Katherine Montaño Mejia (Montaje de prototipo físico, ensayos experimentales y reporte técnico).
- **Documentación principal:**
  - [Informe Técnico Oficial](INFORME_TECNICO.md) (cumplimiento de rúbrica, análisis, mediciones físicas y evidencias).
  - [Protocolo de Aplicación](protocolo.md) (especificación formal de mensajes, gramática y diagramas de flujo).

---

## Arquitectura y Lógica de Funcionamiento

```text
+--------------------------+          Wi-Fi (TCP:5000)          +--------------------------+
|       ESP32 SENSOR       | ---------------------------------> |   SERVIDOR CENTRAL PC    |
| - Transductor HC-SR04    |      LECTURA <sec> <dist> <t>      | - Python 3.11+           |
| - Trigger: GPIO 14       | <--------------------------------- | - Multihilo (RLock)      |
| - Echo:    GPIO 27       |          RECIBIDO <sec>            | - Filtro de mediana (N=3)|
+--------------------------+                                    | - Supervisor (25 ms)     |
                                                                | - Registro JSONL         |
+--------------------------+          Wi-Fi (TCP:5000)          +--------------------------+
|      ESP32 ACTUADOR      | <---------------------------------              |
| - LED Rojo:     GPIO 33  |          ORDEN <sec> <color>                    |
| - LED Amarillo: GPIO 25  | --------------------------------->              |
| - LED Verde:    GPIO 26  |          APLICADO <sec>                         |
| - Fail-safe:    3 s      |                                                 |
+--------------------------+                                                 v
                                                                [registros/ensayo.jsonl]
```

### Rangos de Control Operativo
La lógica de control centralizada procesa la distancia utilizando un **filtro de mediana móvil de 3 muestras** para filtrar perturbaciones transitorias:

| Rango de Distancia | Estado LED | Pin GPIO Activo | Comportamiento |
|---|:---:|:---:|---|
| $2 \text{ cm} \le d \le 10 \text{ cm}$ | **ROJO** | GPIO 33 | LED Rojo encendido (alarma de proximidad crítica). |
| $10 \text{ cm} < d \le 20 \text{ cm}$ | **AMARILLO** | GPIO 25 | LED Amarillo encendido (zona intermedia de precaución). |
| $20 \text{ cm} < d \le 30 \text{ cm}$ | **VERDE** | GPIO 26 | LED Verde encendido (zona libre / distancia segura). |
| $d < 2 \text{ cm}$, $d > 30 \text{ cm}$ o `SIN_ECO` | **APAGADO** | Ninguno | Todos los LEDs apagados (fuera de alcance o zona ciega). |

### Conexiones de Hardware

- **Objeto Sensor (ESP32 DevKit v1):**
  - `VCC` → 5 V (Pin VIN / 5V del ESP32).
  - `GND` → GND común.
  - `Trigger` → GPIO 14.
  - `Echo` → GPIO 27 (conexión directa en banco; se recomienda divisor resistivo para despliegues permanentes).
- **Objeto Actuador (ESP32 DevKit v1):**
  - `LED Rojo` → Ánodo a resistencia limitadora de 220 Ω en serie con GPIO 33; cátodo a GND común.
  - `LED Amarillo` → Ánodo a resistencia limitadora de 220 Ω en serie con GPIO 25; cátodo a GND común.
  - `LED Verde` → Ánodo a resistencia limitadora de 220 Ω en serie con GPIO 26; cátodo a GND común.

---

## Estructura del Repositorio

```text
IoT_practica_2/
├── platformio.ini                 # Configuración de entornos PlatformIO (sensor, actuador, native)
├── comun/                        # Código C++ compartido entre firmwares
│   ├── ClienteTcp.h              # Cliente socket TCP no bloqueante con reconexión
│   ├── ProtocoloAplicacion.h     # Parser de tramas y serialización de mensajes
│   └── ConfiguracionRedEjemplo.h # Plantilla de configuración Wi-Fi y servidor
├── firmware/
│   ├── include/
│   │   ├── sensor/SensorUltrasonico.h  # Interfaz del controlador del transductor HC-SR04
│   │   └── actuador/IndicadorLeds.h    # Interfaz del controlador de LEDs con exclusión mutua
│   └── src/
│       ├── sensor/
│       │   ├── SensorUltrasonico.cpp   # Disparo Trigger, medición con pulseIn y timeout
│       │   └── main.cpp                # Bucle no bloqueante y ciclo de vida del sensor
│       └── actuador/
│           ├── IndicadorLeds.cpp       # Conmutación de pines GPIO y apagado total
│           └── main.cpp                # Bucle no bloqueante, recepción y fail-safe de 3 s
├── servidor/                     # Servidor central TCP en Python
│   ├── __main__.py               # Punto de entrada de línea de comandos CLI
│   ├── servidor.py               # Servidor concurrente multihilo (lectores, escritores, supervisor)
│   ├── control.py                # Ventana deslizante, filtro de mediana y mapeo de estados
│   ├── protocolo.py              # Validación estricta de tramas, sintaxis y 14 códigos de error
│   └── registro.py               # Escritura asíncrona de eventos en consola y archivo JSONL
├── pruebas/                      # Suites automatizadas de verificación y análisis
│   ├── test_control.py           # Pruebas unitarias de rangos, fronteras y filtro de mediana
│   ├── test_protocolo.py         # Pruebas unitarias de sintaxis, fragmentación y CRLF
│   ├── test_integracion.py       # Pruebas de integración sobre sockets TCP en localhost
│   ├── test_registro.py          # Pruebas de concurrencia y tolerancia a fallos de I/O en disco
│   ├── test_robustez_servidor.py # Pruebas de timeouts, excepciones de hilos y apagado prioritario
│   ├── test_analizar_registro.py # Pruebas del analizador de sesiones y métricas JSONL
│   ├── analizar_registro.py      # Herramienta CLI de cálculo de frecuencias y estadísticas
│   ├── validar_software.py       # Validador integral automático del software
│   ├── dobles/                   # Mocks para compilación cruzada en Unity (Arduino, lwIP)
│   └── unity/                    # Pruebas unitarias nativas C++ para firmwares
│       ├── test_componentes/     # Pruebas del parser y componentes lógicos
│       ├── test_sensor/          # Pruebas del cliente sensor con dobles de red
│       └── test_actuador/        # Pruebas del cliente actuador y temporizador fail-safe
├── documentacion/
│   ├── diagramas/informe/        # Esquemas eléctricos vectoriales SVG (sensor y actuador)
│   ├── fotografias/              # Fotografías del prototipo físico en los 5 rangos de ensayo
│   └── evidencias/esenciales/    # Salidas consolidadas y hashes SHA-256 de las ejecuciones
├── protocolo.md                  # Especificación formal del protocolo de aplicación
├── INFORME_TECNICO.md            # Informe técnico oficial del proyecto (conforme a rúbrica)
└── README.md                     # Guía de puesta en marcha, comandos y arquitectura
```

---

## Guía de Puesta en Marcha y Comandos

### 1. Configuración de Red Wi-Fi y Servidor
Copiar la plantilla de configuración e ingresar el SSID, la contraseña de la red Wi-Fi local y la dirección IPv4 de la computadora donde corre el servidor:

```powershell
# En Windows PowerShell:
Copy-Item comun/ConfiguracionRedEjemplo.h comun/ConfiguracionRed.h
```

Editar `comun/ConfiguracionRed.h`:
```cpp
const char* const RED_WIFI_SSID = "Tu_Red_WiFi";
const char* const RED_WIFI_CLAVE = "Tu_Contraseña";
const char* const SERVIDOR_HOST = "192.168.1.X"; // IPv4 de la laptop (consultar con ipconfig)
const uint16_t SERVIDOR_PUERTO = 5000;
```
*(Este archivo está excluido en `.gitignore` para no versionar contraseñas).*

---

### 2. Ejecutar el Servidor TCP (Python)
Requiere Python 3.11 o posterior. Se puede ejecutar con `python` o con el lanzador `py` en Windows:

```powershell
# Iniciar servidor en el puerto 5000 con registro asíncrono en JSONL:
python -m servidor --direccion 0.0.0.0 --puerto 5000 --registro registros/ensayo.jsonl

# En entornos Windows con lanzador 'py':
py -m servidor --direccion 0.0.0.0 --puerto 5000 --registro registros/ensayo.jsonl
```

---

### 3. Compilar y Cargar el Firmware a las Placas ESP32
Desde la raíz del repositorio, utilizando PlatformIO CLI:

```powershell
# Compilación de ambos firmwares:
pio run -e esp32_sensor
pio run -e esp32_actuador

# Carga (flashing) a los microcontroladores (sustituir por los puertos COM reales de cada placa):
pio run -e esp32_sensor -t upload --upload-port COM3
pio run -e esp32_actuador -t upload --upload-port COM4

# Monitor serie para diagnóstico (a 115200 baudios):
pio device monitor -p COM3 -b 115200
pio device monitor -p COM4 -b 115200
```

---

### 4. Ejecución de Pruebas Automatizadas

#### Batería de pruebas Python (27 pruebas unitarias y de integración):
```powershell
python -B -m unittest discover -s pruebas -p "test_*.py" -v
# o en Windows:
py -B -m unittest discover -s pruebas -p "test_*.py" -v
```

#### Batería de pruebas nativas en Unity C++ (17 pruebas de firmware):
```powershell
pio test -e native
```

#### Validación integral consolidada de software:
```powershell
python -B pruebas/validar_software.py
# o en Windows:
py -B pruebas/validar_software.py
```

#### Análisis y auditoría del archivo de registro JSONL:
```powershell
python -B pruebas/analizar_registro.py registros/ensayo.jsonl
# o en Windows:
py -B pruebas/analizar_registro.py registros/ensayo.jsonl
```

---

## Resultados Destacados del Prototipo Físico

- **Exactitud experimental:** Error absoluto máximo de **0,28 cm** en el rango de 2 a 30 cm (promedio de 0,17 cm), superando con creces la tolerancia de $\le 3\text{ cm}$.
- **Tiempo de respuesta:** Latencia total extremo a extremo de sensado a conmutación de LED **< 400 ms** (meta $\le 1\text{ s}$).
- **Frecuencia de recepción efectiva:** **$\ge 8,5\text{ lecturas/s}$** válidas recibidas y procesadas en el servidor central (meta $\ge 2\text{ lecturas/s}$).
- **Estabilidad sostenida:** Operación continua de 15 minutos en banco sin reinicios, caídas de socket ni acumulación de memoria.
- **Seguridad y tolerancia a fallos:** Apagado autónomo a los 3 s en actuador ante contingencias de red y prioridad inmediata para la orden `APAGADO`.
