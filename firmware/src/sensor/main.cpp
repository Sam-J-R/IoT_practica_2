#include <Arduino.h>
#include <WiFi.h>
#if __has_include("ConfiguracionRed.h")
#include "ConfiguracionRed.h"
#else
#include "ConfiguracionRedEjemplo.h"
#endif
#include "SensorUltrasonico.h"
#include "ClienteTcp.h"
#include "ProtocoloAplicacion.h"

const unsigned long intervaloLecturaMs = 100;
SensorUltrasonico sensor(14, 27);
unsigned long ultimaLectura = 0;
unsigned long numeroLectura = 0;
unsigned long ultimaRecibida = 0;
unsigned long inicioEsperaConfirmacion = 0;
bool estabaRegistrado = false;

ClienteTcp conexion(nombreRed, claveRed, direccionServidor, puertoServidor,
                    "sensor");

void limpiarSesion() {
    numeroLectura = ultimaRecibida = 0;
    inicioEsperaConfirmacion = 0;
    estabaRegistrado = false;
}

void recibirMensaje(String linea) {
    ProtocoloAplicacion mensaje;
    unsigned long numero;
    if (!mensaje.interpretar(linea) ||
        mensaje.comando != "RECIBIDO" || mensaje.cantidad != 1 ||
        !ProtocoloAplicacion::entero(mensaje.obtener("numero"), numero) ||
        numero <= ultimaRecibida || numero > numeroLectura) {
        conexion.desconectar("RESPUESTA_INVALIDA");
        return;
    }
    ultimaRecibida = numero;
    inicioEsperaConfirmacion = millis();
}

void setup() {
    Serial.begin(115200);
    sensor.iniciar();
    Serial.printf("INICIO_SENSOR tiempo_ms=%lu\n", millis());
    conexion.iniciar();
    conexion.activarDepuracion(depuracionActiva);
}

void loop() {
    conexion.actualizar();
    if (!conexion.registrado()) {
        limpiarSesion();
        return;
    }
    String respuesta;
    if (conexion.recibirMensaje(respuesta)) recibirMensaje(respuesta);
    if (!conexion.registrado()) {
        limpiarSesion();
        return;
    }
    unsigned long ahora = millis();
    if (!estabaRegistrado) {
        estabaRegistrado = true;
        ultimaLectura = ahora - intervaloLecturaMs;
    }
    if (numeroLectura > ultimaRecibida && ahora - inicioEsperaConfirmacion >= 1000) {
        conexion.desconectar("LECTURA_SIN_CONFIRMACION");
        return;
    }
    if (ahora - ultimaLectura < intervaloLecturaMs) return;
    ultimaLectura = ahora;
    if (numeroLectura == 4294967295UL) {
        conexion.desconectar("REINICIAR_SECUENCIA");
        return;
    }
    // Si todo estaba confirmado, esta lectura inicia una nueva espera.
    // El tiempo sin lecturas pendientes no consume el plazo de un segundo.
    if (numeroLectura == ultimaRecibida) inicioEsperaConfirmacion = ahora;
    ++numeroLectura;
    float distanciaCm = 0;
    bool hayEco = sensor.medir(distanciaCm);
    String valor = "SIN_ECO";
    if (hayEco) valor = String(distanciaCm, 2);
    String mensaje = "LECTURA numero=" + String(numeroLectura);
    mensaje += ", tiempo_ms=" + String(ahora);
    mensaje += ", distancia_cm=" + valor;
    if (conexion.enviar(mensaje)) Serial.println(mensaje);
}
