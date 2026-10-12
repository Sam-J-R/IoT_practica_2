# Estado de validación

Validación de software realizada el **11 de octubre de 2026**, después de corregir las inconsistencias de la revisión. Las salidas originales están en [evidencias/software/](evidencias/software/); el [resumen JSON](evidencias/software/resumen.json) identifica comandos, códigos de salida, estado global y commit de referencia. `codigo_sha256` identifica los archivos realmente probados: el commit de referencia puede tener cambios locales sin confirmar. Los datos corresponden a software y clientes simulados, sin placas conectadas.

## 1. Comprobaciones ejecutadas

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Python: lógica, protocolo e integración | **23 pruebas aprobadas**. | [Salida completa](evidencias/software/pruebas_python.txt) |
| TCP real en localhost | Registro, decimales, estados, confirmaciones, fragmentación, roles, reemplazo y reconexión comprobados por las pruebas de integración. | [Casos](../pruebas/test_integracion.py) y salida Python |
| Plazo de inactividad de cinco segundos | Desde estado ROJO: conservar a los 4,99 s y cerrar sensor, vaciar filtro y entregar APAGADO a los 5 s. También se verifica apagado ante cierre TCP. Reloj controlado y sockets reales; no ensayo WiFi físico. | `test_inactividad_exactamente_cinco_segundos` y `test_desconexion_del_sensor_solicita_apagado` |
| Unity en PC | **24 pruebas aprobadas**: ocho de componentes y ocho independientes por cada programa real con red/reloj simulados. Incluyen la espera de confirmación del sensor tras una pausa. | [Salida](evidencias/software/pruebas_unity.txt), [componentes](../pruebas/unity/test_componentes/test_main.cpp), [programas](../pruebas/unity/comprobar_cliente.h) |
| Compilación del sensor ESP32 | **Correcta**, con espressif32 7.0.1 y Arduino. | [Salida original](evidencias/software/compilacion_sensor.txt) |
| Compilación del actuador ESP32 | **Correcta**, con espressif32 7.0.1 y Arduino. | [Salida original](evidencias/software/compilacion_actuador.txt) |
| Ncat 7.991 real | **Aprobado**: registro, tres rangos, SIN_ECO, inactividad de cinco segundos reales, reconexión, reemplazo, falta de confirmación, confirmación incorrecta, secuencia repetida y longitud excesiva. | [Salida](evidencias/software/pruebas_ncat.txt), [eventos originales](evidencias/software/sesiones_ncat.jsonl), [guion](../pruebas/verificar_ncat.py) |

La [instalación local de Ncat](evidencias/software/instalacion_ncat.json) conserva origen oficial, versión, firma válida y huellas del instalador y ejecutable. Los binarios están en `.herramientas/ncat/`, excluidos de Git. El plazo real medido por el guion aparece en su salida; no mide latencia física sobre WiFi.

Las pruebas de Python verifican que `APLICADO` no genera una nueva confirmación, que solo hay una orden pendiente, que no se acumulan estados anteriores y que `SIN_ECO` comunica actividad mientras fuerza apagado. Se comprueba también que el sensor no pueda enviar APLICADO ni el actuador LECTURA. Los dobles C++ comprueban exclusión de colores durante las transiciones; no demuestran iluminación física ni medición acústica.

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

Desde la raíz del repositorio, con Python 3.11 o posterior, PlatformIO y g++ disponibles:

```powershell
python -B pruebas/validar_software.py
```

Guarda las salidas originales y un resumen en esta carpeta. Devuelve 0 solo si las cinco comprobaciones aprueban, 1 si alguna falla y 2 si faltan herramientas. La ejecución incompleta ya se comprobó indicando rutas inexistentes de PlatformIO y Ncat; se regeneraron después las evidencias completas. Cuando se omite una comprobación, su archivo de salida indica PENDIENTE para no conservar un resultado anterior como actual. El validador busca PlatformIO en el PATH y en su instalación habitual de Windows; admite `--platformio RUTA` y `--ncat RUTA`. Las pruebas Unity se ejecutan por separado con `pio test -e native`.

Los registros de hardware pueden resumirse con:

```powershell
python pruebas/analizar_registro.py registros/ejecucion.jsonl
```

Este resumen mide frecuencia de recepción (incluye SIN_ECO) y confirmación de software, no exactitud ni respuesta física. La confirmación se mide desde ORDEN encolada hasta APLICADO recibido, incluyendo la cola de salida. El evento MENSAJE_ENCOLADO no acredita entrega. Conservar el archivo original y asociar cada ensayo a su montaje y condiciones.


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

La validación anterior con `assert` se sustituyó por **Unity real con PlatformIO**. En la revisión posterior, los dos ensayos largos se dividieron en pruebas independientes para que un fallo no impida ejecutar los demás escenarios. El aumento de casos contados reflejaba principalmente esa división, sin agregar clases al firmware. Después se fusionaron el catálogo válido con las lecturas de Python y la confirmación con los parámetros de C++, conservando sus verificaciones. Las pruebas de Python siguen verificando los rangos y el servidor. El resumen y sus huellas corresponden a la ejecución actual.

Cambios de implementación: pines y cantidades `int`, distancias `float`, banderas `bool`, tiempos/secuencias `unsigned long`, mensajes `String`; separación de interfaz (`.h`) e implementación (`.cpp`) en las clases de hardware; clases Python con anotaciones de tipo, colores mediante `StrEnum`, mediana mediante lista y comunicación con `select.select`. Las anotaciones no validan mensajes por sí solas. En el sensor, la espera de confirmación comienza cuando aparecen lecturas pendientes; una pausa previa ya no provoca desconexión inmediata. En la PC se conserva el segundo de espera incluyendo la cola de salida y se documenta ese instante. Se mantienen mensajes, distancias y límites temporales.

`String` usa memoria dinámica interna. Se limitan las líneas a 128 bytes y los envíos pendientes a 512 bytes, y se reserva espacio para las dos cadenas del transporte. La estabilidad con placas reales debe verificarse con el ensayo de 15 minutos; compilar y probar en PC no la demuestra.

## 7. Qué verifica cada prueba

La práctica exige evidencias de los requisitos, no una cantidad fija de pruebas automáticas. Se conservan las comprobaciones breves de control, protocolo y recuperación. Los escenarios similares en C++ y Python verifican implementaciones distintas. Ncat añade otra herramienta de transporte y plazos reales. Ninguno reemplaza los ensayos físicos del apartado 3.

### Python: control (3)

Archivo: [test_control.py](../pruebas/test_control.py). Los nombres siguientes omiten el prefijo `test_`.

| Prueba | Qué comprueba y por qué se conserva |
|---|---|
| fronteras_y_datos_no_confiables | Los límites 2, 10, 20 y 30 cm, valores no finitos y apagado fuera del rango. Verifica RF2. |
| espera_tres_lecturas_y_rechaza_un_pico | Espera tres muestras y usa la mediana para reducir el efecto de una lectura aislada. Verifica el filtro acordado. |
| error_vacia_el_filtro_y_exige_tres_nuevas | Una lectura inválida apaga, borra el filtro y exige tres adquisiciones válidas nuevas. Evita reutilizar datos anteriores al fallo. |

### Python: protocolo (6)

Archivo: [test_protocolo.py](../pruebas/test_protocolo.py).

| Prueba | Qué comprueba y por qué se conserva |
|---|---|
| distancias_decimales_y_sin_eco | Convierte centímetros con decimales, representa SIN_ECO y acepta los ejemplos válidos de los siete mensajes en la misma prueba. |
| datos_rechazados | Rechaza comandos, versiones, campos y valores incorrectos, duplicados o faltantes. |
| fragmentacion_concatenacion_y_crlf | Reconstruye líneas divididas, separa líneas juntas y acepta CRLF. TCP no conserva los límites de nuestros mensajes. |
| limite_incluye_terminador | Aplica 128 bytes incluyendo LF o CRLF, también cuando nunca llega un terminador. |
| rechaza_codificacion_y_controles | Rechaza bytes no ASCII, controles, líneas vacías y retornos de carro mal ubicados. |
| linea_valida_antes_de_error_se_procesa | Una línea válida se entrega antes de rechazar otra posterior dentro del mismo bloque TCP. |

### Python: integración (14)

Archivo: [test_integracion.py](../pruebas/test_integracion.py). Usa sockets reales en localhost y reloj controlado.

| Prueba | Qué comprueba y por qué se conserva |
|---|---|
| recorrido_tres_rangos_y_sin_eco | Lecturas, filtro, órdenes para tres colores y apagado por SIN_ECO; verifica el recorrido del servidor. |
| inactividad_exactamente_cinco_segundos | Desde ROJO, mantiene sensor a 4,99 s y entrega APAGADO a 5 s. Confirma refrescos para no confundir inactividad con fallo del actuador. |
| desconexion_del_sensor_solicita_apagado | Desde ROJO, un cierre TCP del sensor vacía el filtro y entrega APAGADO sin esperar cinco segundos. |
| sin_eco_demuestra_actividad | SIN_ECO renueva el plazo de actividad: ausencia de eco no equivale a sensor desconectado. |
| confirmacion_agotada_y_reconexion | Sin APLICADO durante un segundo, cierra actuador y acepta una nueva sesión con secuencia reiniciada. |
| confirmacion_incorrecta_se_rechaza | Rechaza una confirmación cuyo número no corresponde a la orden pendiente. |
| estado_mas_reciente_sin_cola_de_ordenes | Solo hay una orden pendiente; después se entrega el último estado deseado y no colores desactualizados. |
| reemplazo_cierra_antiguo_y_preserva_nueva_sesion | Reemplaza sensor sin que la limpieza de la sesión anterior borre la nueva. |
| reconexion_del_actuador_recibe_estado_vigente | El actuador recién conectado recibe el color vigente sin esperar otro cambio de distancia. |
| refresco_independiente_de_nuevas_lecturas | Reenvía el estado al cumplirse un segundo aunque no lleguen lecturas nuevas. |
| roles_y_secuencia | Rechaza mensajes antes del registro, lecturas repetidas, APLICADO desde sensor y LECTURA desde actuador. |
| error_del_cliente_no_produce_otro_error | Un ERROR cierra la sesión sin provocar un bucle de respuestas ERROR. |
| registro_con_plazo_y_linea_excesiva | Cierra una conexión sin registro a los tres segundos y rechaza una línea excesiva. |
| fragmentos_tcp_reales | El servidor procesa registro y lecturas fragmentadas o concatenadas por un socket real. Complementa la prueba aislada del receptor. |

### Unity: componentes (8)

Archivo: [test_componentes/test_main.cpp](../pruebas/unity/test_componentes/test_main.cpp). No usa hardware real.

| Prueba | Qué comprueba y por qué se conserva |
|---|---|
| probarNumerosDelProtocolo | Enteros de hasta 32 bits sin signo; rechaza desbordamiento, negativos, decimales y texto vacío. |
| probarOrdenConParametros | Separa campos, acepta el orden y las comas permitidas y comprueba que RECIBIDO no conserva parámetros anteriores. |
| probarMensajesIncorrectos | Rechaza sintaxis incorrecta, duplicados y exceso de campos o longitud. |
| probarColoresExclusivos | Solo el LED solicitado permanece encendido; verifica RF3 en GPIO simulados. |
| probarApagadoAntesDelCambio | La transición pasa por apagado y nunca tiene dos colores activos. No exige un número fijo de escrituras. |
| probarApagadoYEstadoIncorrecto | APAGADO desactiva los tres pines y los estados desconocidos se rechazan. |
| probarConversionDelEco | Un eco simulado de 1000 µs se convierte en 17,15 cm; no demuestra exactitud acústica. |
| probarAusenciaDeEcoYLimite | Un eco ausente o superior al dominio de 400 cm se informa como adquisición inválida. |

### Unity: programas (8 por cliente)

Archivo compartido: [comprobar_cliente.h](../pruebas/unity/comprobar_cliente.h). Cada prueba empieza con estado limpio y ejecuta el `main.cpp` real.

| Prueba | Cliente | Qué comprueba |
|---|---|---|
| probarRegistroFragmentado | Ambos | No habilita el intercambio hasta recibir ACEPTADO REGISTRO completo; admite CRLF. |
| probarReconexionYLimpieza | Ambos | Pérdida de WiFi, limpieza de datos, apagado del actuador y nuevo registro tras dos segundos. |
| probarDesconexionTcp | Ambos | Cierre TCP detectado limpia la sesión y apaga el actuador. |
| probarMensajeIncorrecto | Ambos | Sensor rechaza confirmación de lectura no enviada; actuador rechaza estado desconocido. |
| probarEnvioBloqueado | Ambos | Un envío que no avanza mantiene el bucle operativo y cierra al cumplirse un segundo. |
| probarRegistroSinRespuesta | Ambos | Cierra si no llega aceptación del registro en tres segundos. |
| probarMuestreoYConfirmaciones | Sensor | Muestrea a 100 ms y procesa dos confirmaciones recibidas juntas sin perder ninguna. |
| probarEsperaConfirmacionTrasPausa | Sensor | Una lectura nueva dispone de un segundo después de una pausa; no se desconecta al primer milisegundo. |
| probarActuacionYConfirmacionParcial | Actuador | Aplica el color y transmite APLICADO completo aunque el envío ocurra en fragmentos. |
| probarApagadoSinOrdenes | Actuador | Conserva el color a 2999 ms, apaga a 3000 ms y acepta una nueva orden válida. |

### Ncat, compilación y herramientas

Se conserva [verificar_ncat.py](../pruebas/verificar_ncat.py) porque se solicitó verificar el protocolo con Ncat real. Comprueba registro, decimales, tres rangos y confirmaciones; SIN_ECO y apagado; cinco segundos reales de inactividad; reconexión; reemplazo; mensajes sin registro; falta de confirmación; confirmación incorrecta; secuencia repetida y línea excesiva. Algunos casos repiten integración Python, pero aportan intercambio mediante otro programa. No prueban WiFi ni los ESP32 físicos.

Las dos compilaciones verifican los archivos `.h`/`.cpp` y las bibliotecas reales de ESP32: los dobles de Unity no pueden hacerlo. `validar_software.py` coordina estas comprobaciones y guarda evidencia; `analizar_registro.py` solo resume datos, no es una prueba automática ni acredita los atributos físicos.
