#pragma once
#include <string>
#include <errno.h>
const int MSG_DONTWAIT = 1;
extern std::string salidaSimulada;
extern int maximoEnvioSimulado;
extern bool envioBloqueadoSimulado;
inline int send(int, const void* datos, size_t longitud, int) {
    if (envioBloqueadoSimulado) { errno = EAGAIN; return -1; }
    int cantidad = longitud;
    if (cantidad > maximoEnvioSimulado) cantidad = maximoEnvioSimulado;
    salidaSimulada.append((const char*) datos, cantidad);
    return cantidad;
}
