// Pruebas Unity en PC: no requieren ESP32 ni un sensor conectado.
#include <unity.h>
#include "../../../comun/ProtocoloAplicacion.h"
#include "../../../sensor/include/SensorUltrasonico.h"
#include "../../../actuador/include/IndicadorLeds.h"

int nivelesSimulados[40] = {};
int escriturasSimuladas[128][2] = {};
int cantidadEscrituras = 0;
unsigned long ecoSimulado = 0;

void setUp() {
    for (int i = 0; i < 40; i++) nivelesSimulados[i] = LOW;
    cantidadEscrituras = 0;
    ecoSimulado = 0;
}
void tearDown() {}

void probarNumerosDelProtocolo() {
    unsigned long numero = 0;
    TEST_ASSERT_TRUE(ProtocoloAplicacion::entero("4294967295", numero));
    TEST_ASSERT_EQUAL_UINT32(4294967295UL, numero);
    TEST_ASSERT_FALSE(ProtocoloAplicacion::entero("4294967296", numero));
    TEST_ASSERT_FALSE(ProtocoloAplicacion::entero("-1", numero));
    TEST_ASSERT_FALSE(ProtocoloAplicacion::entero("1.0", numero));
    TEST_ASSERT_FALSE(ProtocoloAplicacion::entero("", numero));
}

void probarOrdenConParametros() {
    ProtocoloAplicacion mensaje;
    TEST_ASSERT_TRUE(mensaje.interpretar("ORDEN numero=81, estado=AMARILLO"));
    TEST_ASSERT_TRUE(mensaje.comando == "ORDEN");
    TEST_ASSERT_TRUE(mensaje.obtener("estado") == "AMARILLO");
    TEST_ASSERT_TRUE(mensaje.obtener("numero") == "81");
    TEST_ASSERT_TRUE(mensaje.interpretar("ORDEN estado=ROJO,numero=2"));
    TEST_ASSERT_TRUE(mensaje.obtener("numero") == "2");
}

void probarConfirmacion() {
    ProtocoloAplicacion mensaje;
    mensaje.interpretar("ORDEN numero=1, estado=VERDE");
    TEST_ASSERT_TRUE(mensaje.interpretar("RECIBIDO numero=3"));
    TEST_ASSERT_EQUAL_INT(1, mensaje.cantidad);
    TEST_ASSERT_TRUE(mensaje.obtener("estado") == "");
}

void probarMensajesIncorrectos() {
    ProtocoloAplicacion mensaje;
    TEST_ASSERT_FALSE(mensaje.interpretar("ORDEN"));
    TEST_ASSERT_FALSE(mensaje.interpretar("ORDEN numero="));
    TEST_ASSERT_FALSE(mensaje.interpretar("ORDEN numero=1, numero=2"));
    TEST_ASSERT_FALSE(mensaje.interpretar("ORDEN numero=1,"));
    TEST_ASSERT_FALSE(mensaje.interpretar("ORDEN Numero=1"));
    TEST_ASSERT_FALSE(mensaje.interpretar("ORDEN numero=1, estado=VE-RDE"));
    TEST_ASSERT_FALSE(mensaje.interpretar("ORDEN numero=1, estado=VERDE, otro=1, extra=2"));
    String larga;
    for (int i = 0; i < 128; i++) larga += 'a';
    TEST_ASSERT_FALSE(mensaje.interpretar(larga));
}

void probarColoresExclusivos() {
    IndicadorLeds indicador(33, 25, 26);
    TEST_ASSERT_TRUE(indicador.aplicar("ROJO"));
    TEST_ASSERT_EQUAL_INT(HIGH, nivelesSimulados[33]);
    TEST_ASSERT_EQUAL_INT(LOW, nivelesSimulados[25] + nivelesSimulados[26]);
    TEST_ASSERT_TRUE(indicador.aplicar("AMARILLO"));
    TEST_ASSERT_EQUAL_INT(HIGH, nivelesSimulados[25]);
    TEST_ASSERT_EQUAL_INT(LOW, nivelesSimulados[33] + nivelesSimulados[26]);
    TEST_ASSERT_TRUE(indicador.aplicar("VERDE"));
    TEST_ASSERT_EQUAL_INT(HIGH, nivelesSimulados[26]);
    TEST_ASSERT_EQUAL_INT(LOW, nivelesSimulados[33] + nivelesSimulados[25]);
}

void probarApagadoAntesDelCambio() {
    IndicadorLeds indicador(33, 25, 26);
    indicador.aplicar("VERDE");
    cantidadEscrituras = 0;
    indicador.aplicar("ROJO");
    TEST_ASSERT_EQUAL_INT(4, cantidadEscrituras);
    for (int i = 0; i < 3; i++) TEST_ASSERT_EQUAL_INT(LOW, escriturasSimuladas[i][1]);
    TEST_ASSERT_EQUAL_INT(33, escriturasSimuladas[3][0]);
    TEST_ASSERT_EQUAL_INT(HIGH, escriturasSimuladas[3][1]);
}

void probarApagadoYEstadoIncorrecto() {
    IndicadorLeds indicador(33, 25, 26);
    indicador.aplicar("ROJO");
    TEST_ASSERT_TRUE(indicador.aplicar("APAGADO"));
    TEST_ASSERT_EQUAL_INT(0, nivelesSimulados[33] + nivelesSimulados[25] + nivelesSimulados[26]);
    TEST_ASSERT_FALSE(indicador.aplicar("AZUL"));
    TEST_ASSERT_FALSE(indicador.aplicar(""));
}

void probarConversionDelEco() {
    SensorUltrasonico sensor(14, 27);
    float distancia = 0;
    ecoSimulado = 1000;
    TEST_ASSERT_TRUE(sensor.medir(distancia));
    TEST_ASSERT_FLOAT_WITHIN(0.001, 17.15, distancia);
}

void probarAusenciaDeEcoYLimite() {
    SensorUltrasonico sensor(14, 27);
    float distancia = 0;
    TEST_ASSERT_FALSE(sensor.medir(distancia));
    ecoSimulado = 30000;
    TEST_ASSERT_FALSE(sensor.medir(distancia));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(probarNumerosDelProtocolo);
    RUN_TEST(probarOrdenConParametros);
    RUN_TEST(probarConfirmacion);
    RUN_TEST(probarMensajesIncorrectos);
    RUN_TEST(probarColoresExclusivos);
    RUN_TEST(probarApagadoAntesDelCambio);
    RUN_TEST(probarApagadoYEstadoIncorrecto);
    RUN_TEST(probarConversionDelEco);
    RUN_TEST(probarAusenciaDeEcoYLimite);
    return UNITY_END();
}
