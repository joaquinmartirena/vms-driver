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
class DeviceInfo:
    """
    Configuración estática del dispositivo — va en base de datos.
    No cambia a menos que cambie el hardware o la red.
    """
    ip: str
    port: int                  = 161
    community_read: str        = "public"
    community_write: str       = "administrator"
    device_type: str           = "daktronics_vfc"
    width_pixels: int          = 144   # confirmado: vmsSignWidthPixels = 144
    height_pixels: int         = 96    # confirmado: vmsSignHeightPixels = 96


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
class Message:
    """
    Representa un mensaje en la dmsMessageTable del panel.
    Identifica el slot por (memory_type, slot) y lleva el contenido MULTI.

    Tipos de memoria confirmados en VFC real (quirk: valores invertidos respecto al estándar):
        3 = changeable — persiste, sobrescribible  ← usar por defecto (MEMORY_CHANGEABLE)
        4 = volatile   — se pierde al apagar
        5 = currentBuffer — mensaje activo en pantalla (solo lectura)
    """
    memory_type: int
    slot: int
    multi_string: str
    status: Optional[MessageStatus] = None
    crc: Optional[int]              = None