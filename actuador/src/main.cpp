#include <Arduino.h>
#include <WiFi.h>
#if __has_include("../../comun/ConfiguracionRed.h")
#include "../../comun/ConfiguracionRed.h"
#else
#include "../../comun/ConfiguracionRedEjemplo.h"
#endif
#include "IndicadorLeds.h"
#include "../../comun/ClienteTcp.h"
#include "../../comun/ProtocoloAplicacion.h"

const unsigned long esperaOrdenMs = 3000;
IndicadorLeds indicador(33, 25, 26);
unsigned long ultimaOrden = 0;
unsigned long numeroOrden = 0;
bool habiaOrden = false;

ClienteTcp conexion(nombreRed, claveRed, direccionServidor, puertoServidor,
                    "actuador");

void apagarYLimpiar() {
    indicador.apagar();
    numeroOrden = 0;
    habiaOrden = false;
}

void recibirMensaje(String linea) {
    ProtocoloAplicacion mensaje;
    unsigned long numero;
    if (!mensaje.interpretar(linea) ||
        mensaje.comando != "ORDEN" || mensaje.cantidad != 2 ||
        !ProtocoloAplicacion::entero(mensaje.obtener("numero"), numero) ||
        numero <= numeroOrden || !indicador.aplicar(mensaje.obtener("estado"))) {
        conexion.desconectar("ORDEN_INVALIDA");
        return;
    }
    numeroOrden = numero;
    ultimaOrden = millis();
    habiaOrden = true;
    // Confirmar después de ejecutar digitalWrite; no es una medición óptica.
    conexion.enviar("APLICADO numero=" + String(numero));
    Serial.printf("APLICADO numero=%lu estado=%s tiempo_ms=%lu\n",
                  numero, mensaje.obtener("estado").c_str(), millis());
}

void setup() {
    Serial.begin(115200);
    indicador.iniciar();
    Serial.printf("INICIO_ACTUADOR tiempo_ms=%lu\n", millis());
    conexion.iniciar();
    conexion.activarDepuracion(depuracionActiva);
}

void comprobarOrdenVencida() {
    if (habiaOrden && millis() - ultimaOrden >= esperaOrdenMs) {
        indicador.apagar();
        habiaOrden = false;
        Serial.println("APAGADO motivo=ORDEN_VENCIDA");
    }
}

void loop() {
    // Revisar antes y después de atender el transporte, cuyos intentos duran <=250 ms.
    comprobarOrdenVencida();
    conexion.actualizar();
    if (!conexion.registrado()) {
        apagarYLimpiar();
        return;
    }
    String orden;
    if (conexion.recibirMensaje(orden)) recibirMensaje(orden);
    if (!conexion.registrado()) {
        apagarYLimpiar();
        return;
    }
    comprobarOrdenVencida();
}
