"""
Diagnóstico paso a paso de subida de gráfico NTCIP 1203.
Ejecuta cada SET individualmente y reporta resultado + estado del dispositivo.

Uso:
    python tools/diag_graphic.py <path_imagen> [slot]
    python tools/diag_graphic.py "toros nieve.jpeg" 4
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pysnmp.proto.rfc1902 import OctetString, Integer32
from snmp.client import SNMPClient
from snmp.ntcip1203 import (
    DMS_GRAPHIC_BLOCK_SIZE, DMS_NUM_GRAPHICS, DMS_GRAPHIC_MAX_SIZE,
    gfx_status, gfx_number, gfx_height, gfx_width, gfx_color_type, gfx_block_data,
)

IP        = os.getenv("VMS_PANEL_IP",        "66.17.99.157")
PORT      = int(os.getenv("VMS_PANEL_PORT",  "161"))
COMM_R    = os.getenv("VMS_COMMUNITY_READ",  "public")
COMM_W    = os.getenv("VMS_COMMUNITY_WRITE", "administrator")
TIMEOUT   = int(os.getenv("VMS_SNMP_TIMEOUT", "15"))
RETRIES   = int(os.getenv("VMS_SNMP_RETRIES", "1"))

GFX_STATUS_NAMES = {
    1: "notUsed",
    2: "modifying",
    3: "calculatingID",
    4: "readyForUse",
    5: "error",
    6: "notUsedReq",
    7: "modifyReq",
    8: "readyForUseReq",
}

def ok(msg):   print(f"  ✓ {msg}")
def fail(msg): print(f"  ✗ {msg}"); sys.exit(1)
def info(msg): print(f"  · {msg}")
def step(msg): print(f"\n[{msg}]")


def snmp_get(client, oid, label):
    try:
        v = client.get(oid)
        ok(f"GET {label} = {v}")
        return v
    except Exception as e:
        fail(f"GET {label} → {e}")


def snmp_set(client, oid, value, label):
    try:
        client.set(oid, value)
        ok(f"SET {label} = {value!r}")
        return True
    except Exception as e:
        fail(f"SET {label} → {e}")


def poll_status(client, slot, target, timeout=10, label=""):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            raw = int(client.get(gfx_status(slot)))
            name = GFX_STATUS_NAMES.get(raw, f"?({raw})")
            if raw == target:
                ok(f"poll status → {name}  {label}")
                return True
            info(f"  poll: status={raw} ({name}), esperando {target} ({GFX_STATUS_NAMES.get(target, '?')})...")
        except Exception as e:
            info(f"  poll error: {e}")
        time.sleep(0.5)
    fail(f"timeout esperando status={target} ({GFX_STATUS_NAMES.get(target, '?')})  {label}")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else input("Path imagen: ").strip()
    slot = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    if not os.path.isfile(path):
        print(f"Archivo no encontrado: {path}"); sys.exit(1)

    r = SNMPClient(IP, COMM_R, PORT, timeout=TIMEOUT, retries=RETRIES)
    w = SNMPClient(IP, COMM_W, PORT, timeout=TIMEOUT, retries=RETRIES)

    print(f"\n{'='*54}")
    print(f"  Diagnóstico gráfico — {IP}:{PORT}  slot={slot}")
    print(f"  Imagen: {path}")
    print(f"{'='*54}")

    # ── 1. Leer capacidades del dispositivo ──────────────────
    step("1. Capacidades del dispositivo")
    num_graphics = snmp_get(r, DMS_NUM_GRAPHICS,     "dmsNumGraphics")
    max_size     = snmp_get(r, DMS_GRAPHIC_MAX_SIZE,  "dmsGraphicMaxSize")
    block_size   = snmp_get(r, DMS_GRAPHIC_BLOCK_SIZE,"dmsGraphicBlockSize")
    block_size_reported = int(block_size)
    # El VFC reporta 64449 en .10.3.0 (es el maxSize, no el blockSize).
    # El block size real confirmado es 1023 — forzamos ese valor.
    block_size = int(os.getenv("VMS_GFX_BLOCK_SIZE_OVERRIDE", "1023"))
    info(f"Block size reportado={block_size_reported}, usando={block_size}")

    # ── 2. Leer estado actual del slot ───────────────────────
    step("2. Estado actual del slot")
    current_raw = int(snmp_get(r, gfx_status(slot), f"gfx_status[{slot}]"))
    current_name = GFX_STATUS_NAMES.get(current_raw, f"?({current_raw})")
    info(f"Estado: {current_raw} = {current_name}")

    # ── 3. Preparar bitmap ───────────────────────────────────
    step("3. Preparar bitmap")
    from driver.graphics.image import load_image, resize_to_sign, to_ntcip_bitmap
    from driver.graphics.bitmap import split_into_blocks
    img    = load_image(path)
    info(f"Imagen original: {img.size}")
    img    = resize_to_sign(img, 144, 96, "center")
    info(f"Redimensionada: {img.size}")
    bitmap = to_ntcip_bitmap(img, color_type=4)
    blocks = split_into_blocks(bitmap, block_size)
    info(f"Bitmap: {len(bitmap)} bytes → {len(blocks)} bloques de {block_size} bytes")
    ok("Bitmap listo")

    # ── 4+5. modifyReq directo (VFC no soporta notUsedReq) ───
    step("4+5. SET modifyReq(7) — directo desde cualquier estado")
    info(f"Estado actual: {current_raw} ({current_name}) → enviando modifyReq(7) directo")
    snmp_set(w, gfx_status(slot), Integer32(7), f"gfx_status[{slot}] = modifyReq(7)")
    poll_status(r, slot, target=2, timeout=10, label="→ esperando modifying(2)")

    # ── 6. Metadata ──────────────────────────────────────────
    step("6. Metadata del gráfico")
    snmp_set(w, gfx_number(slot),     Integer32(slot), f"gfx_number[{slot}]     = {slot}")
    snmp_set(w, gfx_height(slot),     Integer32(96),   f"gfx_height[{slot}]     = 96")
    snmp_set(w, gfx_width(slot),      Integer32(144),  f"gfx_width[{slot}]      = 144")
    snmp_set(w, gfx_color_type(slot), Integer32(4),    f"gfx_color_type[{slot}] = 4 (color24bit)")

    # ── 7. Bloques ───────────────────────────────────────────
    step(f"7. Enviando {len(blocks)} bloques")
    for i, block in enumerate(blocks, start=1):
        oid = gfx_block_data(slot, i)
        try:
            w.set(oid, OctetString(block))
            print(f"  ✓ bloque {i:3}/{len(blocks)}  ({len(block)} bytes)  OID ...{oid.split('.')[-3]}.{oid.split('.')[-2]}.{oid.split('.')[-1]}")
        except Exception as e:
            fail(f"bloque {i}/{len(blocks)} → {e}\n     OID={oid}")
        time.sleep(0.05)

    # ── 8. readyForUseReq ────────────────────────────────────
    step("8. SET readyForUseReq(8)")
    snmp_set(w, gfx_status(slot), Integer32(8), f"gfx_status[{slot}] = readyForUseReq(8)")
    poll_status(r, slot, target=4, timeout=15, label="→ esperando readyForUse(4)")

    # ── 9. Verificar ─────────────────────────────────────────
    step("9. Verificación final")
    final = int(snmp_get(r, gfx_status(slot), f"gfx_status[{slot}]"))
    final_name = GFX_STATUS_NAMES.get(final, f"?({final})")
    if final == 4:
        print(f"\n  ÉXITO — Gráfico en slot {slot} listo. Úsalo con [g{slot}] en MULTI.\n")
    else:
        print(f"\n  FALLO — Estado final: {final} ({final_name})\n")


if __name__ == "__main__":
    main()
