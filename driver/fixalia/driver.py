"""
Driver para Fixalia — implementa NTCIPDriver sobre NTCIP 1203 / SNMP v2c.
Simulador: 127.0.0.1 · panel full-matrix 320×64 px
"""

from driver.ntcip_driver import NTCIPDriver


class FixaliaDriver(NTCIPDriver):
    """Driver para Fixalia."""
