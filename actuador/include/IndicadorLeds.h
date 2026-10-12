#pragma once
#include <Arduino.h>

/**
 * @brief Salidas exclusivas del semáforo LED:
 * apaga todo antes de activar un color.
 */
class IndicadorLeds {
public:
    IndicadorLeds(int pinRojo, int pinAmarillo, int pinVerde);

    void iniciar();
    void apagar();
    bool aplicar(String estado);

private:
    int rojo;
    int amarillo;
    int verde;
};
