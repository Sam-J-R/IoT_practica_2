# Práctica 2 — IoT distribuido con TCP y servidor con hilos

Dos placas **DOIT ESP32 DevKit v1** se conectan por Wi-Fi a un servidor Python en una laptop. El ESP32 sensor envía las distancias del HC-SR04 y el ESP32 actuador aplica los colores indicados por el servidor. El protocolo de aplicación propio utiliza mensajes en español.

## Estructura del proyecto

```text
IoT_practica_2/
├── platformio.ini                 # ÚNICO proyecto PlatformIO: dos entornos
├── firmware/
│   ├── src/sensor/               # Programa del ESP32 sensor
│   ├── src/actuador/             # Programa del ESP32 actuador
│   ├── include/sensor/
│   └── include/actuador/
├── comun/                        # Cliente TCP y parser compartidos por ambas placas
├── servidor/
│   ├── servidor.py               # Hilos de clientes y supervisión
│   ├── control.py                # Mediana y rangos
│   ├── protocolo.py              # Gramática del protocolo
│   ├── registro.py               # Registro asíncrono con cola acotada
│   └── __main__.py               # Entrada del programa
├── pruebas/                       # Python, Unity y C++ nativo
├── documentacion/
│   ├── ARQUITECTURA_HILOS.md
│   ├── VALIDACION.md
│   └── evidencias/hilos/          # Salidas auténticas de los ensayos
├── protocolo.md                  # Contrato oficial de mensajes
└── PLAN.md                       # Decisiones y actividades restantes
```

## Ejecutar el servidor Python

Requiere Python **3.11 o posterior**. Desde la raíz del repositorio:

```powershell
python -m servidor --direccion 0.0.0.0 --puerto 5000
```

El servidor crea un hilo para aceptar conexiones, uno para supervisar temporizadores, un lector y un escritor por conexión TCP, y un hilo independiente para los registros. La clase `ServidorTcp` utiliza un `threading.RLock` para proteger el estado compartido; la espera de red y la escritura de registros ocurren fuera de ese bloqueo. Los hilos de conexión se retiran al terminar. No se utiliza `select`.

## Configurar las dos placas

Copia `comun/ConfiguracionRedEjemplo.h` a `comun/ConfiguracionRed.h` e introduce el nombre/contraseña de la Wi-Fi y **la IPv4 actual de la laptop** (consultar con `ipconfig`). Este archivo está excluido de Git para no publicar claves. Las tres máquinas deben estar en la misma red y el firewall debe permitir el puerto TCP 5000.

Desde **la raíz** del repositorio:

```powershell
pio run -e esp32_sensor
pio run -e esp32_actuador
```

Para cargar el firmware a la placa correspondiente, después de verificar el puerto COM:

```powershell
pio run -e esp32_sensor -t upload --upload-port COM3
pio run -e esp32_actuador -t upload --upload-port COM4
```

Sustituye `COM3` y `COM4` por los puertos reales de cada placa. Cada entorno contiene solo el firmware que corresponde a esa placa.

## Hardware y control

- **Sensor:** HC-SR04 con `Trigger` en GPIO 14, `Echo` en GPIO 27 y divisor de nivel en Echo de 1 kΩ (superior) + 2 kΩ (inferior); alimentación y masa común. La salida teórica es ~3,33 V con entrada nominal de 5 V: está ligeramente por encima de 3,3 V, por lo que debe comprobarse la compatibilidad eléctrica/tolerancias. La versión de 1 kΩ + 1,8 kΩ tendría más margen.
- **Actuador:** LED rojo GPIO 33, amarillo GPIO 25, verde GPIO 26; una resistencia de 220 Ω en serie con cada LED.
- **Control:** rojo para `2 ≤ d ≤ 10 cm`, amarillo para `10 < d ≤ 20 cm`, verde para `20 < d ≤ 30 cm`. Fuera de `[2,30]` o `SIN_ECO`, todos apagados. La decisión utiliza mediana de las tres últimas lecturas válidas.

El sensor envía `LECTURA`, la PC responde `RECIBIDO`, el servidor envía `ORDEN` y el actuador confirma con `APLICADO`. Primero los clientes envían `REGISTRO`. Ver [protocolo.md](protocolo.md) para la gramática completa.

## Pruebas reproducibles

```powershell
python -B -m unittest discover -s pruebas -p "test_*.py" -v
python -B pruebas/validar_software.py
pio test -e native
```

El validador ejecuta la suite Python, Unity y las dos compilaciones, y guarda salidas y huellas SHA-256 en una carpeta por ejecución bajo [documentacion/evidencias/esenciales/](documentacion/evidencias/esenciales/). Si falta PlatformIO, deja constancia **NO EJECUTADO**. No necesita Ncat. Las pruebas automáticas protegen las funciones esenciales; en el informe se resumen por requisito, sin describir cada caso interno. La ejecución en PC no sustituye las mediciones físicas de exactitud, estabilidad o respuesta.

Documentos complementarios: [arquitectura](documentacion/ARQUITECTURA_HILOS.md), [validación](documentacion/VALIDACION.md), [plan](PLAN.md).
