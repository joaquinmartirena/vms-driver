"""
Test de integración contra el panel ChainZone.
IP leída de la variable de entorno VMS_PANEL_IP (default: 192.168.8.49).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

from driver.chainzone.driver import ChainZoneDriver
from models.device import MessageStatus

IP = os.getenv("VMS_PANEL_IP", "192.168.8.49")


def test_ping():
    print("\n=== Test: ping ===")
    driver = ChainZoneDriver(ip=IP)
    result = driver.ping()
    print(f"Ping: {result}")
    assert result is True, "El panel debería responder al ping"
    print("OK")


def test_get_status():
    print("\n=== Test: get_status ===")
    driver = ChainZoneDriver(ip=IP)
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
    driver = ChainZoneDriver(ip=IP)
    msg = driver.get_current_message()
    print(f"Mensaje activo: '{msg}'")
    print("OK")


def test_panel_info():
    print("\n=== Test: panel_info ===")
    driver = ChainZoneDriver(ip=IP)
    info = driver.panel_info

    print(f"IP:             {info['ip']}")
    print(f"Slots:          {info['slots']}")
    print(f"Fuentes:        {len(info['fonts'])}")
    print(f"Fuente mayor:   {info['largest_font']}")
    print(f"Fuente bold:    {info['bold_largest_font']}")
    print(f"Tags:           {' '.join(f'[{t}]' for t in info['supported_tags'])}")

    assert info["slots"] > 0, "Debe haber al menos un slot"
    assert isinstance(info["supported_tags"], list), "supported_tags debe ser una lista"
    assert len(info["supported_tags"]) > 0, "Debe haber al menos un tag soportado"
    print("OK")


def test_send_message():
    print("\n=== Test: send_message ===")
    driver = ChainZoneDriver(ip=IP)

    # Usar la fuente más grande disponible dinámicamente
    largest = driver.get_bold_largest_font()
    if largest:
        multi = f"[fo{largest}][jl3]CHAIN[np][fo{largest}][jl3]ZONE"
    else:
        multi = "[jl3]CHAIN[np][jl3]ZONE"

    print(f"  MULTI: {multi}")
    try:
        result = driver.send_message(multi)
        print(f"  Memory type: {result.memory_type}")
        print(f"  Slot:        {result.slot}")
        print(f"  MULTI:       {result.multi_string}")
        print(f"  Status:      {result.status}")
        print(f"  CRC:         {result.crc}")
        assert result.status == MessageStatus.VALID
        print("OK")
    except Exception as e:
        import traceback
        print(f"  ERROR: {e}")
        traceback.print_exc(file=sys.stdout)
        raise


def test_get_messages():
    print("\n=== Test: get_messages ===")
    driver = ChainZoneDriver(ip=IP)

    # Asegurarse de que hay al menos un mensaje
    driver.send_message("[jl3]TEST LISTA")

    msgs = driver.get_messages()
    print(f"Mensajes encontrados: {len(msgs)}")
    for m in msgs:
        print(f"  slot={m.slot}  status={m.status}  multi='{m.multi_string}'")

    print("OK")


def test_delete_message():
    print("\n=== Test: delete_message ===")
    driver = ChainZoneDriver(ip=IP)

    msg = driver.send_message("[jl3]BORRAR ESTO")
    slot = msg.slot
    print(f"Mensaje enviado en slot {slot}")

    ok = driver.delete_message(slot)
    print(f"delete_message({slot}): {ok}")

    assert ok is True
    assert driver._slots.is_available(slot), f"El slot {slot} debería estar FREE tras delete"
    print("OK")


def test_clear_message():
    print("\n=== Test: clear_message ===")
    driver = ChainZoneDriver(ip=IP)

    driver.send_message("[jl3]LIMPIAR[np][jl3]PANEL")

    result = driver.clear_message()
    print(f"clear_message: {result}")

    assert result is True
    assert driver._slots.status()["in_use"] == 0, "No debería quedar ningún slot IN_USE"
    print("OK")


if __name__ == "__main__":
    print("=== Integration Tests — ChainZone ===\n")
    print("─" * 50)
    test_ping()
    print("─" * 50)
    test_get_status()
    print("─" * 50)
    test_get_current_message()
    print("─" * 50)
    test_panel_info()
    print("─" * 50)
    test_send_message()
    print("─" * 50)
    test_get_messages()
    print("─" * 50)
    test_delete_message()
    print("─" * 50)
    test_clear_message()
    print("─" * 50)
    print("\n=== Todos los tests pasaron ===\n")
