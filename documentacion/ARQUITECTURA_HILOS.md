# Arquitectura del proyecto unificado por hilos

## 1. Objetivo

Implementar un objeto IoT distribuido con dos ESP32 y una laptop: la placa sensor adquiere distancias, el servidor clasifica y la placa actuador maneja tres LEDs. La aplicación se organiza en **un repositorio y un único proyecto PlatformIO**, con dos entornos de compilación independientes y **un servidor Python multihilo**.

## 2. Distribución

```mermaid
flowchart LR
    HC["HC-SR04<br/>Trigger 14 / Echo 27"] --> S["ESP32 sensor<br/>firmware/src/sensor"]
    S -->|"LECTURA / RECIBIDO<br/>TCP por Wi-Fi"| PC["Laptop<br/>ServidorTcp"]
    PC -->|"ORDEN / APLICADO<br/>TCP por Wi-Fi"| A["ESP32 actuador<br/>firmware/src/actuador"]
    A --> LED["LED rojo 33<br/>amarillo 25<br/>verde 26"]
```

Los pines son los del montaje declarado, y las credenciales e IP de la laptop se configuran en `comun/ConfiguracionRed.h` (no se publica).

## 3. Concurrencia del servidor

```mermaid
flowchart TD
    INI["ServidorTcp.iniciar()"] --> AC["Hilo tcp-aceptador<br/>accept()"]
    AC --> C1["Hilo tcp-cliente-1<br/>recv / interpretar"]
    AC --> C2["Hilo tcp-cliente-2<br/>recv / interpretar"]
    AC --> W1["Hilo tcp-escritor-1<br/>cola / sendall"]
    AC --> W2["Hilo tcp-escritor-2<br/>cola / sendall"]
    INI --> SUP["Hilo tcp-supervisor<br/>temporizadores cada ~25 ms"]
    C1 --> LOCK["RLock<br/>roles, filtro, sesiones, órdenes"]
    C2 --> LOCK
    SUP --> LOCK
    LOCK --> EST["ControlDistancia<br/>mediana y estado"]
    LOCK --> Q["Colas de salida por cliente"]
    Q --> W1
    Q --> W2
    LOCK --> R["Cola de registros<br/>máximo 1024 eventos"]
    R --> LOG["Hilo registro-eventos<br/>consola / JSONL"]
```

- `tcp-aceptador` acepta conexiones y crea un lector y un escritor por conexión.
- `tcp-cliente-N` reconstruye mensajes TCP, valida comandos y actualiza la sesión.
- `tcp-escritor-N` consume una cola de hasta 32 mensajes y envía sin retener el RLock. Cada operación de socket tiene timeout de 250 ms.
- `tcp-supervisor` verifica registro, inactividad, confirmaciones, refresco y el plazo total de cierre por error de 0,5 s. Comprueba los plazos aproximadamente cada 25 ms, sujeto a la planificación del sistema operativo.
- El `threading.RLock` protege roles, secuencias, estado y órdenes. `recv()`, `sendall()` y la escritura de registros no esperan dentro de ese bloqueo.
- El rechazo o cierre del sensor retira su rol, invalida el filtro y solicita `APAGADO` inmediatamente. El intento posterior de entregar ERROR no retrasa esa invalidación.
- `registro-eventos` escribe consola y JSONL desde una cola de hasta 1024 eventos. Si se llena, descarta eventos nuevos y contabiliza la pérdida; al avanzar el consumidor emite `REGISTROS_DESCARTADOS`. Un destino que falla se deshabilita, el fallo queda en `RegistroPruebas.error` y se avisa por consola si esta funciona. El control TCP continúa, pero esos registros no constituyen evidencia completa.
- El cierre espera hasta 0,6 s al consumidor de registros. Si un destino sigue bloqueado, queda indicado en `error`; el hilo daemon podrá finalizar si se desbloquea, pero no impide salir del programa ni garantiza guardar toda la cola.
- Cada hilo TCP se retira de la lista al terminar. Una excepción inesperada en un hilo TCP detiene el servicio, cierra las conexiones y hace que la entrada principal termine con error, en lugar de continuar sin supervisión.
- Solo se conserva el número del color interrumpido mientras APAGADO espera confirmación. Confirmar APAGADO o cerrar la sesión elimina ese número. Confirmar el color no confirma APAGADO ni renueva su plazo.
- `APLICADO` demuestra que el firmware llamó a `digitalWrite`, no prueba por sí mismo el estado eléctrico del LED.

Esta arquitectura sustituye el bucle `select` anterior. Combina hilos de I/O con colas acotadas y sincronización explícita del estado compartido.

## 4. Diagrama de clases y responsabilidades

```mermaid
classDiagram
    class ServidorTcp {
        +iniciar()
        +cerrar()
        -_aceptar()
        -_leer_cliente(sesion)
        -_escribir_cliente(sesion)
        -_supervisar()
        -_procesar(sesion,linea)
        -_solicitar_estado()
    }
    class SesionCliente {
        +rol
        +numero_lectura
        +numero_pendiente
        +numero_interrumpido
        +estado_confirmado
    }
    class ControlDistancia {
        +clasificar(distancia)
        +procesar(distancia)
        +invalidar()
    }
    class RegistroPruebas {
        +registrar(evento)
        +cerrar()
        +error
        +descartados
    }
    class ProtocoloAplicacion {
        +interpretar(linea)
        +codificar(linea)
    }
    class ClienteTcp {
        +actualizar()
        +enviar(mensaje)
        +recibirMensaje(mensaje)
    }
    class SensorUltrasonico {
        +medir(distancia)
    }
    class IndicadorLeds {
        +aplicar(estado)
        +apagar()
    }
    ServidorTcp --> SesionCliente
    ServidorTcp --> ControlDistancia
    ServidorTcp --> ProtocoloAplicacion
    ServidorTcp --> RegistroPruebas
    ClienteTcp --> ProtocoloAplicacion
```

La medición física y el control de pines se mantienen encapsulados en C++. El servidor es el único lugar donde se deciden los colores; no se duplica esa lógica en el sensor o actuador.

## 5. Secuencia típica

```mermaid
sequenceDiagram
    participant S as ESP32 Sensor
    participant SRV as Servidor TCP con hilos
    participant A as ESP32 Actuador
    S->>SRV: REGISTRO tipo=sensor, version=1
    SRV-->>S: ACEPTADO REGISTRO
    A->>SRV: REGISTRO tipo=actuador, version=1
    SRV-->>A: ACEPTADO REGISTRO
    SRV->>A: ORDEN numero=1, estado=APAGADO
    A-->>SRV: APLICADO numero=1
    loop Cada ~100 ms
        S->>SRV: LECTURA numero=N, tiempo_ms=T, distancia_cm=15.20
        SRV-->>S: RECIBIDO numero=N
    end
    Note over SRV: Mediana de tres lecturas validas
    SRV->>A: ORDEN numero=2, estado=AMARILLO
    A-->>SRV: APLICADO numero=2
```

`REGISTRO`, `LECTURA`, `ORDEN`, `APLICADO`, `RECIBIDO` y `ERROR` mantienen el contrato anterior; ver [protocolo.md](../protocolo.md) para errores y reglas de secuencia.

## 6. Proyecto PlatformIO único

El archivo [platformio.ini](../platformio.ini) crea tres entornos:

| Entorno | Fuentes compiladas | Propósito |
|---|---|---|
| `esp32_sensor` | `firmware/src/sensor/` | Carga en placa conectada al HC-SR04 |
| `esp32_actuador` | `firmware/src/actuador/` | Carga en placa conectada a los LEDs |
| `native` | `pruebas/unity/` | Pruebas simuladas con Unity en PC |

Los archivos `comun/ClienteTcp.h` y `comun/ProtocoloAplicacion.h` se comparten como cabeceras; no hay dos copias independientes del cliente TCP.

## 7. Consideraciones físicas

- **Echo HC-SR04:** resistencia 1 kΩ entre Echo y GPIO 27, resistencia 2 kΩ de GPIO 27 a GND; tensión teórica del nodo ≈ 3,33 V a 5 V nominal. Esto está ligeramente por encima de 3,3 V. Conviene verificar especificaciones de la placa y tolerancias, o cambiar la resistencia inferior a 1,8 kΩ si está disponible.
- **Trigger:** GPIO 14 al Trigger. HC-SR04 alimentado a 5 V con tierra común.
- **LEDs:** GPIO 33/25/26, cada uno con su resistencia de 220 Ω en serie y cátodo a GND.

## 8. Límites de las comprobaciones

Las pruebas de software verifican el comportamiento lógico y de sockets. No prueban el tiempo entre movimiento real de un objeto y encendido del LED, la tolerancia del divisor bajo carga ni el funcionamiento Wi-Fi tras esta refactorización. Se requiere repetir la demostración física con el nuevo firmware y servidor.
