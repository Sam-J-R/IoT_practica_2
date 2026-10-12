#pragma once
#include <Arduino.h>

// Lee una línea: comando y hasta tres parámetros clave=valor.
// Ejemplo: ORDEN numero=1, estado=ROJO
class ProtocoloAplicacion {
public:
    String comando;
    int cantidad = 0;
    static const int maximoMensaje = 128;

    String obtener(String nombre) {
        for (int i = 0; i < cantidad; i++) {
            if (claves[i] == nombre) return valores[i];
        }
        return ""; // El parámetro no existe.
    }

    bool interpretar(String linea) {
        cantidad = 0;
        if ((int) linea.length() >= maximoMensaje) return false;
        int espacio = linea.indexOf(' ');
        if (espacio <= 0) return false;
        comando = linea.substring(0, espacio);
        String pendientes = linea.substring(espacio + 1);

        while (pendientes.length() > 0) {
            if (cantidad == 3) return false;
            int coma = pendientes.indexOf(',');
            String campo = pendientes;
            if (coma >= 0) campo = pendientes.substring(0, coma);
            int igual = campo.indexOf('=');
            if (igual <= 0) return false;
            String clave = campo.substring(0, igual);
            String valor = campo.substring(igual + 1);
            if (valor.length() == 0 || obtener(clave) != "") return false;

            for (int i = 0; i < (int) clave.length(); i++) {
                char letra = clave[i];
                if (!((letra >= 'a' && letra <= 'z') || letra == '_')) return false;
            }
            for (int i = 0; i < (int) valor.length(); i++) {
                char letra = valor[i];
                bool permitida = (letra >= 'a' && letra <= 'z') ||
                                 (letra >= 'A' && letra <= 'Z') ||
                                 (letra >= '0' && letra <= '9') || letra == '_' || letra == '.';
                if (!permitida) return false;
            }
            claves[cantidad] = clave;
            valores[cantidad] = valor;
            cantidad++;
            if (coma < 0) return true;
            pendientes = pendientes.substring(coma + 1);
            if (pendientes.startsWith(" ")) pendientes = pendientes.substring(1);
            if (pendientes.length() == 0) return false;
        }
        return false;
    }

    static bool entero(String texto, unsigned long& numero) {
        if (texto.length() == 0) return false;
        unsigned long resultado = 0;
        for (int i = 0; i < (int) texto.length(); i++) {
            if (texto[i] < '0' || texto[i] > '9') return false;
            int digito = texto[i] - '0';
            // El protocolo permite números de hasta 32 bits, sin signo.
            if (resultado > (4294967295UL - digito) / 10) return false;
            resultado = resultado * 10 + digito;
        }
        numero = resultado;
        return true;
    }

private:
    String claves[3];
    String valores[3];
};
