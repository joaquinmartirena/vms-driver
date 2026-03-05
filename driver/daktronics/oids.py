"""
OIDs confirmados para Daktronics VFC
Basados en NTCIP 1203 v03 y pruebas directas contra el dispositivo
"""

# ─── System ───────────────────────────────────────────────────────────────────
SYS_DESCR                   = "1.3.6.1.2.1.1.1.0"

# ─── Sign Control ─────────────────────────────────────────────────────────────
DMS_CONTROL_MODE            = "1.3.6.1.4.1.1206.4.2.3.6.1.0"
DMS_ACTIVATE_MESSAGE        = "1.3.6.1.4.1.1206.4.2.3.6.3.0"
DMS_ACTIVATE_MSG_ERROR      = "1.3.6.1.4.1.1206.4.2.3.6.4.0"

# ─── Message Table ────────────────────────────────────────────────────────────
# Formato: OID_BASE.memory_type.slot
DMS_MSG_MULTI_STRING        = "1.3.6.1.4.1.1206.4.2.3.5.8.1.3"
DMS_MSG_OWNER               = "1.3.6.1.4.1.1206.4.2.3.5.8.1.4"
DMS_MSG_CRC                 = "1.3.6.1.4.1.1206.4.2.3.5.8.1.5"
DMS_MSG_RUN_TIME_PRIORITY   = "1.3.6.1.4.1.1206.4.2.3.5.8.1.8"
DMS_MSG_STATUS              = "1.3.6.1.4.1.1206.4.2.3.5.8.1.9"

# ─── Status ───────────────────────────────────────────────────────────────────
STAT_MULTI_FIELD_ROWS       = "1.3.6.1.4.1.1206.4.2.3.9.1.0"
DMS_CURRENT_SPEED           = "1.3.6.1.4.1.1206.4.2.3.9.3.0"
WATCHDOG_FAILURE_COUNT      = "1.3.6.1.4.1.1206.4.2.3.9.5.0"
DMS_STAT_DOOR_OPEN          = "1.3.6.1.4.1.1206.4.2.3.9.6.0"
SHORT_ERROR_STATUS          = "1.3.6.1.4.1.1206.4.2.3.9.7.1.0"

# ─── Helpers ──────────────────────────────────────────────────────────────────
def msg_multi_string(memory_type: int, slot: int) -> str:
    return f"{DMS_MSG_MULTI_STRING}.{memory_type}.{slot}"

def msg_status(memory_type: int, slot: int) -> str:
    return f"{DMS_MSG_STATUS}.{memory_type}.{slot}"

def msg_crc(memory_type: int, slot: int) -> str:
    return f"{DMS_MSG_CRC}.{memory_type}.{slot}"