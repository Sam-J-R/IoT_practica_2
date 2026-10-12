# Plan final — Integración de Objetos Inteligentes con TCP/IP

Estado: implementación del servidor y ambos ESP32 completada; pruebas de software y compilaciones aprobadas. Ncat 7.991 instalado y sus verificaciones aprobadas. Validaciones físicas pendientes. Ver [estado y evidencias](documentacion/VALIDACION.md). Fecha de actualización: 11 de octubre de 2026.

## 1. Alcance y orden de trabajo

Construir un sistema con dos ESP32 y un servidor TCP en Python. El primer ESP32 mide con un HC-SR04; la PC procesa y clasifica las lecturas; el segundo ESP32 controla tres LEDs. Ambos ESP32 inician conexiones TCP persistentes hacia la PC.

Primero se completará y verificará el código. Los otros integrantes elaborarán el informe a partir de la implementación; después se revisarán su coherencia, diagramas y evidencias. La especificación del protocolo y las instrucciones de ejecución se actualizarán junto con el código.

- ESP32: Arduino C++ con PlatformIO y placas DOIT ESP32 DevKit v1.
- Servidor: Python con consola y registros, sin interfaz gráfica.
- Red prevista: punto de acceso de un celular en 2,4 GHz. Verificar comunicación entre los clientes y la PC; si existe aislamiento, utilizar un router de laboratorio prestado.
- Español en identificadores propios, comentarios, mensajes y documentación. Conservar identificadores obligatorios de lenguajes y bibliotecas.
- No utilizar BMAD ni incorporar sus archivos al repositorio.
- Aprovechar las adaptaciones existentes, corrigiendo incompatibilidades y recuperando la organización en clases. No trasladar resultados anteriores como resultados de esta práctica.

## 2. Dos proyectos PlatformIO dentro de un repositorio

Un repositorio Git contiene todo el trabajo. Cada proyecto PlatformIO es una subcarpeta con su propio `platformio.ini`, código y configuración. La siguiente es la estructura base implementada; se añadió `comun/` para las cabeceras de comunicación compartidas y las pruebas se centralizaron en `pruebas/`:

```text
IoT_practica_2/
├── .git/                       # Único repositorio Git existente
├── .gitignore
├── README.md
├── PLAN.md
├── protocolo.md
├── sensor/                     # Proyecto PlatformIO del sensor
│   ├── platformio.ini
│   ├── include/
│   ├── src/
│   │   └── main.cpp
├── actuador/                   # Proyecto PlatformIO del actuador
│   ├── platformio.ini
│   ├── include/
│   ├── src/
│   │   └── main.cpp
├── comun/                      # TCP, analizador y configuración compartida
├── servidor/                   # Programa Python; no es un proyecto PlatformIO
│   ├── control.py              # Parámetros, filtro y rangos
│   ├── protocolo.py            # Formato y validación de mensajes
│   └── servidor.py             # Sesiones, órdenes y registros
├── pruebas/                    # Pruebas del servidor y de integración
└── documentacion/              # Informe, diagramas y evidencias posteriores
```

El servidor anterior de `server/server.py` se sustituyó por los módulos de `servidor/`; su versión original sigue disponible en el historial Git. No se crearon repositorios internos ni submódulos. La versión comprobada de la plataforma quedó fijada en `espressif32@7.0.1`.

Ambos archivos `platformio.ini` partirán de esta configuración:

```ini
[env:esp32doit-devkit-v1]
platform = espressif32
board = esp32doit-devkit-v1
framework = arduino
monitor_speed = 115200
```

El mismo nombre de entorno puede utilizarse en ambos proyectos: están en directorios independientes. Durante la implementación se fijará la versión de la plataforma después de comprobar la compilación, para reproducirla.

Se podrá abrir cada carpeta de proyecto por separado en Visual Studio Code. Desde una terminal con PlatformIO disponible, situada en la raíz del repositorio, estos serán los comandos de compilación:

```powershell
pio run --project-dir sensor
pio run --project-dir actuador
```

Para cargar cada programa se elegirá explícitamente el puerto de su ESP32. COM5 y COM6 son solo ejemplos y deberán reemplazarse por los puertos reales, consultables con `pio device list`:

```powershell
pio run --project-dir sensor --target upload --upload-port COM5
pio run --project-dir actuador --target upload --upload-port COM6
```

Cada proyecto generará su propia carpeta `.pio/`. Se excluirán de Git los archivos de compilación, entornos Python y configuraciones con contraseñas. Se versionarán ejemplos de configuración sin credenciales.

Referencia: [selección de proyecto y puerto en PlatformIO](https://docs.platformio.org/en/latest/core/userguide/cmd_run.html).

## 3. Control, adquisición y circuitos

El sensor intentará medir cada **100 ms**, con espera máxima de eco de **30 ms**. Enviará distancias y avisos explícitos de ausencia de eco. Para una velocidad de sonido de 343 m/s, la conversión será `0.01715` cm/µs; cualquier calibración posterior deberá sustentarse en mediciones.

El servidor validará las lecturas, aplicará la mediana de tres mediciones válidas consecutivas y clasificará el resultado:

| Distancia | Actuación |
|---|---|
| 2 ≤ d ≤ 10 cm | Rojo fijo |
| 10 < d ≤ 20 cm | Amarillo fijo |
| 20 < d ≤ 30 cm | Verde fijo |
| Fuera de 2–30 cm o sin eco | Todos apagados |

Una lectura inválida provocará el apagado solicitado y vaciará el filtro. La indicación se reanudará después de tres lecturas válidas. Se retirarán los parpadeos del borrador actual del protocolo. Rechazar valores menores de 2 cm no garantiza detectar físicamente todos los objetos dentro de la zona ciega del sensor.

- Sensor: GPIO 14 para disparo, GPIO 27 para eco; divisor de 1 kΩ entre ECHO y GPIO 27 y 2 kΩ entre GPIO 27 y tierra.
- Actuador: GPIO 33, 25 y 26 para rojo, amarillo y verde; una resistencia de 220 Ω por LED.
- Apagar primero todos los LEDs y después activar el seleccionado.
- Alimentación USB de cada placa; documentar alimentación, polaridades y tierra de cada circuito.
- Elaborar posteriormente un esquema eléctrico por objeto, coherente con el montaje verificado.

La clasificación se realizará exclusivamente en Python. Las clases previstas son `SensorUltrasonico`, `IndicadorLeds` y `ClienteTcp` en los ESP32, y `ServidorTcp`, `SesionCliente`, `ProtocoloAplicacion`, `ControlDistancia` y `RegistroPruebas` en Python. El servidor utilizará `socket` y `select`, con búferes de entrada y salida, sin bloqueos indefinidos. Los umbrales se centralizarán en su configuración.

## 4. Protocolo definitivo

Conservar la base del protocolo existente: texto ASCII, argumentos `clave=valor` separados por comas y mensajes terminados en salto de línea. Esta decisión sustituye la propuesta inicial de campos separados por `|`.

| Mensaje de ejemplo | Función |
|---|---|
| `REGISTRO tipo=sensor, version=1` | Identificar al sensor |
| `REGISTRO tipo=actuador, version=1` | Identificar al actuador |
| `ACEPTADO REGISTRO` | Confirmar el registro |
| `LECTURA numero=42, tiempo_ms=12500, distancia_cm=15.20` | Enviar una medición |
| `LECTURA numero=43, tiempo_ms=12600, distancia_cm=SIN_ECO` | Informar ausencia de eco |
| `RECIBIDO numero=42` | Confirmar recepción de una lectura |
| `ORDEN numero=81, estado=AMARILLO` | Solicitar una salida |
| `APLICADO numero=81` | Confirmar la actualización de los pines |
| `ERROR codigo=FORMATO` | Rechazar un mensaje |

Las salidas permitidas serán `ROJO`, `AMARILLO`, `VERDE` y `APAGADO`. El servidor escuchará en el puerto configurable 5000; su dirección se configurará en ambos ESP32.

- Mantener el límite de **128 bytes por mensaje**, incluido el terminador.
- Emitir `\n` y aceptar `\n` o `\r\n`; emitir coma y espacio entre argumentos y aceptar coma con o sin ese espacio.
- Reconstruir mensajes fragmentados y procesar varias líneas recibidas juntas.
- Validar campos obligatorios, duplicados, valores, versión y permisos del rol.
- Aceptar decimales finitos sin redondear a centímetros enteros.
- Cerrar la conexión ante mensajes malformados o excesivos y registrar el motivo.
- Exigir registro dentro de tres segundos desde la conexión.
- Procesar confirmaciones como respuestas: no responder a una confirmación con otra confirmación.
- Numerar lecturas y órdenes de forma creciente dentro de cada sesión; reiniciar contadores y descartar datos pendientes al reconectar.
- Actualizar conjuntamente los tres programas y `protocolo.md`; no mantener compatibilidad con los mensajes antiguos.

## 5. Inactividad, confirmaciones y reconexión

### Sensor inactivo durante 5 segundos

Contar desde la última `LECTURA` correctamente formada del sensor registrado. Una lectura `SIN_ECO` demuestra actividad, aunque obliga al apagado. Al registrar una nueva sesión, iniciar el plazo de espera de la primera lectura.

Si transcurren **5 segundos sin lecturas**, invalidar el estado, vaciar el filtro, cerrar la conexión del sensor y solicitar el apagado. Ante un cierre TCP detectado, realizar estas acciones inmediatamente.

### Confirmaciones del actuador

- Enviar `APLICADO` después de actualizar los pines; la confirmación de software no constituye prueba óptica del LED.
- Mantener como máximo una orden pendiente por conexión y esperar su confirmación durante **1 segundo**.
- Mientras exista una orden pendiente, conservar únicamente el último estado deseado; las lecturas inválidas o la pérdida del sensor lo sustituyen por `APAGADO`.
- Si falta la confirmación, cerrar la conexión del actuador y registrar el fallo.
- Enviar los cambios de estado cuando no exista una orden pendiente y reenviar el estado vigente cada **1 segundo**.
- El actuador se apagará localmente tras **3 segundos sin órdenes válidas**, aunque TCP todavía parezca conectado, y de inmediato al detectar desconexión.

### Reconexión

- Reintentar WiFi/TCP cada **2 segundos**, con intentos limitados en tiempo que permitan atender los temporizadores.
- Volver a registrar el rol después de cada conexión TCP y esperar su aceptación antes del intercambio normal.
- Vaciar búferes, contadores de sesión y confirmaciones pendientes al desconectar.
- Si un cliente nuevo registra un rol ocupado, cerrar y reemplazar la conexión anterior. La limpieza de la sesión antigua no deberá borrar la nueva.
- Al registrar el actuador, enviar el último estado vigente; si no hay una lectura vigente, enviar `APAGADO`.

## 6. Implementación y verificación

1. Actualizar el protocolo: mensajes, límites, temporizadores, errores y ejemplos.
2. Implementar el servidor: clases, validación, control, sesiones y registros.
3. Implementar el sensor: medición periódica, errores de lectura, recepción de respuestas y reconexión con registro.
4. Implementar el actuador: interpretación estricta, exclusión de LEDs, confirmaciones y apagado local.
5. Ejecutar pruebas automáticas: fronteras de 2, 10, 20 y 30 cm, filtro, datos incorrectos, mensajes fragmentados y concatenados, caducidad, confirmaciones y reemplazo de conexiones.
6. Compilar ambos proyectos PlatformIO y realizar la integración física.

### Pruebas con Ncat

Ejecutadas con Ncat 7.991 real el 11 de octubre de 2026; consultar [salida y evidencias](documentacion/VALIDACION.md).

Utilizar Ncat para simular conexiones y comprobar registro, distancias decimales, ausencia de eco, órdenes, confirmaciones con su número, ausencia de confirmación, sensor inactivo durante cinco segundos, desconexión, nuevo registro, reemplazo de sesiones y mensajes incorrectos.

Los casos con plazos cortos utilizarán secuencias automatizadas para no depender de la velocidad de escritura manual. Conservar entradas y salidas como evidencia. Ncat verificará el intercambio TCP; las placas reales deberán demostrar medición y actuación física.

## 7. Evidencias, informe y aceptación

Registrar conexiones, lecturas originales y filtradas, órdenes, confirmaciones, desconexiones y errores. Relacionar cada requerimiento con su componente, prueba, evidencia y resultado.

| Atributo | Criterio y verificación |
|---|---|
| Estabilidad | 15 minutos sin reinicios ni bloqueos, con registro completo de sesiones y lecturas. |
| Exactitud | Error absoluto máximo de 3 cm entre 2 y 30 cm; 10 lecturas por punto a 2, 5, 10, 15, 20, 25 y 30 cm. Calcular promedio, dispersión y máximo error absoluto. |
| Muestreo | Al menos 2 lecturas válidas/s en condiciones normales; distinguir intentos, lecturas válidas y mensajes recibidos. |
| Respuesta | Hasta 1 segundo de extremo a extremo, incluyendo adquisición, filtro, procesamiento y actuación. Verificar al menos 20 cambios de rango en ambos sentidos. |

La disponibilidad del instrumento de respuesta física sigue pendiente. Método previsto: video de al menos 60 cuadros/s mostrando obstáculo, referencia de distancia y LEDs; contar cuadros y documentar incertidumbre. No sustituirlo por estimaciones ni por tiempos medidos únicamente en la PC; no restar relojes distintos sin sincronización.

Con el código comprobado, los demás integrantes elaborarán el informe Markdown con las ocho secciones exigidas. Después revisar código, diagramas, enlaces relativos, trazabilidad, evidencias y conclusiones. Distribuir el trabajo entre sensor y circuito, servidor y protocolo, y actuador e integración; realizar revisión cruzada y conservar aportes identificables en Git.

La entrega estará completa cuando la implementación cumpla el protocolo, supere las pruebas de software y físicas, y el informe describa lo realmente construido y verificado. Los resultados pendientes permanecerán identificados como pendientes.

## 8. Simplificación y guía de lectura

Se mantienen las decisiones de control, el protocolo y todos los tiempos. Los ESP32 usan tipos básicos y `String` para construir y leer mensajes. Se retiraron matrices de caracteres, tipos de ancho fijo y conversiones especiales del código propio de las placas. Python usa clases comunes, textos para los colores y una lista de tres distancias.

Las pruebas C++ se ejecutan con Unity mediante `pio test -e native` desde la raíz, usando el `platformio.ini` dedicado a pruebas de PC. Los proyectos de las dos placas siguen siendo `sensor/` y `actuador/`. Las pruebas del servidor y los rangos se mantienen en Python, donde está la clasificación.

El README empieza con una tabla para encontrar cada responsabilidad y un ejemplo del recorrido de una lectura. No se deben modificar ni estudiar primero los simuladores de `pruebas/dobles/` para entender el prototipo.

Consultar [validación y comparación con la práctica 1](documentacion/VALIDACION.md). Las pruebas físicas y la revisión del informe siguen pendientes.
