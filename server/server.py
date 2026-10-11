"""TCP server for the ESP32 distance sensor and LED actuator."""

import socket
import threading
import time
from dataclasses import dataclass, field

HOST = "0.0.0.0"
PORT = 5000
SENSOR_TIMEOUT = 5.0
SET_INTERVAL = 1.0
ACK_TIMEOUT = 3.0
MAX_MESSAGE_BYTES = 128
OFF = "SET redLed=off, yellowLed=off, greenLed=off"


@dataclass(eq=False)
class Client:
    connection: socket.socket
    address: tuple
    role: str | None = None
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    pending_ack: bool = False
    ack_sent_at: float = 0.0


class TCPServer:
    def __init__(self):
        self.clients = {"sensor": None, "actuator": None}
        self.lock = threading.RLock()
        self.last_sensor_post = None
        self.last_state = OFF
        self.last_set_at = 0.0
        self.last_sent_command = None

    @staticmethod
    def led_command(distance):
        if 0 <= distance <= 10:
            values = ("blink_4", "off", "off")
        elif 10 < distance <= 20:
            values = ("off", "blink_2", "off")
        elif 20 < distance <= 30:
            values = ("off", "off", "on")
        else:
            values = ("off", "off", "off")
        red, yellow, green = values
        return f"SET redLed={red}, yellowLed={yellow}, greenLed={green}"

    def send(self, client, message):
        try:
            with client.send_lock:
                client.connection.sendall((message + "\n").encode("ascii"))
            print(f"[SEND] {client.role or client.address}: {message}")
            return True
        except OSError:
            print(f"[ERROR] Send failed: {client.address}")
            self.disconnect(client)
            return False

    def disconnect(self, client):
        sensor_lost = False
        with self.lock:
            if client.role and self.clients.get(client.role) is client:
                self.clients[client.role] = None
                if client.role == "sensor":
                    sensor_lost = True
                    self.last_sensor_post = None
                    self.last_state = OFF
                print(f"[DISCONNECT] {client.role}: {client.address}")
        try:
            client.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        client.connection.close()
        if sensor_lost:
            self.send_state(force=True)

    def send_state(self, force=False):
        with self.lock:
            actuator = self.clients["actuator"]
            now = time.monotonic()
            if not actuator or actuator.pending_ack:
                return
            if not force and now - self.last_set_at < SET_INTERVAL:
                return
            command = self.last_state
            self.last_sent_command = command
            actuator.pending_ack = True
            actuator.ack_sent_at = now
            self.last_set_at = now
        if not self.send(actuator, command):
            return

    def register(self, client, message):
        if client.role is not None:
            self.send(client, "ERROR ALREADY_REGISTERED")
            return
        if not message.startswith("REGISTER type=") or message.count(" ") != 1:
            self.send(client, "ERROR BAD_FORMAT")
            return
        role = message[len("REGISTER type="):]
        if role not in self.clients:
            self.send(client, "ERROR INVALID_VALUE")
            return
        with self.lock:
            previous = self.clients[role]
            self.clients[role] = client
            client.role = role
            if role == "sensor":
                self.last_sensor_post = None
                self.last_state = OFF
            else:
                self.last_set_at = 0.0
        if previous and previous is not client:
            print(f"[REPLACE] Previous {role} connection")
            self.disconnect(previous)
        print(f"[REGISTER] {role}: {client.address}")
        self.send(client, "OK")
        if role == "actuator" or role == "sensor":
            self.send_state(force=True)

    def post(self, client, message):
        if client.role is None:
            self.send(client, "ERROR NOT_REGISTERED")
            return
        if client.role != "sensor":
            self.send(client, "ERROR NOT_ALLOWED")
            return
        if not message.startswith("POST distance=") or message.count(" ") != 1:
            self.send(client, "ERROR BAD_FORMAT")
            return
        raw = message[len("POST distance="):]
        if not raw or (raw != "-1" and not raw.isascii()):
            self.send(client, "ERROR INVALID_VALUE")
            return
        if raw != "-1" and (not raw.isdecimal() or len(raw) > 3):
            self.send(client, "ERROR INVALID_VALUE")
            return
        distance = int(raw)
        if distance != -1 and not 0 <= distance <= 400:
            self.send(client, "ERROR INVALID_VALUE")
            return
        command = self.led_command(distance)
        with self.lock:
            if self.clients["sensor"] is not client:
                self.send(client, "ERROR NOT_REGISTERED")
                return
            changed = command != self.last_state
            self.last_state = command
            self.last_sensor_post = time.monotonic()
        print(f"[POST] distance={distance} cm")
        self.send(client, "OK")
        if changed:
            self.send_state(force=True)

    def acknowledgment(self, client, message):
        if client.role != "actuator":
            self.send(client, "ERROR NOT_ALLOWED")
            return
        with self.lock:
            if not client.pending_ack:
                print(f"[WARNING] Unexpected actuator response: {message}")
                return
            client.pending_ack = False
            state_changed = self.last_state != self.last_sent_command
        print(f"[ACTUATOR] Response: {message}")
        if message.startswith("ERROR "):
            print("[WARNING] Actuator rejected the SET command")
        elif state_changed:
            self.send_state(force=True)

    def process(self, client, message):
        print(f"[RECV] {client.role or client.address}: {message}")
        command = message.split(" ", 1)[0]
        if command == "REGISTER":
            self.register(client, message)
        elif command == "POST":
            self.post(client, message)
        elif command == "SET":
            self.send(client, "ERROR NOT_REGISTERED" if client.role is None else "ERROR NOT_ALLOWED")
        elif command == "OK" or command == "ERROR":
            if client.role is None:
                self.send(client, "ERROR NOT_REGISTERED")
            elif client.role != "actuator":
                self.send(client, "ERROR NOT_ALLOWED")
            elif message == "OK" or (message.startswith("ERROR ") and len(message.split()) == 2):
                self.acknowledgment(client, message)
            else:
                print("[WARNING] Invalid actuator response")
        else:
            self.send(client, "ERROR UNKNOWN_COMMAND")

    def handle_client(self, connection, address):
        client = Client(connection, address)
        print(f"[CONNECT] {address}")
        buffer = bytearray()
        discarding = False
        try:
            while True:
                data = connection.recv(1024)
                if not data:
                    break
                for byte in data:
                    if byte == 10:
                        if not discarding:
                            line = bytes(buffer).removesuffix(b"\r")
                            try:
                                message = line.decode("ascii")
                            except UnicodeDecodeError:
                                self.send(client, "ERROR BAD_FORMAT")
                            else:
                                if message:
                                    self.process(client, message)
                                else:
                                    self.send(client, "ERROR BAD_FORMAT")
                        buffer.clear()
                        discarding = False
                    elif not discarding:
                        buffer.append(byte)
                        if len(buffer) >= MAX_MESSAGE_BYTES:
                            self.send(client, "ERROR BAD_FORMAT")
                            buffer.clear()
                            discarding = True
        except OSError:
            print(f"[ERROR] Connection lost: {address}")
        finally:
            self.disconnect(client)

    def monitor(self):
        while True:
            time.sleep(0.1)
            now = time.monotonic()
            with self.lock:
                sensor = self.clients["sensor"]
                last_post = self.last_sensor_post
                actuator = self.clients["actuator"]
                expired_ack = bool(actuator and actuator.pending_ack and now - actuator.ack_sent_at >= ACK_TIMEOUT)
                sensor_expired = bool(sensor and last_post is not None and now - last_post >= SENSOR_TIMEOUT)
                if sensor_expired:
                    print("[TIMEOUT] Sensor inactive for 5 seconds")
                    self.last_sensor_post = None
                    self.last_state = OFF
            if expired_ack:
                print("[TIMEOUT] Actuator acknowledgment missing")
                self.disconnect(actuator)
            if sensor_expired:
                self.disconnect(sensor)
            else:
                self.send_state()

    def run(self):
        threading.Thread(target=self.monitor, daemon=True).start()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((HOST, PORT))
            server.listen(5)
            print(f"[SERVER] Listening on {HOST}:{PORT}")
            try:
                while True:
                    connection, address = server.accept()
                    threading.Thread(target=self.handle_client, args=(connection, address), daemon=True).start()
            except KeyboardInterrupt:
                print("\n[SERVER] Stopped")


if __name__ == "__main__":
    TCPServer().run()
