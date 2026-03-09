"""
Driver para Daktronics VFC — implementa NTCIPDriver sobre NTCIP 1203 / SNMP v2c.
Dispositivo real: 66.17.99.157 · panel full-matrix 144×96 px
"""

from driver.ntcip_driver import NTCIPDriver


class DaktronicsVFCDriver(NTCIPDriver):
    """Driver para Daktronics VFC."""
