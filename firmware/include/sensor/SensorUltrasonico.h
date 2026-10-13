#pragma once
#include <Arduino.h>

/**
 * @brief Adquisición física con sensor ultrasónico HC-SR04.
 * No clasifica distancias ni decide los LEDs.
 */
class SensorUltrasonico {
public:
    SensorUltrasonico(int disparo, int eco);

    void iniciar();

    /** Devuelve false si no hubo eco; la salida conserva los cm sin filtrar. */
    bool medir(float& distanciaCm);

private:
    int pinDisparo;
    int pinEco;
    const unsigned long esperaEcoUs = 30000;
    const float centimetrosPorMicrosegundo = 0.01715f;
};
