#pragma once
// Solo la PC usa este doble; las placas utilizan WiFi de Arduino.
#include <string>
const int WIFI_STA = 1;
const int WL_CONNECTED = 3;
extern bool redSimulada;
extern bool servidorDisponible;
extern bool conexionSimulada;
extern int intentosTcp;
extern int plazoConexion;
extern std::string entradaSimulada;

class IPAddress {
public:
    bool fromString(const char*) { return true; }
    std::string toString() { return "127.0.0.1"; }
};
class RedSimulada {
public:
    void mode(int) {}
    void setAutoReconnect(bool) {}
    void begin(const char*, const char*) {}
    void reconnect() {}
    int status() { return redSimulada ? WL_CONNECTED : 0; }
    IPAddress localIP() { return IPAddress(); }
};
extern RedSimulada WiFi;

class WiFiClient {
public:
    operator bool() { return conexionSimulada; }
    bool connected() { return conexionSimulada; }
    bool connect(IPAddress, uint16_t, int plazo) {
        ++intentosTcp;
        plazoConexion = plazo;
        conexionSimulada = servidorDisponible;
        return conexionSimulada;
    }
    void setNoDelay(bool) {}
    void stop() { conexionSimulada = false; entradaSimulada.clear(); }
    int fd() { return 7; }
    int available() { return entradaSimulada.size(); }
    int read() {
        if (entradaSimulada.empty()) return -1;
        int letra = (unsigned char) entradaSimulada[0];
        entradaSimulada.erase(0, 1);
        return letra;
    }
};
