# Resultado final de la validación

Rama: `maria-correcciones`. Código sin modificaciones durante esta validación.

| Verificación | Resultado | Evidencia |
|---|---|---|
| Python | 27/27 aprobadas | `pruebas_python.txt` |
| Unity nativo | 17/17 aprobadas | `pruebas_unity_msys2.txt` |
| Firmware ESP32 sensor | Compilación aprobada | `compilacion_esp32_sensor.txt` |
| Firmware ESP32 actuador | Compilación aprobada | `compilacion_esp32_actuador.txt` |

El `resumen.json` original conserva el resultado FALLIDO del primer intento de Unity: gcc y g++ no estaban en PATH. Se repitió únicamente Unity añadiendo `C:\msys64\ucrt64\bin` al PATH del proceso, con código de salida 0. No se cambiaron las pruebas ni la configuración del proyecto. Las huellas del resumen corresponden al mismo código utilizado en el reintento.

La ejecución anterior, en `../20261013T174238_207052Z/`, estuvo limitada por permisos del entorno: conexiones TCP locales bloqueadas y escritura denegada en la carpeta de PlatformIO. Se conserva como evidencia del intento, no como diagnóstico de un defecto del código.

Resultado final del software: APROBADO. No se cargaron firmwares en placas ni se verificaron circuitos, Wi-Fi física, exactitud o latencia sensor a LED.
