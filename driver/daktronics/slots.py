# driver/daktronics/slots.py — shim de compatibilidad
# SlotManager se movió a driver.slots (módulo compartido entre drivers).
# Importar desde driver.slots directamente.
from driver.slots import SlotManager, SlotState  # noqa: F401

__all__ = ["SlotManager", "SlotState"]
