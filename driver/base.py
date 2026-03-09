"""
Interfaz base para todos los drivers VMS.
Cada fabricante implementa esta interfaz — el resto del sistema
nunca sabe qué fabricante está usando.
"""

from abc import ABC, abstractmethod
from models.device import DeviceStatus, Message


class VMSDriver(ABC):
    """
    Contrato que todo driver de fabricante debe implementar.
    El Command Handler y el Polling Worker solo hablan con esta interfaz.

    Para agregar soporte a un fabricante nuevo:
        1. Crear driver/fabricante/__init__.py
        2. Crear driver/fabricante/driver.py  (subclase de VMSDriver)
        3. Registrar el driver en driver/factory.py (_REGISTRY)
    """

    @abstractmethod
    def get_status(self) -> DeviceStatus:
        """Lee el estado actual del panel."""
        ...

    @abstractmethod
    def get_current_message(self) -> str:
        """Lee el MULTI string del mensaje activo."""
        ...

    @abstractmethod
    def get_message(self, slot: int) -> Message | None:
        """
        Lee un mensaje específico de la messageTable.
        Devuelve None si el slot está vacío (notUsed).
        """
        ...

    @abstractmethod
    def get_messages(self) -> list[Message]:
        """Lista todos los mensajes válidos actualmente en la tabla del panel."""
        ...

    @abstractmethod
    def send_message(self, multi_string: str, priority: int = 3) -> Message:
        """
        Escribe y activa un mensaje en el panel.
        El driver gestiona la asignación de slots internamente.
        Devuelve el Message con status y CRC confirmados por el panel.
        """
        ...

    @abstractmethod
    def delete_message(self, slot: int) -> bool:
        """
        Borra un mensaje de la messageTable.
        No afecta el mensaje activo en pantalla — usar clear_message() para eso.
        Devuelve True si tuvo éxito.
        """
        ...

    @abstractmethod
    def clear_message(self) -> bool:
        """
        Activa el mensaje blank — el panel queda sin contenido visible.
        Devuelve True si tuvo éxito.
        """
        ...
