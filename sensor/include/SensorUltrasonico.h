#pragma once
#include <Arduino.h>

/** Adquisición física; no clasifica distancias ni decide los LEDs. */
class SensorUltrasonico {
public:
    SensorUltrasonico(int disparo, int eco) {
        pinDisparo = disparo;
        pinEco = eco;
    }

    void iniciar() {
        pinMode(pinDisparo, OUTPUT);
        pinMode(pinEco, INPUT);
        digitalWrite(pinDisparo, LOW);
    }

    /** Devuelve false si no hubo eco; la salida conserva los cm sin filtrar. */
    bool medir(float& distanciaCm) {
        digitalWrite(pinDisparo, LOW);
        delayMicroseconds(2);
        digitalWrite(pinDisparo, HIGH);
        delayMicroseconds(10);
        digitalWrite(pinDisparo, LOW);
        unsigned long duracion = pulseIn(pinEco, HIGH, esperaEcoUs);
        if (!duracion) return false;
        distanciaCm = duracion * centimetrosPorMicrosegundo;
        // El protocolo solo representa distancias de 0 a 400 cm.
        return distanciaCm <= 400.0f;
    }

private:
    int pinDisparo;
    int pinEco;
    const unsigned long esperaEcoUs = 30000;
    const float centimetrosPorMicrosegundo = 0.01715f;
};
