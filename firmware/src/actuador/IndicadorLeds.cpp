#include "IndicadorLeds.h"

IndicadorLeds::IndicadorLeds(int pinRojo, int pinAmarillo, int pinVerde) {
    rojo = pinRojo;
    amarillo = pinAmarillo;
    verde = pinVerde;
}

void IndicadorLeds::iniciar() {
    pinMode(rojo, OUTPUT);
    pinMode(amarillo, OUTPUT);
    pinMode(verde, OUTPUT);
    apagar();
}

void IndicadorLeds::apagar() {
    digitalWrite(rojo, LOW);
    digitalWrite(amarillo, LOW);
    digitalWrite(verde, LOW);
}

bool IndicadorLeds::aplicar(String estado) {
    int pin = -1;
    if (estado == "ROJO") pin = rojo;
    else if (estado == "AMARILLO") pin = amarillo;
    else if (estado == "VERDE") pin = verde;
    else if (estado != "APAGADO") return false;
    apagar();
    if (pin >= 0) digitalWrite(pin, HIGH);
    return true;
}
