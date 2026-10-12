#pragma once
// Doble de laboratorio: simula GPIO y eco solo para pruebas en la PC.
#include <stdint.h>
#include <string>
#include <sstream>
#include <iomanip>
#include <stdio.h>
#include <string.h>
const int LOW = 0;
const int HIGH = 1;
const int INPUT = 0;
const int OUTPUT = 1;
extern int nivelesSimulados[40];
extern unsigned long ecoSimulado;
extern int escriturasSimuladas[128][2];
extern int cantidadEscrituras;
extern unsigned long tiempoSimulado;
inline unsigned long millis() { return tiempoSimulado; }

// Sustituto de String para ejecutar el código de Arduino en una PC.
class String {
public:
    String() {}
    String(const char* valor) : texto(valor ? valor : "") {}
    String(std::string valor) : texto(valor) {}
    String(unsigned long valor) : texto(std::to_string(valor)) {}
    String(float valor, int decimales) {
        std::ostringstream salida;
        salida << std::fixed << std::setprecision(decimales) << valor;
        texto = salida.str();
    }
    int length() const { return texto.size(); }
    const char* c_str() const { return texto.c_str(); }
    void reserve(int espacio) { texto.reserve(espacio); }
    int indexOf(char letra) const {
        auto posicion = texto.find(letra);
        return posicion == std::string::npos ? -1 : posicion;
    }
    String substring(int desde) const { return texto.substr(desde); }
    String substring(int desde, int hasta) const { return texto.substr(desde, hasta - desde); }
    bool startsWith(String prefijo) const { return texto.compare(0, prefijo.length(), prefijo.texto) == 0; }
    bool endsWith(String sufijo) const {
        return length() >= sufijo.length() && texto.compare(length() - sufijo.length(), sufijo.length(), sufijo.texto) == 0;
    }
    void remove(int desde) { texto.erase(desde); }
    void remove(int desde, int cantidad) { texto.erase(desde, cantidad); }
    char operator[](int posicion) const { return texto[posicion]; }
    bool operator==(String otra) const { return texto == otra.texto; }
    bool operator!=(String otra) const { return texto != otra.texto; }
    String& operator+=(String otra) { texto += otra.texto; return *this; }
    String& operator+=(char letra) { texto += letra; return *this; }
    friend String operator+(String una, String otra) { return una.texto + otra.texto; }
private:
    std::string texto;
};

class PuertoSerieSimulado {
public:
    void begin(int) {}
    void println(const char*) {}
    void println(String) {}
    void printf(const char*, ...) {}
};
extern PuertoSerieSimulado Serial;
inline void pinMode(int, int) {}
inline void delayMicroseconds(unsigned long) {}
inline void digitalWrite(int pin, int nivel) {
    nivelesSimulados[pin] = nivel;
    if (cantidadEscrituras < 128) {
        escriturasSimuladas[cantidadEscrituras][0] = pin;
        escriturasSimuladas[cantidadEscrituras][1] = nivel;
        cantidadEscrituras++;
    }
}
inline unsigned long pulseIn(int, int, unsigned long) { return ecoSimulado; }
