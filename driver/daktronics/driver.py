"""
Driver para Daktronics VFC — implementa VMSDriver sobre NTCIP 1203 / SNMP v2c.
Dispositivo real: 66.17.99.157
"""

import time
import socket
import struct
import logging
from datetime import datetime

from pysnmp.hlapi.v3arch.asyncio import OctetString

from driver.base import VMSDriver
from driver.multi import MultiValidator
from driver.daktronics.slots import SlotManager
from models.device import DeviceStatus, Message, MessageStatus, ControlMode, ShortErrorBit
from snmp.client import SNMPClient
from driver.daktronics.oids import *

logger = logging.getLogger(__name__)


class DaktronicsVFCDriver(VMSDriver):
    """
    Driver para Daktronics VFC.
    Implementa la secuencia NTCIP 1203 para escribir y activar mensajes.
    """

    VALIDATE_TIMEOUT  = 10    # segundos esperando que el VFC valide
    VALIDATE_INTERVAL = 0.5   # segundos entre cada poll de status

    def __init__(self, ip: str, port: int = 161, source_ip: str | None = None):
        self.ip   = ip
        self.port = port
        self._read  = SNMPClient(ip=ip, community=COMMUNITY_READ,  port=port)
        self._write = SNMPClient(ip=ip, community=COMMUNITY_WRITE, port=port)
        self._slots = SlotManager()
        self._source_ip = source_ip or self._detect_source_ip()
        self._validator = self._init_validator()

    def _detect_source_ip(self) -> str:
        """Detecta la IP de la interfaz que tiene ruta al panel, sin enviar tráfico."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((self.ip, self.port))
            return s.getsockname()[0]

    def _init_validator(self) -> MultiValidator:
        """Consulta dimensiones y límites al panel vía SNMP para construir el validador."""
        try:
            width             = int(self._read.get(VMS_SIGN_WIDTH_PIXELS))
            height            = int(self._read.get(VMS_SIGN_HEIGHT_PIXELS))
            max_string_length = int(self._read.get(MULTI_MAX_MULTI_STRING_LENGTH))
            max_pages         = int(self._read.get(MULTI_MAX_NUMBER_PAGES))
            logger.debug(
                f"Panel {self.ip}: {width}×{height}px, "
                f"max_string={max_string_length}, max_pages={max_pages}"
            )
        except Exception as e:
            logger.warning(f"No se pudieron leer dimensiones de {self.ip}, usando defaults: {e}")
            width, height, max_string_length, max_pages = 144, 96, 1500, 6

        return MultiValidator(
            width=width,
            height=height,
            max_string_length=max_string_length,
            max_pages=max_pages,
        )

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
        """Lee el MULTI string del mensaje activo (currentBuffer = memory_type 5, slot 1)."""
        try:
            value = self._read.get(msg_multi_string(MEMORY_CURRENT_BUFFER, 1))
            return str(value)
        except Exception as e:
            logger.warning(f"No se pudo leer mensaje activo en {self.ip}: {e}")
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
            logger.warning(f"Error leyendo slot ({memory_type},{slot}): {e}")
            return None

    def get_messages(self, memory_type: int = MEMORY_CHANGEABLE) -> list[Message]:
        """
        Lista todos los mensajes válidos en un tipo de memoria.

        Recorre los slots del SlotManager y devuelve los que tienen
        messageStatus == VALID con contenido no vacío.
        Solo consulta slots que el SlotManager conoce como IN_USE,
        más un scan inicial de los primeros 20 slots para detectar
        mensajes que existían antes de que arrancara el driver.
        """
        messages = []
        checked = set()

        # Slots que el SlotManager sabe que están en uso
        in_use_slots = self._slots.in_use_slots()

        # Scan de los primeros 20 slots para detectar mensajes preexistentes
        scan_slots = list(range(1, 21))

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
            1. SET messageStatus = modifyReq   (abrir slot)
            2. SET messageMultiString          (escribir contenido)
            3. SET messageStatus = validateReq (solicitar validación)
            4. Poll hasta messageStatus == valid
            5. GET messageCRC
            6. SET activateMessage             (mostrar en panel)

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
            # 1. Abrir slot para edición
            self._write.set(msg_status(memory_type, slot), 6)  # modifyReq
            logger.debug(f"Slot ({memory_type},{slot}) abierto")

            # 2. Escribir MULTI string
            self._write.set(msg_multi_string(memory_type, slot), OctetString(multi_string))
            logger.debug(f"MULTI string escrito: {multi_string}")

            # 3. Solicitar validación
            self._write.set(msg_status(memory_type, slot), 7)  # validateReq
            logger.debug("Validación solicitada")

            # 4. Poll hasta valid o timeout
            val_status = self._poll_until_valid(memory_type, slot)
            if val_status != MessageStatus.VALID:
                corrupted = True
                self._slots.mark_corrupted(slot)
                self._rollback(memory_type, slot)
                raise ValueError(f"Validación fallida — status: {val_status}")

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
            logger.info(f"Mensaje activado en {self.ip} (slot={slot}): {multi_string}")

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
            logger.error(f"Error enviando mensaje a {self.ip}: {e}")
            raise

    def delete_message(self, slot: int, memory_type: int = MEMORY_CHANGEABLE) -> bool:
        """
        Borra un mensaje de la messageTable liberando el slot.

        Secuencia NTCIP 1203:
            SET messageStatus = notUsedReq (8) → el VFC pasa el slot a notUsed (1)

        También libera el slot en el SlotManager si estaba registrado.
        No afecta el mensaje activo en pantalla — usar clear_message() para eso.
        """
        try:
            self._write.set(msg_status(memory_type, slot), 8)  # notUsedReq
            logger.info(f"Slot ({memory_type},{slot}) borrado")

            # Liberar en SlotManager si estaba registrado y está ocupado
            if self._slots.is_tracked(slot) and not self._slots.is_available(slot):
                self._slots.release(slot)

            return True

        except Exception as e:
            logger.error(f"Error borrando slot ({memory_type},{slot}): {e}")
            return False

    def clear_message(self) -> bool:
        """
        Activa el mensaje blank del panel y libera todos los slots IN_USE.
        """
        try:
            blank_hex = self._build_activate_hex(memory_type=MEMORY_BLANK, slot=1, crc=0, priority=3)
            self._write.set(DMS_ACTIVATE_MESSAGE, blank_hex)
            logger.info(f"Panel {self.ip} blankeado")

            for slot in self._slots.in_use_slots():
                self._slots.release(slot)

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