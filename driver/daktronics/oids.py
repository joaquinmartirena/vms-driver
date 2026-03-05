"""
Valores y constantes para Daktronics VFC
Contiene únicamente valores confirmados contra el dispositivo real
(IP 66.17.99.157) y constantes que extienden el estándar.
Los OIDs NTCIP 1203 se importan desde snmp.ntcip1203.
Dispositivo: Daktronics VFC — panel full-matrix 144×96 px, SNMP v2c
"""

# Re-exportar OIDs estándar para que los módulos del driver puedan importar
# todo desde un único lugar.
from snmp.ntcip1203 import (  # noqa: F401
    SYS_DESCR,
    # dmsSignCfg
    DMS_SIGN_ACCESS, DMS_SIGN_TYPE, DMS_SIGN_HEIGHT, DMS_SIGN_WIDTH,
    DMS_HORIZONTAL_BORDER, DMS_VERTICAL_BORDER, DMS_SIGN_TECHNOLOGY,
    # vmsCfg
    VMS_CHARACTER_HEIGHT_PIXELS, VMS_CHARACTER_WIDTH_PIXELS,
    VMS_SIGN_HEIGHT_PIXELS, VMS_SIGN_WIDTH_PIXELS,
    VMS_HORIZONTAL_PITCH, VMS_VERTICAL_PITCH, VMS_MONOCHROME_COLOR,
    # multiCfg
    MULTI_DEFAULT_BACKGROUND_COLOR, MULTI_DEFAULT_FOREGROUND_COLOR,
    MULTI_DEFAULT_FLASH_ON, MULTI_DEFAULT_FLASH_OFF,
    MULTI_DEFAULT_FONT, MULTI_DEFAULT_JUSTIFICATION_LINE,
    MULTI_DEFAULT_JUSTIFICATION_PAGE, MULTI_DEFAULT_PAGE_ON_TIME,
    MULTI_DEFAULT_PAGE_OFF_TIME, MULTI_DEFAULT_CHARACTER_SET,
    MULTI_COLOR_SCHEME, MULTI_DEFAULT_BACKGROUND_RGB,
    MULTI_DEFAULT_FOREGROUND_RGB, MULTI_MAX_NUMBER_PAGES,
    MULTI_MAX_MULTI_STRING_LENGTH,
    # dmsMessage escalares
    DMS_NUM_PERMANENT_MSG, DMS_NUM_CHANGEABLE_MSG, DMS_MAX_CHANGEABLE_MSG,
    DMS_FREE_CHANGEABLE_MEMORY, DMS_NUM_VOLATILE_MSG, DMS_MAX_VOLATILE_MSG,
    DMS_FREE_VOLATILE_MEMORY,
    # dmsMessageTable
    DMS_MSG_MULTI_STRING, DMS_MSG_OWNER, DMS_MSG_CRC,
    DMS_MSG_RUN_TIME_PRIORITY, DMS_MSG_STATUS,
    # signControl
    DMS_CONTROL_MODE, DMS_SOFTWARE_RESET, DMS_ACTIVATE_MESSAGE,
    DMS_ACTIVATE_MSG_ERROR, DMS_MSG_TABLE_SOURCE,
    # dmsStatus
    STAT_MULTI_FIELD_ROWS, DMS_CURRENT_SPEED, WATCHDOG_FAILURE_COUNT,
    DMS_STAT_DOOR_OPEN, SHORT_ERROR_STATUS, CONTROLLER_ERROR_STATUS,
    DMS_PIXEL_FAILURE_TEST_ROWS, DMS_PIXEL_FAILURE_MESSAGE_ROWS,
    # helpers
    msg_multi_string, msg_owner, msg_crc, msg_run_time_priority, msg_status,
)

# ─── Acceso SNMP ──────────────────────────────────────────────────────────────
COMMUNITY_READ               = "public"
COMMUNITY_WRITE              = "administrator"

# ─── Dimensiones del panel (confirmadas en dispositivo) ───────────────────────
SIGN_WIDTH_PIXELS            = 144   # vmsSignWidthPixels  confirmado: 144 px
SIGN_HEIGHT_PIXELS           = 96    # vmsSignHeightPixels confirmado: 96 px

# ─── Defaults MULTI confirmados (leídos del dispositivo) ──────────────────────
DEFAULT_FONT                 = 24    # defaultFont confirmado: fuente 24
DEFAULT_JUSTIFICATION_LINE   = 3     # 3 = center
DEFAULT_JUSTIFICATION_PAGE   = 3     # 3 = middle
DEFAULT_PAGE_ON_TIME         = 30    # 30 décimas = 3.0 s
DEFAULT_FOREGROUND_RGB       = (0xFF, 0xB4, 0x00)  # ámbar confirmado: FF B4 00

# ─── Capacidades del dispositivo (confirmadas) ────────────────────────────────
MAX_MULTI_STRING_LEN         = 1500  # dmsMaxMultiStringLength confirmado
MAX_NUMBER_PAGES             = 6     # dmsMaxNumberPages confirmado
COLOR_SCHEME                 = 4     # colorClassic confirmado

# ─── Tipos de memoria (dmsMessageMemoryType) ──────────────────────────────────
MEMORY_PERMANENT      = 2   # permanent — mensajes de fábrica, solo lectura
MEMORY_CHANGEABLE     = 3   # changeable — persiste, sobrescribible ← usar por defecto
MEMORY_VOLATILE       = 4   # volatile — se pierde al apagar
MEMORY_CURRENT_BUFFER = 5   # currentBuffer — mensaje activo en pantalla
MEMORY_SCHEDULE       = 6   # schedule — mensajes programados
MEMORY_BLANK          = 7   # blank — apaga el panel

# ─── Tabla de mensajes ────────────────────────────────────────────────────────
MSG_SLOTS_PER_MEMORY_TYPE    = 500   # slots por tipo de memoria confirmado