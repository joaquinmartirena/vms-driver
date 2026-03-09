"""
Driver para Fixalia — implementa NTCIPDriver sobre NTCIP 1203 / SNMP v2c.
Simulador: 127.0.0.1 · panel full-matrix 320×64 px
"""

from driver.ntcip_driver import NTCIPDriver
from driver.fixalia.oids import ACTIVATE_MESSAGE_PRIORITY


class FixaliaDriver(NTCIPDriver):
    """Driver para Fixalia VMS — NTCIP 1203 sobre SNMP v2c."""

    def _get_activate_priority(self) -> int:
        """Fixalia requiere priority=0xFF en dmsActivateMessage."""
        return ACTIVATE_MESSAGE_PRIORITY
