"""
Interfaz base para todos los drivers VMS.
Cada fabricante implementa esta interfaz — el resto del sistema
nunca sabe qué fabricante está usando.
"""

from abc import ABC, abstractmethod
from models.device import DeviceStatus, Message


class VMSDriver(ABC):
    """
    Interfaz que todo driver de fabricante debe implementar.
    El Command Handler y el Polling Worker solo hablan con esta interfaz.
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
    def send_message(self, multi_string: str, slot: int = 1, priority: int = 3) -> Message:
        """
        Escribe y activa un mensaje en el panel.
        Devuelve el Message con status y CRC confirmados.
        """
        ...

    @abstractmethod
    def clear_message(self) -> bool:
        """Limpia el mensaje activo — muestra panel en blanco."""
        ...