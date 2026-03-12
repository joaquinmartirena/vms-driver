"""
Driver para paneles ChainZone.
NTCIP 1203 sobre SNMP v2c — community read/write: public.
Panel confirmado: 48x96px, 9 slots, 19 fuentes.
Tags y fuentes se auto-descubren al inicializar.
"""

from driver.ntcip_driver import NTCIPDriver
from driver.chainzone.oids import ACTIVATE_MESSAGE_PRIORITY


class ChainZoneDriver(NTCIPDriver):
    """Driver para paneles ChainZone — NTCIP 1203 sobre SNMP v2c."""

    def _get_activate_priority(self) -> int:
        return ACTIVATE_MESSAGE_PRIORITY
