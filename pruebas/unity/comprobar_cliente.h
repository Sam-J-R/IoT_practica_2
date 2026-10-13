// Ejecuta cada main.cpp real con red, reloj, GPIO y eco simulados.
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
#include "../../firmware/src/sensor/SensorUltrasonico.cpp"
#include "../../firmware/src/sensor/main.cpp"
#else
#include "../../firmware/src/actuador/IndicadorLeds.cpp"
#include "../../firmware/src/actuador/main.cpp"
#endif

// Antes de cada prueba se reinicia el estado: ninguna depende de la anterior.
void setUp() {
    conexion.desconectar("REINICIO_PRUEBA");
    tiempoSimulado = 0;
    ecoSimulado = 1000;
    redSimulada = servidorDisponible = true;
    envioBloqueadoSimulado = false;
    intentosTcp = plazoConexion = cantidadEscrituras = 0;
    maximoEnvioSimulado = 512;
    entradaSimulada.clear();
    salidaSimulada.clear();
    for (int i = 0; i < 40; i++) nivelesSimulados[i] = LOW;
#ifdef PRUEBA_SENSOR
    limpiarSesion();
#else
    apagarYLimpiar();
#endif
    setup();
}
void tearDown() {}

void registrar() {
    loop();
    TEST_ASSERT_EQUAL_INT(250, plazoConexion);
    TEST_ASSERT_TRUE(salidaSimulada.find("REGISTRO tipo=") != std::string::npos);
    entradaSimulada = "ACEPTADO ";
    loop();
    TEST_ASSERT_FALSE(conexion.registrado());
    entradaSimulada = "REGISTRO\r\n";
    loop();
    TEST_ASSERT_TRUE(conexion.registrado());
    salidaSimulada.clear();
}

void comprobarSesionLimpia() {
#ifdef PRUEBA_SENSOR
    TEST_ASSERT_EQUAL_UINT32(0, numeroLectura);
    TEST_ASSERT_EQUAL_UINT32(0, ultimaRecibida);
#else
    TEST_ASSERT_EQUAL_UINT32(0, numeroOrden);
    TEST_ASSERT_FALSE(habiaOrden);
    TEST_ASSERT_EQUAL_INT(0, nivelesSimulados[33] + nivelesSimulados[25] + nivelesSimulados[26]);
#endif
}

void probarRegistroFragmentado() {
    registrar();
}

void probarReconexionYLimpieza() {
    registrar();
#ifndef PRUEBA_SENSOR
    entradaSimulada = "ORDEN numero=1, estado=ROJO\n";
    loop();
    TEST_ASSERT_EQUAL_INT(HIGH, nivelesSimulados[33]);
#endif
    redSimulada = false;
    loop();
    TEST_ASSERT_FALSE(conexion.registrado());
    comprobarSesionLimpia();
    redSimulada = true;
    int intentosPrevios = intentosTcp;
    tiempoSimulado = 1999;
    loop();
    TEST_ASSERT_EQUAL_INT(intentosPrevios, intentosTcp);
    tiempoSimulado = 2000;
    salidaSimulada.clear();
    registrar();
    TEST_ASSERT_EQUAL_INT(intentosPrevios + 1, intentosTcp);
#ifdef PRUEBA_SENSOR
    TEST_ASSERT_EQUAL_UINT32(1, numeroLectura);
    TEST_ASSERT_EQUAL_UINT32(0, ultimaRecibida);
#else
    comprobarSesionLimpia();
#endif
}

void probarDesconexionTcp() {
    registrar();
#ifndef PRUEBA_SENSOR
    entradaSimulada = "ORDEN numero=1, estado=VERDE\n";
    loop();
    TEST_ASSERT_EQUAL_INT(HIGH, nivelesSimulados[26]);
#endif
    conexionSimulada = false;
    loop();
    TEST_ASSERT_FALSE(conexion.registrado());
    comprobarSesionLimpia();
}

void probarMensajeIncorrecto() {
    registrar();
#ifdef PRUEBA_SENSOR
    entradaSimulada = "RECIBIDO numero=2\n"; // Solo se envió la lectura 1.
#else
    entradaSimulada = "ORDEN numero=1, estado=AZUL\n";
#endif
    loop();
    TEST_ASSERT_FALSE(conexion.registrado());
    comprobarSesionLimpia();
}

void probarEnvioBloqueado() {
    envioBloqueadoSimulado = true;
    loop();
    tiempoSimulado = 999;
    loop();
    TEST_ASSERT_TRUE(conexionSimulada);
    tiempoSimulado = 1000;
    loop();
    TEST_ASSERT_FALSE(conexionSimulada);
}

void probarRegistroSinRespuesta() {
    loop();
    tiempoSimulado = 2999;
    loop();
    TEST_ASSERT_TRUE(conexionSimulada);
    tiempoSimulado = 3000;
    loop();
    TEST_ASSERT_FALSE(conexionSimulada);
}

#ifdef PRUEBA_SENSOR
void probarMuestreoYConfirmaciones() {
    registrar();
    TEST_ASSERT_EQUAL_UINT32(1, numeroLectura);
    entradaSimulada = "RECIBIDO numero=1\n";
    loop();
    tiempoSimulado = 99;
    loop();
    TEST_ASSERT_EQUAL_UINT32(1, numeroLectura);
    tiempoSimulado = 100;
    loop();
    TEST_ASSERT_EQUAL_UINT32(2, numeroLectura);
    tiempoSimulado = 200;
    loop();
    TEST_ASSERT_EQUAL_UINT32(3, numeroLectura);
    entradaSimulada = "RECIBIDO numero=2\nRECIBIDO numero=3\n";
    loop();
    loop();
    TEST_ASSERT_EQUAL_UINT32(3, ultimaRecibida);
    TEST_ASSERT_TRUE(salidaSimulada.find("distancia_cm=17.15") != std::string::npos);
}

void probarEsperaConfirmacionTrasPausa() {
    registrar();
    entradaSimulada = "RECIBIDO numero=1\n";
    loop();
    tiempoSimulado = 1200;
    loop(); // Nueva lectura: empieza su espera después de la pausa.
    TEST_ASSERT_EQUAL_UINT32(2, numeroLectura);
    tiempoSimulado = 1201;
    loop();
    TEST_ASSERT_TRUE(conexion.registrado());
    tiempoSimulado = 2199;
    loop();
    TEST_ASSERT_TRUE(conexion.registrado());
    tiempoSimulado = 2200;
    loop();
    TEST_ASSERT_FALSE(conexion.registrado());
    loop();
    comprobarSesionLimpia();
}
#else
void probarActuacionYConfirmacionParcial() {
    registrar();
    entradaSimulada = "ORDEN numero=1, estado=VERDE\n";
    loop();
    TEST_ASSERT_EQUAL_INT(HIGH, nivelesSimulados[26]);
    maximoEnvioSimulado = 3;
    for (int i = 0; i < 10; i++) loop();
    TEST_ASSERT_TRUE(salidaSimulada == "APLICADO numero=1\n");
}

void probarApagadoSinOrdenes() {
    registrar();
    entradaSimulada = "ORDEN numero=1, estado=VERDE\n";
    loop();
    tiempoSimulado = 2999;
    loop();
    TEST_ASSERT_EQUAL_INT(HIGH, nivelesSimulados[26]);
    tiempoSimulado = 3000;
    loop();
    TEST_ASSERT_EQUAL_INT(0, nivelesSimulados[33] + nivelesSimulados[25] + nivelesSimulados[26]);
    entradaSimulada = "ORDEN numero=2, estado=ROJO\n";
    loop();
    TEST_ASSERT_EQUAL_INT(HIGH, nivelesSimulados[33]);
}
#endif

int main() {
    UNITY_BEGIN();
    RUN_TEST(probarRegistroFragmentado);
    RUN_TEST(probarReconexionYLimpieza);
    RUN_TEST(probarDesconexionTcp);
    RUN_TEST(probarMensajeIncorrecto);
    RUN_TEST(probarEnvioBloqueado);
    RUN_TEST(probarRegistroSinRespuesta);
#ifdef PRUEBA_SENSOR
    RUN_TEST(probarMuestreoYConfirmaciones);
    RUN_TEST(probarEsperaConfirmacionTrasPausa);
#else
    RUN_TEST(probarActuacionYConfirmacionParcial);
    RUN_TEST(probarApagadoSinOrdenes);
#endif
    return UNITY_END();
}
