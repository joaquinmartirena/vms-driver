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
from models.device import DeviceStatus, DeviceInfo, GraphicInfo, Message, MessageStatus, ControlMode, SignDimensions, SignType, BrightnessStatus
from snmp.client import SNMPClient
from snmp.ntcip1203 import (
    SYS_DESCR,
    DMS_MAX_CHANGEABLE_MSG,
    DMS_SIGN_HEIGHT, DMS_SIGN_WIDTH, DMS_SIGN_TYPE, DMS_SIGN_TECHNOLOGY,
    DMS_ILLUM_CONTROL, DMS_ILLUM_NUM_BRIGHT_LEVELS, DMS_ILLUM_BRIGHT_LEVEL_STATUS,
    DMS_ILLUM_MAN_LEVEL, DMS_ILLUM_LIGHT_OUTPUT_STATUS,
    VMS_SIGN_WIDTH_PIXELS, VMS_SIGN_HEIGHT_PIXELS,
    VMS_CHARACTER_HEIGHT_PIXELS, VMS_CHARACTER_WIDTH_PIXELS,
    MULTI_MAX_MULTI_STRING_LENGTH, MULTI_MAX_NUMBER_PAGES, MULTI_SUPPORTED_MULTI_TAGS,
    DMS_ACTIVATE_MESSAGE,
    DMS_CONTROL_MODE,
    SHORT_ERROR_STATUS, SHORT_ERROR_BITS, DMS_STAT_DOOR_OPEN, WATCHDOG_FAILURE_COUNT,
    msg_multi_string, msg_crc, msg_status,
    gfx_status, gfx_number, gfx_height, gfx_width, gfx_color_type, gfx_id, gfx_block_data,
    DMS_GRAPHIC_BLOCK_SIZE, DMS_GRAPHIC_MAX_SIZE, DMS_NUM_GRAPHICS, GFX_STATUS_COL,
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

# ─── Configuración de subida de gráficos ───────────────────────────────────────
# El VFC reporta 64449 en dmsGraphicBlockSize pero ese es el max size total.
# El block size real (confirmado empíricamente) es 1023 bytes.
_GFX_BLOCK_SIZE  = int(os.getenv("VMS_GFX_BLOCK_SIZE",  "1023"))   # bytes por bloque SNMP
_GFX_META_DELAY  = float(os.getenv("VMS_GFX_META_DELAY",  "0.0"))  # ya no necesario (hay poll)
_GFX_BLOCK_DELAY = float(os.getenv("VMS_GFX_BLOCK_DELAY", "0.05")) # s entre bloques

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
        """Orquesta el auto-descubrimiento completo del panel."""
        self._source_ip      = self._source_ip_override or self._detect_source_ip()
        self._slots          = SlotManager(total_slots=self._discover_slot_count())
        self._sign_width     = int(self._read.get(VMS_SIGN_WIDTH_PIXELS))
        self._sign_height    = int(self._read.get(VMS_SIGN_HEIGHT_PIXELS))
        self._fonts          = self._discover_fonts()
        self._supported_tags = self._discover_supported_tags()
        self._validator      = self._init_validator()
        logger.info("panel inicializado", extra={
            "ip": self.ip,
            "slots": self._slots._total,
            "fonts": len(self._fonts),
            "supported_tags": sorted(self._supported_tags),
        })

    def _discover_fonts(self) -> dict[int, dict]:
        """
        Lee la tabla de fuentes del panel vía SNMP.
        Devuelve dict: {font_number: {"name": str, "height": int, "width": int}}
        Si el panel no soporta fonts, devuelve {}.
        """
        fonts = {}
        try:
            num_fonts = int(self._read.get("1.3.6.1.4.1.1206.4.2.3.3.1.0"))
            for n in range(1, num_fonts + 1):
                try:
                    name = str(self._read.get(f"1.3.6.1.4.1.1206.4.2.3.3.2.1.3.{n}"))
                    if not name:
                        continue
                    height = int(self._read.get(f"1.3.6.1.4.1.1206.4.2.3.3.2.1.5.{n}"))
                    width  = int(self._read.get(f"1.3.6.1.4.1.1206.4.2.3.3.2.1.6.{n}"))
                    fonts[n] = {"name": name, "height": height, "width": width}
                except Exception:
                    continue
            logger.debug("fuentes descubiertas", extra={"ip": self.ip, "count": len(fonts)})
        except Exception:
            logger.debug("panel sin soporte de fuentes", extra={"ip": self.ip})
        return fonts

    def get_largest_font(self) -> int | None:
        """Devuelve el número de la fuente con mayor altura. None si no hay fuentes."""
        if not self._fonts:
            return None
        return max(self._fonts, key=lambda n: self._fonts[n]["height"])

    def get_bold_largest_font(self) -> int | None:
        """
        Devuelve el número de la fuente bold más grande.
        Detecta bold por nombre — fuentes que empiezan con 'fb'.
        Fallback a get_largest_font() si no hay bold.
        """
        bold_fonts = {n: f for n, f in self._fonts.items() if f["name"].startswith("fb")}
        if not bold_fonts:
            return self.get_largest_font()
        return max(bold_fonts, key=lambda n: bold_fonts[n]["height"])

    @property
    def panel_info(self) -> dict:
        """Información descubierta del panel — útil para el playground."""
        return {
            "ip": self.ip,
            "slots": self._slots._total,
            "fonts": self._fonts,
            "supported_tags": sorted(self._supported_tags),
            "largest_font": self.get_largest_font(),
            "bold_largest_font": self.get_bold_largest_font(),
        }

    def _discover_supported_tags(self) -> set[str]:
        """
        Descubre los tags MULTI soportados por el panel.

        Estrategia:
        1. Intentar leer dmsSupportedMultiTags (bitmask NTCIP 1203)
        2. Si devuelve valor válido (>0) → decodificar bitmask
        3. Si devuelve 0 o error → hacer probe empírico
        """
        try:
            raw = self._read.get(MULTI_SUPPORTED_MULTI_TAGS)
            # El VFC devuelve OctetString (bytes) en lugar de Integer.
            # Convertir usando NTCIP bit-packing: byte i, bit 7-j → flag i*8+j
            try:
                bitmask = int(raw)
            except (ValueError, TypeError):
                data = bytes(raw)
                bitmask = 0
                for i, byte in enumerate(data):
                    for j in range(8):
                        if byte & (0x80 >> j):
                            bitmask |= (1 << (i * 8 + j))
            if bitmask > 0:
                tags = self._decode_supported_tags_bitmask(bitmask)
                logger.debug("tags desde bitmask", extra={"ip": self.ip, "bitmask": hex(bitmask), "tags": sorted(tags)})
                tags |= self._probe_missing_tags(tags, {"tr", "g"})
                return tags
        except Exception:
            pass

        logger.debug("iniciando probe empírico de tags", extra={"ip": self.ip})
        return self._probe_supported_tags()

    def _probe_missing_tags(self, known: set[str], candidates: set[str]) -> set[str]:
        """Prueba empíricamente solo los tags en `candidates` que no estén en `known`."""
        PROBES = {
            "tr": "[tr1,1,100,50]TEST",
            "g":  None,  # no probeable sin gráfico — usar dmsNumGraphics
        }
        found: set[str] = set()
        slot = 1
        for tag in candidates - known:
            if tag == "g":
                try:
                    if int(self._read.get(DMS_NUM_GRAPHICS)) > 0:
                        found.add("g")
                        logger.debug("tag [g] detectado vía dmsNumGraphics", extra={"ip": self.ip})
                except Exception:
                    pass
                continue
            multi = PROBES.get(tag)
            if not multi:
                continue
            try:
                self._write.set(msg_status(MEMORY_CHANGEABLE, slot), 6)
                self._write.set(msg_multi_string(MEMORY_CHANGEABLE, slot), OctetString(multi))
                self._write.set(msg_status(MEMORY_CHANGEABLE, slot), 7)
                status = self._poll_until_valid(MEMORY_CHANGEABLE, slot)
                if status == MessageStatus.VALID:
                    found.add(tag)
                    logger.debug(f"tag [{tag}] confirmado por probe", extra={"ip": self.ip})
            except Exception:
                pass
            finally:
                try:
                    self._write.set(msg_status(MEMORY_CHANGEABLE, slot), 8)
                except Exception:
                    pass
        return found

    def _probe_supported_tags(self) -> set[str]:
        """
        Probe empírico: escribe mensajes de test en slot 1 y verifica validación.

        Para cada tag, escribe un MULTI mínimo, solicita validación y verifica
        si el panel devuelve status VALID. Tags core siempre incluidos sin probe.
        Al terminar, limpia el slot 1 dejándolo en notUsed.
        """
        CORE_TAGS = {"jl", "jp", "nl", "np"}

        TAG_PROBES = {
            "pt":  "[pt10o0]TEST",
            "cf":  "[cf255,255,255]TEST",
            "cb":  "[cb0,0,0]TEST",
            "pb":  "[pb0,0,0]TEST",
            "sc":  "[sc2]TEST",
            "fo":  "[fo1]TEST",
            "fl":  "[fl5o0]TEST",
            "hc":  "[hc41]",
            "mv":  "[mv10o0,4,3,0]T",
            "tr":  "[tr1,1,100,50]TEST",
            "cr":  "[cr10,10]",
            "sl":  "[sl5]TEST",
            "f":   "[f1,0]",
        }

        supported = set(CORE_TAGS)
        slot = 1

        for tag, multi in TAG_PROBES.items():
            try:
                self._write.set(msg_status(MEMORY_CHANGEABLE, slot), 6)   # modifyReq
                self._write.set(msg_multi_string(MEMORY_CHANGEABLE, slot), OctetString(multi))
                self._write.set(msg_status(MEMORY_CHANGEABLE, slot), 7)   # validateReq
                status = self._poll_until_valid(MEMORY_CHANGEABLE, slot)
                if status == MessageStatus.VALID:
                    supported.add(tag)
                    logger.debug(f"tag soportado: [{tag}]", extra={"ip": self.ip})
                else:
                    logger.debug(f"tag NO soportado: [{tag}]", extra={"ip": self.ip})
            except Exception as e:
                logger.debug(f"tag probe error: [{tag}]", extra={"ip": self.ip, "error": str(e)})
            finally:
                try:
                    self._write.set(msg_status(MEMORY_CHANGEABLE, slot), 8)  # notUsedReq
                except Exception:
                    pass

        supported |= self._probe_missing_tags(supported, {"g"})
        logger.debug("probe completado", extra={"ip": self.ip, "supported": sorted(supported)})
        return supported

    def _decode_supported_tags_bitmask(self, bitmask: int) -> set[str]:
        """Decodifica el bitmask NTCIP 1203 v03 de dmsSupportedMultiTags."""
        BIT_TAG_MAP = {
            0:  "cb",   # color background
            1:  "cf",   # color foreground
            2:  "fl",   # flashing
            3:  "fo",   # font
            4:  "g",    # graphic
            5:  "hc",   # hex char
            6:  "jl",   # justification line
            7:  "jp",   # justification page
            8:  "ms",   # manufacturer specific
            9:  "mv",   # moving text
            10: "nl",   # new line
            11: "np",   # new page
            12: "pt",   # page time
            13: "sc",   # spacing char
            14: "f",    # dynamic field
            15: "pb",   # page background
            16: "sr",   # speed range
            17: "tr",   # text rectangle
            18: "cr",   # color rectangle
            19: "sl",   # line spacing
        }
        return {tag for bit, tag in BIT_TAG_MAP.items() if bitmask & (1 << bit)}

    def _get_activate_priority(self) -> int:
        """Priority para dmsActivateMessage. Sobreescribir en subclases si es necesario."""
        return 3

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
        """Consulta límites al panel vía SNMP. Usa dimensiones ya cacheadas."""
        max_string_length = int(self._read.get(MULTI_MAX_MULTI_STRING_LENGTH))
        max_pages         = int(self._read.get(MULTI_MAX_NUMBER_PAGES))
        logger.debug("dimensiones del panel", extra={
            "ip": self.ip, "width": self._sign_width, "height": self._sign_height,
            "max_string": max_string_length, "max_pages": max_pages,
        })
        validator = MultiValidator(
            width=self._sign_width,
            height=self._sign_height,
            max_string_length=max_string_length,
            max_pages=max_pages,
        )
        validator.set_supported_tags(self._supported_tags)
        return validator

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
                priority=self._get_activate_priority(),
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
                priority=self._get_activate_priority(),
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

    def send_graphic(
        self,
        path: str,
        slot: int,
        color_type: int = 4,
        crop: str = "left",
        width: int | None = None,
        height: int | None = None,
    ) -> "GraphicPayload":
        """
        Sube una imagen al panel como gráfico NTCIP 1203.

        Secuencia:
            1. convert_image() → bitmap dividido en bloques
            2. SET dmsGraphicStatus = modifyReq (7)
            3. SET dmsGraphicNumber, Height, Width, Type
            4. SET dmsGraphicBlockData para cada bloque (1-based)
            5. SET dmsGraphicStatus = readyForUseReq (8)

        El gráfico queda disponible para usarlo con [g{slot}] en MULTI.
        """
        from driver.graphics.payload import GraphicPayload, convert_image

        # Leer parámetros gráficos del panel via SNMP antes de calcular bloques.
        try:
            max_entries = int(self._read.get(DMS_NUM_GRAPHICS))
        except Exception:
            max_entries = None

        try:
            max_size = int(self._read.get(DMS_GRAPHIC_MAX_SIZE))
        except Exception:
            max_size = None

        try:
            reported_bs = int(self._read.get(DMS_GRAPHIC_BLOCK_SIZE))
            block_size = reported_bs if reported_bs > 0 else _GFX_BLOCK_SIZE
        except Exception:
            block_size = _GFX_BLOCK_SIZE

        logger.debug("parámetros gráficos del panel",
                     extra={"ip": self.ip, "max_entries": max_entries,
                            "max_size": max_size, "block_size": block_size})

        target_w = width  if width  is not None else self._sign_width
        target_h = height if height is not None else self._sign_height
        payload = convert_image(
            path, target_w, target_h,
            slot, block_size=block_size, color_type=color_type, crop=crop,
        )

        if max_size is not None and payload.total_bytes > max_size:
            raise ValueError(
                f"La imagen ocupa {payload.total_bytes} bytes pero el panel soporta "
                f"máximo {max_size} bytes por gráfico"
            )

        # El VFC no soporta notUsedReq(6). Ir directo a modifyReq(7) desde
        # cualquier estado — el dispositivo acepta la transición.
        current = None
        try:
            current = int(self._read.get(gfx_status(slot)))
            logger.debug("estado actual del gráfico", extra={"ip": self.ip, "slot": slot, "status": current})
        except Exception:
            pass

        self._write.set(gfx_status(slot),     7)               # modifyReq
        self._write.set(gfx_number(slot),     slot)
        self._write.set(gfx_height(slot),     payload.height)
        self._write.set(gfx_width(slot),      payload.width)
        self._write.set(gfx_color_type(slot), payload.color_type)

        # Esperar a que el dispositivo entre en modifying(2) antes de enviar bloques
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                s = int(self._read.get(gfx_status(slot)))
                if s == 2:  # modifying
                    break
            except Exception:
                pass
            time.sleep(0.3)
        else:
            raise TimeoutError(
                f"El panel no entró en modifying(2) para el slot {slot} en 10s"
            )

        for i, block in enumerate(payload.blocks, start=1):
            try:
                self._write.set(gfx_block_data(slot, i), OctetString(block))
            except Exception as exc:
                raise RuntimeError(
                    f"Falló el envío del bloque {i}/{len(payload.blocks)} "
                    f"(slot={slot}, bytes={len(block)}): {exc}"
                ) from exc
            logger.debug("bloque gráfico enviado",
                         extra={"ip": self.ip, "slot": slot, "block": i})
            if _GFX_BLOCK_DELAY > 0:
                time.sleep(_GFX_BLOCK_DELAY)

        self._write.set(gfx_status(slot), 8)                   # readyForUseReq

        # Esperar a readyForUse(4)
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                s = int(self._read.get(gfx_status(slot)))
                if s in (4, 5):  # readyForUse o error
                    break
            except Exception:
                pass
            time.sleep(0.5)

        logger.info("gráfico subido",
                    extra={"ip": self.ip, "slot": slot,
                           "blocks": len(payload.blocks), "bytes": payload.total_bytes})
        return payload

    def get_graphics(self) -> list[GraphicInfo]:
        """
        Devuelve los gráficos almacenados en la dmsGraphicTable.

        Flujo optimizado (sin walk):
          1. GET dmsNumGraphics → número de slots disponibles.
          2. Batch GET de gfx_status(1..N) en grupos de 50 → descubrir slots activos.
          3. Batch GET de las 6 columnas de todos los slots activos juntos.
          4. Construir y retornar list[GraphicInfo].
        """
        # 1. Número de slots disponibles
        try:
            num_slots = int(self._read.get(DMS_NUM_GRAPHICS))
        except Exception:
            num_slots = 255  # fallback al máximo conocido del VFC

        if num_slots == 0:
            return []

        # 2. Batch GET de la columna status para todos los slots
        status_oids = [gfx_status(s) for s in range(1, num_slots + 1)]
        try:
            status_vals = self._read.get_many_batched(status_oids, batch_size=50)
        except Exception as e:
            logger.warning("error leyendo status de gráficos", extra={"ip": self.ip, "error": str(e)})
            return []

        active_slots = [
            s for s, v in zip(range(1, num_slots + 1), status_vals)
            if int(v) != 1  # 1 = notUsed
        ]

        if not active_slots:
            return []

        # 3. Batch GET de las 6 columnas de todos los slots activos
        # OIDs en orden: por cada slot → [number, height, width, color_type, id, status]
        detail_oids = []
        for slot in active_slots:
            detail_oids.extend([
                gfx_number(slot),
                gfx_height(slot),
                gfx_width(slot),
                gfx_color_type(slot),
                gfx_id(slot),
                gfx_status(slot),
            ])

        try:
            detail_vals = self._read.get_many_batched(detail_oids, batch_size=50)
        except Exception as e:
            logger.warning("error leyendo detalles de gráficos", extra={"ip": self.ip, "error": str(e)})
            return []

        # 4. Reconstruir GraphicInfo (6 valores por slot, en el mismo orden)
        graphics: list[GraphicInfo] = []
        for i, slot in enumerate(active_slots):
            base = i * 6
            try:
                graphics.append(GraphicInfo(
                    slot=slot,
                    number=int(detail_vals[base]),
                    height=int(detail_vals[base + 1]),
                    width=int(detail_vals[base + 2]),
                    color_type=int(detail_vals[base + 3]),
                    crc=int(detail_vals[base + 4]),
                    status=int(detail_vals[base + 5]),
                ))
            except Exception as e:
                logger.warning("error parseando gráfico",
                               extra={"ip": self.ip, "slot": slot, "error": str(e)})
                continue

        logger.debug("gráficos leídos", extra={"ip": self.ip, "count": len(graphics)})
        return graphics

    def get_sign_dimensions(self) -> SignDimensions:
        """
        Lee las dimensiones del panel en un solo request SNMP multi-OID.

        Orden de OIDs:
            [0] vmsSignHeightPixels   — filas de píxeles
            [1] vmsSignWidthPixels    — columnas de píxeles
            [2] dmsSignHeight         — altura física (mm)
            [3] dmsSignWidth          — anchura física (mm)
            [4] vmsCharacterHeightPixels  (0 = variable / full-matrix)
            [5] vmsCharacterWidthPixels   (0 = variable / full-matrix)
        """
        vals = self._read.get_many(
            VMS_SIGN_HEIGHT_PIXELS,
            VMS_SIGN_WIDTH_PIXELS,
            DMS_SIGN_HEIGHT,
            DMS_SIGN_WIDTH,
            VMS_CHARACTER_HEIGHT_PIXELS,
            VMS_CHARACTER_WIDTH_PIXELS,
        )
        return SignDimensions(
            height_pixels=int(vals[0]),
            width_pixels=int(vals[1]),
            height_mm=int(vals[2]),
            width_mm=int(vals[3]),
            char_height_pixels=int(vals[4]),
            char_width_pixels=int(vals[5]),
        )

    def get_device_info(self) -> DeviceInfo:
        """
        Lee información estática del dispositivo en un solo request SNMP multi-OID.

        Orden de OIDs:
            [0] dmsSignType         — tipo de panel (ver SignType enum)
            [1] dmsSignTechnology   — bitmap de tecnología (bit1=LED, bit2=FlipDisk, bit3=FiberOptics, bit6=Drum)
            [2] watchdogFailureCount — contador histórico de reinicios por watchdog
        """
        vals = self._read.get_many(
            DMS_SIGN_TYPE,
            DMS_SIGN_TECHNOLOGY,
            WATCHDOG_FAILURE_COUNT,
        )
        try:
            sign_type = SignType(int(vals[0]))
        except ValueError:
            sign_type = None

        return DeviceInfo(
            ip=self.ip,
            port=self.port,
            sign_type=sign_type,
            sign_technology=int(vals[1]),
            watchdog_failures=int(vals[2]),
        )

    def get_brightness(self) -> BrightnessStatus:
        """
        Lee el estado de iluminación del panel en un solo request SNMP multi-OID.

        Orden de OIDs:
            [0] dmsIllumControl           — modo activo
            [1] dmsIllumNumBrightLevels   — niveles soportados
            [2] dmsIllumBrightLevelStatus — nivel actual (read-only)
            [3] dmsIllumLightOutputStatus — light output 0–65535 (read-only)
        """
        vals = self._read.get_many(
            DMS_ILLUM_CONTROL,
            DMS_ILLUM_NUM_BRIGHT_LEVELS,
            DMS_ILLUM_BRIGHT_LEVEL_STATUS,
            DMS_ILLUM_LIGHT_OUTPUT_STATUS,
        )
        return BrightnessStatus(
            control_mode=int(vals[0]),
            max_levels=int(vals[1]),
            current_level=int(vals[2]),
            light_output=int(vals[3]),
        )

    def set_brightness(self, level: int) -> None:
        """
        Pone el panel en modo manualIndexed y establece el nivel de brillo.

        Secuencia NTCIP 1203:
            1. GET dmsIllumNumBrightLevels → validar rango
            2. SET dmsIllumControl = 4 (manualIndexed)
            3. SET dmsIllumManLevel = level

        Lanza ValueError si level está fuera de rango [1, max_levels].
        """
        max_levels = int(self._read.get(DMS_ILLUM_NUM_BRIGHT_LEVELS))
        if not (1 <= level <= max_levels):
            raise ValueError(
                f"Nivel de brillo {level} fuera de rango [1, {max_levels}]"
            )
        self._write.set(DMS_ILLUM_CONTROL,   4)      # manualIndexed
        self._write.set(DMS_ILLUM_MAN_LEVEL, level)
        logger.info("brillo establecido",
                    extra={"ip": self.ip, "level": level, "max_levels": max_levels})

    def get_active_alarms(self) -> list[str]:
        """
        Lee shortErrorStatus y devuelve los nombres de los bits activos.

        Devuelve lista vacía si no hay alarmas.
        """
        raw = int(self._read.get(SHORT_ERROR_STATUS))
        return [name for bit, name in SHORT_ERROR_BITS.items() if raw & (1 << (bit - 1))]

    def delete_graphic(self, slot: int) -> None:
        """
        Elimina un gráfico de la dmsGraphicTable.

        Secuencia NTCIP 1203:
            1. GET dmsGraphicStatus → verificar existencia y que no sea permanent (6)
            2. SET dmsGraphicStatus = notUsedReq (9)
            3. Poll hasta dmsGraphicStatus == notUsed (1)

        Lanza ValueError si el slot es permanent.
        Lanza TimeoutError si el panel no confirma notUsed en tiempo límite.
        """
        _GFX_DELETE_TIMEOUT  = 10.0  # s
        _GFX_DELETE_INTERVAL = 0.3   # s

        current = int(self._read.get(gfx_status(slot)))
        if current == 6:  # permanent
            raise ValueError(f"El gráfico en slot {slot} es permanent y no se puede borrar")

        self._write.set(gfx_status(slot), 9)  # notUsedReq
        logger.debug("notUsedReq enviado", extra={"ip": self.ip, "slot": slot})

        deadline = time.time() + _GFX_DELETE_TIMEOUT
        while time.time() < deadline:
            try:
                s = int(self._read.get(gfx_status(slot)))
                if s == 1:  # notUsed
                    logger.info("gráfico eliminado", extra={"ip": self.ip, "slot": slot})
                    return
            except Exception as e:
                logger.warning("error leyendo status en poll delete_graphic",
                               extra={"ip": self.ip, "slot": slot, "error": str(e)})
            time.sleep(_GFX_DELETE_INTERVAL)

        raise TimeoutError(
            f"El panel no confirmó notUsed para el slot {slot} en {_GFX_DELETE_TIMEOUT}s"
        )

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
