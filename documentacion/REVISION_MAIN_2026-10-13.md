# Revisión de main — 13 de octubre de 2026

Revisión del commit `20ce54953878634a8d1eafb3993df773b124d8d1`, confirmado contra `refs/heads/main` de GitHub. El repositorio estaba limpio al comenzar. Se inspeccionaron servidor, firmware, protocolo, configuración, pruebas, herramientas de validación, documentación, diagramas SVG y manifiestos de evidencias. No se modificó el código de aplicación.

**Resultado:** las compilaciones y pruebas existentes pasan, pero hay una credencial publicada, fallos de robustez y varias discrepancias entre implementación, documentación y evidencia. Los hallazgos siguientes distinguen fallos reproducidos, problemas observables en código y verificaciones físicas pendientes.

**Comprobaciones ejecutadas en esta revisión**

| Comprobación | Resultado |
|---|---|
| Consulta de main en GitHub | Coincide con el commit local |
| Python: `python -B -m unittest discover -s pruebas -p "test_*.py" -v` | 24/24 aprobadas, incluidas 15 de integración TCP |
| PlatformIO: `pio test -e native` | 24/24 aprobadas: 8 actuador, 8 componentes, 8 sensor |
| PlatformIO: `pio run -e esp32_sensor -e esp32_actuador` | Ambos entornos SUCCESS, plataforma 7.0.1 |
| `python -B -m servidor --help` | Funciona sin `servidor/__init__.py` |
| Reproducciones adicionales con dobles y reloj controlado | Resultados detallados debajo |
| Ncat, Wireshark y funcionamiento físico de las placas | No ejecutados en esta revisión |

Se utilizó Python de `C:/Users/Maria/.platformio/penv/Scripts/python.exe` y PlatformIO de la misma carpeta. Las restricciones iniciales del entorno bloquearon localhost y la caché de PlatformIO; al repetir con permisos, las pruebas pasaron. Esos bloqueos no son defectos del proyecto. Compilar los binarios no significa haberlos cargado ni probado en los ESP32.

**1. P1 — Retirar la contraseña del archivo de ejemplo y corregir su uso automático**

Ubicación: `comun/ConfiguracionRedEjemplo.h:4–6`; ambos `firmware/src/*/main.cpp:3–7`.

El archivo versionado contiene un SSID, una contraseña concreta y una IP local, aunque README asegura que las claves quedan fuera de Git. No se reproduce aquí el valor. `.gitignore` solo excluye `ConfiguracionRed.h`; no protege el archivo de ejemplo. Además, si falta el archivo privado, ambos firmwares compilan silenciosamente con los datos del ejemplo. El commit `34ce4b5` introdujo esos valores.

Cambio necesario: sustituir los valores por marcadores, mantener los datos reales únicamente en el archivo privado y hacer explícita la falta de configuración al compilar para las placas. Si la contraseña es real, cambiarla: borrarla del último commit no elimina su exposición histórica. Evaluar la limpieza coordinada del historial si el equipo necesita eliminar el secreto de Git. Para pruebas nativas puede mantenerse una configuración ficticia explícita.

**2. P2 — Invalidar inmediatamente un sensor rechazado y poner plazo total al cierre**

Ubicación: `servidor/servidor.py:204–225`, `227–236`, `331–342`; contrato en `protocolo.md:135`.

`_rechazar()` encola ERROR al final de la salida y marca `terminando`, pero mantiene el rol y el estado válido del sensor hasta que el escritor cierre la conexión. El supervisor no comprueba un plazo propio de terminación. El timeout de 250 ms limita cada `sendall`, no el tiempo acumulado de toda la cola. Por eso no se cumple el cierre en 0,5 s prometido por el protocolo.

Reproducción con dobles: tres respuestas pendientes y cuatro envíos de 240 ms cada uno producen cierre a los **0,96 s simulados**, aunque ninguno agota el timeout individual. Si el escritor todavía no cierra, un sensor rechazado sigue conservando ROJO después de 1 s en la reproducción del estado.

Cambio necesario: retirar inmediatamente el sensor del control, vaciar su filtro y solicitar APAGADO; separar esa invalidación lógica del intento de entregar ERROR. Añadir una fecha límite total de terminación que supervise el servidor y evitar que ERROR espere todo el historial de respuestas. Documentar el plazo elegido.

**3. P2 — Aislar el registro de eventos de los hilos de control**

Ubicación: `servidor/servidor.py:32–43`, `156–180`, `197–201`, `344–348`.

La consola, la escritura JSONL y `flush()` son síncronos. Muchas llamadas a `registrar()` ocurren bajo el RLock global, por lo que un destino de registro lento puede retrasar lecturas, órdenes y supervisión aunque los sockets ya estén separados. Los errores de escritura tampoco se manejan: una excepción de disco sale del lector/escritor/supervisor. El proceso principal puede continuar mientras ha perdido un hilo necesario.

Reproducción: un archivo doble que lanza `OSError` hace que `_leer_cliente()` aborte sin cerrar su sesión.

Cambio necesario: usar un consumidor de registros independiente con cola acotada y política explícita de saturación, manejar errores de escritura y garantizar limpieza de sesiones en `finally`. Si falla la supervisión, el proceso debe detectarlo y adoptar una salida controlada. No ocultar errores sin cambiar el estado del servicio.

**4. P2 — Liberar referencias a hilos terminados**

Ubicación: `servidor/servidor.py:97`, `123–127`, `364–367`.

Cada conexión añade dos objetos Thread a `self.hilos`, pero solo se vacía la lista al detener todo el servidor. Las reconexiones acumulan objetos terminados durante toda la ejecución; `maximo_clientes=8` no limita esa lista histórica.

Reproducción: 100 hilos terminados, ninguno vivo, permanecen referenciados en `self.hilos`.

Cambio necesario: retirar hilos finalizados bajo sincronización o mantener únicamente los activos y los hilos permanentes. Probar muchas reconexiones consecutivas y comprobar que las estructuras regresan a un tamaño estable.

**5. P2 — Acotar las órdenes interrumpidas y definir cuándo deja de aceptarse su confirmación**

Ubicación: `servidor/servidor.py:67`, `250–259`, `308–313`.

Cada color interrumpido por APAGADO entra en un conjunto y solo se elimina si llega exactamente su APLICADO. Un cliente que confirma los apagados pero omite los colores puede mantener la sesión y hacer crecer el conjunto indefinidamente. Las confirmaciones de ese conjunto no tienen caducidad ni se comparan con las confirmaciones más recientes.

Reproducción: 100 ciclos dejan 100 identificadores retenidos. Una confirmación del primero se acepta a los **1000 s simulados**, incluso después de confirmar órdenes posteriores. Este escenario representa un cliente incompleto o defectuoso; no demuestra que el firmware actual omita esas respuestas normalmente.

Cambio necesario: definir una ventana acotada para respuestas de órdenes sustituidas, depurarla al confirmar una orden posterior y decidir qué hacer con las respuestas tardías. Aprovechar que el transporte TCP conserva el orden de los mensajes. Añadir pruebas específicas de la interrupción por APAGADO.

**6. P2 — Separar ejecuciones en los registros y en el analizador**

Ubicación: `servidor/servidor.py:30`, `94`, `148`; `pruebas/analizar_registro.py:13–24`.

El JSONL se abre en modo append, pero los identificadores de sesión vuelven a empezar al reiniciar el servidor. El analizador agrupa exclusivamente por `sesion`. Por tanto, dos ejecuciones habituales del comando README pueden acabar tratadas como una sola sesión, incluyendo el intervalo entre ejecuciones en la frecuencia calculada.

Reproducción: dos sesiones independientes con dos lecturas a 10 Hz cada una, separadas por 100 s, se resumen como una sesión de cuatro lecturas a **0,02997 Hz**.

Cambio necesario: incluir un identificador de ejecución en todos los eventos y agrupar por `(ejecucion, sesion)`, o crear un archivo distinto por ejecución. Para archivos antiguos, segmentar por `SERVIDOR_INICIADO`. Añadir también una métrica de lecturas válidas por segundo: la frecuencia actual incluye SIN_ECO y no basta para acreditar el requisito de lecturas válidas.

**7. P2 — Actualizar arquitectura y contrato de protocolo al comportamiento vigente**

Ubicación: `documentacion/ARQUITECTURA_HILOS.md:22–39`, `documentacion/GUIA_CAMBIOS.md:7–9`, `README.md:46`, `protocolo.md:120–135`, `200`, `242`, `338`.

Hay contradicciones concretas:

- La documentación dice que los envíos ocurren bajo el bloqueo global y que se evitan colas; el código ya tiene una cola y un hilo escritor por cliente, con `sendall` fuera del RLock.
- El diagrama omite los escritores. Con dos clientes hay seis hilos de servicio: aceptador, supervisor, dos lectores y dos escritores, además del principal.
- El protocolo describe una sola orden pendiente y un apagado que puede esperar al APLICADO anterior. Ahora APAGADO puede enviarse mientras falta esa confirmación y el servidor conserva identificadores interrumpidos.
- El contrato dice que las confirmaciones tardías o distintas de la pendiente cierran la sesión; el código hace una excepción para órdenes interrumpidas.
- Los 0,5 s de cierre por ERROR no están implementados como plazo total.
- `protocolo.md` todavía describe pruebas de inactividad con reloj controlado; la suite de integración vigente usa tiempos reales acortados.

Cambio necesario: conservar una especificación única y actualizar diagramas, secuencias, plazos y explicaciones. Describir una orden vigente y las excepciones acotadas para órdenes sustituidas. Aclarar que la prioridad lógica de APAGADO no permite retirar bytes ya enviados por TCP y decidir si se deben descartar colores que todavía están en la cola local.

**8. P2 — Regenerar evidencias para el commit realmente entregado y ampliar las regresiones**

Ubicación: `documentacion/evidencias/hilos/resumen.json`, `documentacion/VALIDACION.md`, `pruebas/test_integracion.py`, `pruebas/validar_software.py`.

El manifiesto actual no corresponde exactamente al árbol revisado. Incluso tolerando las diferencias LF/CRLF, cambian `servidor/servidor.py`, `servidor/__main__.py`, `comun/ConfiguracionRedEjemplo.h`, y el manifiesto incluye `servidor/__init__.py`, que ya fue eliminado. La evidencia de hilos antecede a la última corrección del servidor.

Las pruebas existentes pasan hoy, pero no protegen suficientemente las nuevas colas, escritores ni interrupciones. En particular, la prueba de estado final envía la confirmación anterior antes de comprobar el apagado, así que por sí sola no demuestra que APAGADO llegue sin esperar ese APLICADO.

Cambio necesario: agregar regresiones para APAGADO sin confirmación previa, confirmación antigua antes/después de la nueva, escritor lento y cola llena, cierre con ERROR pendiente, errores de registro, reconexiones repetidas y aislamiento entre clientes. Después generar evidencias nuevas con commit, sistema, versiones de herramientas, comandos y hashes. Mantener separadas las ejecuciones históricas. Incluir también la repetibilidad en el validador si se sigue ofreciendo como resultado reproducible automático.

Las compilaciones y las pruebas Unity ya fueron ejecutadas con éxito en esta revisión; sus resultados pueden incorporarse como nueva evidencia sin presentarlos como demostración física. El validador debería permitir una carpeta de salida por ejecución para no sobrescribir automáticamente el histórico.

**9. P3 — Unificar la gramática Python/C++**

Ubicación: `servidor/protocolo.py:73–81`; `comun/ProtocoloAplicacion.h:23–40`; `protocolo.md:34`.

Python acepta `APLICADO  numero=1` con dos espacios: elimina un espacio al inicio de cualquier campo, incluido el primero. C++ rechaza el campo cuya clave empieza por espacio y el documento exige un único espacio tras el comando.

Cambio necesario: aplicar el espacio opcional solamente a los campos posteriores a una coma, o cambiar coherentemente ambos parsers y el contrato. Añadir el mismo conjunto de casos de aceptación y rechazo a Python y C++. Es un problema de conformidad, no una avería del intercambio normal, cuyos emisores usan el formato correcto.

**10. P2 de entrega — Unificar los criterios de aceptación y completar las mediciones**

Ubicación: `documentacion/VALIDACION.md:77–81`, `protocolo.md:351–354`, `PLAN.md:20–25`.

VALIDACION pide al menos 10 minutos y cinco medidas por punto; protocolo pide 15 minutos y diez lecturas. La consigna original del docente no está en el repositorio revisado, por lo que no se puede decidir cuál es el requisito oficial.

Cambio necesario: contrastar la consigna y usar los mismos criterios en todos los documentos. Si no se exige otra cosa, 15 minutos y diez medidas satisfacen los dos mínimos actuales. Documentar exactitud, lecturas válidas/s, 20 transiciones para latencia y recuperación ante pérdida de Wi-Fi, sensor, actuador y servidor. Crear el `INFORME_TECNICO.md` mencionado en PLAN cuando existan resultados verificables.

**11. Pendiente físico — Cerrar la decisión del divisor y reflejar el montaje real**

README, PLAN y el esquema proponen 1 kΩ/2 kΩ, mientras el texto menciona 1,8 kΩ como alternativa. No basta con dejar ambas opciones sin registrar cuál se montó, las tolerancias ni la tensión medida.

No se puede concluir que 3,33 V nominales sean automáticamente incompatibles por superar 3,3 V: la tabla 5-3 del [datasheet oficial del ESP32](https://documentation.espressif.com/esp32_datasheet_en.html) especifica el nivel alto de entrada hasta VDD + 0,3 V, bajo sus condiciones. El criterio debe considerar el dominio de alimentación real y las tolerancias. El divisor de 1 kΩ/1,8 kΩ da aproximadamente 3,21 V a 5 V nominales; esto es un cálculo, no una medición ni una garantía del montaje.

Cambio necesario antes de validar hardware: fijar valores y tolerancias, comprobar las tensiones de alimentación y Echo, y actualizar esquema, README e informe con el circuito realmente utilizado. No se verificaron físicamente las placas en esta revisión.

**Qué no requiere una reescritura**

Los dos entornos de firmware están correctamente separados y compilan. Los GPIO coinciden entre código y documentación. La lógica de mediana, rangos y borrado ante SIN_ECO tiene pruebas que pasan. Eliminar `__init__.py` no rompe en este entorno la entrada documentada `python -m servidor`; restaurarlo puede ser una elección de empaquetado, pero no es una corrección urgente demostrada. Tampoco hay motivo encontrado para volver a `select` o duplicar los proyectos PlatformIO.

El reemplazo de roles sin autenticación está definido en el protocolo. Para una práctica en una red controlada es una decisión de alcance; si se usa una red compartida o se expone el servidor, habría que restringir el acceso y autenticar dispositivos. No se presenta como un requisito adicional obligatorio de la práctica.

**Orden de corrección sugerido**

1. Credenciales y configuración de las placas.
2. Invalidación y cierre por ERROR; aislamiento de registros y limpieza de hilos.
3. Caducidad de órdenes interrumpidas y pruebas de regresión.
4. Identidad de ejecuciones y cálculo de métricas.
5. Protocolo, arquitectura, gramática y criterios de aceptación.
6. Evidencias del commit final, mediciones físicas e informe.

Las reproducciones auxiliares están en `work/revision_main/comprobar_hallazgos.py` y `work/revision_main/dos_ejecuciones.jsonl` (carpeta ignorada por Git). Usan dobles para los escenarios excepcionales; los 0,96 s y 1000 s citados son tiempo simulado, no mediciones de la red física.
