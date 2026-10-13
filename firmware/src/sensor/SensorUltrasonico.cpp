#include "SensorUltrasonico.h"

SensorUltrasonico::SensorUltrasonico(int disparo, int eco) {
    pinDisparo = disparo;
    pinEco = eco;
}

void SensorUltrasonico::iniciar() {
    pinMode(pinDisparo, OUTPUT);
    pinMode(pinEco, INPUT);
    digitalWrite(pinDisparo, LOW);
}

bool SensorUltrasonico::medir(float& distanciaCm) {
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
