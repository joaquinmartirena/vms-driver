"""
OIDs del estándar NTCIP 1203 v03 — Dynamic Message Signs (DMS)

Válidos para cualquier fabricante que cumpla con el estándar.
Referencia: NTCIP 1203 v03 — SNMP Management Information Base for DMS
Base OID:   1.3.6.1.4.1.1206.4.2.3
            enterprises(1).ntcip(1206).devices(4).vmsDev(2).dms(3)
"""

_BASE = "1.3.6.1.4.1.1206.4.2.3"

# ─── MIB-II System ────────────────────────────────────────────────────────────
SYS_DESCR                        = "1.3.6.1.2.1.1.1.0"   # sysDescr — descripción del agente

# ═══════════════════════════════════════════════════════════════════════════════
# dmsSignCfg (dms.1) — Configuración física del panel
# ═══════════════════════════════════════════════════════════════════════════════
DMS_SIGN_ACCESS                  = f"{_BASE}.1.1.0"   # dmsSignAccess — tipo de acceso físico al gabinete
DMS_SIGN_TYPE                    = f"{_BASE}.1.2.0"   # dmsSignType — tipo de panel (6=vmsFullMatrix confirmado en VFC)
DMS_SIGN_HEIGHT                  = f"{_BASE}.1.3.0"   # dmsSignHeight — altura física de la cara del panel (mm)
DMS_SIGN_WIDTH                   = f"{_BASE}.1.4.0"   # dmsSignWidth — anchura física de la cara del panel (mm)
DMS_HORIZONTAL_BORDER            = f"{_BASE}.1.5.0"   # dmsHorizontalBorder — borde horizontal (mm)
DMS_VERTICAL_BORDER              = f"{_BASE}.1.6.0"   # dmsVerticalBorder — borde vertical (mm)
DMS_LEGEND                       = f"{_BASE}.1.7.0"   # dmsLegend — texto de leyenda fija del panel
DMS_BEACON_TYPE                  = f"{_BASE}.1.8.0"   # dmsBeaconType — tipo de baliza asociada (BITS)
DMS_SIGN_TECHNOLOGY              = f"{_BASE}.1.9.0"   # dmsSignTechnology — tecnología de píxel (BITS: LED, flipdisc, etc.)

# ═══════════════════════════════════════════════════════════════════════════════
# vmsCfg (dms.2) — Configuración VMS: dimensiones en píxeles y pitch
# ═══════════════════════════════════════════════════════════════════════════════
VMS_CHARACTER_HEIGHT_PIXELS      = f"{_BASE}.2.1.0"   # vmsCharacterHeightPixels — alto de carácter (0=variable, full matrix)
VMS_CHARACTER_WIDTH_PIXELS       = f"{_BASE}.2.2.0"   # vmsCharacterWidthPixels  — ancho de carácter (0=variable, full matrix)
VMS_SIGN_HEIGHT_PIXELS           = f"{_BASE}.2.3.0"   # vmsSignHeightPixels — filas de píxeles totales (confirmado: 96)
VMS_SIGN_WIDTH_PIXELS            = f"{_BASE}.2.4.0"   # vmsSignWidthPixels  — columnas de píxeles totales (confirmado: 144)
VMS_HORIZONTAL_PITCH             = f"{_BASE}.2.5.0"   # vmsHorizontalPitch — distancia horizontal entre centros de píxeles (mm)
VMS_VERTICAL_PITCH               = f"{_BASE}.2.6.0"   # vmsVerticalPitch   — distancia vertical entre centros de píxeles (mm)
VMS_MONOCHROME_COLOR             = f"{_BASE}.2.7.0"   # monochromeColor — colores ON/OFF para paneles monocromáticos (6 bytes)

# ═══════════════════════════════════════════════════════════════════════════════
# multiCfg (dms.4) — Valores por defecto del lenguaje MULTI
# ═══════════════════════════════════════════════════════════════════════════════
MULTI_DEFAULT_BACKGROUND_COLOR   = f"{_BASE}.4.1.0"   # defaultBackgroundColor — color de fondo clásico por defecto
MULTI_DEFAULT_FOREGROUND_COLOR   = f"{_BASE}.4.2.0"   # defaultForegroundColor — color de primer plano clásico por defecto
MULTI_DEFAULT_FLASH_ON           = f"{_BASE}.4.3.0"   # defaultFlashOn  — tiempo encendido del flash (1/10 s)
MULTI_DEFAULT_FLASH_OFF          = f"{_BASE}.4.4.0"   # defaultFlashOff — tiempo apagado del flash (1/10 s)
MULTI_DEFAULT_FONT               = f"{_BASE}.4.5.0"   # defaultFont — número de fuente por defecto (confirmado: 24)
MULTI_DEFAULT_JUSTIFICATION_LINE = f"{_BASE}.4.6.0"   # defaultJustificationLine — alineación de línea (2=left,3=center,4=right,5=full) (confirmado: 3)
MULTI_DEFAULT_JUSTIFICATION_PAGE = f"{_BASE}.4.7.0"   # defaultJustificationPage — alineación de página (2=top,3=middle,4=bottom) (confirmado: 3)
MULTI_DEFAULT_PAGE_ON_TIME       = f"{_BASE}.4.8.0"   # defaultPageOnTime  — tiempo de visualización de página (1/10 s) (confirmado: 30 = 3s)
MULTI_DEFAULT_PAGE_OFF_TIME      = f"{_BASE}.4.9.0"   # defaultPageOffTime — tiempo de apagado entre páginas (1/10 s)
MULTI_DEFAULT_CHARACTER_SET      = f"{_BASE}.4.10.0"  # defaultCharacterSet — codificación de caracteres (1=other, 2=eightBit)
MULTI_COLOR_SCHEME               = f"{_BASE}.4.11.0"  # dmsColorScheme — esquema de color (1=mono1bit,2=mono8bit,3=colorClassic,4=color24bit) (confirmado: 4)
MULTI_DEFAULT_BACKGROUND_RGB     = f"{_BASE}.4.12.0"  # defaultBackgroundRGB — color de fondo RGB (3 bytes) (confirmado: 00 00 00)
MULTI_DEFAULT_FOREGROUND_RGB     = f"{_BASE}.4.13.0"  # defaultForegroundRGB — color de primer plano RGB (3 bytes) (confirmado: FF B4 00 = ámbar)
MULTI_SUPPORTED_MULTI_TAGS       = f"{_BASE}.4.14.0"  # dmsSupportedMultiTags — bitmap de tags MULTI soportados
MULTI_MAX_NUMBER_PAGES           = f"{_BASE}.4.15.0"  # dmsMaxNumberPages — máximo de páginas por mensaje (confirmado: 6)
MULTI_MAX_MULTI_STRING_LENGTH    = f"{_BASE}.4.16.0"  # dmsMaxMultiStringLength — longitud máxima del string MULTI en bytes (confirmado: 1500)

# ═══════════════════════════════════════════════════════════════════════════════
# dmsMessage — Escalares (dms.5.X.0)
# ═══════════════════════════════════════════════════════════════════════════════
DMS_NUM_PERMANENT_MSG            = f"{_BASE}.5.1.0"   # dmsNumPermanentMsg       — cantidad de mensajes permanentes
DMS_NUM_CHANGEABLE_MSG           = f"{_BASE}.5.2.0"   # dmsNumChangeableMsg      — mensajes changeables actualmente usados (confirmado: 2)
DMS_MAX_CHANGEABLE_MSG           = f"{_BASE}.5.3.0"   # dmsMaxChangeableMsg      — slots changeables disponibles (confirmado: 500)
DMS_FREE_CHANGEABLE_MEMORY       = f"{_BASE}.5.4.0"   # dmsFreeChangeableMemory  — memoria changeable libre en bytes (confirmado: 747000)
DMS_NUM_VOLATILE_MSG             = f"{_BASE}.5.5.0"   # dmsNumVolatileMsg        — mensajes volátiles actualmente usados
DMS_MAX_VOLATILE_MSG             = f"{_BASE}.5.6.0"   # dmsMaxVolatileMsg        — slots volátiles disponibles (confirmado: 4)
DMS_FREE_VOLATILE_MEMORY         = f"{_BASE}.5.7.0"   # dmsFreeVolatileMemory    — memoria volátil libre en bytes (confirmado: 6000)

# ═══════════════════════════════════════════════════════════════════════════════
# dmsMessageTable (dms.5.8.1.X) — Tabla de mensajes
#
# Índice de fila: memory_type + slot
#   memory_type: 1=volatile, 2=changeable, 3=permanent
#   slot:        1..dmsMaxChangeableMsg / dmsMaxVolatileMsg
#
# NO usar directamente — usar los helpers de abajo.
# ═══════════════════════════════════════════════════════════════════════════════
_MSG_TABLE                       = f"{_BASE}.5.8.1"

DMS_MSG_MULTI_STRING             = f"{_MSG_TABLE}.3"  # dmsMessageMultiString      — cadena MULTI del mensaje
DMS_MSG_OWNER                    = f"{_MSG_TABLE}.4"  # dmsMessageOwner            — propietario/origen del mensaje
DMS_MSG_CRC                      = f"{_MSG_TABLE}.5"  # dmsMessageCRC              — CRC-16 calculado sobre el MULTI string
DMS_MSG_RUN_TIME_PRIORITY        = f"{_MSG_TABLE}.8"  # dmsMessageRunTimePriority  — prioridad de ejecución (1=low … 255=high)
DMS_MSG_STATUS                   = f"{_MSG_TABLE}.9"  # dmsMessageStatus           — estado del slot (ver MessageStatus enum)

# ═══════════════════════════════════════════════════════════════════════════════
# dmsIllum (dms.7) — Iluminación del panel
# ═══════════════════════════════════════════════════════════════════════════════
DMS_ILLUM_CONTROL                = f"{_BASE}.7.1.0"   # dmsIllumControl           — modo (1=other,2=photocell,3=manual,4=manualIndexed)
DMS_ILLUM_NUM_BRIGHT_LEVELS      = f"{_BASE}.7.4.0"   # dmsIllumNumBrightLevels   — cantidad de niveles soportados
DMS_ILLUM_BRIGHT_LEVEL_STATUS    = f"{_BASE}.7.5.0"   # dmsIllumBrightLevelStatus — nivel actual (read-only)
DMS_ILLUM_MAN_LEVEL              = f"{_BASE}.7.6.0"   # dmsIllumManLevel          — nivel manual (read-write)
DMS_ILLUM_LIGHT_OUTPUT_STATUS    = f"{_BASE}.7.9.0"   # dmsIllumLightOutputStatus — light output actual 0–65535 (read-only)

# ═══════════════════════════════════════════════════════════════════════════════
# signControl (dms.6) — Control del panel
# ═══════════════════════════════════════════════════════════════════════════════
DMS_CONTROL_MODE                 = f"{_BASE}.6.1.0"   # dmsControlMode       — modo de control activo (2=local,4=central,5=centralOverride)
DMS_SOFTWARE_RESET               = f"{_BASE}.6.2.0"   # dmsSWReset           — reset por software (SET 2 para resetear)
DMS_ACTIVATE_MESSAGE             = f"{_BASE}.6.3.0"   # dmsActivateMessage   — activa mensaje (hex: duration+priority+memType+slot+CRC+IP)
DMS_ACTIVATE_MSG_ERROR           = f"{_BASE}.6.4.0"   # dmsActivateMsgError  — resultado del último activate (2=none = ok)
DMS_MSG_TABLE_SOURCE             = f"{_BASE}.6.5.0"   # dmsShortPowerLossMessage — mensaje activo ante corte de energía

# ═══════════════════════════════════════════════════════════════════════════════
# dmsStatus (dms.9) — Estado del panel
# ═══════════════════════════════════════════════════════════════════════════════
STAT_MULTI_FIELD_ROWS            = f"{_BASE}.9.1.0"   # statMultiFieldRows      — filas activas en tabla de campos MULTI
DMS_CURRENT_SPEED                = f"{_BASE}.9.3.0"   # dmsCurrentSpeed         — velocidad de tráfico detectada (km/h)
WATCHDOG_FAILURE_COUNT           = f"{_BASE}.9.5.0"   # watchdogFailureCount    — contador histórico de reinicios por watchdog
DMS_STAT_DOOR_OPEN               = f"{_BASE}.9.6.0"   # dmsStatDoorOpen         — puertas del gabinete abiertas (bitmap, 0=todas cerradas)
SHORT_ERROR_STATUS               = f"{_BASE}.9.7.1.0" # shortErrorStatus        — bitmap de errores activos (ver ShortErrorBit enum)

SHORT_ERROR_BITS = {
    1:  "COMMUNICATIONS",
    2:  "POWER",
    3:  "ATTACHED_DEVICE",
    4:  "LAMP",
    5:  "PIXEL",
    6:  "PHOTOCELL",
    7:  "MESSAGE",
    8:  "CONTROLLER",
    9:  "TEMPERATURE_WARNING",
    10: "CLIMATE_CONTROL",
    11: "CRITICAL_TEMPERATURE",
    12: "DRUM_ROTOR",
    13: "DOOR_OPEN",
    14: "HUMIDITY",
}
CONTROLLER_ERROR_STATUS          = f"{_BASE}.9.7.2.0" # controllerErrorStatus   — errores del controlador (0=ninguno)
DMS_PIXEL_FAILURE_TEST_ROWS      = f"{_BASE}.9.7.19.0"# dmsPixelFailureTestRows    — píxeles fallados en test (0=ninguno)
DMS_PIXEL_FAILURE_MESSAGE_ROWS   = f"{_BASE}.9.7.20.0"# dmsPixelFailureMessageRows — píxeles fallados en display (0=ninguno)

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers — OIDs completos para dmsMessageTable
#
# Construyen el OID de instancia añadiendo .memory_type.slot al OID de columna.
# Ejemplo: msg_multi_string(2, 1) → "1.3.6.1.4.1.1206.4.2.3.5.8.1.3.2.1"
# ═══════════════════════════════════════════════════════════════════════════════

def msg_multi_string(memory_type: int, slot: int) -> str:
    """OID de dmsMessageMultiString para (memory_type, slot)."""
    return f"{DMS_MSG_MULTI_STRING}.{memory_type}.{slot}"

def msg_owner(memory_type: int, slot: int) -> str:
    """OID de dmsMessageOwner para (memory_type, slot)."""
    return f"{DMS_MSG_OWNER}.{memory_type}.{slot}"

def msg_crc(memory_type: int, slot: int) -> str:
    """OID de dmsMessageCRC para (memory_type, slot)."""
    return f"{DMS_MSG_CRC}.{memory_type}.{slot}"

def msg_run_time_priority(memory_type: int, slot: int) -> str:
    """OID de dmsMessageRunTimePriority para (memory_type, slot)."""
    return f"{DMS_MSG_RUN_TIME_PRIORITY}.{memory_type}.{slot}"

def msg_status(memory_type: int, slot: int) -> str:
    """OID de dmsMessageStatus para (memory_type, slot)."""
    return f"{DMS_MSG_STATUS}.{memory_type}.{slot}"


# ═══════════════════════════════════════════════════════════════════════════════
# dmsGraphic (dms.10) — Tabla de gráficos
#
# dmsGraphicTable  (dms.10.6.1.X.slot):
#   col  2 = dmsGraphicNumber    — número de gráfico almacenado en el slot
#   col  4 = dmsGraphicHeight    — alto en píxeles
#   col  5 = dmsGraphicWidth     — ancho en píxeles
#   col  6 = dmsGraphicType      — tipo de color (1=mono1bit, 2=mono8bit, 4=color24bit)
#   col 10 = dmsGraphicStatus    — estado (7=modifyReq, 8=readyForUseReq)
#
# dmsGraphicBitmapTable (dms.10.7.1.3.slot.block):
#   col  3 = dmsGraphicBlockData — datos del bloque (OctetString, 1-based)
# ═══════════════════════════════════════════════════════════════════════════════
DMS_NUM_GRAPHICS       = f"{_BASE}.10.1.0"  # dmsNumGraphics      — cantidad de slots de gráficos disponibles
DMS_GRAPHIC_MAX_SIZE   = f"{_BASE}.10.2.0"  # dmsGraphicMaxSize   — tamaño máximo de un gráfico en bytes
DMS_GRAPHIC_BLOCK_SIZE = f"{_BASE}.10.3.0"  # dmsGraphicBlockSize — bytes por bloque (ej: 1023 en Daktronics VFC)

_GFX_TABLE = f"{_BASE}.10.6.1"
_GFX_BLOCK = f"{_BASE}.10.7.1.3"


def gfx_status(slot: int) -> str:
    """OID de dmsGraphicStatus para el slot dado."""
    return f"{_GFX_TABLE}.10.{slot}"

def gfx_number(slot: int) -> str:
    """OID de dmsGraphicNumber para el slot dado."""
    return f"{_GFX_TABLE}.2.{slot}"

def gfx_height(slot: int) -> str:
    """OID de dmsGraphicHeight para el slot dado."""
    return f"{_GFX_TABLE}.4.{slot}"

def gfx_width(slot: int) -> str:
    """OID de dmsGraphicWidth para el slot dado."""
    return f"{_GFX_TABLE}.5.{slot}"

def gfx_color_type(slot: int) -> str:
    """OID de dmsGraphicType para el slot dado."""
    return f"{_GFX_TABLE}.6.{slot}"

def gfx_id(slot: int) -> str:
    """OID de dmsGraphicID (col 7 — CRC calculado por el panel) para el slot dado."""
    return f"{_GFX_TABLE}.7.{slot}"

def gfx_block_data(slot: int, i: int) -> str:
    """OID de dmsGraphicBlockData para el slot y bloque i (1-based)."""
    return f"{_GFX_BLOCK}.{slot}.{i}"

# Columna de status sin instancia — usar como base para walk
GFX_STATUS_COL = f"{_GFX_TABLE}.10"