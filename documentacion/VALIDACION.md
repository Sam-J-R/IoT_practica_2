# Estado de validación

Validación de software realizada el **11 de octubre de 2026**. Las salidas originales están en [evidencias/software/](evidencias/software/); el [resumen JSON](evidencias/software/resumen.json) identifica los comandos y sus códigos de salida. Los datos de esta carpeta corresponden a software y clientes simulados, sin placas conectadas.

## 1. Comprobaciones ejecutadas

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Python: lógica, protocolo e integración | **23 pruebas aprobadas**. | [Salida completa](evidencias/software/pruebas_python.txt) |
| TCP real en localhost | Registro, decimales, estados, confirmaciones, fragmentación, roles, reemplazo y reconexión comprobados por las pruebas de integración. | [Casos](../pruebas/test_integracion.py) y salida Python |
| Plazo de inactividad de cinco segundos | Verificado a ambos lados del límite con reloj controlado y sockets reales. No es un ensayo físico de cinco segundos de WiFi. | `test_inactividad_exactamente_cinco_segundos` |
| Unity en PC | **11 pruebas aprobadas**: nueve de componentes y una de cada programa real con red/reloj simulados. | [Salida](evidencias/software/pruebas_unity.txt), [casos sencillos](../pruebas/unity/test_componentes/test_main.cpp), [ensayo de programas](../pruebas/unity/comprobar_cliente.h) |
| Compilación del sensor ESP32 | **Correcta**, con espressif32 7.0.1 y Arduino. | [Salida original](evidencias/software/compilacion_sensor.txt) |
| Compilación del actuador ESP32 | **Correcta**, con espressif32 7.0.1 y Arduino. | [Salida original](evidencias/software/compilacion_actuador.txt) |
| Ncat 7.991 real | **Aprobado**: registro, tres rangos, SIN_ECO, inactividad de cinco segundos reales, reconexión, reemplazo, falta de confirmación, confirmación incorrecta, secuencia repetida y longitud excesiva. | [Salida](evidencias/software/pruebas_ncat.txt), [eventos originales](evidencias/software/sesiones_ncat.jsonl), [guion](../pruebas/verificar_ncat.py) |

La [instalación local de Ncat](evidencias/software/instalacion_ncat.json) conserva origen oficial, versión, firma válida y huellas del instalador y ejecutable. Los binarios están en `.herramientas/ncat/`, excluidos de Git. El plazo real medido por el guion aparece en su salida; no mide latencia física sobre WiFi.

Las pruebas de Python verifican que `APLICADO` no genera una nueva confirmación, que solo hay una orden pendiente, que no se acumulan estados anteriores y que `SIN_ECO` comunica actividad mientras fuerza apagado. Los dobles C++ comprueban el orden de las escrituras de GPIO; no demuestran iluminación física ni medición acústica.

La compilación no implica que el programa ya se haya cargado en las placas. Utiliza valores de red de ejemplo hasta crear el archivo compartido `comun/ConfiguracionRed.h`.

## 2. Trazabilidad del código

| Requisito | Implementación | Comprobación disponible | Verificación física pendiente |
|---|---|---|---|
| RF1: distancia | [SensorUltrasonico](../sensor/include/SensorUltrasonico.h) | Conversión y ausencia de eco con doble C++. | Lectura real frente a cinta métrica. |
| RF2: tres rangos contiguos | [ControlDistancia](../servidor/control.py) | Fronteras de 2, 10, 20 y 30 cm y filtro. | Recorrido con obstáculo real. |
| RF3: actuación distinta | [IndicadorLeds](../actuador/include/IndicadorLeds.h) y órdenes del servidor | GPIO simulados y estados TCP. | Tres colores, apagado y transiciones reales. |
| RF4: sockets TCP sobre WiFi | [ServidorTcp](../servidor/servidor.py), [ClienteTcp](../comun/ClienteTcp.h), [protocolo](../protocolo.md) | TCP local real y compilación de ambos clientes. | Red de celular y comunicación entre las placas y la PC. |

## 3. Validaciones de laboratorio pendientes

| Atributo | Objetivo | Procedimiento |
|---|---|---|
| Estabilidad | 15 minutos sin reinicios ni bloqueos. | Guardar JSONL completo y monitores serie de ambas placas, con inicio, fin y número de lecturas. Una sesión TCP nueva por sí sola no permite distinguir reinicio de desconexión. |
| Exactitud | Máximo error absoluto de 3 cm entre 2 y 30 cm. | Diez lecturas por punto a 2, 5, 10, 15, 20, 25 y 30 cm; registrar referencia, datos originales, promedio, dispersión y máximo error. |
| Muestreo | Al menos dos lecturas válidas/s en condiciones normales. | Usar tiempos y números del sensor, distinguir intentos de lecturas válidas y comparar con recepción en PC. |
| Respuesta física | Hasta un segundo en 20 cambios de rango, en ambos sentidos. | Video de al menos 60 cuadros/s mostrando obstáculo, referencia y LED, o instrumentación con tiempo común. El instrumento aún debe confirmarse. |
| Recuperación | Apagado y nuevo registro conforme al protocolo. | Interrumpir sensor, servidor y WiFi por separado; medir los plazos y registrar la recuperación. |

No trasladar resultados del proyecto anterior ni presentar objetivos como mediciones obtenidas. El análisis de registros de PC no reemplaza la evidencia del circuito o el ensayo óptico.

## 4. Reproducir la validación

Desde la raíz del repositorio, con Python, PlatformIO y g++ disponibles:

```powershell
python -B pruebas/validar_software.py
```

Guarda las salidas originales y un resumen en esta carpeta. Un fallo devuelve código 1. Los recursos ausentes se marcan como pendientes; comprobar el resumen aunque el comando termine con código 0. Para incluir Ncat indicar `--ncat` y su ruta. Las pruebas Unity se ejecutan por separado desde la raíz con `pio test -e native`.

Los registros de hardware pueden resumirse con:

```powershell
python pruebas/analizar_registro.py registros/ejecucion.jsonl
```

Este resumen mide frecuencia de recepción y confirmación de software, no exactitud ni respuesta física. Conservar el archivo original y asociar cada ensayo a su montaje y condiciones.


## 5. Comparación con el código de la práctica 1

La comparación utiliza el informe con el código anterior y su retroalimentación de **13/16 puntos**. Se reutiliza la base útil; no se trasladan sus resultados físicos como evidencia nueva.

| Aspecto | Práctica 1 | Código actual y revisión |
|---|---|---|
| Organización | Un ESP32 con clases de sensor e indicador; clasificación local. | Dos ESP32 con clases simples y coordinación en `loop()`; la clasificación está exclusivamente en Python. |
| Cantidad de archivos | Separación en cabeceras y fuentes, además de herramientas ajenas a la práctica. | Se conservan archivos con responsabilidades claras; la configuración de la raíz sirve solo para Unity. Clases de hardware con `.h` y `.cpp` separados. Configuración WiFi única; parámetros junto al control; registros junto al servidor. Sin BMAD. |
| C++ comprensible | Clases y función pura; identificadores en dos idiomas. | Clases modulares (`.h`/`.cpp`), tipos básicos y `String`; rutas de inclusión sin anidamiento (`-I ../comun`). Identificadores propios en español. |
| Rangos | Cerca comenzaba en 0 cm, aunque el trabajo declarado empezaba en 2 cm. | Se conserva la decisión corregida: [2,10], (10,20] y (20,30]; fuera de 2–30 o SIN_ECO apaga. |
| Conversión | Factor 0.01723 frente a una justificación de 343 m/s. | Factor ya acordado 0.01715 cm/µs y espera máxima de eco de 30 ms. La calibración real sigue pendiente. |
| Ruido en fronteras | Se recomendó mediana o histéresis. | Se conserva la mediana de tres lecturas válidas consecutivas, sin añadir histéresis. |
| LEDs | Actualización de los tres pines por caso. | Apagado previo de todos y después activación de uno; prueba automatizada del orden de las escrituras. |
| Pruebas automáticas | Cinco pruebas Unity de clasificación en PC. | Pruebas Python de fronteras, filtro, protocolo y servidor; Unity del analizador/sensor/LEDs y de ambos `main.cpp` con dobles; Ncat real. No se perdió la prueba de rangos: se ejecuta donde reside ahora la decisión, en Python. |
| Depuración | Monitor serie y variable `debugActivo`. | Monitor serie de ambas placas; opción `depuracionActiva` para cada mensaje y registros JSONL en PC. |
| Red y fallos | No existían sockets ni sesiones TCP. | Registro, confirmaciones correlacionadas, sensor inactivo 5 s, reconexión 2 s, orden pendiente 1 s y apagado local 3 s. |
| Documentación del código | Doxygen detallado. | Comentarios breves que explican responsabilidades, entradas, límites y decisiones; guía de lectura en README y enlaces relativos. No se exige una herramienta para generar documentación. |
| Seguridad eléctrica | ECHO de 5 V conectado directamente; divisor solo recomendado. | Divisor 1 kΩ/2 kΩ definido en el montaje. Su instalación física debe comprobarse; el software no puede demostrarla. |
| Evidencias | Repeticiones, medición temporal y anexos inconsistentes según la revisión. | Salidas originales conservadas y matriz de trazabilidad. Las mediciones físicas se declaran pendientes hasta realizarlas. |

### Qué falta para cumplir toda la práctica 2

El software dispone de pruebas automáticas y depuración; no son elementos ausentes. Faltan las verificaciones físicas indicadas en el apartado 3 y los entregables que dependen de ellas:

- Cargar ambos ESP32 con los datos de red reales, revisar divisor/resistencias y verificar TCP sobre WiFi, incluidos los casos límite con objetos reales.
- Registrar estabilidad de 15 minutos, exactitud con diez repeticiones por punto, al menos dos lecturas válidas/s y respuesta física máxima de un segundo en veinte cambios.
- Elaborar el informe Markdown con sus ocho secciones, esquema eléctrico de cada objeto, diagrama de clases, arquitectura y secuencia consistentes con el código final. Los dos últimos ya tienen base en `protocolo.md`.
- Enlazar fotografías y datos originales; calcular error absoluto sin signo, dispersión y análisis de errores. No copiar cifras de la práctica 1.
- Registrar aportes de cada integrante mediante commits identificables, preparar la demostración y practicar la defensa de todo el sistema.

La simplicidad del código no elimina POO ni los controles de seguridad. La confirmación de software, los dobles y la compilación permiten verificar partes del sistema; no acreditan por sí solos la exactitud del HC-SR04, la iluminación de los LEDs o la estabilidad del montaje.

## 6. Refactorización para facilitar la lectura

La validación anterior con `assert` se sustituyó por **Unity real con PlatformIO**, sin retirar las comprobaciones de hardware simulado y transporte. Las pruebas de Python siguen verificando los rangos y el servidor. Las evidencias de la versión anterior se apartaron en `work/antes_de_unity/`; la tabla de este documento y el resumen JSON corresponden al código actual.

Cambios de implementación: pines y cantidades `int`, distancias `float`, banderas `bool`, tiempos/secuencias `unsigned long`, mensajes `String`; separación de interfaz (`.h`) e implementación (`.cpp`) en clases de hardware (`SensorUltrasonico` e `IndicadorLeds`) con banderas de inclusión modular (`-I ../comun`); clases Python con anotaciones de tipo (`type hints`), colores mediante enumeración tipada (`StrEnum`), mediana mediante lista y comunicación con `select.select` sin máscaras de eventos. Los mensajes, los rangos y los plazos del protocolo se conservan.

`String` usa memoria dinámica interna. Se limitan las líneas a 128 bytes y los envíos pendientes a 512 bytes, y se reserva espacio para las dos cadenas del transporte. La estabilidad con placas reales debe verificarse con el ensayo de 15 minutos; compilar y probar en PC no la demuestra.
