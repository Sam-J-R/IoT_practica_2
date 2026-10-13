# Validación esencial

Esta es una guía de trabajo previa al informe oficial. Se documentan los requisitos y resultados relevantes, sin convertir cada prueba automática en una sección del informe.

## Comprobaciones automáticas

Desde la raíz del repositorio:

```powershell
python -B pruebas/validar_software.py
```

El validador ejecuta Python, Unity y la compilación de ambas placas. Guarda las salidas y hashes en una carpeta nueva bajo `documentacion/evidencias/esenciales/`. Admite `--platformio RUTA` y `--salida CARPETA`.

La ejecución del 13 de octubre de 2026 aprobó **24 pruebas Python, 17 Unity y las dos compilaciones ESP32**. [Resumen y fuentes comprobadas](evidencias/esenciales/2026-10-13/resumen.json). La suite conserva rangos y filtro, mensajes TCP, adquisición y LEDs simulados, apagado, reconexión y los fallos críticos corregidos. Se eliminaron casos redundantes, el segundo ensayo C++ y el guion Ncat duplicado.

Estas comprobaciones se pueden resumir en un párrafo del informe. No prueban el circuito, la Wi-Fi real ni las métricas físicas. Los directorios de evidencias anteriores son históricos y no se reescribieron.

## Cinco escenarios para la validación física

| Escenario | Qué demostrar y conservar |
|---|---|
| 1. Integración y rangos (RF1–RF4) | Dos ESP32 conectados por Wi-Fi a la PC; lecturas y órdenes TCP; rojo en [2,10], amarillo en (10,20], verde en (20,30]; comprobar fronteras, fuera de rango y SIN_ECO. Foto del circuito, vídeo y registro de una ejecución. |
| 2. Exactitud | Comparar diez lecturas por punto en 2, 5, 10, 15, 20, 25 y 30 cm con una referencia física. Registrar error absoluto y máximo; objetivo declarado ≤ 3 cm. |
| 3. Respuesta | Medir 20 cambios entre rangos desde el cambio físico de distancia hasta el LED, usando vídeo con una referencia temporal común. Objetivo declarado ≤ 1 s. APLICADO no mide ese recorrido completo. |
| 4. Estabilidad y muestreo | Operar 15 minutos continuos, sin reinicios ni bloqueos, registrando las lecturas por segundo. Objetivo declarado ≥ 2 lecturas/s, diferenciando intentos, mediciones válidas y SIN_ECO. Puede realizarse en la misma sesión del escenario 1. |
| 5. Recuperación | Desconectar sensor, actuador, Wi-Fi y servidor por separado; observar apagado y reconexión. Comparar con los plazos del protocolo, distinguiendo cierre TCP detectado de pérdida silenciosa de red. |

Los 15 minutos y diez lecturas por punto son elecciones del proyecto, no cantidades obligatorias de la consigna. Los valores de referencia de esta deben declararse y verificarse, no presentarse como mediciones ya realizadas. Ncat y Wireshark son opcionales.

## Antes de tomar resultados

- Comprobar y fotografiar el montaje real, incluido el divisor de Echo y las resistencias de cada LED.
- Usar la versión actual de ambos firmwares y del servidor.
- Corregir el analizador antes de usar sus cifras: actualmente mezcla identificadores de sesión entre ejecuciones del mismo archivo y no evalúa la pérdida de registros. Mientras tanto, guardar cada ensayo en un JSONL distinto con `--registro` y revisar cualquier aviso `REGISTROS_DESCARTADOS` o `FALLO_REGISTRO`.
- Medir el muestreo del sensor y la recepción por separado. No confundir el intervalo programado de 100 ms con una frecuencia mínima observada.

Los cinco escenarios siguen pendientes de ejecución física con esta versión. Sus resultados alimentarán la sección Pruebas y Validaciones del informe oficial; no hace falta narrar las 41 comprobaciones internas.
