"""
Driver NTCIP 1203 v03 base — lógica común para cualquier panel compatible.

Implementa la secuencia completa: validación MULTI, gestión de slots,
escritura en messageTable, activación por dmsActivateMessage.

Para añadir un fabricante nuevo:
    1. Crear driver/fabricante/__init__.py  (vacío)
    2. Crear driver/fabricante/driver.py    (subclase de NTCIPDriver, ~3 líneas)
    3. Registrar el driver en driver/factory.py (_REGISTRY)
"""

import os
import time
import socket
import struct
import logging
from datetime import datetime

from pysnmp.hlapi.v3arch.asyncio import OctetString

from driver.base import VMSDriver
from driver.multi import MultiValidator
from driver.slots import SlotManager
from models.device import DeviceStatus, Message, MessageStatus, ControlMode
from snmp.client import SNMPClient
from snmp.ntcip1203 import (
    SYS_DESCR,
    DMS_MAX_CHANGEABLE_MSG,
    VMS_SIGN_WIDTH_PIXELS, VMS_SIGN_HEIGHT_PIXELS,
    MULTI_MAX_MULTI_STRING_LENGTH, MULTI_MAX_NUMBER_PAGES,
    DMS_ACTIVATE_MESSAGE,
    DMS_CONTROL_MODE,
    SHORT_ERROR_STATUS, DMS_STAT_DOOR_OPEN, WATCHDOG_FAILURE_COUNT,
    msg_multi_string, msg_crc, msg_status,
)

logger = logging.getLogger(__name__)

# ─── Configuración SNMP (12-factor III — todo desde variables de entorno) ──────
_COMMUNITY_READ  = os.getenv("VMS_COMMUNITY_READ",  "public")
_COMMUNITY_WRITE = os.getenv("VMS_COMMUNITY_WRITE", "administrator")
_SNMP_PORT       = int(os.getenv("VMS_SNMP_PORT",    "161"))
_SNMP_TIMEOUT    = int(os.getenv("VMS_SNMP_TIMEOUT", "10"))
_SNMP_RETRIES    = int(os.getenv("VMS_SNMP_RETRIES", "3"))

# ─── Configuración de validación ───────────────────────────────────────────────
_VALIDATE_TIMEOUT  = float(os.getenv("VMS_VALIDATE_TIMEOUT",  "10"))
_VALIDATE_INTERVAL = float(os.getenv("VMS_VALIDATE_INTERVAL", "0.5"))

# ─── Otros parámetros configurables ───────────────────────────────────────────
_SCAN_SLOTS             = int(os.getenv("VMS_SCAN_SLOTS",      "20"))
_BLANK_MESSAGE_PRIORITY = int(os.getenv("VMS_BLANK_PRIORITY",  "3"))

# ─── Tipos de memoria (NTCIP 1203 — estándar) ─────────────────────────────────
MEMORY_CHANGEABLE     = 3   # changeable — persiste, sobrescribible ← usar por defecto
MEMORY_CURRENT_BUFFER = 5   # currentBuffer — mensaje activo en pantalla (solo lectura)
MEMORY_BLANK          = 7   # blank — apaga el panel


class NTCIPDriver(VMSDriver):
    """
    Implementación completa de NTCIP 1203 v03 sobre SNMP v2c.

    Cubre la totalidad del protocolo: lectura de estado, messageTable,
    activación de mensajes y limpieza de slots.

    Todos los parámetros de red y temporización se leen de variables de entorno
    al arrancar — nunca hay valores hardcodeados en el código.
    """

    def __init__(self, ip: str, port: int = _SNMP_PORT, source_ip: str | None = None):
        self.ip   = ip
        self.port = port
        self._read  = SNMPClient(ip=ip, community=_COMMUNITY_READ,
                                 port=self.port, timeout=_SNMP_TIMEOUT,
                                 retries=_SNMP_RETRIES)
        self._write = SNMPClient(ip=ip, community=_COMMUNITY_WRITE,
                                 port=self.port, timeout=_SNMP_TIMEOUT,
                                 retries=_SNMP_RETRIES)
        self._source_ip_override = source_ip
        self._init()

    def _init(self) -> None:
        """Inicializa estado que requiere IO: IP origen, slots, validador."""
        self._source_ip = self._source_ip_override or self._detect_source_ip()
        self._slots     = SlotManager(total_slots=self._discover_slot_count())
        self._validator = self._init_validator()

    def _detect_source_ip(self) -> str:
        """Detecta la IP de la interfaz con ruta al panel, sin enviar tráfico."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((self.ip, self.port))
            return s.getsockname()[0]

    def _discover_slot_count(self) -> int:
        """Lee DMS_MAX_CHANGEABLE_MSG del panel. Lanza ConnectionError si falla."""
        try:
            count = int(self._read.get(DMS_MAX_CHANGEABLE_MSG))
            logger.debug("slots disponibles", extra={"ip": self.ip, "count": count})
            return count
        except Exception as e:
            raise ConnectionError(
                f"No se pudo conectar al panel en {self.ip}:{self.port} — {e}"
            ) from e

    def _init_validator(self) -> MultiValidator:
        """Consulta dimensiones y límites al panel vía SNMP. Sin fallback."""
        width             = int(self._read.get(VMS_SIGN_WIDTH_PIXELS))
        height            = int(self._read.get(VMS_SIGN_HEIGHT_PIXELS))
        max_string_length = int(self._read.get(MULTI_MAX_MULTI_STRING_LENGTH))
        max_pages         = int(self._read.get(MULTI_MAX_NUMBER_PAGES))
        logger.debug("dimensiones del panel", extra={
            "ip": self.ip, "width": width, "height": height,
            "max_string": max_string_length, "max_pages": max_pages,
        })
        return MultiValidator(
            width=width,
            height=height,
            max_string_length=max_string_length,
            max_pages=max_pages,
        )

    # ─── Interfaz pública ─────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Verifica conectividad leyendo sysDescr (OID mínimo garantizado)."""
        try:
            self._read.get(SYS_DESCR)
            return True
        except Exception:
            return False

    def get_status(self) -> DeviceStatus:
        """Lee el estado actual del panel vía SNMP."""
        try:
            error_status     = int(self._read.get(SHORT_ERROR_STATUS))
            door_open        = int(self._read.get(DMS_STAT_DOOR_OPEN)) != 0
            watchdog         = int(self._read.get(WATCHDOG_FAILURE_COUNT))
            control_mode_val = int(self._read.get(DMS_CONTROL_MODE))

            try:
                control_mode = ControlMode(control_mode_val)
            except ValueError:
                control_mode = None

            return DeviceStatus(
                ip=self.ip,
                online=True,
                control_mode=control_mode,
                short_error_status=error_status,
                door_open=door_open,
                watchdog_failures=watchdog,
                last_polled=datetime.now(),
            )

        except Exception as e:
            logger.warning("panel no responde", extra={"ip": self.ip, "error": str(e)})
            return DeviceStatus(ip=self.ip, online=False, last_polled=datetime.now())

    def get_current_message(self) -> str:
        """Lee el MULTI string del mensaje activo (currentBuffer = memory_type 5, slot 1)."""
        try:
            value = self._read.get(msg_multi_string(MEMORY_CURRENT_BUFFER, 1))
            return str(value)
        except Exception as e:
            logger.warning("no se pudo leer mensaje activo",
                           extra={"ip": self.ip, "error": str(e)})
            return ""

    def get_message(self, slot: int, memory_type: int = MEMORY_CHANGEABLE) -> Message | None:
        """
        Lee un mensaje específico de la messageTable.
        Devuelve None si el slot está vacío (notUsed).
        """
        try:
            raw_status = int(self._read.get(msg_status(memory_type, slot)))
            status = MessageStatus(raw_status)

            if status == MessageStatus.NOT_USED:
                return None

            multi = str(self._read.get(msg_multi_string(memory_type, slot)))
            crc   = int(self._read.get(msg_crc(memory_type, slot))) if status == MessageStatus.VALID else None

            return Message(
                memory_type=memory_type,
                slot=slot,
                multi_string=multi,
                status=status,
                crc=crc,
            )

        except Exception as e:
            logger.warning("error leyendo slot",
                           extra={"ip": self.ip, "slot": slot,
                                  "memory_type": memory_type, "error": str(e)})
            return None

    def get_messages(self, memory_type: int = MEMORY_CHANGEABLE) -> list[Message]:
        """
        Lista todos los mensajes válidos en un tipo de memoria.

        Combina los slots IN_USE conocidos por el SlotManager con un scan
        de los primeros VMS_SCAN_SLOTS slots (default 20) para detectar
        mensajes escritos antes de que arrancara este driver.
        """
        messages = []
        checked = set()

        in_use_slots = self._slots.in_use_slots()
        scan_slots   = list(range(1, _SCAN_SLOTS + 1))

        for slot in sorted(set(in_use_slots + scan_slots)):
            if slot in checked:
                continue
            checked.add(slot)

            msg = self.get_message(slot, memory_type)
            if msg and msg.status == MessageStatus.VALID and msg.multi_string:
                messages.append(msg)

        return messages

    def send_message(self, multi_string: str, priority: int = 3) -> Message:
        """
        Escribe y activa un mensaje en el panel.

        El slot se obtiene automáticamente de SlotManager y permanece IN_USE
        mientras el mensaje esté activo. Llamar clear_message() libera los slots.

        Secuencia NTCIP 1203:
            1. Validar MULTI string
            2. SET messageStatus = modifyReq   (abrir slot)
            3. SET messageMultiString          (escribir contenido)
            4. SET messageStatus = validateReq (solicitar validación)
            5. Poll hasta messageStatus == valid
            6. GET messageCRC
            7. SET activateMessage             (mostrar en panel)

        Si la validación devuelve ERROR, el slot se marca CORRUPTED.
        Cualquier otro fallo libera el slot.
        """
        result = self._validator.validate(multi_string)
        if not result:
            raise ValueError(f"MULTI string inválido: {result}")

        memory_type = MEMORY_CHANGEABLE
        slot = self._slots.acquire()
        corrupted = False

        try:
            # 2. Abrir slot para edición
            self._write.set(msg_status(memory_type, slot), 6)  # modifyReq
            logger.debug("slot abierto",
                         extra={"ip": self.ip, "slot": slot, "memory_type": memory_type})

            # 3. Escribir MULTI string
            self._write.set(msg_multi_string(memory_type, slot), OctetString(multi_string))
            logger.debug("multi string escrito",
                         extra={"ip": self.ip, "slot": slot, "multi": multi_string})

            # 4. Solicitar validación
            self._write.set(msg_status(memory_type, slot), 7)  # validateReq
            logger.debug("validación solicitada",
                         extra={"ip": self.ip, "slot": slot})

            # 5. Poll hasta valid o timeout
            val_status = self._poll_until_valid(memory_type, slot)
            if val_status != MessageStatus.VALID:
                corrupted = True
                self._slots.mark_corrupted(slot)
                self._rollback(memory_type, slot)
                raise ValueError(f"Validación fallida — status: {val_status}")

            # 6. Leer CRC
            crc = int(self._read.get(msg_crc(memory_type, slot)))
            logger.debug("crc leído", extra={"ip": self.ip, "slot": slot, "crc": crc})

            # 7. Activar mensaje en el panel
            activate_hex = self._build_activate_hex(
                memory_type=memory_type,
                slot=slot,
                crc=crc,
                priority=priority,
            )
            self._write.set(DMS_ACTIVATE_MESSAGE, activate_hex)
            logger.info("mensaje activado",
                        extra={"ip": self.ip, "slot": slot, "multi": multi_string})

            return Message(
                memory_type=memory_type,
                slot=slot,
                multi_string=multi_string,
                status=MessageStatus.VALID,
                crc=crc,
            )

        except Exception as e:
            if not corrupted:
                self._slots.release(slot)
            logger.error("error enviando mensaje",
                         extra={"ip": self.ip, "slot": slot, "error": str(e)})
            raise

    def delete_message(self, slot: int, memory_type: int = MEMORY_CHANGEABLE) -> bool:
        """
        Borra un mensaje de la messageTable liberando el slot.

        Secuencia NTCIP 1203:
            SET messageStatus = notUsedReq (8) → el panel pasa el slot a notUsed (1)

        También libera el slot en el SlotManager si estaba registrado.
        No afecta el mensaje activo en pantalla — usar clear_message() para eso.
        """
        try:
            self._write.set(msg_status(memory_type, slot), 8)  # notUsedReq
            logger.info("slot borrado",
                        extra={"ip": self.ip, "slot": slot, "memory_type": memory_type})

            if self._slots.is_tracked(slot) and not self._slots.is_available(slot):
                self._slots.release(slot)

            return True

        except Exception as e:
            logger.error("error borrando slot",
                         extra={"ip": self.ip, "slot": slot, "error": str(e)})
            return False

    def clear_message(self) -> bool:
        """
        Activa el mensaje blank del panel y libera todos los slots IN_USE.
        """
        try:
            blank_hex = self._build_activate_hex(
                memory_type=MEMORY_BLANK, slot=1, crc=0,
                priority=_BLANK_MESSAGE_PRIORITY,
            )
            self._write.set(DMS_ACTIVATE_MESSAGE, blank_hex)
            logger.info("panel blankeado", extra={"ip": self.ip})

            for slot in self._slots.in_use_slots():
                self._slots.release(slot)

            return True
        except Exception as e:
            logger.error("error blankeando panel",
                         extra={"ip": self.ip, "error": str(e)})
            return False

    # ─── Métodos internos ─────────────────────────────────────────────────────

    def _poll_until_valid(self, memory_type: int, slot: int) -> MessageStatus:
        """Poll de messageStatus hasta VALID o timeout."""
        deadline = time.time() + _VALIDATE_TIMEOUT
        while time.time() < deadline:
            try:
                raw    = int(self._read.get(msg_status(memory_type, slot)))
                status = MessageStatus(raw)
                if status in (MessageStatus.VALID, MessageStatus.ERROR):
                    return status
            except Exception as e:
                logger.warning("error leyendo status en poll",
                               extra={"ip": self.ip, "slot": slot, "error": str(e)})
            time.sleep(_VALIDATE_INTERVAL)

        logger.warning("timeout esperando validación",
                       extra={"ip": self.ip, "slot": slot, "memory_type": memory_type})
        return MessageStatus.ERROR

    def _rollback(self, memory_type: int, slot: int) -> None:
        """Limpia un slot que quedó en estado inválido."""
        try:
            self._write.set(msg_status(memory_type, slot), 6)   # modifyReq
            self._write.set(msg_multi_string(memory_type, slot), OctetString(""))
            self._write.set(msg_status(memory_type, slot), 7)   # validateReq
            logger.info("rollback exitoso",
                        extra={"ip": self.ip, "slot": slot, "memory_type": memory_type})
        except Exception as e:
            logger.error("rollback fallido",
                         extra={"ip": self.ip, "slot": slot, "error": str(e)})

    def _build_activate_hex(
        self,
        memory_type: int,
        slot: int,
        crc: int,
        priority: int = 3,
        duration: int = 0xFFFF,
    ):
        """
        Construye el valor binario de dmsActivateMessage.

        Formato NTCIP 1203 (12 bytes):
            2 bytes — duration     (0xFFFF = infinito)
            1 byte  — priority
            1 byte  — memory_type
            2 bytes — slot
            2 bytes — CRC
            4 bytes — IP origen
        """
        ip_bytes = socket.inet_aton(self._source_ip)
        payload = struct.pack(
            ">HBBHH4s",
            duration,
            priority,
            memory_type,
            slot,
            crc,
            ip_bytes,
        )
        return OctetString(payload)
