// Compila cada main.cpp real con red, reloj, GPIO y eco simulados.
// Los tipos avanzados de estos dobles pertenecen a pruebas, no al firmware.
#include <unity.h>
#include "../dobles/Arduino.h"
#include "../dobles/WiFi.h"

int nivelesSimulados[40] = {};
unsigned long ecoSimulado = 1000;
unsigned long tiempoSimulado = 0;
int escriturasSimuladas[128][2] = {};
int cantidadEscrituras = 0;
PuertoSerieSimulado Serial;
RedSimulada WiFi;
bool redSimulada = true;
bool servidorDisponible = true;
bool conexionSimulada = false;
bool envioBloqueadoSimulado = false;
int intentosTcp = 0;
int plazoConexion = 0;
int maximoEnvioSimulado = 512;
std::string entradaSimulada;
std::string salidaSimulada;

#ifdef PRUEBA_SENSOR
#include "../../sensor/src/main.cpp"
#else
#include "../../actuador/src/main.cpp"
#endif

void registrar() {
    loop();
    TEST_ASSERT_TRUE(plazoConexion == 250);
    TEST_ASSERT_TRUE(salidaSimulada.find("REGISTRO tipo=") != std::string::npos);
    // Una respuesta fragmentada no habilita prematuramente la sesión.
    entradaSimulada = "ACEPTADO ";
    loop();
    TEST_ASSERT_TRUE(!conexion.registrado());
    entradaSimulada = "REGISTRO\r\n";
    loop();
    TEST_ASSERT_TRUE(conexion.registrado());
    salidaSimulada.clear();
}

void comprobarProgramaCompleto() {
    setup();
    registrar();
#ifdef PRUEBA_SENSOR
    TEST_ASSERT_TRUE(numeroLectura == 1);
    entradaSimulada = "RECIBIDO numero=1\n";
    loop();
    TEST_ASSERT_TRUE(ultimaRecibida == 1);
    // La adquisición sigue cada 100 ms; dos respuestas juntas se conservan.
    tiempoSimulado = 100;
    loop();
    tiempoSimulado = 200;
    loop();
    entradaSimulada = "RECIBIDO numero=2\nRECIBIDO numero=3\n";
    loop();
    loop();
    TEST_ASSERT_TRUE(ultimaRecibida == 3);
    TEST_ASSERT_TRUE(salidaSimulada.find("distancia_cm=17.15") != std::string::npos);
    tiempoSimulado = 1200;
    loop();
    TEST_ASSERT_TRUE(conexion.registrado()); // No hay pendientes antes de esta nueva lectura.
    tiempoSimulado = 1201;
    loop();
    TEST_ASSERT_TRUE(!conexion.registrado()); // No llegó confirmación en un segundo.
    loop();
    TEST_ASSERT_TRUE(numeroLectura == 0 && ultimaRecibida == 0);
#else
    entradaSimulada = "ORDEN numero=1, estado=VERDE\n";
    loop();
    TEST_ASSERT_TRUE(nivelesSimulados[26] == HIGH);
    // Envíos parciales mantienen todos los bytes y su orden.
    maximoEnvioSimulado = 3;
    for (int i = 0; i < 10; ++i) loop();
    TEST_ASSERT_TRUE(salidaSimulada == "APLICADO numero=1\n");
    maximoEnvioSimulado = 512;
    tiempoSimulado = 2999;
    loop();
    TEST_ASSERT_TRUE(nivelesSimulados[26] == HIGH);
    tiempoSimulado = 3000;
    loop();
    TEST_ASSERT_TRUE(nivelesSimulados[26] == LOW);
    entradaSimulada = "ORDEN numero=2, estado=ROJO\n";
    loop();
    TEST_ASSERT_TRUE(nivelesSimulados[33] == HIGH);
    redSimulada = false;
    loop();
    TEST_ASSERT_TRUE(nivelesSimulados[33] == LOW && !conexion.registrado());
    redSimulada = true;
#endif
    // No reconectar antes de dos segundos; volver a registrar con búfer limpio.
    int intentosPrevios = intentosTcp;
    tiempoSimulado += 1999;
    loop();
    TEST_ASSERT_TRUE(intentosTcp == intentosPrevios);
    ++tiempoSimulado;
    salidaSimulada.clear();
    registrar();
    TEST_ASSERT_TRUE(intentosTcp == intentosPrevios + 1);
#ifdef PRUEBA_SENSOR
    TEST_ASSERT_TRUE(numeroLectura == 1 && ultimaRecibida == 0);
    entradaSimulada = "RECIBIDO numero=2\n";
#else
    TEST_ASSERT_TRUE(numeroOrden == 0 && !habiaOrden);
    entradaSimulada = "ORDEN numero=1, estado=AZUL\n";
#endif
    loop();
    TEST_ASSERT_TRUE(!conexion.registrado());
    TEST_ASSERT_TRUE(nivelesSimulados[33] + nivelesSimulados[25] + nivelesSimulados[26] == 0);
    // Un envío que nunca avanza tampoco bloquea el loop ni espera indefinidamente.
    tiempoSimulado += 2000;
    envioBloqueadoSimulado = true;
    loop();
    tiempoSimulado += 1000;
    loop();
    TEST_ASSERT_TRUE(!conexionSimulada);
    envioBloqueadoSimulado = false;
    tiempoSimulado += 2000;
    loop();
    TEST_ASSERT_TRUE(conexionSimulada && !conexion.registrado());
    tiempoSimulado += 2999;
    loop();
    TEST_ASSERT_TRUE(conexionSimulada);
    ++tiempoSimulado;
    loop();
    TEST_ASSERT_TRUE(!conexionSimulada);
}

void setUp() {}
void tearDown() {}
int main() {
    UNITY_BEGIN();
    RUN_TEST(comprobarProgramaCompleto);
    return UNITY_END();
}
