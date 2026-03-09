"""
Test de integración contra el simulador Fixalia.
IP leída de la variable de entorno VMS_PANEL_IP (default: 127.0.0.1).
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.DEBUG)

from driver.fixalia.driver import FixaliaDriver
from models.device import MessageStatus

IP = os.getenv("VMS_PANEL_IP", "127.0.0.1")


def test_ping():
    print("\n=== Test: ping ===")
    driver = FixaliaDriver(ip=IP)
    result = driver.ping()
    print(f"Ping: {result}")
    assert result is True, "El panel debería responder al ping"
    print("OK")


def test_get_status():
    print("\n=== Test: get_status ===")
    driver = FixaliaDriver(ip=IP)
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
    driver = FixaliaDriver(ip=IP)
    msg = driver.get_current_message()
    print(f"Mensaje activo: '{msg}'")
    print("OK")


def test_send_message():
    print("\n=== Test: send_message ===")
    driver = FixaliaDriver(ip=IP)

    result = driver.send_message(
        multi_string="[jl3]HOLA[np][jl3]FIXALIA",
        priority=3,
    )

    print(f"Memory type: {result.memory_type}")
    print(f"Slot:        {result.slot}")
    print(f"MULTI:       {result.multi_string}")
    print(f"Status:      {result.status}")
    print(f"CRC:         {result.crc}")

    assert result.status == MessageStatus.VALID
    print("OK")


def test_get_messages():
    print("\n=== Test: get_messages ===")
    driver = FixaliaDriver(ip=IP)

    # Asegurarse de que hay al menos un mensaje
    driver.send_message("[jl3]TEST LISTA", priority=3)

    msgs = driver.get_messages()
    print(f"Mensajes encontrados: {len(msgs)}")
    for m in msgs:
        print(f"  slot={m.slot}  status={m.status}  multi='{m.multi_string}'")

    print("OK")


def test_delete_message():
    print("\n=== Test: delete_message ===")
    driver = FixaliaDriver(ip=IP)

    # Enviar un mensaje y guardar el slot
    msg = driver.send_message("[jl3]BORRAR ESTO", priority=3)
    slot = msg.slot
    print(f"Mensaje enviado en slot {slot}")

    # Borrar el mensaje
    ok = driver.delete_message(slot)
    print(f"delete_message({slot}): {ok}")

    assert ok is True
    assert driver._slots.is_available(slot), f"El slot {slot} debería estar FREE tras delete"
    print("OK")


def test_clear_message():
    print("\n=== Test: clear_message ===")
    driver = FixaliaDriver(ip=IP)

    # Enviar un mensaje para asegurarse de que hay algo activo
    driver.send_message("[jl3]LIMPIAR[np][jl3]PANEL", priority=3)

    result = driver.clear_message()
    print(f"clear_message: {result}")

    assert result is True
    assert driver._slots.status()["in_use"] == 0, "No debería quedar ningún slot IN_USE"
    print("OK")


def test_slots_status():
    print("\n=== Test: slots_status ===")
    driver = FixaliaDriver(ip=IP)
    s = driver._slots.status()
    print(f"free={s['free']}  in_use={s['in_use']}  corrupted={s['corrupted']}  total={s['total']}")
    assert s["total"] > 0, "El total de slots debe ser mayor que cero"
    print("OK")


if __name__ == "__main__":
    print("=== Integration Tests — Fixalia ===\n")
    print("─" * 50)
    test_ping()
    print("─" * 50)
    test_get_status()
    print("─" * 50)
    test_get_current_message()
    print("─" * 50)
    test_send_message()
    print("─" * 50)
    test_get_messages()
    print("─" * 50)
    test_delete_message()
    print("─" * 50)
    test_clear_message()
    print("─" * 50)
    test_slots_status()
    print("─" * 50)
    print("\n=== Todos los tests pasaron ===\n")
