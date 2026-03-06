# vms-driver

Driver NTCIP 1203 sobre SNMP v2c para paneles VMS/DMS de señalización variable.
Implementación actual: **Daktronics VFC** — panel full-matrix 144×96 px, ámbar.

---

## Tabla de contenidos

- [Arquitectura](#arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Capa SNMP — `snmp/client.py`](#capa-snmp)
- [Capa de OIDs](#capa-de-oids)
  - [`snmp/ntcip1203.py` — Estándar NTCIP 1203 v03](#snmpntcip1203py)
  - [`driver/daktronics/oids.py` — Constantes Daktronics VFC](#driverdaktronicsoidspy)
- [Interfaz de driver — `driver/base.py`](#interfaz-de-driver)
- [Driver Daktronics VFC](#driver-daktronics-vfc)
  - [`driver/daktronics/driver.py`](#driverdaktronicdriverpy)
  - [`driver/daktronics/slots.py`](#driverdaktroniicsslotspy)
- [Dispositivo de referencia](#dispositivo-de-referencia)
- [Uso rápido](#uso-rápido)
- [Dependencias](#dependencias)

---

## Arquitectura

```
┌──────────────────────────────────────────────┐
│              Aplicación / API                │
└─────────────────────┬────────────────────────┘
                      │  VMSDriver (interfaz abstracta)
┌─────────────────────▼────────────────────────┐
│          DaktronicsVFCDriver                 │  driver/daktronics/driver.py
│  send_message · get_status · clear_message   │
│  get_current_message                         │
└──────────┬──────────────────┬────────────────┘
           │                  │
           │ gestión slots     │ OIDs + constantes
┌──────────▼──────┐  ┌────────▼───────────────────┐
│  SlotManager    │  │  driver/daktronics/oids.py  │
│  slots.py       │  │  (re-exporta ntcip1203)     │
└─────────────────┘  └────────────────────────────┘
                                  │ OIDs estándar
                     ┌────────────▼───────────────┐
                     │    snmp/ntcip1203.py        │
                     │  7 grupos NTCIP 1203 v03    │
                     └────────────────────────────┘
                                  │ transporte
                     ┌────────────▼───────────────┐
                     │      snmp/client.py         │
                     │  SNMPClient — get/set/walk  │
                     │  pysnmp v7 · SNMP v2c       │
                     └────────────────────────────┘
```

El sistema está diseñado para múltiples fabricantes: cada uno implementa `VMSDriver`
sin que el resto del sistema sepa qué hardware hay debajo.

---

## Estructura del proyecto

```
vms-driver/
├── snmp/
│   ├── __init__.py
│   ├── client.py          # SNMPClient: get, set, walk (pysnmp v7, asyncio)
│   └── ntcip1203.py       # OIDs estándar NTCIP 1203 v03 + helpers de tabla
│
├── driver/
│   ├── __init__.py
│   ├── base.py            # VMSDriver — interfaz abstracta
│   ├── factory.py         # (pendiente) instanciación por fabricante/modelo
│   └── daktronics/
│       ├── __init__.py
│       ├── driver.py      # DaktronicsVFCDriver — implementación completa
│       ├── oids.py        # Constantes del dispositivo + re-export ntcip1203
│       ├── slots.py       # SlotManager — gestión thread-safe de slots
│       └── multi.py       # MultiBuilder + MultiValidator — lenguaje MULTI
│
├── models/
│   └── device.py          # DeviceStatus, Message, MessageStatus, ControlMode, …
└── tools/
    └── message_playground.py  # CLI interactivo para pruebas en dispositivo real
```

---

## Capa SNMP

**`snmp/client.py`** — `SNMPClient`

Cliente SNMP v2c sincrónico que envuelve la API asyncio de pysnmp v7.
Internamente usa `asyncio.run()` en cada llamada, por lo que es compatible
con código síncrono ordinario.

```python
from snmp.client import SNMPClient

client = SNMPClient(ip="66.17.99.157", community="public")

value = client.get("1.3.6.1.2.1.1.1.0")         # → valor SNMP
ok    = client.set("1.3.6.1.4.1.1206.4.2.3.6.1.0", 4)  # → True
pairs = client.walk("1.3.6.1.4.1.1206.4.2.3")    # → list[(oid_str, value)]
```

| Parámetro   | Default | Descripción                         |
|-------------|---------|-------------------------------------|
| `ip`        | —       | Dirección IP del panel              |
| `community` | —       | Community string (lectura o escritura) |
| `port`      | `161`   | Puerto UDP                          |
| `timeout`   | `10`    | Segundos por intento                |
| `retries`   | `3`     | Reintentos ante timeout             |

**Conversión automática de tipos en `set()`:**

| Tipo Python | Tipo SNMP enviado |
|-------------|-------------------|
| `int`       | `Integer32`       |
| `str`       | `OctetString`     |
| `bytes`     | `OctetString`     |
| tipo SNMP   | se usa sin cambios |

**Errores:**
- `ConnectionError` — `errorIndication` (timeout, host unreachable, …)
- `ValueError` — `errorStatus` (noSuchObject, wrongType, …)

---

## Capa de OIDs

### `snmp/ntcip1203.py`

OIDs del estándar NTCIP 1203 v03, válidos para cualquier fabricante.
Base: `1.3.6.1.4.1.1206.4.2.3`

#### Grupos de OIDs

| Grupo | Sub-árbol | Descripción |
|---|---|---|
| `dmsSignCfg` | `.1.X.0` | Configuración física del panel (tipo, dimensiones mm, tecnología, bordes) |
| `vmsCfg` | `.2.X.0` | Dimensiones en píxeles, pitch, color monocromático |
| `multiCfg` | `.4.X.0` | Defaults del lenguaje MULTI (fuente, justificación, tiempos, color, longitud máxima) |
| `dmsMessage` escalares | `.5.X.0` | Contadores de slots por tipo de memoria y memoria libre |
| `dmsMessageTable` | `.5.8.1.X` | Tabla de mensajes (multiString, owner, CRC, priority, status) |
| `signControl` | `.6.X.0` | Control del panel (modo, reset, activateMessage, error de activación) |
| `dmsStatus` | `.9.X.0` | Estado (errores, puerta, watchdog, velocidad, fallos de píxel) |

#### Constantes destacadas

```python
from snmp.ntcip1203 import (
    # vmsCfg
    VMS_SIGN_HEIGHT_PIXELS,        # .2.3.0 — filas totales de píxeles
    VMS_SIGN_WIDTH_PIXELS,         # .2.4.0 — columnas totales de píxeles
    # multiCfg
    MULTI_DEFAULT_FONT,            # .4.5.0
    MULTI_DEFAULT_JUSTIFICATION_LINE,  # .4.6.0
    MULTI_DEFAULT_PAGE_ON_TIME,    # .4.8.0
    MULTI_COLOR_SCHEME,            # .4.11.0
    MULTI_DEFAULT_FOREGROUND_RGB,  # .4.13.0
    MULTI_MAX_MULTI_STRING_LENGTH, # .4.16.0
    # dmsMessage escalares
    DMS_MAX_CHANGEABLE_MSG,        # .5.3.0 — slots changeables disponibles
    DMS_FREE_CHANGEABLE_MEMORY,    # .5.4.0 — memoria libre (bytes)
    # signControl
    DMS_ACTIVATE_MESSAGE,          # .6.3.0
    DMS_ACTIVATE_MSG_ERROR,        # .6.4.0
    # dmsStatus
    SHORT_ERROR_STATUS,            # .9.7.1.0
    DMS_STAT_DOOR_OPEN,            # .9.6.0
    WATCHDOG_FAILURE_COUNT,        # .9.5.0
)
```

#### Helpers para `dmsMessageTable`

Los OIDs de la tabla requieren dos índices: `memory_type` y `slot`.
Los helpers construyen el OID de instancia completo.

```python
from snmp.ntcip1203 import (
    msg_multi_string,      # columna 3 — cadena MULTI
    msg_owner,             # columna 4 — propietario
    msg_crc,               # columna 5 — CRC-16
    msg_run_time_priority, # columna 8 — prioridad
    msg_status,            # columna 9 — estado del slot
)

msg_multi_string(3, 2)
# → "1.3.6.1.4.1.1206.4.2.3.5.8.1.3.3.2"

msg_status(3, 2)
# → "1.3.6.1.4.1.1206.4.2.3.5.8.1.9.3.2"
```

---

### `driver/daktronics/oids.py`

Re-exporta todos los símbolos de `snmp.ntcip1203` y añade las constantes
específicas del dispositivo. Los módulos del driver importan exclusivamente
desde aquí.

```python
from driver.daktronics.oids import (
    # acceso SNMP
    COMMUNITY_READ,    # "public"
    COMMUNITY_WRITE,   # "administrator"
    # dimensiones (confirmadas en dispositivo)
    SIGN_WIDTH_PIXELS,   # 144
    SIGN_HEIGHT_PIXELS,  # 96
    # defaults MULTI (confirmados en dispositivo)
    DEFAULT_FONT,                 # 24
    DEFAULT_JUSTIFICATION_LINE,   # 3 = center
    DEFAULT_JUSTIFICATION_PAGE,   # 3 = middle
    DEFAULT_PAGE_ON_TIME,         # 30 (= 3,0 s en décimas)
    DEFAULT_FOREGROUND_RGB,       # (0xFF, 0xB4, 0x00) — ámbar
    # capacidades (confirmadas en dispositivo)
    MAX_MULTI_STRING_LEN,   # 1500 bytes
    MAX_NUMBER_PAGES,       # 6 páginas
    COLOR_SCHEME,           # 4 = colorClassic
    # tipos de memoria (confirmados en dispositivo)
    MEMORY_PERMANENT,      # 2  (solo lectura)
    MEMORY_CHANGEABLE,     # 3  ← usar por defecto
    MEMORY_VOLATILE,       # 4
    MEMORY_CURRENT_BUFFER, # 5  (solo lectura — mensaje activo)
    MEMORY_BLANK,          # 7  (apaga el panel)
    # tabla de mensajes
    MSG_SLOTS_PER_MEMORY_TYPE,  # 500
    # … y todos los OIDs de ntcip1203 via re-export
)
```

**Tabla de constantes del dispositivo:**

| Constante | Valor | Notas |
|---|---|---|
| `COMMUNITY_READ` | `"public"` | |
| `COMMUNITY_WRITE` | `"administrator"` | |
| `SIGN_WIDTH_PIXELS` | `144` | confirmado |
| `SIGN_HEIGHT_PIXELS` | `96` | confirmado |
| `DEFAULT_FONT` | `24` | confirmado |
| `DEFAULT_JUSTIFICATION_LINE` | `3` | center |
| `DEFAULT_JUSTIFICATION_PAGE` | `3` | middle |
| `DEFAULT_PAGE_ON_TIME` | `30` | 3,0 s en décimas |
| `DEFAULT_FOREGROUND_RGB` | `(255, 180, 0)` | ámbar `#FFB400` |
| `MAX_MULTI_STRING_LEN` | `1500` | confirmado |
| `MAX_NUMBER_PAGES` | `6` | confirmado |
| `COLOR_SCHEME` | `4` | colorClassic |
| `MEMORY_PERMANENT` | `2` | solo lectura |
| `MEMORY_CHANGEABLE` | `3` | changeable (NTCIP 1203) |
| `MEMORY_VOLATILE` | `4` | se pierde al apagar |
| `MEMORY_CURRENT_BUFFER` | `5` | solo lectura — mensaje activo |
| `MEMORY_BLANK` | `7` | apaga el panel |
| `MSG_SLOTS_PER_MEMORY_TYPE` | `500` | confirmado |

---

## Interfaz de driver

**`driver/base.py`** — `VMSDriver` (ABC)

Contrato que todo driver de fabricante debe implementar. El resto del sistema
opera exclusivamente contra esta interfaz.

```python
class VMSDriver(ABC):

    def get_status(self) -> DeviceStatus:
        """Lee el estado actual del panel."""

    def get_current_message(self) -> str:
        """Lee el MULTI string del mensaje activo."""

    def send_message(self, multi_string: str, priority: int = 3) -> Message:
        """Escribe y activa un mensaje. Devuelve Message con CRC confirmado."""

    def clear_message(self) -> bool:
        """Activa el mensaje blank. Devuelve True si tuvo éxito."""
```

Para agregar soporte a un nuevo fabricante: crear una subclase de `VMSDriver`,
implementar los cuatro métodos e instanciarla vía `driver/factory.py`.

---

## Driver Daktronics VFC

### `driver/daktronics/driver.py`

**`DaktronicsVFCDriver`** — implementación completa de `VMSDriver` para el
Daktronics VFC sobre NTCIP 1203 / SNMP v2c.

#### Inicialización

```python
from driver.daktronics.driver import DaktronicsVFCDriver

driver = DaktronicsVFCDriver(ip="66.17.99.157")
# puerto por defecto: 161
```

Internamente crea:
- `self._read` — `SNMPClient` con `community=public`
- `self._write` — `SNMPClient` con `community=administrator`
- `self._slots` — `SlotManager(total_slots=500)`

#### `send_message(multi_string, priority=3) → Message`

Implementa la secuencia NTCIP 1203 completa. El slot se obtiene
automáticamente del `SlotManager` y queda `IN_USE` mientras el mensaje esté
activo en el panel.

```
slot = SlotManager.acquire()
│
├─ 1. SET dmsMessageStatus  = modifyReq (6)
├─ 2. SET dmsMessageMultiString = <MULTI string>
├─ 3. SET dmsMessageStatus  = validateReq (7)
├─ 4. POLL dmsMessageStatus  hasta valid(5) — timeout 10 s, intervalo 0,5 s
│        │
│        ├─ valid    → continuar
│        └─ error    → mark_corrupted(slot) + rollback + raise ValueError
├─ 5. GET dmsMessageCRC
└─ 6. SET dmsActivateMessage = <payload 12 bytes>
         │
         ├─ ok      → slot queda IN_USE, retorna Message
         └─ excepción → release(slot) + raise
```

**Payload de `dmsActivateMessage` (12 bytes, big-endian):**

```
Offset  Tamaño  Campo        Valor típico
──────  ──────  ───────────  ────────────────────────
0       2 B     duration     0xFFFF (infinito)
2       1 B     priority     3
3       1 B     memory_type  3 (MEMORY_CHANGEABLE)
4       2 B     slot         número de slot asignado
6       2 B     CRC          leído del panel en paso 5
8       4 B     IP origen    IP del host que envía
```

Ejemplo capturado del dispositivo real:
```
FF FF  FF  03  00 02  E4 13  7F 00 00 01
 ↑↑↑    ↑    ↑   ↑↑↑↑   ↑↑↑↑  ↑↑↑↑↑↑↑↑
 inf  prio  mt=3 slot=2  CRC   127.0.0.1
```

#### `get_status() → DeviceStatus`

Lee en una sola pasada cuatro OIDs de `dmsStatus`:

| OID | Constante | Campo en `DeviceStatus` |
|---|---|---|
| `.9.7.1.0` | `SHORT_ERROR_STATUS` | `short_error_status` (bitmap) |
| `.9.6.0` | `DMS_STAT_DOOR_OPEN` | `door_open` (bool) |
| `.9.5.0` | `WATCHDOG_FAILURE_COUNT` | `watchdog_failures` |
| `.6.1.0` | `DMS_CONTROL_MODE` | `control_mode` (enum) |

Si el panel no responde, devuelve `DeviceStatus(online=False)` sin lanzar
excepción, para que el polling worker pueda continuar.

#### `get_current_message() → str`

Lee `dmsMessageMultiString` del buffer activo (`MEMORY_CURRENT_BUFFER`, slot 1).
Devuelve `""` si falla.

#### `clear_message() → bool`

Activa el mensaje blank estándar NTCIP (`memory_type=7, slot=1, CRC=0`) y
a continuación libera todos los slots marcados como `IN_USE` en el `SlotManager`.

#### Métodos internos

| Método | Descripción |
|---|---|
| `_poll_until_valid(memory_type, slot)` | Poll de `dmsMessageStatus` hasta `VALID` o `ERROR`. Timeout: 10 s, intervalo: 0,5 s. |
| `_rollback(memory_type, slot)` | Vacía un slot inválido: `modifyReq` → escribe `""` → `validateReq`. |
| `_build_activate_hex(...)` | Construye el `OctetString` de 12 bytes para `dmsActivateMessage`. |

---

### `driver/daktronics/slots.py`

**`SlotManager`** — gestión thread-safe de los 500 slots de `dmsMessageTable`.

#### `SlotState` (Enum)

| Estado | Descripción |
|---|---|
| `FREE` | Disponible para ser asignado |
| `IN_USE` | Ocupado por un mensaje activo |
| `CORRUPTED` | Falló en el panel; nunca se vuelve a usar |

Al iniciar, todos los slots comienzan en `FREE`.

#### API pública

```python
from driver.daktronics.slots import SlotManager

mgr = SlotManager(total_slots=500)

slot = mgr.acquire()         # → int — primer slot FREE; pasa a IN_USE (atómico)
mgr.release(slot)            # FREE (ignorado si está CORRUPTED)
mgr.mark_corrupted(slot)     # CORRUPTED permanente
mgr.is_available(slot)       # → bool — True si FREE
mgr.is_tracked(slot)         # → bool — True si el slot está en rango (sin lanzar KeyError)
mgr.in_use_slots()           # → list[int] — slots actualmente IN_USE, ordenados
mgr.status()                 # → {"free": 499, "in_use": 1, "corrupted": 0, "total": 500}
```

**`acquire()`** lanza `RuntimeError` si no hay ningún slot `FREE`.

**Thread-safety:** todas las operaciones sobre el estado interno están
protegidas por un `threading.Lock`. Dos hilos concurrentes nunca recibirán
el mismo slot.

#### Ciclo de vida de un slot

```
FREE ──acquire()──► IN_USE ──release()──► FREE
                       │
                  mark_corrupted()
                       │
                       ▼
                   CORRUPTED  (terminal, no hay salida)
```

---

## Dispositivo de referencia

| Parámetro | Valor |
|---|---|
| Modelo | Daktronics VFC |
| IP | `66.17.99.157` |
| Puerto SNMP | `161` UDP |
| Versión SNMP | v2c (`mpModel=1`) |
| Community lectura | `public` |
| Community escritura | `administrator` |
| Tipo de panel | Full-matrix (6 = vmsFullMatrix) |
| Dimensiones | 144 × 96 píxeles |
| Color de píxel | Ámbar — RGB(255, 180, 0) / `#FFB400` |
| Fuente por defecto | 24 |
| Justificación de línea | 3 = center |
| Justificación de página | 3 = middle |
| Tiempo de página activa | 30 décimas = 3,0 s |
| MULTI string máx. | 1 500 bytes |
| Páginas máx. por mensaje | 6 |
| Esquema de color | 4 = colorClassic |
| Slots por tipo de memoria | 500 |

---

## Uso rápido

```python
from driver.daktronics.driver import DaktronicsVFCDriver

driver = DaktronicsVFCDriver(ip="66.17.99.157")

# Enviar un mensaje
msg = driver.send_message("[pt30o0][pb3][cf255,180,0]PRECAUCIÓN[nl]OBRAS EN VÍA")
print(f"slot={msg.slot}  CRC={msg.crc}  status={msg.status}")

# Consultar estado del panel
status = driver.get_status()
print(f"online={status.online}  errores={status.short_error_status}  puerta={status.door_open}")

# Inspeccionar slots
print(driver._slots.status())
# {'free': 499, 'in_use': 1, 'corrupted': 0, 'total': 500}

# Limpiar pantalla (libera todos los slots IN_USE)
driver.clear_message()
```

---

## Playground interactivo

`tools/message_playground.py` es una CLI de prueba para el dispositivo real.
Permite construir y enviar mensajes MULTI paso a paso, ver el estado del panel
y gestionar la tabla de mensajes sin escribir código.

```bash
python tools/message_playground.py
```

#### Opciones del menú

| Opción | Descripción |
|---|---|
| `1` | Envío asistido — guía fuente, justificación, color, páginas y campos dinámicos |
| `2` | Envío directo — ingresá el MULTI string completo |
| `3` | Limpiar panel — activa el mensaje blank |
| `4` | Ver estado completo — online, modo de control, errores, watchdog |
| `5` | Ver mensajes en tabla — scan de los primeros 20 slots + slots IN_USE activos |
| `6` | Borrar mensaje — libera un slot por número |

#### Campos dinámicos disponibles

| Tag | Descripción |
|---|---|
| `[f1]` | Hora local 12 h (con segundos) |
| `[f2]` | Hora local 24 h (con segundos) |
| `[f3]` / `[f4]` | Temperatura °C / °F |
| `[f5]` / `[f6]` | Velocidad km/h / mph |
| `[f7]` | Día de la semana |
| `[f8]` / `[f9]` | Fecha mm/dd/yy / dd/mm/yy |
| `[f10]` | Año yyyy |
| `[f11]` / `[f12]` | Hora sin segundos 12 h / 24 h |

---

## Dependencias

```
pysnmp-lextudio >= 6.0   # fork mantenido; expone pysnmp.hlapi.v3arch.asyncio
```

```bash
pip install pysnmp-lextudio
```

> **Nota:** el proyecto usa la API `pysnmp.hlapi.v3arch.asyncio` (pysnmp >= 6.x).
> El paquete original `pysnmp` dejó de mantenerse en la versión 4.x; usar
> `pysnmp-lextudio` para garantizar compatibilidad.
