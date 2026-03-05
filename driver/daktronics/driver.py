"""
Driver para Daktronics VFC — implementa VMSDriver sobre NTCIP 1203 / SNMP v2c.
Dispositivo real: 66.17.99.157
"""

import time
import socket
import struct
import logging
from datetime import datetime

from driver.base import VMSDriver
from models.device import DeviceStatus, Message, MessageStatus, ControlMode, ShortErrorBit
from snmp.client import SNMPClient
from driver.daktronics.oids import *

logger = logging.getLogger(__name__)


class DaktronicsVFCDriver(VMSDriver):
    """
    Driver para Daktronics VFC.
    Implementa la secuencia NTCIP 1203 para escribir y activar mensajes.
    """

    # Timeouts y reintentos
    VALIDATE_TIMEOUT  = 10    # segundos esperando que el VFC valide
    VALIDATE_INTERVAL = 0.5   # segundos entre cada poll de status

    def __init__(self, ip: str, port: int = 161):
        self.ip   = ip
        self.port = port
        self._read  = SNMPClient(ip=ip, community=COMMUNITY_READ,  port=port)
        self._write = SNMPClient(ip=ip, community=COMMUNITY_WRITE, port=port)

    # ─── Interfaz pública ─────────────────────────────────────────────────────

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
            logger.warning(f"Panel {self.ip} no responde: {e}")
            return DeviceStatus(ip=self.ip, online=False, last_polled=datetime.now())

    def get_current_message(self) -> str:
        try:
            value = self._read.get(msg_multi_string(MEMORY_CURRENT_BUFFER, 1))
            return str(value)
        except Exception as e:
            logger.warning(f"No se pudo leer mensaje activo en {self.ip}: {e}")
            return ""

    def send_message(self, multi_string: str, slot: int = 1, priority: int = 3) -> Message:
        """
        Escribe y activa un mensaje en el panel.

        Secuencia NTCIP 1203:
          1. SET messageStatus = modifyReq  (abrir slot)
          2. SET messageMultiString         (escribir contenido)
          3. SET messageStatus = validateReq (validar)
          4. Poll hasta messageStatus == valid
          5. GET messageCRC
          6. SET activateMessage            (mostrar en panel)
        """
        memory_type = MEMORY_CHANGEABLE

        try:
            # 1. Abrir slot para edición
            self._write.set(msg_status(memory_type, slot), 6)  # modifyReq
            logger.debug(f"Slot ({memory_type},{slot}) abierto")

            # 2. Escribir MULTI string
            from pysnmp.hlapi.asyncio import OctetString
            self._write.set(msg_multi_string(memory_type, slot), OctetString(multi_string))
            logger.debug(f"MULTI string escrito: {multi_string}")

            # 3. Solicitar validación
            self._write.set(msg_status(memory_type, slot), 7)  # validateReq
            logger.debug("Validación solicitada")

            # 4. Poll hasta valid o timeout
            status = self._poll_until_valid(memory_type, slot)
            if status != MessageStatus.VALID:
                self._rollback(memory_type, slot)
                raise ValueError(f"Validación fallida — status: {status}")

            # 5. Leer CRC
            crc = int(self._read.get(msg_crc(memory_type, slot)))
            logger.debug(f"CRC: {crc}")

            # 6. Activar mensaje en el panel
            activate_hex = self._build_activate_hex(
                memory_type=memory_type,
                slot=slot,
                crc=crc,
                priority=priority
            )
            self._write.set(DMS_ACTIVATE_MESSAGE, activate_hex)
            logger.info(f"Mensaje activado en {self.ip}: {multi_string}")

            return Message(
                memory_type=memory_type,
                slot=slot,
                multi_string=multi_string,
                status=MessageStatus.VALID,
                crc=crc,
            )

        except Exception as e:
            logger.error(f"Error enviando mensaje a {self.ip}: {e}")
            raise

    def clear_message(self) -> bool:
        """Activa el mensaje blank del panel (memory_type=7, slot=1 = blank en NTCIP)."""
        try:
            blank_hex = self._build_activate_hex(memory_type=7, slot=1, crc=0, priority=3)
            self._write.set(DMS_ACTIVATE_MESSAGE, blank_hex)
            logger.info(f"Panel {self.ip} blankeado")
            return True
        except Exception as e:
            logger.error(f"Error blankeando panel {self.ip}: {e}")
            return False

    # ─── Métodos internos ─────────────────────────────────────────────────────

    def _poll_until_valid(self, memory_type: int, slot: int) -> MessageStatus:
        """Poll de messageStatus hasta VALID o timeout."""
        deadline = time.time() + self.VALIDATE_TIMEOUT
        while time.time() < deadline:
            try:
                raw = int(self._read.get(msg_status(memory_type, slot)))
                status = MessageStatus(raw)
                if status == MessageStatus.VALID:
                    return status
                if status == MessageStatus.ERROR:
                    return status
            except Exception as e:
                logger.warning(f"Error leyendo status: {e}")
            time.sleep(self.VALIDATE_INTERVAL)

        logger.warning(f"Timeout esperando validación en slot ({memory_type},{slot})")
        return MessageStatus.ERROR

    def _rollback(self, memory_type: int, slot: int) -> None:
        """Limpia un slot que quedó en estado inválido."""
        try:
            from pysnmp.hlapi.asyncio import OctetString
            self._write.set(msg_status(memory_type, slot), 6)   # modifyReq
            self._write.set(msg_multi_string(memory_type, slot), OctetString(""))
            self._write.set(msg_status(memory_type, slot), 7)   # validateReq
            logger.info(f"Rollback exitoso en slot ({memory_type},{slot})")
        except Exception as e:
            logger.error(f"Rollback fallido en slot ({memory_type},{slot}): {e}")

    def _build_activate_hex(
        self,
        memory_type: int,
        slot: int,
        crc: int,
        priority: int = 3,
        duration: int = 0xFFFF,  # infinito por defecto
    ):
        """
        Construye el valor binario de dmsActivateMessage.

        Formato NTCIP 1203 (12 bytes):
          2 bytes — duration   (0xFFFF = infinito)
          1 byte  — priority
          1 byte  — memory_type
          2 bytes — slot
          2 bytes — CRC
          4 bytes — IP origen

        Confirmado contra comando manual:
           FF FF FF 03 00 02 E4 13 7F 00 00 01
        """
        from pysnmp.hlapi.asyncio import OctetString

        ip_bytes = socket.inet_aton(socket.gethostbyname(socket.gethostname()))

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