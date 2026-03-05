import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from snmp.client import SNMPClient

# Configuración del VFC de Daktronics
IP        = "66.17.99.157"
COMMUNITY_READ  = "public"
COMMUNITY_WRITE = "administrator"

# OID básico — sysDescr, cualquier dispositivo SNMP lo tiene
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"

def test_get_sysdescr():
    client = SNMPClient(ip=IP, community=COMMUNITY_READ)
    value = client.get(OID_SYS_DESCR)
    print(f"sysDescr: {value}")
    assert value is not None
    print("OK - GET funciona")

def test_get_message_status():
    """Lee el status del slot 2 en memoria 3 — el que usaste antes"""
    OID_MSG_STATUS = "1.3.6.1.4.1.1206.4.2.3.5.8.1.9.3.2"
    client = SNMPClient(ip=IP, community=COMMUNITY_READ)
    value = client.get(OID_MSG_STATUS)
    print(f"messageStatus slot (3,2): {value}")
    assert value is not None
    print("OK - GET NTCIP funciona")

if __name__ == "__main__":
    print("=== Test SNMPClient ===\n")
    test_get_sysdescr()
    print()
    test_get_message_status()