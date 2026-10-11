
import socket
import threading

HOST = "0.0.0.0"
PORT = 5000

# Clientes conectados
clientes = {
    "sensor": None,
    "actuator": None
}

lock = threading.Lock()


# Enviar un mensaje por TCP
def enviar(cliente, mensaje):
    try:
        cliente.sendall((mensaje + "\n").encode("ascii"))
        print(f"[ENVIADO] {mensaje}")
        return True
    except OSError:
        print("[ERROR] No se pudo enviar el mensaje")
        return False


# Determinar el estado de los LEDs
def controlar_leds(distancia):
    if 0 <= distancia <= 10:
        return "blink_4", "off", "off"

    elif 10 < distancia <= 20:
        return "off", "blink_2", "off"

    elif 20 < distancia <= 30:
        return "off", "off", "on"

    else:
        return "off", "off", "off"


# Enviar una orden al ESP32 actuador
def actualizar_leds(distancia):
    rojo, amarillo, verde = controlar_leds(distancia)

    mensaje = (
        f"SET redLed={rojo}, "
        f"yellowLed={amarillo}, "
        f"greenLed={verde}"
    )

    with lock:
        actuador = clientes["actuator"]

    if actuador is not None:
        enviar(actuador, mensaje)
    else:
        print("[AVISO] No hay actuador conectado")


# Procesar los mensajes recibidos
def procesar_mensaje(cliente, mensaje):
    partes = mensaje.split()

    if not partes:
        return

    comando = partes[0]

    # Registrar un ESP32
    if comando == "REGISTER":

        if len(partes) != 2 or not partes[1].startswith("type="):
            enviar(cliente, "ERROR BAD_FORMAT")
            return

        tipo = partes[1].split("=", 1)[1]

        if tipo not in clientes:
            enviar(cliente, "ERROR INVALID_VALUE")
            return

        with lock:
            if cliente in clientes.values():
                enviar(cliente, "ERROR ALREADY_REGISTERED")
                return

            clientes[tipo] = cliente

        print(f"[REGISTRO] {tipo} conectado")
        enviar(cliente, "OK")

        if tipo == "actuator":
            actualizar_leds(-1)

    # Recibir una distancia del sensor
    elif comando == "POST":

        with lock:
            es_sensor = cliente is clientes["sensor"]

        if not es_sensor:
            enviar(cliente, "ERROR NOT_ALLOWED")
            return

        if len(partes) != 2 or not partes[1].startswith("distance="):
            enviar(cliente, "ERROR BAD_FORMAT")
            return

        try:
            distancia = int(partes[1].split("=", 1)[1])
        except ValueError:
            enviar(cliente, "ERROR INVALID_VALUE")
            return

        if distancia != -1 and not 0 <= distancia <= 400:
            enviar(cliente, "ERROR INVALID_VALUE")
            return

        print(f"[SENSOR] Distancia: {distancia} cm")

        enviar(cliente, "OK")
        actualizar_leds(distancia)

    else:
        enviar(cliente, "ERROR UNKNOWN_COMMAND")


# Atender a un cliente
def atender_cliente(cliente, direccion):
    print(f"[CONEXION] {direccion}")

    buffer = ""

    try:
        while True:
            datos = cliente.recv(1024)

            if not datos:
                break

            buffer += datos.decode("ascii")

            # Procesar mensajes completos
            while "\n" in buffer:
                mensaje, buffer = buffer.split("\n", 1)
                mensaje = mensaje.strip()

                if mensaje:
                    print(f"[RECIBIDO] {mensaje}")
                    procesar_mensaje(cliente, mensaje)

    except (OSError, UnicodeError):
        print(f"[ERROR] Conexion perdida: {direccion}")

    finally:
        sensor_desconectado = False

        with lock:
            for tipo in clientes:
                if clientes[tipo] is cliente:
                    clientes[tipo] = None
                    print(f"[DESCONECTADO] {tipo}")

                    if tipo == "sensor":
                        sensor_desconectado = True

        if sensor_desconectado:
            actualizar_leds(-1)

        cliente.close()


# Iniciar el servidor TCP
def main():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    servidor.bind((HOST, PORT))
    servidor.listen(5)

    print("=" * 40)
    print("SERVIDOR TCP - PRACTICA IoT")
    print(f"Puerto: {PORT}")
    print("Esperando conexiones...")
    print("=" * 40)

    try:
        while True:
            cliente, direccion = servidor.accept()

            hilo = threading.Thread(
                target=atender_cliente,
                args=(cliente, direccion),
                daemon=True
            )

            hilo.start()

    except KeyboardInterrupt:
        print("\nServidor detenido")

    finally:
        servidor.close()


if __name__ == "__main__":
    main()
