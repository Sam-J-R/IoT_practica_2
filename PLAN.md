# Decisiones actuales de diseño — Práctica 2

Este archivo registra las decisiones; la especificación completa de comandos se mantiene solamente en [protocolo.md](protocolo.md).

1. **Arquitectura:** una laptop central (servidor Python) y dos ESP32 clientes conectados por Wi-Fi. El servidor tiene aceptador, supervisor, lector y escritor por conexión, y registro asíncrono; utiliza un `RLock` para roles, filtro y estados. Ver [arquitectura](documentacion/ARQUITECTURA_HILOS.md).
2. **Un proyecto PlatformIO:** un solo `platformio.ini` raíz con `esp32_sensor`, `esp32_actuador` y `native` para pruebas. Se conserva un `main.cpp` por placa.
3. **Código existente:** mensajes y nombres en español, según el acuerdo del equipo. Se mantienen las clases de sensor, LEDs y cliente TCP compartido. Comentarios explicativos en español.
4. **Control:** tres rangos válidos entre 2 y 30 cm; mediana de tres lecturas; pérdida de eco desconecta la señal útil y pide apagar los LEDs.
5. **Plazos:** registro en 3 s, desconexión por inactividad del sensor en 5 s, confirmación del actuador en 1 s, refresco en 1 s, reconexiones de los ESP32 aproximadamente cada 2 s y apagado local del actuador tras 3 s sin órdenes.
6. **Hardware:** GPIO sensor 14/27 y LEDs 33/25/26; divisor propuesto de 1 kΩ/2 kΩ en Echo y resistencias de 220 Ω en cada LED. Antes de montar, revisar la compatibilidad del nivel alto teórico (~3,33 V).
7. **Entrega y pruebas:** consultar [validación](documentacion/VALIDACION.md) para diferenciar resultados ejecutados en PC, registros anteriores y verificaciones físicas aún pendientes.

## Pendientes antes de entregar

La revisión con la consigna completa confirma que RF1–RF4 están implementados: medición ultrasónica, tres rangos contiguos dentro del rango de trabajo, tres LEDs con comportamiento distinto y dos clientes TCP hacia la PC. Los colores fijos son válidos; parpadeo, servo, interfaz, base de datos, Ncat y Wireshark no son funciones obligatorias. Falta comprobar el prototipo físico actual.

- **Software verificado:** 24 pruebas Python, 17 Unity y las dos compilaciones aprobadas. Ver [validación esencial](documentacion/VALIDACION.md).
- **Herramienta de medición pendiente:** corregir `pruebas/analizar_registro.py` para separar ejecuciones, distinguir muestreo/recepción/medidas válidas y advertir registros incompletos antes de usar sus cifras en el informe. No afecta a la selección de LEDs.
- **Detalle del protocolo pendiente:** Python permite dos espacios después del comando y C++ no; unificar ese caso antes de cerrar la especificación. Los emisores actuales utilizan el formato correcto.
- **Montaje y puesta en marcha:** comprobar las conexiones y el divisor de Echo; cargar ambos firmwares y repetir los cinco escenarios físicos de VALIDACION. La configuración de red se mantiene pendiente para la demo por decisión del equipo.
- **Atributos no funcionales:** verificar 15 minutos de estabilidad, error máximo ≤ 3 cm en 2–30 cm, respuesta extremo a extremo ≤ 1 s y al menos 2 lecturas/s. Son objetivos declarados; aún no son resultados medidos de esta versión.
- **Informe posterior:** crear `INFORME_TECNICO.md` con las ocho secciones de la consigna, diagramas actuales, enlaces al código y resultados físicos. Resumir las pruebas automáticas por requisito, sin narrar cada caso.
- **Entrega:** cada integrante aporta commits propios; subir la versión revisada y anexos, comprobar acceso del docente y enviar el enlace por LMS. Los cambios locales aún no equivalen a una entrega en GitHub.
