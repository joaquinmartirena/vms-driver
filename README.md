# vms-driver

Driver NTCIP 1203 sobre SNMP v2c para paneles VMS/DMS de señalización variable.
Implementación inicial para **Daktronics VFC** (panel full-matrix 144×96 px, ámbar).

---

## Tabla de contenidos

- [Arquitectura](#arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Capa SNMP](#capa-snmp)
- [Capa de OIDs](#capa-de-oids)
- [Interfaz de driver](#interfaz-de-driver)
- [Driver Daktronics VFC](#driver-daktronics-vfc)
- [Dispositivo de referencia](#dispositivo-de-referencia)
- [Quirks del dispositivo](#quirks-del-dispositivo)
- [Uso rápido](#uso-rápido)
- [Dependencias](#dependencias)

---

## Arquitectura

```
┌─────────────────────────────────────────┐
│           Aplicación / API              │
└────────────────────┬────────────────────┘
                     │ VMSDriver (interfaz)
┌────────────────────▼────────────────────┐
│         DaktronicsVFCDriver             │  driver/daktronics/driver.py
│   send_message · get_status · clear     │
└────────────────────┬────────────────────┘
                     │ importa OIDs desde
┌────────────────────▼────────────────────┐
│      driver/daktronics/oids.py          │  constantes del dispositivo
│      (re-exporta snmp/ntcip1203.py)     │  + quirks Daktronics
└────────────────────┬────────────────────┘
                     │ OIDs estándar
┌────────────────────▼────────────────────┐
│         snmp/ntcip1203.py               │  OIDs NTCIP 1203 v03
│   7 grupos · helpers dmsMessageTable    │  válidos para cualquier fabricante
└────────────────────┬────────────────────┘
                     │ transporte
┌────────────────────▼────────────────────┐
│           snmp/client.py                │  SNMPClient — get / set / walk
│           pysnmp v7 (asyncio)           │  SNMP v2c (mpModel=1)
└─────────────────────────────────────────┘
```

El sistema está diseñado para soportar múltiples fabricantes: cada uno implementa
`VMSDriver` sin que el resto del sistema sepa qué hardware hay debajo.

---

## Estructura del proyecto

```
vms-driver/
├── snmp/
│   ├── client.py          # SNMPClient: get, set, walk (pysnmp v7 asyncio)
│   └── ntcip1203.py       # OIDs estándar NTCIP 1203 v03 + helpers
│
├── driver/
│   ├── base.py            # VMSDriver — interfaz abstracta
│   ├── factory.py         # (pendiente) factory por fabricante/modelo
│   └── daktronics/
│       ├── driver.py      # DaktronicsVFCDriver — implementación completa
│       ├── oids.py        # Constantes del dispositivo + re-export ntcip1203
│       ├── multi.py       # (pendiente) helpers lenguaje MULTI
│       └── slots.py       # (pendiente) gestión de slots de memoria
│
└── models/
    └── device.py          # DeviceStatus, Message, MessageStatus, ControlMode, …
```

---

## Capa SNMP

**`snmp/client.py`** — `SNMPClient`

Cliente SNMP v2c sincrónico que envuelve la API asyncio de pysnmp v7.

```python
from snmp.client import SNMPClient

client = SNMPClient(ip="66.17.99.157", community="public")
value  = client.get("1.3.6.1.2.1.1.1.0")   # GET
client.set("1.3.6.1.4.1.1206.4.2.3.6.1.0", 4)  # SET
pairs  = client.walk("1.3.6.1.4.1.1206.4.2.3")  # WALK → list[(oid, value)]
```

| Parámetro   | Default | Descripción                        |
|-------------|---------|------------------------------------|
| `ip`        | —       | Dirección IP del panel             |
| `community` | —       | Community string (read o write)    |
| `port`      | `161`   | Puerto UDP                         |
| `timeout`   | `10`    | Segundos por intento               |
| `retries`   | `3`     | Reintentos ante timeout            |

El tipo del `value` en `set()` se resuelve automáticamente:
`int` → `Integer32`, `str`/`bytes` → `OctetString`, tipo SNMP nativo → se usa tal cual.

---

## Capa de OIDs

### `snmp/ntcip1203.py` — Estándar NTCIP 1203 v03

OIDs válidos para cualquier fabricante que implemente el estándar.
Base: `1.3.6.1.4.1.1206.4.2.3`

| Grupo | Base OID | Constantes principales |
|---|---|---|
| `dmsSignCfg` | `.1.X.0` | `DMS_SIGN_TYPE`, `DMS_SIGN_HEIGHT`, `DMS_SIGN_WIDTH`, `DMS_HORIZONTAL_BORDER`, `DMS_VERTICAL_BORDER`, `DMS_SIGN_TECHNOLOGY` |
| `vmsCfg` | `.2.X.0` | `VMS_SIGN_HEIGHT_PIXELS`, `VMS_SIGN_WIDTH_PIXELS`, `VMS_HORIZONTAL_PITCH`, `VMS_VERTICAL_PITCH`, `VMS_MONOCHROME_COLOR` |
| `multiCfg` | `.4.X.0` | `MULTI_DEFAULT_FONT`, `MULTI_DEFAULT_JUSTIFICATION_LINE`, `MULTI_DEFAULT_JUSTIFICATION_PAGE`, `MULTI_DEFAULT_PAGE_ON_TIME`, `MULTI_COLOR_SCHEME`, `MULTI_DEFAULT_FOREGROUND_RGB`, `MULTI_MAX_MULTI_STRING_LENGTH` |
| `dmsMessage` (escalares) | `.5.X.0` | `DMS_NUM_CHANGEABLE_MSG`, `DMS_MAX_CHANGEABLE_MSG`, `DMS_FREE_CHANGEABLE_MEMORY`, `DMS_MAX_VOLATILE_MSG` |
| `dmsMessageTable` | `.5.8.1.X` | `DMS_MSG_MULTI_STRING`, `DMS_MSG_OWNER`, `DMS_MSG_CRC`, `DMS_MSG_RUN_TIME_PRIORITY`, `DMS_MSG_STATUS` |
| `signControl` | `.6.X.0` | `DMS_CONTROL_MODE`, `DMS_ACTIVATE_MESSAGE`, `DMS_ACTIVATE_MSG_ERROR`, `DMS_SOFTWARE_RESET` |
| `dmsStatus` | `.9.X.0` | `SHORT_ERROR_STATUS`, `CONTROLLER_ERROR_STATUS`, `DMS_STAT_DOOR_OPEN`, `WATCHDOG_FAILURE_COUNT`, `DMS_PIXEL_FAILURE_TEST_ROWS` |

#### Helpers para `dmsMessageTable`

Los OIDs de la tabla requieren dos índices: `memory_type` y `slot`.

```python
from snmp.ntcip1203 import msg_multi_string, msg_status, msg_crc, msg_owner, msg_run_time_priority

msg_multi_string(2, 1)   # → "1.3.6.1.4.1.1206.4.2.3.5.8.1.3.2.1"
msg_status(2, 1)         # → "1.3.6.1.4.1.1206.4.2.3.5.8.1.9.2.1"
msg_crc(2, 1)            # → "1.3.6.1.4.1.1206.4.2.3.5.8.1.5.2.1"
```

### `driver/daktronics/oids.py` — Constantes Daktronics VFC

Re-exporta todos los OIDs de `ntcip1203` y añade las constantes específicas
del dispositivo. Los módulos del driver importan únicamente desde aquí.

```python
from driver.daktronics.oids import (
    COMMUNITY_READ, COMMUNITY_WRITE,
    MEMORY_CHANGEABLE, MEMORY_VOLATILE, MEMORY_PERMANENT,
    MSG_SLOTS_PER_MEMORY_TYPE,
    SIGN_WIDTH_PIXELS, SIGN_HEIGHT_PIXELS,
    DEFAULT_FONT, DEFAULT_FOREGROUND_RGB,
    # … y todos los OIDs NTCIP 1203 via re-export
)
```

| Constante | Valor | Descripción |
|---|---|---|
| `COMMUNITY_READ` | `"public"` | Community de lectura |
| `COMMUNITY_WRITE` | `"administrator"` | Community de escritura |
| `SIGN_WIDTH_PIXELS` | `144` | Ancho del panel en píxeles |
| `SIGN_HEIGHT_PIXELS` | `96` | Alto del panel en píxeles |
| `DEFAULT_FONT` | `24` | Fuente por defecto |
| `DEFAULT_JUSTIFICATION_LINE` | `3` | Center |
| `DEFAULT_JUSTIFICATION_PAGE` | `3` | Middle |
| `DEFAULT_PAGE_ON_TIME` | `30` | 3,0 s (en décimas de segundo) |
| `DEFAULT_FOREGROUND_RGB` | `(0xFF, 0xB4, 0x00)` | Ámbar |
| `MAX_MULTI_STRING_LEN` | `1500` | Bytes máximos por string MULTI |
| `MAX_NUMBER_PAGES` | `6` | Páginas máximas por mensaje |
| `COLOR_SCHEME` | `4` | `colorClassic` |
| `MEMORY_VOLATILE` | `1` | Memoria volátil |
| `MEMORY_CHANGEABLE` | `3` | Memoria changeable (**ver quirk**) |
| `MEMORY_PERMANENT` | `3` | Memoria permanente |
| `MSG_SLOTS_PER_MEMORY_TYPE` | `500` | Slots por tipo de memoria |

---

## Interfaz de driver

**`driver/base.py`** — `VMSDriver` (ABC)

```python
class VMSDriver(ABC):
    def get_status(self) -> DeviceStatus: ...
    def get_current_message(self) -> str: ...
    def send_message(self, multi_string: str, slot: int = 1, priority: int = 3) -> Message: ...
    def clear_message(self) -> bool: ...
```

Cualquier driver nuevo debe heredar de `VMSDriver` e implementar estos cuatro métodos.
El resto del sistema opera exclusivamente contra esta interfaz.

---

## Driver Daktronics VFC

**`driver/daktronics/driver.py`** — `DaktronicsVFCDriver`

### Inicialización

```python
from driver.daktronics.driver import DaktronicsVFCDriver

driver = DaktronicsVFCDriver(ip="66.17.99.157")
```

Internamente instancia dos `SNMPClient`: uno con `community=public` (lectura)
y otro con `community=administrator` (escritura).

### `send_message(multi_string, slot=1, priority=3)`

Implementa la secuencia NTCIP 1203 completa para escribir y activar un mensaje:

```
1. SET dmsMessageStatus  = modifyReq (6)   → abre el slot para edición
2. SET dmsMessageMultiString = <MULTI>     → escribe el contenido
3. SET dmsMessageStatus  = validateReq (7) → solicita validación al panel
4. POLL dmsMessageStatus hasta valid (5)   → espera confirmación (timeout 10 s)
5. GET  dmsMessageCRC                      → lee el CRC calculado por el panel
6. SET  dmsActivateMessage = <payload>     → muestra el mensaje en pantalla
```

El payload de `dmsActivateMessage` es un `OctetString` de 12 bytes:

```
┌──────────┬──────────┬───────────┬──────┬─────┬─────────────┐
│ duration │ priority │ mem_type  │ slot │ CRC │  IP origen  │
│  2 bytes │  1 byte  │  1 byte   │2 bytes│2 bytes│  4 bytes  │
└──────────┴──────────┴───────────┴──────┴─────┴─────────────┘
```

Ejemplo real capturado del dispositivo:
```
FF FF  FF  03  00 02  E4 13  7F 00 00 01
 ↑↑↑↑   ↑    ↑   ↑↑↑↑   ↑↑↑↑   ↑↑↑↑↑↑↑↑
 inf  prio=3 mt=3 slot=2 CRC   127.0.0.1
```

Si la validación falla, el driver ejecuta automáticamente un **rollback**:
vacía el slot y lo deja en estado `notUsed`.

### `get_status()` → `DeviceStatus`

Lee en una sola pasada: `SHORT_ERROR_STATUS`, `DMS_STAT_DOOR_OPEN`,
`WATCHDOG_FAILURE_COUNT` y `DMS_CONTROL_MODE`. Si el panel no responde,
devuelve `DeviceStatus(online=False)` sin lanzar excepción.

### `get_current_message()` → `str`

Lee `dmsMessageMultiString` del buffer activo (`memory_type=4, slot=1`).

### `clear_message()` → `bool`

Activa el mensaje blank estándar NTCIP: `memory_type=7, slot=1, CRC=0`.

---

## Dispositivo de referencia

| Parámetro | Valor |
|---|---|
| Modelo | Daktronics VFC |
| IP | `66.17.99.157` |
| Puerto SNMP | `161` (UDP) |
| Versión SNMP | v2c |
| Community lectura | `public` |
| Community escritura | `administrator` |
| Dimensiones | 144 × 96 píxeles (full-matrix) |
| Color | Ámbar — `RGB(255, 180, 0)` / `#FFB400` |
| Fuente por defecto | 24 |
| Justificación de línea | Center (3) |
| Justificación de página | Middle (3) |
| Tiempo de página activa | 3,0 s (valor `30` en décimas) |
| Longitud máx. MULTI | 1 500 bytes |
| Páginas máx. por mensaje | 6 |
| Esquema de color | `colorClassic` (4) |
| Slots por tipo de memoria | 500 |

---

## Quirks del dispositivo

### `memory_type` invertido respecto al estándar

El estándar NTCIP 1203 define:

| `memory_type` | Estándar NTCIP 1203 | Este VFC |
|:---:|---|---|
| `1` | volatile | volatile ✓ |
| `2` | changeable | **no funcional** |
| `3` | permanent | **changeable** ← usar este |

Este VFC acepta escrituras en `memory_type=3`, no en `memory_type=2`.
La constante `MEMORY_CHANGEABLE = 3` en `driver/daktronics/oids.py` encapsula
este comportamiento. **Nunca usar el literal `2` para mensajes changeables
en este dispositivo.**

---

## Uso rápido

```python
from driver.daktronics.driver import DaktronicsVFCDriver

driver = DaktronicsVFCDriver(ip="66.17.99.157")

# Enviar un mensaje de dos páginas
msg = driver.send_message("[pt30o0][pb3][cf255,180,0]PRECAUCIÓN[nl]OBRAS EN VÍA")
print(f"Activado — CRC: {msg.crc}, status: {msg.status}")

# Leer estado del panel
status = driver.get_status()
print(f"Online: {status.online}, errores: {status.short_error_status}")

# Limpiar pantalla
driver.clear_message()
```

---

## Dependencias

```
pysnmp >= 7.0        # SNMP v2c, API asyncio
```

Instalación:

```bash
pip install pysnmp
```