"""
Valores y constantes para Fixalia.
Contiene únicamente valores confirmados contra el simulador (IP 127.0.0.1)
y constantes que extienden el estándar.
Los OIDs NTCIP 1203 se importan desde snmp.ntcip1203.
Dispositivo: Fixalia — panel full-matrix 320×64 px, SNMP v2c
"""

import os

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

# ─── Acceso SNMP (12-factor III) ──────────────────────────────────────────────
COMMUNITY_READ  = os.getenv("VMS_COMMUNITY_READ",  "public")
COMMUNITY_WRITE = os.getenv("VMS_COMMUNITY_WRITE", "administrator")

# ─── Parámetros SNMP ──────────────────────────────────────────────────────────
SNMP_PORT    = int(os.getenv("VMS_SNMP_PORT",    "161"))
SNMP_TIMEOUT = int(os.getenv("VMS_SNMP_TIMEOUT", "10"))
SNMP_RETRIES = int(os.getenv("VMS_SNMP_RETRIES", "3"))

# ─── Parámetros de validación de mensajes ─────────────────────────────────────
VALIDATE_TIMEOUT  = float(os.getenv("VMS_VALIDATE_TIMEOUT",  "10"))
VALIDATE_INTERVAL = float(os.getenv("VMS_VALIDATE_INTERVAL", "0.5"))

# ─── Constantes de referencia — solo documentación, NO usar como fallback ─────
SIGN_WIDTH_PIXELS         = 320   # vmsSignWidthPixels  confirmado en simulador
SIGN_HEIGHT_PIXELS        = 64    # vmsSignHeightPixels confirmado en simulador
MSG_SLOTS_PER_MEMORY_TYPE = 100   # conservador — se lee de DMS_MAX_CHANGEABLE_MSG

# ─── Tipos de memoria (dmsMessageMemoryType) ──────────────────────────────────
MEMORY_PERMANENT      = 2   # permanent  (NTCIP 1203) — solo lectura
MEMORY_CHANGEABLE     = 3   # changeable (NTCIP 1203) — persiste, sobrescribible ← usar por defecto
MEMORY_VOLATILE       = 4   # volatile   (NTCIP 1203) — se pierde al apagar
MEMORY_CURRENT_BUFFER = 5   # currentBuffer — mensaje activo en pantalla
MEMORY_SCHEDULE       = 6   # schedule — mensajes programados
MEMORY_BLANK          = 7   # blank — apaga el panel
