// Ensayos C++ compilables con g++ sin placas ni PlatformIO.
// Se emplean dobles de Arduino. No reemplazan las pruebas con hardware real.
#include <cassert>
#include <cmath>
#include <iostream>
#include "ProtocoloAplicacion.h"
#include "SensorUltrasonico.h"
#include "IndicadorLeds.h"

int nivelesSimulados[40] = {};
unsigned long ecoSimulado = 0;
int escriturasSimuladas[128][2] = {};
int cantidadEscrituras = 0;
unsigned long tiempoSimulado = 0;
PuertoSerieSimulado Serial;

int main() {
    int aprobadas = 0;
    ProtocoloAplicacion protocolo;
    assert(protocolo.interpretar("ORDEN numero=5, estado=AMARILLO"));
    assert(protocolo.obtener("estado") == "AMARILLO");
    ++aprobadas;
    assert(!protocolo.interpretar("ORDEN numero=1, numero=2"));
    ++aprobadas;
    unsigned long numero = 0;
    assert(ProtocoloAplicacion::entero("4294967295", numero) && numero == 4294967295UL);
    assert(!ProtocoloAplicacion::entero("4294967296", numero));
    ++aprobadas;

    SensorUltrasonico sensor(14, 27);
    sensor.iniciar();
    float distancia = 0;
    ecoSimulado = 1000;
    assert(sensor.medir(distancia) && std::fabs(distancia - 17.15f) < .01);
    ++aprobadas;
    ecoSimulado = 0;
    assert(!sensor.medir(distancia));
    ++aprobadas;
    ecoSimulado = 30000;
    assert(!sensor.medir(distancia));
    ++aprobadas;

    IndicadorLeds leds(33,25,26);
    leds.iniciar();
    assert(leds.aplicar("ROJO") && nivelesSimulados[33] == HIGH && nivelesSimulados[25] == LOW);
    ++aprobadas;
    assert(leds.aplicar("AMARILLO") && nivelesSimulados[25] == HIGH && nivelesSimulados[33] == LOW);
    assert(leds.aplicar("VERDE") && nivelesSimulados[26] == HIGH && nivelesSimulados[25] == LOW);
    ++aprobadas;
    assert(leds.aplicar("APAGADO") && nivelesSimulados[33] + nivelesSimulados[25] + nivelesSimulados[26] == 0);
    assert(!leds.aplicar("AZUL"));
    ++aprobadas;
    std::cout << "APROBADO: " << aprobadas << " verificaciones C++ con dobles de hardware\n";
    return 0;
}
