# Decisiones actuales de diseño — Práctica 2

Este archivo registra las decisiones; la especificación completa de comandos se mantiene solamente en [protocolo.md](protocolo.md).

1. **Arquitectura:** una laptop central (servidor Python) y dos ESP32 clientes conectados por Wi-Fi. El servidor se ejecuta con `threading`, con un hilo lector por conexión y uno de supervisión; utiliza un `RLock` para roles, filtro y estados. Ver [arquitectura](documentacion/ARQUITECTURA_HILOS.md).
2. **Un proyecto PlatformIO:** un solo `platformio.ini` raíz con `esp32_sensor`, `esp32_actuador` y `native` para pruebas. Se conserva un `main.cpp` por placa.
3. **Código existente:** mensajes y nombres en español, según el acuerdo del equipo. Se mantienen las clases de sensor, LEDs y cliente TCP compartido. Comentarios explicativos en español.
4. **Control:** tres rangos válidos entre 2 y 30 cm; mediana de tres lecturas; pérdida de eco desconecta la señal útil y pide apagar los LEDs.
5. **Plazos:** registro en 3 s, desconexión por inactividad del sensor en 5 s, confirmación del actuador en 1 s, refresco en 1 s, reconexiones de los ESP32 aproximadamente cada 2 s y apagado local del actuador tras 3 s sin órdenes.
6. **Hardware:** GPIO sensor 14/27 y LEDs 33/25/26; divisor propuesto de 1 kΩ/2 kΩ en Echo y resistencias de 220 Ω en cada LED. Antes de montar, revisar la compatibilidad del nivel alto teórico (~3,33 V).
7. **Entrega y pruebas:** consultar [validación](documentacion/VALIDACION.md) para diferenciar resultados ejecutados en PC, registros anteriores y verificaciones físicas aún pendientes.

## Pendientes antes de entregar

- Ejecutar `pio run -e esp32_sensor`, `pio run -e esp32_actuador` y `pio test -e native` en una laptop con PlatformIO.
- Cargar ambos firmware nuevos y **volver a probar físicamente**: la prueba anterior fue con la arquitectura anterior.
- Repetir Ncat, Wireshark y comprobaciones de desconexiones con el servidor por hilos.
- Registrar mediciones y capturas trazables: distancias repetidas, latencia extremo a extremo, frecuencia y funcionamiento continuo.
- Integrar los diagramas y resultados reales en `INFORME_TECNICO.md` cuando estén verificados.
- Cada integrante debe aportar commits con su propia cuenta conforme a la consigna del docente.
