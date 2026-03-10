"""
Playground interactivo para enviar mensajes MULTI al Daktronics VFC.

Uso:
    python tools/message_playground.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from driver.base import VMSDriver
from driver.factory import create_driver
from driver.multi import MultiBuilder, MultiValidator
from models.device import DeviceInfo


# ─── Fuentes reales del panel (confirmadas vía fontTable) ─────────────────────
FONTS = {
    1:  ("07X04", 7),    2:  ("07X06", 7),    3:  ("FW11X7", 11),
    4:  ("FW07X5", 7),   5:  ("08X04", 8),    6:  ("08X06", 8),
    7:  ("FW14X8", 14),  8:  ("07GRAPH", 7),  9:  ("11X07", 11),
    10: ("11X09", 11),   11: ("14X08", 14),   12: ("14X10", 14),
    13: ("16X08", 16),   14: ("16X10", 16),   15: ("09X06", 9),
    16: ("09X05", 9),    17: ("09X08", 9),    18: ("07X08", 7),
    19: ("08X08", 8),    20: ("24x15", 24),   21: ("12x8", 12),
    22: ("15x10", 15),   23: ("15x11", 15),   24: ("23x15", 23),
    25: ("23x17", 23),   26: ("20x16 SeriesE", 20), 27: ("23x19 SeriesE", 23),
    28: ("24x19 SeriesE", 24), 29: ("23x14", 23), 30: ("29x19", 29),
}

JUSTIFICATIONS = {
    "1": ("[jl2]", "izquierda"),
    "2": ("[jl3]", "centro ★ default"),
    "3": ("[jl4]", "derecha"),
    "4": ("[jl5]", "full"),
}

PAGE_JUSTIFICATIONS = {
    "1": ("[jp2]", "arriba"),
    "2": ("[jp3]", "medio ★ default"),
    "3": ("[jp4]", "abajo"),
}

# Colores clásicos NTCIP
CLASSIC_COLORS = {
    "0": ("negro",   "0,0,0"),
    "1": ("rojo",    "255,0,0"),
    "2": ("amarillo","255,255,0"),
    "3": ("verde",   "0,255,0"),
    "4": ("cyan",    "0,255,255"),
    "5": ("azul",    "0,0,255"),
    "6": ("magenta", "255,0,255"),
    "7": ("blanco",  "255,255,255"),
    "8": ("naranja", "255,165,0"),
    "9": ("ambar ★ default", "255,180,0"),
}

# Campos dinámicos
DYNAMIC_FIELDS = {
    "1":  ("[f1]",  "hora local 12h          -> 02:35 PM"),
    "2":  ("[f2]",  "hora local 24h          -> 14:35"),
    "3":  ("[f3]",  "temperatura °C          -> 23"),
    "4":  ("[f4]",  "temperatura °F          -> 73"),
    "5":  ("[f5]",  "velocidad km/h          -> 87"),
    "6":  ("[f6]",  "velocidad mph           -> 54"),
    "7":  ("[f7]",  "dia de semana           -> Jueves"),
    "8":  ("[f8]",  "fecha mm/dd/yy          -> 03/05/26"),
    "9":  ("[f9]",  "fecha dd/mm/yy          -> 05/03/26"),
    "10": ("[f10]", "anio yyyy               -> 2026"),
    "11": ("[f11]", "hora 12h sin segundos   -> 02:35 PM"),
    "12": ("[f12]", "hora 24h sin segundos   -> 14:35"),
}


def clear_screen():
    os.system('clear')


def print_header(ip: str, device_type: str = ""):
    label = f"VMS Message Playground — {device_type}" if device_type else "VMS Message Playground"
    print("╔══════════════════════════════════════════════════════╗")
    print(f"║{label:^54}║")
    print(f"║{ip:^54}║")
    print("╚══════════════════════════════════════════════════════╝")
    print()


def ask_font(height_pixels: int) -> int:
    print("─── Fuentes disponibles ───────────────────────────────")
    print(f"  {'N':<4} {'Nombre':<24} {'Alto':<6} {'Lineas en panel'}")
    print(f"  {'──':<4} {'──────':<24} {'────':<6} {'───────────────'}")
    for num, (name, height) in FONTS.items():
        lines = height_pixels // height
        default = " *" if num == 24 else ""
        print(f"  {num:<4} {name:<24} {height}px    {lines} lineas{default}")
    print()
    while True:
        raw = input("  Fuente [Enter=24]: ").strip()
        if raw == "":
            return 24
        try:
            n = int(raw)
            if n in FONTS:
                return n
            print("  * Elegi entre 1-30.")
        except ValueError:
            print("  * Ingresa un numero.")


def ask_justification() -> str:
    print("─── Justificacion de linea ─────────────────────────────")
    for k, (tag, label) in JUSTIFICATIONS.items():
        print(f"  {k}) {label}")
    while True:
        raw = input("  [Enter=centro]: ").strip()
        if raw == "":
            return "[jl3]"
        if raw in JUSTIFICATIONS:
            return JUSTIFICATIONS[raw][0]
        print("  * Opcion invalida.")


def ask_page_justification() -> str:
    print("─── Posicion vertical ──────────────────────────────────")
    for k, (tag, label) in PAGE_JUSTIFICATIONS.items():
        print(f"  {k}) {label}")
    while True:
        raw = input("  [Enter=medio]: ").strip()
        if raw == "":
            return "[jp3]"
        if raw in PAGE_JUSTIFICATIONS:
            return PAGE_JUSTIFICATIONS[raw][0]
        print("  * Opcion invalida.")


def ask_page_time() -> str:
    print("─── Tiempo de pagina ───────────────────────────────────")
    print("  Segundos por pagina. 0 = no rota (pagina unica).")
    while True:
        raw = input("  Segundos [Enter=3.0]: ").strip()
        if raw == "":
            return "[pt30o0]"
        try:
            secs = float(raw)
            if secs == 0:
                return ""
            return f"[pt{int(secs * 10)}o0]"
        except ValueError:
            print("  * Ingresa un numero.")


def ask_color_foreground() -> str:
    print("─── Color de texto ─────────────────────────────────────")
    print("  Colores clasicos:")
    for k, (name, rgb) in CLASSIC_COLORS.items():
        print(f"  {k}) {name:<12} ({rgb})")
    print("  r) RGB personalizado")
    print("  Enter = ambar (default del panel)")
    print()
    raw = input("  Color: ").strip().lower()
    if raw == "":
        return ""  # usa default del panel (ambar)
    if raw == "r":
        r = input("  R (0-255): ").strip()
        g = input("  G (0-255): ").strip()
        b = input("  B (0-255): ").strip()
        return f"[cf{r},{g},{b}]"
    if raw in CLASSIC_COLORS:
        rgb = CLASSIC_COLORS[raw][1]
        return f"[cf{rgb}]"
    return ""


def ask_color_background() -> str:
    print("─── Color de fondo de pagina ───────────────────────────")
    print("  Colores clasicos:")
    for k, (name, rgb) in CLASSIC_COLORS.items():
        print(f"  {k}) {name:<12} ({rgb})")
    print("  r) RGB personalizado")
    print("  Enter = negro (default del panel)")
    print()
    raw = input("  Fondo: ").strip().lower()
    if raw == "":
        return ""  # usa default del panel (negro)
    if raw == "r":
        r = input("  R (0-255): ").strip()
        g = input("  G (0-255): ").strip()
        b = input("  B (0-255): ").strip()
        return f"[pb{r},{g},{b}]"
    if raw in CLASSIC_COLORS:
        rgb = CLASSIC_COLORS[raw][1]
        return f"[pb{rgb}]"
    return ""


def ask_content_with_dynamic_fields() -> str:
    """
    Pide el texto de una pagina con soporte para insertar campos dinamicos.
    Usa | para nueva linea, y @N para insertar campo dinamico N.
    """
    print()
    print("  Campos dinamicos disponibles (usa @N para insertar):")
    for k, (tag, desc) in DYNAMIC_FIELDS.items():
        print(f"    @{k:<3} {desc}")
    print()
    print("  Separadores: | = nueva linea")
    print("  Ejemplo: TEMP: @3°C | HORA: @2")
    print()

    raw = input("  Texto: ").strip()
    if not raw:
        return ""

    # Reemplazar @N por el tag dinamico correspondiente
    for k, (tag, _) in sorted(DYNAMIC_FIELDS.items(), key=lambda x: -len(x[0])):
        raw = raw.replace(f"@{k}", tag)

    # Reemplazar | por [nl]
    raw = raw.replace("|", "[nl]")

    return raw


def _parse_coord(raw: str, name: str, lo: int, hi: int, allow_zero: bool = False) -> int | None:
    """Parsea y valida un entero en rango. Devuelve None si invalido."""
    try:
        v = int(raw)
        if allow_zero and v == 0:
            return 0
        if v < lo or v > hi:
            print(f"  * {name} debe estar entre {lo} y {hi}{' (o 0 para extender al borde)' if allow_zero else ''}.")
            return None
        return v
    except ValueError:
        print(f"  * Ingresa un numero entero.")
        return None


def ask_rect(rect_num: int, device_info: DeviceInfo) -> str:
    """
    Guia al usuario para definir un rectangulo de texto [tr].
    Devuelve el fragmento MULTI para ese rectangulo.
    """
    W = device_info.width_pixels
    H = device_info.height_pixels

    print(f"\n─── Rectangulo {rect_num} ─────────────────────────────────────")
    print(f"  Panel: {W} x {H} px  (X: 1–{W}, Y: 1–{H})")
    print(f"  (1,1){'─' * 20}({W},1)")
    print(f"  │{' ' * 20}│")
    print(f"  (1,{H}){'─' * 19}({W},{H})")
    print(f"  W=0 o H=0 extiende hasta el borde del panel.")
    print()

    # X
    while True:
        x = _parse_coord(input(f"  X (1–{W}): ").strip(), "X", 1, W)
        if x is not None:
            break

    # Y
    while True:
        y = _parse_coord(input(f"  Y (1–{H}): ").strip(), "Y", 1, H)
        if y is not None:
            break

    # W
    while True:
        w = _parse_coord(input(f"  W ancho (0=hasta borde): ").strip(), "W", 1, W - x + 1, allow_zero=True)
        if w is not None:
            if w > 0 and x + w > W + 1:
                print(f"  * X({x}) + W({w}) = {x+w} supera el ancho del panel ({W}).")
                continue
            break

    # H
    while True:
        h = _parse_coord(input(f"  H alto (0=hasta borde): ").strip(), "H", 1, H - y + 1, allow_zero=True)
        if h is not None:
            if h > 0 and y + h > H + 1:
                print(f"  * Y({y}) + H({h}) = {y+h} supera el alto del panel ({H}).")
                continue
            break

    print(f"  -> [tr{x},{y},{w},{h}]")

    # Texto
    content = ask_content_with_dynamic_fields()
    if not content:
        content = ""

    # Fuente
    print()
    font_num = ask_font(H)
    font_tag = f"[fo{font_num}]"

    # Color
    print()
    cf_tag = ask_color_foreground()

    # Justificacion de linea dentro del rect
    print()
    jl_tag = ask_justification()

    return f"[tr{x},{y},{w},{h}]{font_tag}{cf_tag}{jl_tag}{content}"


def build_message(driver: VMSDriver, device_info: DeviceInfo) -> str | None:
    """Guia al usuario para construir un mensaje MULTI completo."""
    clear_screen()
    print_header(device_info.ip, device_info.device_type)
    print("─── Nuevo mensaje ──────────────────────────────────────\n")

    # Modo de posicionamiento
    print("─── Modo de posicionamiento ────────────────────────────")
    print("  1) Automatico * default")
    print("  2) Por rectangulo [tr]")
    raw_mode = input("  [Enter=automatico]: ").strip()
    rect_mode = raw_mode == "2"
    print()

    # Tiempo de pagina y fondo (comunes a ambos modos)
    pt_tag = ask_page_time()
    print()
    pb_tag = ask_color_background()
    print()

    if rect_mode:
        # ── Modo rectangulo ──────────────────────────────────────
        pages_parts = []
        page_num = 1
        while page_num <= 6:
            print(f"\n═══ Pagina {page_num} ═══════════════════════════════════════════")
            rect_num = 1
            page_rects = []
            while True:
                rect_multi = ask_rect(rect_num, device_info)
                page_rects.append(rect_multi)
                otra = input(f"\n  Agregar otro rectangulo en pagina {page_num}? [s/N]: ").strip().lower()
                if otra != "s":
                    break
                rect_num += 1

            pages_parts.append("".join(page_rects))
            page_num += 1
            if page_num <= 6:
                otra = input(f"\n  Agregar pagina {page_num}? [s/N]: ").strip().lower()
                if otra != "s":
                    break

        if not pages_parts:
            return None

        parts = []
        for i, page in enumerate(pages_parts):
            if i > 0:
                parts.append("[np]")
            if pt_tag:
                parts.append(pt_tag)
            if pb_tag:
                parts.append(pb_tag)
            parts.append(page)

    else:
        # ── Modo automatico ──────────────────────────────────────
        font_num = ask_font(device_info.height_pixels)
        font_name = FONTS[font_num][0]
        font_height = FONTS[font_num][1]
        lines_fit = device_info.height_pixels // font_height
        font_tag = f"[fo{font_num}]"
        print(f"\n  * Fuente {font_num} ({font_name}, {font_height}px) — hasta {lines_fit} lineas\n")

        jl_tag = ask_justification()
        print()
        jp_tag = ask_page_justification()
        print()
        cf_tag = ask_color_foreground()
        print()

        # Contenido por paginas
        pages = []
        print("─── Contenido ──────────────────────────────────────────")
        page_num = 1
        while page_num <= 6:
            content = ask_content_with_dynamic_fields()
            if not content:
                if page_num == 1:
                    print("  * Necesitas al menos una pagina.")
                    continue
                break
            pages.append(content)
            page_num += 1
            if page_num <= 6:
                otra = input(f"\n  Agregar pagina {page_num}? [s/N]: ").strip().lower()
                if otra != "s":
                    break

        if not pages:
            return None

        parts = []
        for i, page in enumerate(pages):
            if i > 0:
                parts.append("[np]")
            if pt_tag:
                parts.append(pt_tag)
            if pb_tag:
                parts.append(pb_tag)
            parts.append(jp_tag)
            parts.append(font_tag)
            if cf_tag:
                parts.append(cf_tag)
            parts.append(jl_tag)
            parts.append(page)

    multi = "".join(parts)

    # Validar
    validator = MultiValidator(
        width=device_info.width_pixels,
        height=device_info.height_pixels,
    )
    result = validator.validate(multi)
    if not result:
        print(f"\n  * MULTI invalido: {result}")
        input("  [Enter para volver]")
        return None

    print(f"\n  MULTI generado:\n  {multi}\n")
    confirm = input("  Enviar? [S/n]: ").strip().lower()
    if confirm == "n":
        return None

    return multi


def show_messages(driver: VMSDriver):
    """Muestra todos los mensajes en la tabla."""
    print()
    print("─── Mensajes en tabla (memory_type=3, changeable) ──────")
    try:
        msgs = driver.get_messages()
        if not msgs:
            print("  (tabla vacia)")
        else:
            print(f"  {'Slot':<6} {'Status':<10} {'CRC':<8} MULTI")
            print(f"  {'────':<6} {'──────':<10} {'───':<8} ─────")
            for m in msgs:
                status_name = m.status.name if m.status else "?"
                crc_str = str(m.crc) if m.crc else "-"
                print(f"  {m.slot:<6} {status_name:<10} {crc_str:<8} {m.multi_string}")
    except Exception as e:
        print(f"  * Error: {e}")
    print()
    input("  [Enter para volver]")


def delete_message_menu(driver: VMSDriver):
    """Borra un mensaje de la tabla por slot."""
    print()

    # Mostrar mensajes existentes primero
    try:
        msgs = driver.get_messages()
        if not msgs:
            print("  No hay mensajes en la tabla.")
            input("  [Enter para volver]")
            return
        print("  Mensajes disponibles:")
        for m in msgs:
            print(f"    Slot {m.slot}: {m.multi_string[:50]}")
    except Exception as e:
        print(f"  * Error leyendo mensajes: {e}")

    print()
    raw = input("  Slot a borrar [Enter=cancelar]: ").strip()
    if not raw:
        return

    try:
        slot = int(raw)
        result = driver.delete_message(slot)
        if result:
            print(f"  Slot {slot} borrado")
        else:
            print(f"  * No se pudo borrar el slot {slot}")
    except ValueError:
        print("  * Ingresa un numero de slot.")

    input("  [Enter para continuar]")


def main_menu(driver: VMSDriver, device_info: DeviceInfo):
    while True:
        clear_screen()
        print_header(device_info.ip, device_info.device_type)

        # Estado actual
        try:
            status = driver.get_status()
            current = driver.get_current_message()
            online_str = "Online" if status.online else "Offline"
            errors_str = f"Errores: {status.active_errors()}" if status.has_errors else "Sin errores"
            msg_str = current if current else "(vacio)"
            tags_str = " ".join(f"[{t}]" for t in sorted(driver._supported_tags))
            print(f"  Estado:  {online_str} | {errors_str}")
            print(f"  Mensaje: {msg_str}")
            print(f"  Tags:    {tags_str}")
        except Exception as e:
            print(f"  * Error leyendo estado: {e}")

        print()
        print("─── Opciones ───────────────────────────────────────────")
        print("  1) Enviar mensaje (asistido)")
        print("  2) Enviar MULTI directo (avanzado)")
        print("  3) Limpiar panel")
        print("  4) Ver estado completo")
        print("  5) Ver mensajes en tabla")
        print("  6) Borrar mensaje de tabla")
        print("  0) Salir")
        print()

        opcion = input("  Opcion: ").strip()

        if opcion == "1":
            multi = build_message(driver, device_info)
            if multi:
                try:
                    result = driver.send_message(multi)
                    print(f"\n  Enviado — Slot: {result.slot} | CRC: {result.crc}")
                except Exception as e:
                    print(f"\n  * Error: {e}")
                input("\n  [Enter para continuar]")

        elif opcion == "2":
            print()
            print(f"  Tags disponibles: {' '.join(f'[{t}]' for t in sorted(driver._supported_tags))}")
            multi = input("  MULTI string: ").strip()
            if multi:
                vr = driver._validator.validate(multi)
                if not vr:
                    print(f"  * MULTI invalido: {vr}")
                else:
                    try:
                        result = driver.send_message(multi)
                        print(f"  Enviado — Slot: {result.slot} | CRC: {result.crc}")
                    except Exception as e:
                        print(f"  * Error: {e}")
                input("\n  [Enter para continuar]")

        elif opcion == "3":
            driver.clear_message()
            print("\n  Panel limpio")
            input("  [Enter para continuar]")

        elif opcion == "4":
            print()
            try:
                status = driver.get_status()
                print(f"  Online:          {status.online}")
                print(f"  Control mode:    {status.control_mode}")
                print(f"  Errores activos: {status.active_errors()}")
                print(f"  Puerta abierta:  {status.door_open}")
                print(f"  Watchdog:        {status.watchdog_failures}")
                print(f"  Ultimo polling:  {status.last_polled}")
                print(f"  Mensaje activo:  {driver.get_current_message()}")
            except Exception as e:
                print(f"  * Error: {e}")
            input("\n  [Enter para continuar]")

        elif opcion == "5":
            show_messages(driver)

        elif opcion == "6":
            delete_message_menu(driver)

        elif opcion == "0":
            print("\n  Hasta luego.\n")
            break


if __name__ == "__main__":
    device_info = DeviceInfo(
        ip=os.getenv("VMS_PANEL_IP", "66.17.99.157"),
        port=int(os.getenv("VMS_PANEL_PORT", "161")),
        community_read=os.getenv("VMS_COMMUNITY_READ", "public"),
        community_write=os.getenv("VMS_COMMUNITY_WRITE", "administrator"),
        device_type=os.getenv("VMS_DEVICE_TYPE", "daktronics_vfc"),
    )
    driver = create_driver(device_info)
    device_info.width_pixels  = driver._validator.width
    device_info.height_pixels = driver._validator.height
    main_menu(driver, device_info)
