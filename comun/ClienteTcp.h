#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <lwip/sockets.h>
#include <errno.h>

// Esta clase solo se ocupa de WiFi, TCP y el registro.
// No mide distancias, no elige colores y no enciende LEDs.
class ClienteTcp {
public:
    ClienteTcp(String nombreRed, String claveRed, String ipServidor,
               int puertoServidor, String tipoCliente) {
        red = nombreRed;
        clave = claveRed;
        direccion = ipServidor;
        puerto = puertoServidor;
        rol = tipoCliente;
        entrada.reserve(128);
        salida.reserve(512);
    }

    void iniciar() {
        WiFi.mode(WIFI_STA);
        WiFi.setAutoReconnect(true);
        WiFi.begin(red.c_str(), clave.c_str());
        ultimoIntentoTcp = millis() - 2000;
        ultimoIntentoRed = millis();
        Serial.println("Conectando a WiFi");
    }

    bool registrado() { return registroAceptado; }
    void activarDepuracion(bool activa) { depuracionActiva = activa; }

    void desconectar(const char* motivo) {
        cliente.stop();
        registroAceptado = false;
        mensajeDisponible = false;
        entrada = "";
        salida = "";
        ultimoIntentoTcp = millis();
        Serial.printf("DESCONEXION motivo=%s tiempo_ms=%lu\n", motivo, millis());
    }

    bool enviar(String mensaje) {
        // Guardar para enviar en la próxima vuelta; agregar el salto de línea.
        if (mensaje.length() + 1 > 128 || salida.length() + mensaje.length() + 1 > 512) {
            desconectar("LIMITE_ENVIO");
            return false;
        }
        if (salida.length() == 0) inicioEnvio = millis();
        salida += mensaje + "\n";
        if (depuracionActiva) Serial.printf("ENVIO %s\n", mensaje.c_str());
        return true;
    }

    bool recibirMensaje(String& mensaje) {
        if (!mensajeDisponible) return false;
        mensaje = entrada;
        entrada = "";
        mensajeDisponible = false;
        return true;
    }

    void actualizar() {
        unsigned long ahora = millis();
        if (WiFi.status() != WL_CONNECTED) {
            if (cliente || registroAceptado) desconectar("WIFI");
            if (ahora - ultimoIntentoRed >= 2000) {
                ultimoIntentoRed = ahora;
                WiFi.reconnect();
            }
            return;
        }
        if (!cliente.connected()) {
            if (cliente || registroAceptado) desconectar("TCP");
            if (ahora - ultimoIntentoTcp < 2000) return;
            ultimoIntentoTcp = ahora;
            IPAddress ip;
            if (!ip.fromString(direccion.c_str())) return;
            if (!cliente.connect(ip, puerto, 250)) return;
            cliente.setNoDelay(true);
            inicioRegistro = millis();
            entrada = "";
            salida = "";
            mensajeDisponible = false;
            registroAceptado = false;
            enviar(String("REGISTRO tipo=") + rol + ", version=1");
            Serial.printf("CONEXION rol=%s tiempo_ms=%lu\n", rol.c_str(), millis());
        }
        enviarPendientes();
        leerEntrada();
        if (cliente.connected() && !registroAceptado && millis() - inicioRegistro >= 3000)
            desconectar("REGISTRO_TIEMPO_AGOTADO");
    }

private:
    WiFiClient cliente;
    String red;
    String clave;
    String direccion;
    String rol;
    int puerto;
    String entrada;
    String salida;
    bool registroAceptado = false;
    bool mensajeDisponible = false;
    bool depuracionActiva = false;
    unsigned long ultimoIntentoRed = 0;
    unsigned long ultimoIntentoTcp = 0;
    unsigned long inicioRegistro = 0;
    unsigned long inicioEnvio = 0;

    void enviarPendientes() {
        if (salida.length() == 0) return;
        // Única llamada de bajo nivel: no esperar si la red no puede enviar.
        // WiFiClient.print puede esperar varios segundos y retrasar el apagado.
        int enviados = send(cliente.fd(), salida.c_str(), salida.length(), MSG_DONTWAIT);
        if (enviados > 0) salida.remove(0, enviados);
        else if (enviados == 0 || (errno != EAGAIN && errno != EWOULDBLOCK)) {
            desconectar("ENVIO_TCP");
            return;
        }
        if (salida.length() > 0 && millis() - inicioEnvio >= 1000)
            desconectar("ENVIO_TIEMPO_AGOTADO");
    }

    void leerEntrada() {
        if (mensajeDisponible) return;
        int leidos = 0;
        while (cliente.available() && leidos < 512) {
            int letra = cliente.read();
            if (letra < 0) return;
            leidos++;
            if (letra > 127 || (letra < 32 && letra != '\n' && letra != '\r')) {
                desconectar("FORMATO");
                return;
            }
            if (letra != '\n') {
                if (entrada.length() >= 127) { desconectar("LONGITUD"); return; }
                entrada += (char) letra;
                continue;
            }
            if (entrada.endsWith("\r")) entrada.remove(entrada.length() - 1);
            if (entrada.length() == 0 || entrada.indexOf('\r') >= 0) {
                desconectar("FORMATO");
                return;
            }
            if (depuracionActiva) Serial.printf("RECEPCION %s\n", entrada.c_str());
            if (entrada.startsWith("ERROR ")) { desconectar("ERROR_SERVIDOR"); return; }
            if (!registroAceptado) {
                if (entrada != "ACEPTADO REGISTRO") { desconectar("REGISTRO_INVALIDO"); return; }
                registroAceptado = true;
                entrada = "";
                Serial.println("Registro aceptado");
            } else {
                mensajeDisponible = true;
                return;
            }
        }
    }
};
