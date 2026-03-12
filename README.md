# vms-driver

Driver NTCIP 1203 sobre SNMP v2c para paneles VMS/DMS de señalización variable.
Implementaciones disponibles: **Daktronics VFC** (144×96 px, ámbar), **Fixalia** (320×64 px) y **ChainZone** (48×96 px).

---

## Tabla de contenidos

- [Arquitectura](#arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Variables de entorno](#variables-de-entorno)
- [Capa SNMP — `snmp/client.py`](#capa-snmp)
- [Capa de OIDs](#capa-de-oids)
  - [`snmp/ntcip1203.py` — Estándar NTCIP 1203 v03](#snmpntcip1203py)
  - [`driver/daktronics/oids.py`](#driverdaktronicsoidspy)
  - [`driver/fixalia/oids.py`](#driverfixaliaoidspy)
- [Modelos de datos — `models/device.py`](#modelos-de-datos)
- [MULTI — `driver/multi.py`](#multi---drivermultipy)
- [SlotManager — `driver/slots.py`](#slotmanager---driversslotspy)
- [Interfaz de driver — `driver/base.py`](#interfaz-de-driver)
- [NTCIPDriver — `driver/ntcip_driver.py`](#ntcipdriver---driverntcip_driverpy)
- [Módulo de gráficos — `driver/graphics/`](#módulo-de-gráficos)
- [Factory — `driver/factory.py`](#factory)
- [Driver Daktronics VFC](#driver-daktronics-vfc)
- [Driver Fixalia](#driver-fixalia)
- [Driver ChainZone](#driver-chainzone)
- [Dispositivos de referencia](#dispositivos-de-referencia)
- [Uso rápido](#uso-rápido)
- [Playground interactivo](#playground-interactivo)
- [Dependencias](#dependencias)

---

## Arquitectura

```
┌──────────────────────────────────────────────────────────┐
│                   Aplicación / API                       │
└─────────────────────────┬────────────────────────────────┘
                          │  VMSDriver (interfaz abstracta)
          ┌───────────────┼───────────────────┐
          │               │                   │
┌─────────▼──────────┐  ┌─▼──────────────┐  ┌▼─────────────────┐
│ DaktronicsVFCDriver│  │  FixaliaDriver  │  │  ChainZoneDriver  │
│ daktronics/driver  │  │ fixalia/driver  │  │ chainzone/driver  │
└─────────┬──────────┘  └────┬────────────┘  └──────┬───────────┘
          │                  │                       │
          └──────────────────┼───────────────────────┘
                             │  NTCIPDriver (implementación base NTCIP 1203)
                    ┌────────▼──────────────────────────────┐
                    │         driver/ntcip_driver.py         │
                    │  8 métodos · auto-descubrimiento       │
                    │  fonts · tags · slots · validación     │
                    └────────┬──────────────────────────────┘
                             │  driver/slots.py (compartido)
                    ┌────────▼───────────────────┐
                    │      SlotManager           │
                    └────────────────────────────┘
          │                  │                       │
    OIDs  │            OIDs  │               OIDs    │
┌─────────▼───────────┐  ┌───▼──────────────────┐  ┌▼──────────────────────┐
│ daktronics/oids.py  │  │  fixalia/oids.py      │  │  chainzone/oids.py    │
│ (re-exporta ntcip)  │  │  (re-exporta ntcip)   │  │  (prioridad override) │
└──────────┬──────────┘  └────────┬──────────────┘  └──────────┬────────────┘
           └────────────┬─────────┘───────────────────────────┘
                        │ OIDs estándar
             ┌──────────▼───────────────────┐
             │    snmp/ntcip1203.py          │
             │  7 grupos NTCIP 1203 v03     │
             └─────────────────────────────┘
                          │ transporte
             ┌────────────▼────────────────┐
             │      snmp/client.py          │
             │  SNMPClient — get/set/walk   │
             │  pysnmp v7 · SNMP v2c        │
             └─────────────────────────────┘
```

El sistema está diseñado para múltiples fabricantes: cada fabricante extiende
`NTCIPDriver` (~3 líneas de código) sin reimplementar el protocolo.
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
│   ├── base.py            # VMSDriver — interfaz abstracta (8 métodos)
│   ├── factory.py         # create_driver(DeviceInfo) — instanciación por fabricante
│   ├── ntcip_driver.py    # NTCIPDriver — implementación base NTCIP 1203 completa
│   ├── multi.py           # MultiBuilder + MultiValidator — lenguaje MULTI (NTCIP 1203)
│   ├── slots.py           # SlotManager — gestión thread-safe de slots (compartido)
│   ├── daktronics/
│   │   ├── __init__.py
│   │   ├── driver.py      # DaktronicsVFCDriver — subclase de NTCIPDriver (~3 líneas)
│   │   ├── oids.py        # Constantes del dispositivo + re-export ntcip1203
│   │   ├── slots.py       # Shim de compatibilidad → re-exporta driver.slots
│   │   └── multi.py       # Shim de compatibilidad → re-exporta driver.multi
│   ├── fixalia/
│   │   ├── __init__.py
│   │   ├── driver.py      # FixaliaDriver — subclase de NTCIPDriver (~3 líneas)
│   │   └── oids.py        # Constantes del dispositivo + re-export ntcip1203
│   └── chainzone/
│       ├── __init__.py
│       ├── driver.py      # ChainZoneDriver — subclase de NTCIPDriver (~3 líneas)
│       └── oids.py        # Prioridad de activación confirmada en panel real
│   ├── graphics/
│   │   ├── __init__.py
│   │   ├── image.py       # load_image, resize_to_sign, to_ntcip_bitmap
│   │   ├── bitmap.py      # split_into_blocks — fragmentación en bloques SNMP
│   │   └── payload.py     # convert_image → GraphicPayload
│   └── chainzone/
│
├── models/
│   └── device.py          # DeviceInfo, DeviceStatus, Message, enums
│
├── tests/
│   ├── test_daktronics_driver.py  # tests de integración — panel real
│   ├── test_fixalia_driver.py     # tests de integración — simulador
│   ├── test_chainzone_driver.py   # tests de integración — panel real
│   └── test_snmp_client.py        # tests de integración — panel real
│
└── tools/
    ├── message_playground.py  # CLI interactivo para pruebas en dispositivo real
    └── diag_graphic.py        # Diagnóstico paso a paso de subida de gráficos NTCIP
```

> **Módulos canónicos compartidos:**
> - `driver/ntcip_driver.py` — `NTCIPDriver` (implementación base; todos los drivers heredan de aquí)
> - `driver/slots.py` — `SlotManager` (todos los drivers importan desde aquí)
> - `driver/multi.py` — `MultiBuilder` / `MultiValidator` (independiente del fabricante)
>
> Los shims `driver/daktronics/slots.py` y `driver/daktronics/multi.py` existen
> solo para compatibilidad con imports históricos.

---

## Variables de entorno

Toda la configuración de red y tiempos se toma del entorno (12-factor III).
Ningún valor está hardcodeado en los módulos del driver.

| Variable | Default | Descripción |
|---|---|---|
| `VMS_COMMUNITY_READ` | `public` | Community string de lectura SNMP |
| `VMS_COMMUNITY_WRITE` | `administrator` | Community string de escritura SNMP |
| `VMS_SNMP_PORT` | `161` | Puerto UDP SNMP |
| `VMS_SNMP_TIMEOUT` | `10` | Timeout por intento (segundos) |
| `VMS_SNMP_RETRIES` | `3` | Reintentos ante timeout |
| `VMS_VALIDATE_TIMEOUT` | `10` | Timeout esperando validación de mensaje (segundos) |
| `VMS_VALIDATE_INTERVAL` | `0.5` | Intervalo entre polls de validación (segundos) |
| `VMS_GFX_BLOCK_SIZE` | `1023` | Bytes por bloque SNMP para gráficos (ver nota Daktronics VFC) |
| `VMS_GFX_BLOCK_DELAY` | `0.05` | Pausa entre bloques de gráfico (segundos) |
| `VMS_PANEL_IP` | — | IP del panel (usada en tests y playground) |
| `VMS_PANEL_PORT` | `161` | Puerto del panel (usado en playground) |

---

## Capa SNMP

**`snmp/client.py`** — `SNMPClient`

Cliente SNMP v2c sincrónico que envuelve la API asyncio de pysnmp v7.

```python
from snmp.client import SNMPClient

client = SNMPClient(ip="66.17.99.157", community="public")

value = client.get("1.3.6.1.2.1.1.1.0")
ok    = client.set("1.3.6.1.4.1.1206.4.2.3.6.1.0", 4)
pairs = client.walk("1.3.6.1.4.1.1206.4.2.3")
```

| Parámetro   | Default | Descripción                              |
|-------------|---------|------------------------------------------|
| `ip`        | —       | Dirección IP del panel                   |
| `community` | —       | Community string (lectura o escritura)   |
| `port`      | `161`   | Puerto UDP                               |
| `timeout`   | `10`    | Segundos por intento                     |
| `retries`   | `3`     | Reintentos ante timeout                  |

**Errores:**
- `ConnectionError` — `errorIndication` (timeout, host unreachable, …)
- `ValueError` — `errorStatus` (noSuchObject, wrongType, …)

---

## Capa de OIDs

### `snmp/ntcip1203.py`

OIDs del estándar NTCIP 1203 v03, válidos para cualquier fabricante.
Base: `1.3.6.1.4.1.1206.4.2.3`

| Grupo | Sub-árbol | Descripción |
|---|---|---|
| `dmsSignCfg` | `.1.X.0` | Configuración física (tipo, dimensiones mm, tecnología, bordes) |
| `vmsCfg` | `.2.X.0` | Dimensiones en píxeles, pitch, color monocromático |
| `multiCfg` | `.4.X.0` | Defaults MULTI (fuente, justificación, tiempos, color, longitud máx.) |
| `dmsMessage` escalares | `.5.X.0` | Contadores de slots por tipo de memoria y memoria libre |
| `dmsMessageTable` | `.5.8.1.X` | Tabla de mensajes (multiString, owner, CRC, priority, status) |
| `signControl` | `.6.X.0` | Control del panel (modo, reset, activateMessage, error de activación) |
| `dmsStatus` | `.9.X.0` | Estado (errores, puerta, watchdog, velocidad, fallos de píxel) |

**Helpers para `dmsMessageTable`:**

```python
from snmp.ntcip1203 import msg_multi_string, msg_crc, msg_status

msg_multi_string(3, 2)  # → "1.3.6.1.4.1.1206.4.2.3.5.8.1.3.3.2"
msg_status(3, 2)        # → "1.3.6.1.4.1.1206.4.2.3.5.8.1.9.3.2"
```

---

### `driver/daktronics/oids.py`

Re-exporta todos los símbolos de `snmp.ntcip1203` y añade las constantes
específicas del Daktronics VFC leídas del entorno.

| Constante | Valor | Notas |
|---|---|---|
| `COMMUNITY_READ` | env / `"public"` | |
| `COMMUNITY_WRITE` | env / `"administrator"` | |
| `SNMP_PORT` | env / `161` | |
| `SNMP_TIMEOUT` | env / `10` | |
| `SNMP_RETRIES` | env / `3` | |
| `VALIDATE_TIMEOUT` | env / `10.0` | |
| `VALIDATE_INTERVAL` | env / `0.5` | |
| `SIGN_WIDTH_PIXELS` | `144` | confirmado en dispositivo |
| `SIGN_HEIGHT_PIXELS` | `96` | confirmado en dispositivo |
| `DEFAULT_FONT` | `24` | confirmado en dispositivo |
| `DEFAULT_FOREGROUND_RGB` | `(255, 180, 0)` | ámbar `#FFB400` |
| `MAX_MULTI_STRING_LEN` | `1500` | confirmado en dispositivo |
| `MAX_NUMBER_PAGES` | `6` | confirmado en dispositivo |
| `COLOR_SCHEME` | `4` | colorClassic |
| `MEMORY_CHANGEABLE` | `3` | usar por defecto |
| `MEMORY_CURRENT_BUFFER` | `5` | solo lectura — mensaje activo |
| `MEMORY_BLANK` | `7` | apaga el panel |
| `MSG_SLOTS_PER_MEMORY_TYPE` | `500` | confirmado en dispositivo |

---

### `driver/fixalia/oids.py`

Mismo patrón que `driver/daktronics/oids.py`. Re-exporta `snmp.ntcip1203`
y añade constantes de referencia del simulador Fixalia.

| Constante | Valor | Notas |
|---|---|---|
| `COMMUNITY_READ` | env / `"public"` | |
| `COMMUNITY_WRITE` | env / `"administrator"` | |
| `SNMP_PORT` | env / `161` | |
| `SNMP_TIMEOUT` | env / `10` | |
| `SNMP_RETRIES` | env / `3` | |
| `VALIDATE_TIMEOUT` | env / `10.0` | |
| `VALIDATE_INTERVAL` | env / `0.5` | |
| `SIGN_WIDTH_PIXELS` | `320` | confirmado en simulador |
| `SIGN_HEIGHT_PIXELS` | `64` | confirmado en simulador |
| `MSG_SLOTS_PER_MEMORY_TYPE` | `100` | conservador — se lee de `DMS_MAX_CHANGEABLE_MSG` |
| `MEMORY_CHANGEABLE` | `3` | usar por defecto |
| `MEMORY_CURRENT_BUFFER` | `5` | solo lectura — mensaje activo |
| `MEMORY_BLANK` | `7` | apaga el panel |

---

## Modelos de datos

**`models/device.py`** — tipos compartidos entre el driver, el polling worker
y el command handler.

### `DeviceInfo`

```python
from models.device import DeviceInfo

device_info = DeviceInfo(
    ip="66.17.99.157",
    port=161,
    device_type="daktronics_vfc",   # o "fixalia"
)
```

### `DeviceStatus`

```python
status.online              # → bool
status.control_mode        # → ControlMode | None
status.short_error_status  # → int (bitmap)
status.has_errors          # → bool (propiedad)
status.active_errors()     # → list[str] — nombres de los bits activos
status.door_open           # → bool
status.watchdog_failures   # → int
status.last_polled         # → datetime | None
```

**`ShortErrorBit`** — bits del bitmap `short_error_status`:

| Bit | Nombre | Descripción |
|---|---|---|
| 1 | `COMMUNICATIONS` | Error de comunicaciones |
| 2 | `POWER` | Error de alimentación |
| 3 | `ATTACHED_DEVICE` | Error en dispositivo externo |
| 4 | `LAMP` | Error de lámparas |
| 5 | `PIXEL` | Error de píxeles |
| 6 | `PHOTOCELL` | Error de fotocélula |
| 7 | `MESSAGE` | Error de mensaje |
| 8 | `CONTROLLER` | Error del controlador |
| 9 | `TEMPERATURE` | Advertencia de temperatura |

### `Message`

```python
@dataclass
class Message:
    memory_type: int           # tipo de memoria (3=changeable, 5=currentBuffer, …)
    slot: int                  # número de slot (1..N)
    multi_string: str
    status: MessageStatus | None
    crc: int | None
```

### Enums

| Enum | Valores clave |
|---|---|
| `ControlMode` | `LOCAL=2`, `CENTRAL=4` |
| `MessageStatus` | `VALID=4`, `ERROR=5`, `MODIFY_REQ=6`, `VALIDATE_REQ=7`, `NOT_USED_REQ=8` |
| `SignType` | `FULL_MATRIX=6` |

---

## MULTI — `driver/multi.py`

`MultiValidator` y `MultiBuilder` implementan el lenguaje MULTI definido en
NTCIP 1203 v03. Son independientes del fabricante.

### `MultiValidator`

```python
from driver.multi import MultiValidator

validator = MultiValidator(width=144, height=96, max_string_length=1500, max_pages=6)
result = validator.validate("[fo24][jl3]PRECAUCIÓN[nl]OBRAS")
if not result:
    print(result.errors)
```

**Chequeos:** no vacío, longitud, páginas, tags NTCIP 1203 válidos (bits 0–29),
fuentes en rango, gráficos en rango, coordenadas `[tr]`/`[cr]` dentro del panel.

### `MultiBuilder`

```python
from driver.multi import MultiBuilder

multi = (
    MultiBuilder()
    .page_time(30, 0)
    .page_middle()
    .font(24)
    .color_foreground(255, 180, 0)
    .center()
    .text("DESVIO")
    .new_page()
    .page_time(30, 0)
    .page_middle()
    .font(24)
    .center()
    .text("RUTA 9")
    .build()
)
```

**Métodos principales:**

| Método | Tag | Descripción |
|---|---|---|
| `.text(s)` | — | Texto literal |
| `.center()` / `.left()` / `.right()` | `[jl3/2/4]` | Justificación horizontal |
| `.page_middle()` / `.page_top()` / `.page_bottom()` | `[jp3/2/4]` | Posición vertical |
| `.new_page()` / `.new_line()` | `[np]` / `[nl]` | Separadores |
| `.font(n)` | `[foN]` | Fuente (1–255) |
| `.page_time(on, off)` | `[ptXoY]` | Tiempo de página en décimas |
| `.color_foreground(r,g,b)` | `[cfR,G,B]` | Color de texto RGB |
| `.color_background(r,g,b)` | `[cbR,G,B]` | Color de fondo RGB |
| `.page_background(r,g,b)` | `[pbR,G,B]` | Fondo de página RGB |
| `.text_rect(x,y,w,h)` | `[trX,Y,W,H]` | Zona de texto |
| `.color_rect(x,y,w,h,r,g,b)` | `[crX,Y,W,H,R,G,B]` | Rectángulo de color |
| `.flash(on, off)` / `.flash_end()` | `[fltXoY]` / `[/fl]` | Flash |
| `.field(n)` | `[fN]` | Campo dinámico (1–12) |
| `.build()` | — | Construye y valida (lanza `ValueError` si inválido) |
| `.build_unsafe()` | — | Construye sin validar (solo para tests) |

**Campos dinámicos `[fN]`:**

| Tag | Descripción |
|---|---|
| `[f1]` / `[f2]` | Hora local 12 h / 24 h (con segundos) |
| `[f3]` / `[f4]` | Temperatura °C / °F |
| `[f5]` / `[f6]` | Velocidad km/h / mph |
| `[f7]` | Día de la semana |
| `[f8]` / `[f9]` | Fecha mm/dd/yy / dd/mm/yy |
| `[f10]` | Año yyyy |
| `[f11]` / `[f12]` | Hora sin segundos 12 h / 24 h |

---

## SlotManager — `driver/slots.py`

Gestor thread-safe de los slots de `dmsMessageTable`. Compartido entre todos
los drivers — importar siempre desde `driver.slots`.

```python
from driver.slots import SlotManager

mgr = SlotManager(total_slots=500)

slot = mgr.acquire()          # → int — primer slot FREE (atómico)
mgr.release(slot)             # FREE
mgr.mark_corrupted(slot)      # CORRUPTED permanente
mgr.is_available(slot)        # → bool
mgr.is_tracked(slot)          # → bool — True si el slot está en rango
mgr.in_use_slots()            # → list[int] ordenada
mgr.status()                  # → {"free": N, "in_use": N, "corrupted": N, "total": N}
```

**Estados:**

```
FREE ──acquire()──► IN_USE ──release()──► FREE
                       │
                  mark_corrupted()
                       │
                       ▼
                   CORRUPTED  (terminal)
```

`acquire()` lanza `RuntimeError` si no hay slots `FREE`.
Todas las operaciones están protegidas por `threading.Lock`.

---

## Interfaz de driver

**`driver/base.py`** — `VMSDriver` (ABC)

```python
class VMSDriver(ABC):

    def ping(self) -> bool:
        """Verifica conectividad SNMP. Más liviano que get_status()."""

    def get_status(self) -> DeviceStatus:
        """Lee el estado actual del panel."""

    def get_current_message(self) -> str:
        """Lee el MULTI string del mensaje activo (currentBuffer)."""

    def get_message(self, slot: int) -> Message | None:
        """Lee un mensaje específico. None si el slot está vacío."""

    def get_messages(self) -> list[Message]:
        """Lista todos los mensajes válidos en la tabla."""

    def send_message(self, multi_string: str, priority: int = 3) -> Message:
        """Escribe y activa un mensaje. Devuelve Message con CRC confirmado."""

    def delete_message(self, slot: int) -> bool:
        """Borra un mensaje de la messageTable. True si tuvo éxito."""

    def clear_message(self) -> bool:
        """Activa el mensaje blank. True si tuvo éxito."""
```

Para agregar un nuevo fabricante:
1. Crear `driver/fabricante/__init__.py`
2. Crear `driver/fabricante/driver.py` (subclase de `NTCIPDriver`, ~3 líneas)
3. Registrar en `driver/factory.py` → `_REGISTRY`

---

## NTCIPDriver — `driver/ntcip_driver.py`

**`NTCIPDriver`** es la implementación base completa de NTCIP 1203 v03.
Todos los drivers de fabricante heredan de esta clase y normalmente solo
sobreescriben `_get_activate_priority()`.

### Auto-descubrimiento en `_init()`

Al instanciar, el driver hace las siguientes lecturas SNMP automáticamente:

| Paso | Método | Descripción |
|---|---|---|
| 1 | `_detect_source_ip()` | Detecta la IP local con ruta al panel (sin tráfico extra) |
| 2 | `_discover_slot_count()` | Lee `DMS_MAX_CHANGEABLE_MSG` → inicializa `SlotManager` |
| 3 | `_discover_fonts()` | Lee la tabla de fuentes (número, nombre, altura, ancho) |
| 4 | `_discover_supported_tags()` | Bitmask NTCIP o probe empírico en slot 1 |
| 5 | `_init_validator()` | Lee resolución + límites → construye `MultiValidator` |

Si el panel no responde en el paso 2, lanza `ConnectionError` (fail fast).

### Descubrimiento de fuentes

```python
driver = ChainZoneDriver(ip="192.168.8.49")

driver.panel_info
# {
#   "ip": "192.168.8.49",
#   "slots": 9,
#   "fonts": {1: {"name": "fb12", "height": 12, "width": 0}, ...},
#   "supported_tags": ["cf", "fo", "jl", "jp", "nl", "np", "pt", ...],
#   "largest_font": 7,
#   "bold_largest_font": 7
# }

driver.get_largest_font()       # → int | None — fuente con mayor altura
driver.get_bold_largest_font()  # → int | None — fuente bold (nombre "fb…") más grande
```

### Descubrimiento de tags MULTI soportados

1. Intenta leer `dmsSupportedMultiTags` (bitmask NTCIP 1203 v03)
   - Algunos firmwares (ej. Daktronics VFC) devuelven el valor como `OctetString`
     en lugar de `Integer`; el driver lo decodifica usando NTCIP bit-packing
     (byte i, bit 7−j → flag i×8+j)
2. Si el panel devuelve `0` o falla → hace probe empírico: escribe un MULTI mínimo
   por cada tag en slot 1, solicita validación y verifica si el panel devuelve `VALID`
3. Los tags core (`jl`, `jp`, `nl`, `np`) siempre se incluyen sin probe

### `send_graphic(path, slot, color_type?, crop?) → GraphicPayload`

Sube una imagen al panel como gráfico NTCIP 1203, referenciable con `[gN]` en MULTI.

```
1. Convertir imagen → bitmap BGR / mono1bit, dividir en bloques de VMS_GFX_BLOCK_SIZE bytes
2. SET dmsGraphicStatus = modifyReq (7)
3. SET dmsGraphicNumber, Height, Width, Type
4. POLL dmsGraphicStatus hasta modifying (2)  ← garantiza que el dispositivo está listo
5. SET dmsGraphicBlockData para cada bloque (1-based, OctetString)
6. SET dmsGraphicStatus = readyForUseReq (8)
7. POLL dmsGraphicStatus hasta readyForUse (4)
```

```python
payload = driver.send_graphic(
    path="foto.jpg",
    slot=4,
    color_type=4,   # 4=color24bit (default), 1=mono1bit
    crop="center",  # "left" (default) | "center" | "right"
)
# payload.width, payload.height, payload.total_bytes, payload.blocks
driver.send_message(f"[g{payload.slot}]")
```

### `send_message(multi_string, priority?) → Message`

```
1. Validar MULTI string (MultiValidator — tags, dimensiones, longitud)
2. acquire() → slot libre del SlotManager
3. SET messageStatus  = modifyReq (6)
4. SET messageMultiString = <MULTI string>
5. SET messageStatus  = validateReq (7)
6. POLL messageStatus hasta valid(4) — timeout VMS_VALIDATE_TIMEOUT
   ├─ valid  → continuar
   └─ error  → mark_corrupted(slot) + raise ValueError
7. GET messageCRC
8. SET activateMessage = <payload 12 bytes big-endian>
   └─ excepción → release(slot) + raise
```

**Payload `dmsActivateMessage` (12 bytes big-endian):**

```
2 B — duration     (0xFFFF = infinito)
1 B — priority     (sobreescribible por subclase)
1 B — memory_type  (3 = changeable)
2 B — slot
2 B — CRC
4 B — IP origen    (detectada automáticamente)
```

---

## Módulo de gráficos

**`driver/graphics/`** — conversión de imagen a bitmap NTCIP 1203 y fragmentación en bloques SNMP.

### `image.py`

```python
from driver.graphics.image import load_image, resize_to_sign, to_ntcip_bitmap

img    = load_image("foto.jpg")                 # abre y convierte a RGB
img    = resize_to_sign(img, 144, 96, "center") # fill + recorte al tamaño del panel
bitmap = to_ntcip_bitmap(img, color_type=4)     # BGR (color24bit) o mono1bit
```

| `color_type` | Formato | Bytes/píxel |
|---|---|---|
| `4` | color24bit — 3 bytes BGR por píxel | 3 |
| `1` | mono1bit — 1 bit/píxel, MSB-first, filas padded a byte boundary | ~1/8 |

### `bitmap.py`

```python
from driver.graphics.bitmap import split_into_blocks

blocks = split_into_blocks(bitmap, block_size=1023)
# El último bloque se zero-padea a block_size bytes
```

### `payload.py`

```python
from driver.graphics.payload import convert_image, GraphicPayload

payload = convert_image("foto.jpg", width=144, height=96, slot=4, block_size=1023)
# payload.width, payload.height, payload.color_type, payload.blocks, payload.total_bytes
```

---

## Factory

**`driver/factory.py`**

```python
from driver.factory import create_driver, available_drivers
from models.device import DeviceInfo

driver = create_driver(DeviceInfo(ip="66.17.99.157",   device_type="daktronics_vfc"))
driver = create_driver(DeviceInfo(ip="127.0.0.1",      device_type="fixalia"))
driver = create_driver(DeviceInfo(ip="192.168.8.49",   device_type="chainzone"))

available_drivers()  # → ["daktronics_vfc", "fixalia", "chainzone"]
```

**Registro actual:**

| `device_type` | Clase |
|---|---|
| `daktronics_vfc` | `driver.daktronics.driver.DaktronicsVFCDriver` |
| `fixalia` | `driver.fixalia.driver.FixaliaDriver` |
| `chainzone` | `driver.chainzone.driver.ChainZoneDriver` |

---

## Driver Daktronics VFC

**`driver/daktronics/driver.py`** — `DaktronicsVFCDriver(NTCIPDriver)`

```python
from driver.daktronics.driver import DaktronicsVFCDriver

driver = DaktronicsVFCDriver(ip="66.17.99.157")
```

Hereda toda la lógica de `NTCIPDriver`. La clase tiene ~3 líneas de código
propio: usa la prioridad de activación estándar (`3`) y no sobreescribe ningún
otro comportamiento.

Todo el auto-descubrimiento (fuentes, tags, slots, dimensiones) lo realiza
`NTCIPDriver._init()` al instanciar. Si el panel no responde, lanza
`ConnectionError` (fail fast).

**Tests:**
```bash
VMS_PANEL_IP=66.17.99.157 python tests/test_daktronics_driver.py
```

---

## Driver Fixalia

**`driver/fixalia/driver.py`** — `FixaliaDriver(NTCIPDriver)`

```python
from driver.fixalia.driver import FixaliaDriver

driver = FixaliaDriver(ip="127.0.0.1")
```

Hereda toda la lógica de `NTCIPDriver`. Auto-descubre resolución, fuentes,
tags y slots al inicializar leyendo el simulador vía SNMP. Sin fallbacks
silenciosos.

**Tests:**
```bash
VMS_PANEL_IP=127.0.0.1 python tests/test_fixalia_driver.py
```

---

## Driver ChainZone

**`driver/chainzone/driver.py`** — `ChainZoneDriver(NTCIPDriver)`

```python
from driver.chainzone.driver import ChainZoneDriver

driver = ChainZoneDriver(ip="192.168.8.49")
```

Panel confirmado: 48×96 px, 9 slots, 19 fuentes. Hereda toda la lógica de
`NTCIPDriver` y sobreescribe únicamente la prioridad de activación
(`0xFF` — confirmado contra panel real).

```python
# Uso recomendado: fuente dinámica descubierta en init
largest = driver.get_bold_largest_font()
multi = f"[fo{largest}][jl3]CHAIN[np][fo{largest}][jl3]ZONE"
msg = driver.send_message(multi)
```

**Constante específica del fabricante (`driver/chainzone/oids.py`):**

| Constante | Valor | Notas |
|---|---|---|
| `ACTIVATE_MESSAGE_PRIORITY` | `0xFF` | Confirmado contra panel real ChainZone |

**Tests:**
```bash
VMS_PANEL_IP=192.168.8.49 python tests/test_chainzone_driver.py
```

---

## Dispositivos de referencia

### Daktronics VFC

| Parámetro | Valor |
|---|---|
| IP | `66.17.99.157` |
| Puerto SNMP | `161` UDP / SNMP v2c |
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
| Páginas máx. | 6 |
| Esquema de color | 4 = colorClassic |
| Slots por tipo de memoria | 500 |
| Slots de gráficos | 255 |
| Graphic max size | 64 449 bytes |
| Graphic block size real | **1 023 bytes** (ver nota) |

> **Quirks del firmware Daktronics VFC:**
> - `dmsSupportedMultiTags` se devuelve como `OctetString` (no `Integer`) — el driver lo decodifica con NTCIP bit-packing
> - `dmsGraphicBlockSize` (OID `.10.3.0`) devuelve `64449`, que es el *max size* total, no el block size de transferencia; el block size real confirmado es **1023 bytes** (hardcodeado como `VMS_GFX_BLOCK_SIZE`)
> - `dmsGraphicStatus = notUsedReq (6)` devuelve `wrongValue` — el driver va directo a `modifyReq (7)` desde cualquier estado
> - Enviar un bloque de 64449 bytes por UDP causa fragmentación IP que el VFC descarta silenciosamente → timeout

### Fixalia (simulador)

| Parámetro | Valor |
|---|---|
| IP (simulador) | `127.0.0.1` |
| Puerto SNMP | `161` UDP / SNMP v2c |
| Community lectura | `public` |
| Community escritura | `administrator` |
| Tipo de panel | Full-matrix (6 = vmsFull) |
| Dimensiones | 320 × 64 píxeles |
| Dimensiones físicas | 2 900 × 2 900 mm |
| Mensajes permanentes | 2 |

### ChainZone

| Parámetro | Valor |
|---|---|
| IP | `192.168.8.49` |
| Puerto SNMP | `161` UDP / SNMP v2c |
| Community lectura | `public` |
| Community escritura | `public` |
| Dimensiones | 48 × 96 píxeles |
| Slots | 9 |
| Fuentes | 19 (auto-descubiertas) |
| Prioridad de activación | `0xFF` |

---

## Uso rápido

```python
from driver.factory import create_driver
from driver.multi import MultiBuilder
from models.device import DeviceInfo

# Daktronics VFC
driver = create_driver(DeviceInfo(ip="66.17.99.157", device_type="daktronics_vfc"))

# Fixalia
driver = create_driver(DeviceInfo(ip="127.0.0.1", device_type="fixalia"))

# ChainZone
driver = create_driver(DeviceInfo(ip="192.168.8.49", device_type="chainzone"))

# Verificar conectividad
if not driver.ping():
    raise RuntimeError("Panel no responde")

# Fuente detectada automáticamente (recomendado para ChainZone y otros)
font = driver.get_bold_largest_font() or 1

# Enviar un mensaje con el builder
multi = (
    MultiBuilder()
    .page_time(30, 0)
    .page_middle()
    .font(font)
    .center()
    .text("PRECAUCIÓN")
    .new_line()
    .text("OBRAS EN VÍA")
    .build()
)
msg = driver.send_message(multi)
print(f"slot={msg.slot}  CRC={msg.crc}  status={msg.status}")

# Estado del panel
status = driver.get_status()
print(f"online={status.online}  errores={status.active_errors()}")

# Info del panel (fuentes, tags, slots)
print(driver.panel_info)

# Listar mensajes en tabla
for m in driver.get_messages():
    print(f"slot={m.slot}  {m.multi_string}")

# Borrar un mensaje específico
driver.delete_message(slot=2)

# Limpiar pantalla
driver.clear_message()

# Subir una imagen como gráfico NTCIP y activarla
payload = driver.send_graphic("foto.jpg", slot=4, color_type=4, crop="center")
driver.send_message(f"[g{payload.slot}]")

# Estado interno de slots
print(driver._slots.status())
# {'free': 499, 'in_use': 1, 'corrupted': 0, 'total': 500}
```

---

## Playground interactivo

`tools/message_playground.py` es una CLI de prueba para el dispositivo real.

```bash
python tools/message_playground.py
```

Variables de entorno para seleccionar el panel:

```bash
VMS_PANEL_IP=10.0.0.5 VMS_DEVICE_TYPE=fixalia python tools/message_playground.py
```

| Variable | Default |
|---|---|
| `VMS_PANEL_IP` | `66.17.99.157` |
| `VMS_PANEL_PORT` | `161` |
| `VMS_COMMUNITY_READ` | `public` |
| `VMS_COMMUNITY_WRITE` | `administrator` |
| `VMS_DEVICE_TYPE` | `daktronics_vfc` |

| Opción | Descripción |
|---|---|
| `1` | Envío asistido — modo automático o por rectángulos `[tr]` |
| `2` | Envío directo — MULTI string completo (valida antes de enviar) |
| `3` | Limpiar panel |
| `4` | Ver estado completo |
| `5` | Ver mensajes en tabla |
| `6` | Borrar mensaje por slot |
| `7` | Subir gráfico (imagen → panel) — color24bit o mono1bit |

### Diagnóstico de gráficos

Para depurar problemas de subida de imágenes, usar el script de diagnóstico:

```bash
python tools/diag_graphic.py "/ruta/imagen.jpg" 4
```

Ejecuta cada SET SNMP por separado con logging explícito e indica el paso exacto donde falla.

---

## Tests de integración

```bash
# Daktronics VFC (panel real)
VMS_PANEL_IP=66.17.99.157 python tests/test_daktronics_driver.py

# Fixalia (simulador)
VMS_PANEL_IP=127.0.0.1 python tests/test_fixalia_driver.py

# ChainZone (panel real)
VMS_PANEL_IP=192.168.8.49 python tests/test_chainzone_driver.py
```

Los tests conectan directamente al panel/simulador — no usan mocks.

---

## Dependencias

Principales:

```
pysnmp==7.1.22     # fork lextudio; expone pysnmp.hlapi.v3arch.asyncio
pysmi==1.6.3
cryptography==46.x
```

Desarrollo / tests:

```
pytest==9.x
pytest-cov==4.x
```

```bash
pip install -r requirements.txt
```

> **Nota:** usar `pysnmp` versión 7.x (fork lextudio). El paquete original dejó de
> mantenerse en la versión 4.x. Este proyecto usa la API `pysnmp.hlapi.v3arch.asyncio`.
