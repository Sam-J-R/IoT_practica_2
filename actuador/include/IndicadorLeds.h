#pragma once
#include <Arduino.h>

/** Salidas exclusivas: apagar todo antes de activar un color. */
class IndicadorLeds {
public:
    IndicadorLeds(int pinRojo, int pinAmarillo, int pinVerde) {
        rojo = pinRojo;
        amarillo = pinAmarillo;
        verde = pinVerde;
    }
    void iniciar() {
        pinMode(rojo, OUTPUT);
        pinMode(amarillo, OUTPUT);
        pinMode(verde, OUTPUT);
        apagar();
    }
    void apagar() {
        digitalWrite(rojo, LOW);
        digitalWrite(amarillo, LOW);
        digitalWrite(verde, LOW);
    }
    bool aplicar(String estado) {
        int pin = -1;
        if (estado == "ROJO") pin = rojo;
        else if (estado == "AMARILLO") pin = amarillo;
        else if (estado == "VERDE") pin = verde;
        else if (estado != "APAGADO") return false;
        apagar();
        if (pin >= 0) digitalWrite(pin, HIGH);
        return true;
    }
private:
    int rojo;
    int amarillo;
    int verde;
};
