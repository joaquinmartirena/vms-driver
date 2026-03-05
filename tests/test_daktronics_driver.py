"""
Test de integración contra el Daktronics VFC real.
IP: 66.17.99.157
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.DEBUG)

from driver.daktronics.driver import DaktronicsVFCDriver
from models.device import MessageStatus

IP = "66.17.99.157"

def test_get_status():
    print("\n=== Test: get_status ===")
    driver = DaktronicsVFCDriver(ip=IP)
    status = driver.get_status()

    print(f"Online:          {status.online}")
    print(f"Control mode:    {status.control_mode}")
    print(f"Errores activos: {status.active_errors()}")
    print(f"Puerta abierta:  {status.door_open}")
    print(f"Watchdog:        {status.watchdog_failures}")
    print(f"Last polled:     {status.last_polled}")

    assert status.online, "Panel debería estar online"
    print("OK")


def test_get_current_message():
    print("\n=== Test: get_current_message ===")
    driver = DaktronicsVFCDriver(ip=IP)
    msg = driver.get_current_message()
    print(f"Mensaje activo: '{msg}'")
    print("OK")


def test_send_message():
    print("\n=== Test: send_message ===")
    driver = DaktronicsVFCDriver(ip=IP)

    result = driver.send_message(
        multi_string="[jl3]TEST[np][jl3]DRIVER",
        slot=1,
        priority=3
    )

    print(f"Memory type: {result.memory_type}")
    print(f"Slot:        {result.slot}")
    print(f"MULTI:       {result.multi_string}")
    print(f"Status:      {result.status}")
    print(f"CRC:         {result.crc}")

    assert result.status == MessageStatus.VALID
    print("OK")


if __name__ == "__main__":
    print("=== Integration Tests — Daktronics VFC ===\n")
    test_get_status()
    test_get_current_message()
    test_send_message()