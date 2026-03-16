"""
Modelos de datos para la vertical VMS.

Definen el vocabulario común entre el driver, el polling worker,
el command handler y RabbitMQ. Todos trabajan con estos tipos —
nunca con diccionarios sueltos ni strings sin estructura.

Datos confirmados contra dispositivo real: Daktronics VFC, IP 66.17.99.157
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# Enums — valores confirmados contra NTCIP 1203 v03 y dispositivo real
# ═══════════════════════════════════════════════════════════════════════════════

class ControlMode(IntEnum):
    """
    dmsControlMode — modo de control activo del panel.
    OID: 1.3.6.1.4.1.1206.4.2.3.6.1.0
    Confirmado en VFC real: CENTRAL (4)
    """
    LOCAL            = 2
    CENTRAL          = 4   # ← valor confirmado en VFC real
    CENTRAL_OVERRIDE = 5


class MessageStatus(IntEnum):
    """
    dmsMessageStatus — estado de un slot en la messageTable.
    OID: 1.3.6.1.4.1.1206.4.2.3.5.8.1.9.{memory_type}.{slot}
    Confirmado en VFC real: VALID (4) en slot (3,2)
    """
    NOT_USED     = 1
    MODIFYING    = 2
    VALIDATING   = 3
    VALID        = 4   # ← confirmado en VFC real
    ERROR        = 5
    MODIFY_REQ   = 6   # SET para abrir el slot a edición
    VALIDATE_REQ = 7   # SET para disparar validación
    NOT_USED_REQ = 8   # SET para liberar el slot


class SignType(IntEnum):
    """
    dmsSignType — tipo de panel.
    OID: 1.3.6.1.4.1.1206.4.2.3.1.2.0
    Confirmado en VFC real: FULL_MATRIX (6)
    """
    OTHER       = 1
    BOS         = 2
    CMS         = 3
    VMS_CHAR    = 4
    VMS_LINE    = 5
    FULL_MATRIX = 6   # ← confirmado en VFC real


class ShortErrorBit(IntEnum):
    """
    Bits del objeto shortErrorStatus (NTCIP 1203 v03, sección 5.11.2.1.1).
    OID: 1.3.6.1.4.1.1206.4.2.3.9.7.1.0
    Confirmado en VFC real: MESSAGE activo (valor 128 = bit 7)

    Uso:
        if status.short_error_status & ShortErrorBit.MESSAGE:
            # hay error de mensaje activo
    """
    COMMUNICATIONS  = 1 << 1   # error de comunicaciones
    POWER           = 1 << 2   # error de alimentación
    ATTACHED_DEVICE = 1 << 3   # error en dispositivo externo
    LAMP            = 1 << 4   # error de lámparas
    PIXEL           = 1 << 5   # error de píxeles
    PHOTOCELL       = 1 << 6   # error de fotocélula
    MESSAGE         = 1 << 7   # error de mensaje ← activo en VFC real
    CONTROLLER      = 1 << 8   # error del controlador
    TEMPERATURE     = 1 << 9   # advertencia de temperatura


# ═══════════════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BrightnessStatus:
    """
    Estado de iluminación del panel leído vía SNMP (dms.7).

    control_mode: 2=photocell, 3=manual, 4=manualIndexed
    light_output:  0–65535 (raw del panel, proporcional al brillo físico)
    """
    control_mode:  int   # dmsIllumControl (7.1.0)
    current_level: int   # dmsIllumBrightLevelStatus (7.5.0)
    max_levels:    int   # dmsIllumNumBrightLevels (7.4.0)
    light_output:  int   # dmsIllumLightOutputStatus (7.9.0)


@dataclass
class SignDimensions:
    """
    Dimensiones del panel leídas vía SNMP en un solo request.

    char_width_pixels / char_height_pixels == 0 → panel full-matrix (variable).
    """
    width_pixels:       int   # vmsSignWidthPixels  — columnas de píxeles (ej: 144)
    height_pixels:      int   # vmsSignHeightPixels — filas de píxeles (ej: 96)
    width_mm:           int   # dmsSignWidth        — anchura física (mm)
    height_mm:          int   # dmsSignHeight       — altura física (mm)
    char_width_pixels:  int   # vmsCharacterWidthPixels  (0 = variable/full-matrix)
    char_height_pixels: int   # vmsCharacterHeightPixels (0 = variable/full-matrix)


@dataclass
class DeviceInfo:
    """
    Configuración estática del dispositivo — va en base de datos.
    No cambia a menos que cambie el hardware o la red.
    """
    ip: str
    port: int                       = 161
    community_read: str             = "public"
    community_write: str            = "administrator"
    device_type: str                = "daktronics_vfc"
    width_pixels: int               = 144           # confirmado: vmsSignWidthPixels = 144
    height_pixels: int              = 96            # confirmado: vmsSignHeightPixels = 96
    sign_type: Optional[SignType]   = None          # dmsSignType (1.2.0)
    sign_technology: int            = 0             # dmsSignTechnology bitmap (1.9.0)
    watchdog_failures: int          = 0             # watchdogFailureCount (9.5.0)


@dataclass
class DeviceStatus:
    """
    Snapshot del estado del panel en un momento dado.
    Lo crea el Polling Worker después de cada ciclo de lectura
    y lo publica a RabbitMQ como vms.event.status_changed.
    """
    ip: str
    online: bool
    control_mode: Optional[ControlMode]  = None
    short_error_status: int              = 0
    door_open: bool                      = False
    watchdog_failures: int               = 0
    active_message: Optional[str]        = None   # MULTI string activo
    last_polled: Optional[datetime]      = None

    @property
    def has_errors(self) -> bool:
        """True si hay algún error activo en shortErrorStatus."""
        return self.short_error_status != 0

    def active_errors(self) -> list[str]:
        """
        Devuelve los nombres de los errores activos en shortErrorStatus.

        Ejemplo:
            status.short_error_status = 128  →  ["MESSAGE"]
            status.short_error_status = 132  →  ["MESSAGE", "PIXEL"]
        """
        return [
            bit.name
            for bit in ShortErrorBit
            if self.short_error_status & bit
        ]


@dataclass
class GraphicInfo:
    """
    Gráfico almacenado en la dmsGraphicTable del panel (NTCIP 1203 v03, dms.10.6.1).

    status values: 1=notUsed, 2=modifying, 3=calculatingID,
                   4=readyForUse, 5=inUse, 6=permanent
    """
    slot:       int
    number:     int
    width:      int
    height:     int
    color_type: int
    crc:        int
    status:     int


@dataclass
class Message:
    """
    Representa un mensaje en la dmsMessageTable del panel.
    Identifica el slot por (memory_type, slot) y lleva el contenido MULTI.

    Tipos de memoria (NTCIP 1203 — el VFC los respeta):
        3 = changeable — persiste, sobrescribible  ← usar por defecto (MEMORY_CHANGEABLE)
        4 = volatile   — se pierde al apagar
        5 = currentBuffer — mensaje activo en pantalla (solo lectura)
    """
    memory_type: int
    slot: int
    multi_string: str
    status: Optional[MessageStatus] = None
    crc: Optional[int]              = None