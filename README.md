# Práctica 2 — Sensor, servidor TCP y LEDs

Un ESP32 mide la distancia y la envía por WiFi a la PC. El servidor Python decide el color. Otro ESP32 recibe la orden y enciende el LED. **Los rangos y los tiempos acordados se mantienen.**

## 1. Dónde buscar cada cosa

Empieza por los primeros tres archivos de esta tabla. No necesitas estudiar los simuladores de pruebas para entender el funcionamiento principal.

| Si quieres entender o cambiar… | Abre… | Busca… |
|---|---|---|
| Los rangos y la elección del color | [servidor/control.py](servidor/control.py) | `clasificar()`; `procesar()` aplica la mediana; `EstadoLed(StrEnum)`. |
| El funcionamiento del ESP32 sensor | [sensor/src/main.cpp](sensor/src/main.cpp) | `setup()` prepara; `loop()` recibe confirmaciones y envía lecturas. |
| El funcionamiento del ESP32 actuador | [actuador/src/main.cpp](actuador/src/main.cpp) | `recibirMensaje()` aplica la orden; `loop()` revisa conexión y apagado. |
| La medición ultrasónica | [sensor/include/SensorUltrasonico.h](sensor/include/SensorUltrasonico.h) y [.cpp](sensor/src/SensorUltrasonico.cpp) | Declaración y método `medir()`: disparo, eco y conversión a cm. |
| El encendido de los LEDs | [actuador/include/IndicadorLeds.h](actuador/include/IndicadorLeds.h) y [.cpp](actuador/src/IndicadorLeds.cpp) | Declaración y método `aplicar()`: apagar todos y encender el solicitado. |
| Cómo conectar ambos ESP32 | [comun/ConfiguracionRedEjemplo.h](comun/ConfiguracionRedEjemplo.h) | Nombre de red, clave, IP y puerto; copiar según el apartado 5. |
| La conexión y reconexión WiFi/TCP | [comun/ClienteTcp.h](comun/ClienteTcp.h) | `actualizar()`, `enviar()` y `recibirMensaje()`. |
| Cómo separar los campos de un mensaje en C++ | [comun/ProtocoloAplicacion.h](comun/ProtocoloAplicacion.h) | `interpretar()` y `obtener()`. |
| El intercambio en la PC | [servidor/servidor.py](servidor/servidor.py) | `_procesar()` recibe mensajes; `_solicitar_estado()` envía órdenes. |
| La validación de mensajes en Python | [servidor/protocolo.py](servidor/protocolo.py) | `interpretar()` revisa nombres, campos y valores. |
| **Las pruebas Unity** | [pruebas/unity/test_componentes/test_main.cpp](pruebas/unity/test_componentes/test_main.cpp) | Funciones `probar…`, `TEST_ASSERT…` y la lista `RUN_TEST`. |
| Las pruebas de rangos en Python | [pruebas/test_control.py](pruebas/test_control.py) | Distancias exactas y cercanas a 2, 10, 20 y 30 cm. |
| Qué se ha comprobado y qué falta | [documentacion/VALIDACION.md](documentacion/VALIDACION.md) | Resultados, evidencias y pruebas físicas pendientes. |

## 2. Seguir una lectura de principio a fin

Ejemplo: el objeto permanece a **15 cm**.

1. El `loop()` del sensor llama a `sensor.medir(distanciaCm)` cada 100 ms.
2. Forma un texto como `LECTURA numero=1, tiempo_ms=100, distancia_cm=15.00` y lo envía.
3. El servidor, en `_procesar()`, reconoce LECTURA, procesa la distancia y responde `RECIBIDO numero=1`.
4. `ControlDistancia.procesar()` espera tres lecturas válidas. Las ordena y toma la del medio: la mediana. Con 15, 15 y 15 resulta 15.
5. `clasificar(15)` devuelve el valor `EstadoLed.AMARILLO` (`"AMARILLO"`). El servidor envía `ORDEN numero=2, estado=AMARILLO` cuando no hay otra orden pendiente.
6. El actuador llama a `indicador.aplicar("AMARILLO")` y después envía `APLICADO numero=2`.

Los números de los ejemplos son ilustrativos. El registro y la orden inicial de apagado se explican en el [protocolo](protocolo.md), con sus diagramas.

| Distancia que clasifica la PC | Salida |
|---|---|
| 2 ≤ d ≤ 10 cm | Rojo fijo. |
| 10 < d ≤ 20 cm | Amarillo fijo. |
| 20 < d ≤ 30 cm | Verde fijo. |
| Fuera de 2–30 cm o SIN_ECO | Todos apagados; se vacía el filtro. |

## 3. Los tipos y las clases

En el C++ propio se utilizan `int` para pines y cantidades, `float` para centímetros, `bool` para respuestas sí/no y `unsigned long` para tiempos y números de mensajes. `String` representa texto y evita manipular matrices de caracteres. No es un tipo primitivo: es la clase habitual de texto de Arduino.

`String(numero)` convierte un número en texto; `String(distanciaCm, 2)` lo escribe con dos decimales. `indexOf()` busca una posición, `substring()` extrae una parte y `+` une textos. `millis()` devuelve milisegundos; `ahora - ultimoTiempo` permite comprobar un plazo sin detener el programa con `delay()`.

Una clase agrupa datos y acciones relacionados. Las clases de hardware (`SensorUltrasonico` e `IndicadorLeds`) separan su declaración en `.h` de su implementación en `.cpp`, siguiendo las buenas prácticas de programación en C++, e incluyen `comun/` de forma modular mediante banderas de compilación (`-I ../comun`).

El servidor usa una enumeración tipada (`StrEnum`) para los colores (`EstadoLed`) garantizando consistencia y validación estricta, y anotaciones de tipo (`type hints`) en todos sus módulos de Python para facilitar la comprensión y el análisis estático.

## 4. Dónde están y cómo ejecutar las pruebas Unity

Desde **la raíz del repositorio**, ejecutar:

```powershell
pio test -e native
```

`native` significa ejecutar en la **PC**, sin placas conectadas. La configuración está en el `platformio.ini` de la raíz; **no crea un tercer programa para un ESP32**. Los dos proyectos de las placas siguen en `sensor/` y `actuador/`.

| Carpeta Unity | Qué comprueba |
|---|---|
| [test_componentes](pruebas/unity/test_componentes/test_main.cpp) | Nueve pruebas de mensajes, números, medición simulada y exclusión de LEDs. Es el punto de entrada más sencillo. |
| [test_sensor](pruebas/unity/test_sensor/test_main.cpp) | Ejecuta el programa real del sensor con red y reloj simulados: confirmaciones, muestreo y reconexión. |
| [test_actuador](pruebas/unity/test_actuador/test_main.cpp) | Ejecuta el programa real del actuador con órdenes simuladas: actuación, confirmación, apagado y reconexión. |

Las dos últimas usan [comprobar_cliente.h](pruebas/unity/comprobar_cliente.h) para compartir el ensayo. `pruebas/dobles/` sustituye Arduino y WiFi solamente al probar en PC; las placas usan sus bibliotecas reales.

**Los rangos se prueban en Python**, porque ahora la decisión está en el servidor. Unity comprueba el C++ de las placas; no se duplicó la clasificación en C++.

```powershell
python -B -m unittest discover -s pruebas -v
python -B pruebas/verificar_ncat.py
```

Para ejecutar todas las comprobaciones y guardar sus salidas:

```powershell
python -B pruebas/validar_software.py
```

Se utiliza Ncat 7.991 instalado localmente en `.herramientas/ncat/`. El guion lo encuentra allí o en el PATH; también acepta `--ncat RUTA`. Los binarios no se incluyen en Git. [Origen y firma de instalación](documentacion/evidencias/software/instalacion_ncat.json).

## 5. Configurar y ejecutar el prototipo

Crear la configuración privada compartida:

```powershell
Copy-Item comun/ConfiguracionRedEjemplo.h comun/ConfiguracionRed.h
```

Completar nombre de red, contraseña e IPv4 de la PC. `ConfiguracionRed.h` está excluido de Git. Sin él se usan datos de ejemplo. Para más mensajes por el monitor serie, poner `depuracionActiva = true` y volver a cargar ambos ESP32.

```powershell
python -m servidor --puerto 5000 --registro registros/ejecucion.jsonl
pio run --project-dir sensor
pio run --project-dir actuador
pio device list
```

Cargar cada proyecto con `pio run --project-dir sensor --target upload --upload-port COM5`, usando el proyecto y puerto correctos. Abrir el monitor con `pio device monitor --port COM5 --baud 115200`. COM5 es solo un ejemplo; cerrar el monitor antes de cargar.

| Circuito | Conexiones |
|---|---|
| Sensor | Disparo GPIO 14; ECHO → 1 kΩ → nodo GPIO 27 → 2 kΩ → GND. VCC a 5 V y tierra común con su placa. |
| Actuador | GPIO 33 rojo, 25 amarillo, 26 verde; resistencia de 220 Ω por LED y cátodos a GND. |

Usar WiFi de 2,4 GHz que permita comunicación entre los equipos. No conectar ECHO de 5 V directamente al GPIO. Las placas se alimentan por USB; la comunicación entre ellas pasa por la PC.

Se mantienen: sensor inactivo 5 s; confirmación del actuador 1 s; apagado local sin órdenes 3 s; reconexión cada 2 s; registro 3 s y refresco de órdenes 1 s. La única llamada de envío TCP de bajo nivel está encapsulada en `ClienteTcp::enviarPendientes()` para que una red bloqueada no detenga esos plazos.

El [protocolo](protocolo.md), el [plan](PLAN.md) y la [validación](documentacion/VALIDACION.md) completan la documentación. Las mediciones físicas y el informe del equipo siguen pendientes.
