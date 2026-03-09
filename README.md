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
- [Modelos de datos — `models/device.py`](#modelos-de-datos)
- [MULTI — `driver/multi.py`](#multi---drivermultipy)
- [Interfaz de driver — `driver/base.py`](#interfaz-de-driver)
- [Factory — `driver/factory.py`](#factory)
- [Driver Daktronics VFC](#driver-daktronics-vfc)
  - [`driver/daktronics/driver.py`](#driverdaktronicdriverpy)
  - [`driver/daktronics/slots.py`](#driverdaktronicsslotspy)
- [Dispositivo de referencia](#dispositivo-de-referencia)
- [Uso rápido](#uso-rápido)
- [Playground interactivo](#playground-interactivo)
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
│  get_current_message · get_message(s)        │
│  delete_message                              │
└──────┬──────────────┬────────────────────────┘
       │              │
       │ gestión slots │ OIDs + constantes
┌──────▼──────┐  ┌────▼────────────────────────┐
│ SlotManager │  │  driver/daktronics/oids.py  │
│  slots.py   │  │  (re-exporta ntcip1203)     │
└─────────────┘  └─────────────────────────────┘
                              │ OIDs estándar
                 ┌────────────▼────────────────┐
                 │    snmp/ntcip1203.py         │
                 │  7 grupos NTCIP 1203 v03     │
                 └─────────────────────────────┘
                              │ transporte
                 ┌────────────▼────────────────┐
                 │      snmp/client.py          │
                 │  SNMPClient — get/set/walk   │
                 │  pysnmp v7 · SNMP v2c        │
                 └─────────────────────────────┘
```

El sistema está diseñado para múltiples fabricantes: cada uno implementa `VMSDriver`
sin que el resto del sistema sepa qué hardware hay debajo.
`driver/factory.py` instancia el driver correcto a partir de un `DeviceInfo`.

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
│   ├── base.py            # VMSDriver — interfaz abstracta (7 métodos)
│   ├── factory.py         # create_driver(DeviceInfo) — instanciación por fabricante
│   ├── multi.py           # MultiBuilder + MultiValidator — lenguaje MULTI (NTCIP 1203)
│   └── daktronics/
│       ├── __init__.py
│       ├── driver.py      # DaktronicsVFCDriver — implementación completa
│       ├── oids.py        # Constantes del dispositivo + re-export ntcip1203
│       ├── slots.py       # SlotManager — gestión thread-safe de slots
│       └── multi.py       # Shim de compatibilidad → re-exporta driver.multi
│
├── models/
│   └── device.py          # DeviceInfo, DeviceStatus, Message, enums
│
└── tools/
    └── message_playground.py  # CLI interactivo para pruebas en dispositivo real
```

> **Nota:** `driver/multi.py` es el módulo canónico del lenguaje MULTI.
> `driver/daktronics/multi.py` es un shim de compatibilidad que re-exporta desde allí.
> Importar siempre desde `driver.multi`.

---

## Capa SNMP

**`snmp/client.py`** — `SNMPClient`

Cliente SNMP v2c sincrónico que envuelve la API asyncio de pysnmp v7.
Internamente usa `asyncio.run()` en cada llamada, por lo que es compatible
con código síncrono ordinario.

```python
from snmp.client import SNMPClient

client = SNMPClient(ip="66.17.99.157", community="public")

value = client.get("1.3.6.1.2.1.1.1.0")                    # → valor SNMP
ok    = client.set("1.3.6.1.4.1.1206.4.2.3.6.1.0", 4)      # → True
pairs = client.walk("1.3.6.1.4.1.1206.4.2.3")              # → list[(oid_str, value)]
```

| Parámetro   | Default | Descripción                              |
|-------------|---------|------------------------------------------|
| `ip`        | —       | Dirección IP del panel                   |
| `community` | —       | Community string (lectura o escritura)   |
| `port`      | `161`   | Puerto UDP                               |
| `timeout`   | `10`    | Segundos por intento                     |
| `retries`   | `3`     | Reintentos ante timeout                  |

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
| `dmsSignCfg` | `.1.X.0` | Configuración física (tipo, dimensiones mm, tecnología, bordes) |
| `vmsCfg` | `.2.X.0` | Dimensiones en píxeles, pitch, color monocromático |
| `multiCfg` | `.4.X.0` | Defaults MULTI (fuente, justificación, tiempos, color, longitud máx.) |
| `dmsMessage` escalares | `.5.X.0` | Contadores de slots por tipo de memoria y memoria libre |
| `dmsMessageTable` | `.5.8.1.X` | Tabla de mensajes (multiString, owner, CRC, priority, status) |
| `signControl` | `.6.X.0` | Control del panel (modo, reset, activateMessage, error de activación) |
| `dmsStatus` | `.9.X.0` | Estado (errores, puerta, watchdog, velocidad, fallos de píxel) |

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
| `MEMORY_CHANGEABLE` | `3` | usar por defecto |
| `MEMORY_VOLATILE` | `4` | se pierde al apagar |
| `MEMORY_CURRENT_BUFFER` | `5` | solo lectura — mensaje activo |
| `MEMORY_BLANK` | `7` | apaga el panel |
| `MSG_SLOTS_PER_MEMORY_TYPE` | `500` | confirmado |

---

## Modelos de datos

**`models/device.py`** — tipos compartidos entre el driver, el polling worker
y el command handler.

### `DeviceInfo`

Configuración estática del dispositivo. Va en base de datos y solo cambia
si cambia el hardware o la red. Es el parámetro que recibe `create_driver()`.

```python
from models.device import DeviceInfo

device_info = DeviceInfo(
    ip="66.17.99.157",
    port=161,
    community_read="public",
    community_write="administrator",
    device_type="daktronics_vfc",
    width_pixels=144,
    height_pixels=96,
)
```

### `DeviceStatus`

Snapshot del estado del panel. Lo crea el driver en `get_status()`.

```python
status = driver.get_status()

status.online              # → bool
status.control_mode        # → ControlMode | None
status.short_error_status  # → int (bitmap)
status.door_open           # → bool
status.watchdog_failures   # → int
status.has_errors          # → bool (propiedad)
status.active_errors()     # → list[str] — nombres de los bits activos
status.last_polled         # → datetime | None
```

`active_errors()` decodifica el bitmap `short_error_status` usando `ShortErrorBit`:

| Bit | Nombre | Descripción |
|---|---|---|
| 1 | `COMMUNICATIONS` | Error de comunicaciones |
| 2 | `POWER` | Error de alimentación |
| 3 | `ATTACHED_DEVICE` | Error en dispositivo externo |
| 4 | `LAMP` | Error de lámparas |
| 5 | `PIXEL` | Error de píxeles |
| 6 | `PHOTOCELL` | Error de fotocélula |
| 7 | `MESSAGE` | Error de mensaje (activo en VFC real) |
| 8 | `CONTROLLER` | Error del controlador |
| 9 | `TEMPERATURE` | Advertencia de temperatura |

### `Message`

Representa un mensaje en la `dmsMessageTable`.

```python
@dataclass
class Message:
    memory_type: int           # tipo de memoria (3=changeable, 5=currentBuffer, …)
    slot: int                  # número de slot (1..500)
    multi_string: str          # contenido MULTI
    status: MessageStatus | None
    crc: int | None
```

### Enums

| Enum | Valores clave | Descripción |
|---|---|---|
| `ControlMode` | `LOCAL=2`, `CENTRAL=4` | Modo de control del panel |
| `MessageStatus` | `VALID=4`, `ERROR=5`, `MODIFY_REQ=6`, `VALIDATE_REQ=7`, `NOT_USED_REQ=8` | Estado de un slot |
| `SignType` | `FULL_MATRIX=6` | Tipo de panel (confirmado en VFC) |
| `ShortErrorBit` | ver tabla arriba | Bitmap de errores del panel |

---

## MULTI — `driver/multi.py`

`MultiValidator` y `MultiBuilder` implementan el lenguaje MULTI definido en
NTCIP 1203 v03. Son independientes del fabricante y pueden usarse desde
cualquier driver.

### `MultiValidator`

Valida MULTI strings antes de enviarlos al panel. No hace llamadas SNMP.

```python
from driver.multi import MultiValidator

validator = MultiValidator(
    width=144,
    height=96,
    max_string_length=1500,
    max_pages=6,
)

result = validator.validate("[fo24][jl3]PRECAUCIÓN[nl]OBRAS")
if not result:
    print(result.errors)  # → list[str]
```

**Chequeos que realiza:**

1. String no vacío
2. Longitud dentro del límite (`max_string_length`)
3. Número de páginas (`[np]`) dentro del límite
4. Solo tags definidos en NTCIP 1203 v03 (bits 0–29 de `dmsSupportedMultiTags`)
5. Números de fuente `[foN]` en rango 1–255
6. Números de gráfico `[gN]` en rango 1–255
7. Coordenadas de `[tr]` y `[cr]` dentro de las dimensiones del panel

**Tags soportados (NTCIP 1203 v03, bits 0–29):**

| Tag | Descripción |
|---|---|
| `[cbX]` / `[cbR,G,B]` | Color de fondo clásico / RGB |
| `[cfX]` / `[cfR,G,B]` | Color de texto clásico / RGB |
| `[fl]` / `[fltXoY]` / `[/fl]` | Flash con tiempos opcionales |
| `[foN]` / `[foN,XXXX]` | Fuente (con versión opcional) |
| `[gN]` / `[gN,x,y]` | Gráfico (con posición opcional) |
| `[hcXX]` | Carácter hexadecimal |
| `[jlN]` | Justificación de línea (2=izq, 3=centro, 4=der, 5=full) |
| `[jpN]` | Justificación de página (2=arriba, 3=medio, 4=abajo) |
| `[msX,Y]` | Tag específico de fabricante |
| `[mvDW,s,r,text]` | Texto en movimiento |
| `[nl]` / `[nlN]` | Nueva línea |
| `[np]` | Nueva página |
| `[ptXoY]` | Tiempo de página (en décimas) |
| `[scN]` | Espaciado entre caracteres |
| `[fN]` (N=1..12) | Campo dinámico |
| `[trX,Y,W,H]` | Rectángulo de texto |
| `[crX,Y,W,H,R,G,B]` | Rectángulo de color |
| `[pbR,G,B]` / `[pbX]` | Fondo de página RGB / clásico |
| `[slN]` | Espaciado entre líneas |

### `MultiBuilder`

Construye MULTI strings de forma fluida. Valida al hacer `build()`.

```python
from driver.multi import MultiBuilder

# Mensaje simple centrado
multi = (
    MultiBuilder()
    .page_time(30, 0)          # [pt30o0] — 3 s por página
    .page_middle()             # [jp3]
    .font(24)                  # [fo24]
    .center()                  # [jl3]
    .text("DESVIO")
    .new_page()
    .page_time(30, 0)
    .page_middle()
    .font(24)
    .center()
    .text("RUTA 9")
    .build()                   # valida y devuelve el string
)

# Con rectángulos de texto
multi = (
    MultiBuilder()
    .text_rect(1, 1, 144, 48)  # [tr1,1,144,48]
    .font(20)
    .center()
    .text("TEMPERATURA")
    .field(3)                  # [f3] — temperatura en °C
    .build()
)
```

**Métodos disponibles:**

| Método | Tag generado | Descripción |
|---|---|---|
| `.text(s)` | — | Texto literal |
| `.center()` | `[jl3]` | Justificación centrada |
| `.left()` | `[jl2]` | Justificación izquierda |
| `.right()` | `[jl4]` | Justificación derecha |
| `.page_top()` | `[jp2]` | Posición vertical arriba |
| `.page_middle()` | `[jp3]` | Posición vertical centro |
| `.page_bottom()` | `[jp4]` | Posición vertical abajo |
| `.new_page()` | `[np]` | Nueva página |
| `.new_line()` | `[nl]` | Nueva línea |
| `.font(n)` | `[foN]` | Fuente (1–255) |
| `.graphic(n, x, y)` | `[gN,x,y]` | Gráfico con posición opcional |
| `.page_time(on, off)` | `[ptXoY]` | Tiempo de página en décimas |
| `.color_foreground(r,g,b)` | `[cfR,G,B]` | Color de texto RGB |
| `.color_background(r,g,b)` | `[cbR,G,B]` | Color de fondo RGB |
| `.page_background(r,g,b)` | `[pbR,G,B]` | Fondo de página RGB |
| `.text_rect(x,y,w,h)` | `[trX,Y,W,H]` | Zona de texto |
| `.color_rect(x,y,w,h,r,g,b)` | `[crX,Y,W,H,R,G,B]` | Rectángulo de color |
| `.flash(on, off)` | `[fltXoY]` | Inicio de flash |
| `.flash_end()` | `[/fl]` | Fin de flash |
| `.field(n)` | `[fN]` | Campo dinámico (1–12) |
| `.char_spacing(n)` | `[scN]` | Espaciado entre caracteres |
| `.line_spacing(n)` | `[slN]` | Espaciado entre líneas |
| `.build()` | — | Construye y valida (lanza `ValueError` si inválido) |
| `.build_unsafe()` | — | Construye sin validar (solo para tests) |

**Campos dinámicos `[fN]`:**

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

## Interfaz de driver

**`driver/base.py`** — `VMSDriver` (ABC)

Contrato que todo driver de fabricante debe implementar.

```python
class VMSDriver(ABC):

    def get_status(self) -> DeviceStatus:
        """Lee el estado actual del panel."""

    def get_current_message(self) -> str:
        """Lee el MULTI string del mensaje activo (currentBuffer)."""

    def get_message(self, slot: int) -> Message | None:
        """Lee un mensaje específico de la messageTable. None si el slot está vacío."""

    def get_messages(self) -> list[Message]:
        """Lista todos los mensajes válidos en la tabla del panel."""

    def send_message(self, multi_string: str, priority: int = 3) -> Message:
        """Escribe y activa un mensaje. Devuelve Message con CRC confirmado."""

    def delete_message(self, slot: int) -> bool:
        """Borra un mensaje de la messageTable. True si tuvo éxito."""

    def clear_message(self) -> bool:
        """Activa el mensaje blank. True si tuvo éxito."""
```

Para agregar soporte a un nuevo fabricante:
1. Crear `driver/fabricante/__init__.py`
2. Crear `driver/fabricante/driver.py` (subclase de `VMSDriver`)
3. Registrar en `driver/factory.py` → `_REGISTRY`

---

## Factory

**`driver/factory.py`**

Instancia el driver correcto a partir de un `DeviceInfo`, sin exponer el tipo
concreto al caller.

```python
from driver.factory import create_driver, available_drivers
from models.device import DeviceInfo

device_info = DeviceInfo(ip="66.17.99.157", device_type="daktronics_vfc")
driver = create_driver(device_info)  # → VMSDriver

available_drivers()  # → ["daktronics_vfc"]
```

Los módulos se cargan dinámicamente, por lo que las dependencias de un
fabricante no se importan si su driver no se usa.

**Registro actual:**

| `device_type` | Clase |
|---|---|
| `daktronics_vfc` | `driver.daktronics.driver.DaktronicsVFCDriver` |

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
# source_ip: se detecta automáticamente
```

Al iniciar crea:
- `self._read` — `SNMPClient` con `community=public`
- `self._write` — `SNMPClient` con `community=administrator`
- `self._slots` — `SlotManager(total_slots=500)`
- `self._source_ip` — IP local detectada automáticamente (sin tráfico extra)
- `self._validator` — `MultiValidator` con dimensiones leídas del panel vía SNMP

#### `send_message(multi_string, priority=3) → Message`

Valida el MULTI string antes de enviarlo. Implementa la secuencia NTCIP 1203
completa. El slot se obtiene automáticamente del `SlotManager` y queda `IN_USE`
mientras el mensaje esté activo en el panel.

```
slot = SlotManager.acquire()
│
├─ 1. Validar MULTI string (MultiValidator) — lanza ValueError si inválido
├─ 2. SET dmsMessageStatus  = modifyReq (6)
├─ 3. SET dmsMessageMultiString = <MULTI string>
├─ 4. SET dmsMessageStatus  = validateReq (7)
├─ 5. POLL dmsMessageStatus hasta valid(4) — timeout 10 s, intervalo 0,5 s
│        │
│        ├─ valid    → continuar
│        └─ error    → mark_corrupted(slot) + rollback + raise ValueError
├─ 6. GET dmsMessageCRC
└─ 7. SET dmsActivateMessage = <payload 12 bytes>
         │
         ├─ ok        → slot queda IN_USE, retorna Message
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
6       2 B     CRC          leído del panel en paso 6
8       4 B     IP origen    IP detectada automáticamente
```

Ejemplo capturado del dispositivo real:
```
FF FF  FF  03  00 02  E4 13  7F 00 00 01
 ↑↑↑    ↑    ↑   ↑↑↑↑   ↑↑↑↑  ↑↑↑↑↑↑↑↑
 inf  prio  mt=3 slot=2  CRC   127.0.0.1
```

#### `get_status() → DeviceStatus`

Lee cuatro OIDs de `dmsStatus` / `signControl`:

| OID | Constante | Campo en `DeviceStatus` |
|---|---|---|
| `.9.7.1.0` | `SHORT_ERROR_STATUS` | `short_error_status` (bitmap) |
| `.9.6.0` | `DMS_STAT_DOOR_OPEN` | `door_open` (bool) |
| `.9.5.0` | `WATCHDOG_FAILURE_COUNT` | `watchdog_failures` |
| `.6.1.0` | `DMS_CONTROL_MODE` | `control_mode` (enum) |

Si el panel no responde, devuelve `DeviceStatus(online=False)` sin lanzar
excepción.

#### `get_current_message() → str`

Lee `dmsMessageMultiString` del buffer activo (`MEMORY_CURRENT_BUFFER=5`, slot 1).
Devuelve `""` si falla.

#### `get_message(slot, memory_type=3) → Message | None`

Lee el estado y contenido de un slot específico.
Devuelve `None` si el slot está en `NOT_USED`.

#### `get_messages(memory_type=3) → list[Message]`

Lista los mensajes válidos de un tipo de memoria. Combina:
- Los slots que el `SlotManager` registra como `IN_USE`
- Un scan de los primeros 20 slots (para detectar mensajes preexistentes al arranque)

Solo incluye slots con `status == VALID` y contenido no vacío.

#### `delete_message(slot, memory_type=3) → bool`

Borra un mensaje de la tabla enviando `notUsedReq (8)`.
También libera el slot en el `SlotManager` si estaba registrado.
No afecta el mensaje activo en pantalla — usar `clear_message()` para eso.

#### `clear_message() → bool`

Activa el mensaje blank estándar NTCIP (`memory_type=7, slot=1, CRC=0`) y
libera todos los slots marcados como `IN_USE` en el `SlotManager`.

#### Métodos internos

| Método | Descripción |
|---|---|
| `_detect_source_ip()` | Detecta la IP local con ruta al panel usando un socket UDP (sin enviar tráfico). |
| `_init_validator()` | Consulta dimensiones y límites al panel vía SNMP para construir el `MultiValidator`. |
| `_poll_until_valid(memory_type, slot)` | Poll de `dmsMessageStatus` hasta `VALID` o `ERROR`. Timeout: 10 s, intervalo: 0,5 s. |
| `_rollback(memory_type, slot)` | Limpia un slot inválido: `modifyReq` → escribe `""` → `validateReq`. |
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

slot = mgr.acquire()          # → int — primer slot FREE; pasa a IN_USE (atómico)
mgr.release(slot)             # FREE (ignorado si está CORRUPTED)
mgr.mark_corrupted(slot)      # CORRUPTED permanente
mgr.is_available(slot)        # → bool — True si FREE
mgr.is_tracked(slot)          # → bool — True si el slot está en rango
mgr.in_use_slots()            # → list[int] — slots IN_USE, ordenados
mgr.status()                  # → {"free": 499, "in_use": 1, "corrupted": 0, "total": 500}
```

**`acquire()`** lanza `RuntimeError` si no hay ningún slot `FREE`.

**Thread-safety:** todas las operaciones están protegidas por un `threading.Lock`.
Dos hilos concurrentes nunca recibirán el mismo slot.

#### Ciclo de vida de un slot

```
FREE ──acquire()──► IN_USE ──release()──► FREE
                       │
                  mark_corrupted()
                       │
                       ▼
                   CORRUPTED  (terminal)
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
from driver.factory import create_driver
from driver.multi import MultiBuilder
from models.device import DeviceInfo

device_info = DeviceInfo(ip="66.17.99.157")
driver = create_driver(device_info)

# Enviar un mensaje con el builder
multi = (
    MultiBuilder()
    .page_time(30, 0)
    .page_middle()
    .font(24)
    .color_foreground(255, 180, 0)
    .center()
    .text("PRECAUCIÓN")
    .new_line()
    .text("OBRAS EN VÍA")
    .build()
)
msg = driver.send_message(multi)
print(f"slot={msg.slot}  CRC={msg.crc}  status={msg.status}")

# Consultar estado del panel
status = driver.get_status()
print(f"online={status.online}  errores={status.active_errors()}  puerta={status.door_open}")

# Leer mensaje activo
print(driver.get_current_message())

# Listar mensajes en tabla
for m in driver.get_messages():
    print(f"slot={m.slot}  {m.multi_string}")

# Borrar un mensaje específico
driver.delete_message(slot=2)

# Limpiar pantalla (libera todos los slots IN_USE)
driver.clear_message()

# Estado interno de slots
print(driver._slots.status())
# {'free': 499, 'in_use': 1, 'corrupted': 0, 'total': 500}
```

---

## Playground interactivo

`tools/message_playground.py` es una CLI de prueba para el dispositivo real.
Permite construir y enviar mensajes MULTI paso a paso, gestionar la tabla de
mensajes y ver el estado del panel sin escribir código.

```bash
python tools/message_playground.py
```

La IP y comunidades se pueden sobreescribir con variables de entorno:

```bash
VMS_PANEL_IP=10.0.0.5 VMS_COMMUNITY_WRITE=secret python tools/message_playground.py
```

| Variable | Default |
|---|---|
| `VMS_PANEL_IP` | `66.17.99.157` |
| `VMS_PANEL_PORT` | `161` |
| `VMS_COMMUNITY_READ` | `public` |
| `VMS_COMMUNITY_WRITE` | `administrator` |
| `VMS_DEVICE_TYPE` | `daktronics_vfc` |

#### Opciones del menú

| Opción | Descripción |
|---|---|
| `1` | Envío asistido — modo automático o por rectángulos `[tr]`; guía fuente, justificación, color, páginas y campos dinámicos |
| `2` | Envío directo — ingresá el MULTI string completo; lo valida antes de enviar |
| `3` | Limpiar panel — activa el mensaje blank |
| `4` | Ver estado completo — online, modo de control, errores activos, watchdog, mensaje activo |
| `5` | Ver mensajes en tabla — slots IN_USE + scan de primeros 20 slots |
| `6` | Borrar mensaje — muestra la lista de mensajes y libera un slot por número |

#### Modos de construcción de mensaje

**Modo automático** — guía font, justificación horizontal/vertical, color y
texto por página. Soporta campos dinámicos (`@N`) y separadores de línea (`|`).

**Modo rectángulo** — permite componer el mensaje con múltiples zonas `[tr]`
por página. Cada zona pide coordenadas, fuente, color y contenido de forma independiente.

#### Campos dinámicos en el playground

| Código | Tag | Descripción |
|---|---|---|
| `@1` | `[f1]` | Hora local 12 h (con segundos) |
| `@2` | `[f2]` | Hora local 24 h (con segundos) |
| `@3` / `@4` | `[f3]` / `[f4]` | Temperatura °C / °F |
| `@5` / `@6` | `[f5]` / `[f6]` | Velocidad km/h / mph |
| `@7` | `[f7]` | Día de la semana |
| `@8` / `@9` | `[f8]` / `[f9]` | Fecha mm/dd/yy / dd/mm/yy |
| `@10` | `[f10]` | Año yyyy |
| `@11` / `@12` | `[f11]` / `[f12]` | Hora sin segundos 12 h / 24 h |

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
