"""
Playground interactivo para enviar mensajes MULTI al Daktronics VFC.

Uso:
    python tools/message_playground.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from driver.daktronics.driver import DaktronicsVFCDriver
from driver.daktronics.multi import MultiBuilder, MultiValidator

IP = "66.17.99.157"

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
    "9": ("ámbar ★ default", "255,180,0"),
}

# Campos dinámicos
DYNAMIC_FIELDS = {
    "1":  ("[f1]",  "hora local 12h          → 02:35 PM"),
    "2":  ("[f2]",  "hora local 24h          → 14:35"),
    "3":  ("[f3]",  "temperatura °C          → 23"),
    "4":  ("[f4]",  "temperatura °F          → 73"),
    "5":  ("[f5]",  "velocidad km/h          → 87"),
    "6":  ("[f6]",  "velocidad mph           → 54"),
    "7":  ("[f7]",  "día de semana           → Jueves"),
    "8":  ("[f8]",  "fecha mm/dd/yy          → 03/05/26"),
    "9":  ("[f9]",  "fecha dd/mm/yy          → 05/03/26"),
    "10": ("[f10]", "año yyyy                → 2026"),
    "11": ("[f11]", "hora 12h sin segundos   → 02:35 PM"),
    "12": ("[f12]", "hora 24h sin segundos   → 14:35"),
}


def clear_screen():
    os.system('clear')


def print_header():
    print("╔══════════════════════════════════════════════════════╗")
    print("║        VMS Message Playground — Daktronics VFC       ║")
    print("║                   66.17.99.157                       ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()


def ask_font() -> int:
    print("─── Fuentes disponibles ───────────────────────────────")
    print(f"  {'Nº':<4} {'Nombre':<24} {'Alto':<6} {'Líneas en panel'}")
    print(f"  {'──':<4} {'──────':<24} {'────':<6} {'───────────────'}")
    for num, (name, height) in FONTS.items():
        lines = 96 // height
        default = " ★" if num == 24 else ""
        print(f"  {num:<4} {name:<24} {height}px    {lines} líneas{default}")
    print()
    while True:
        raw = input("  Fuente [Enter=24]: ").strip()
        if raw == "":
            return 24
        try:
            n = int(raw)
            if n in FONTS:
                return n
            print("  ✗ Elegí entre 1-30.")
        except ValueError:
            print("  ✗ Ingresá un número.")


def ask_justification() -> str:
    print("─── Justificación de línea ─────────────────────────────")
    for k, (tag, label) in JUSTIFICATIONS.items():
        print(f"  {k}) {label}")
    while True:
        raw = input("  [Enter=centro]: ").strip()
        if raw == "":
            return "[jl3]"
        if raw in JUSTIFICATIONS:
            return JUSTIFICATIONS[raw][0]
        print("  ✗ Opción inválida.")


def ask_page_justification() -> str:
    print("─── Posición vertical ──────────────────────────────────")
    for k, (tag, label) in PAGE_JUSTIFICATIONS.items():
        print(f"  {k}) {label}")
    while True:
        raw = input("  [Enter=medio]: ").strip()
        if raw == "":
            return "[jp3]"
        if raw in PAGE_JUSTIFICATIONS:
            return PAGE_JUSTIFICATIONS[raw][0]
        print("  ✗ Opción inválida.")


def ask_page_time() -> str:
    print("─── Tiempo de página ───────────────────────────────────")
    print("  Segundos por página. 0 = no rota (página única).")
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
            print("  ✗ Ingresá un número.")


def ask_color_foreground() -> str:
    print("─── Color de texto ─────────────────────────────────────")
    print("  Colores clásicos:")
    for k, (name, rgb) in CLASSIC_COLORS.items():
        print(f"  {k}) {name:<12} ({rgb})")
    print("  r) RGB personalizado")
    print("  Enter = ámbar (default del panel)")
    print()
    raw = input("  Color: ").strip().lower()
    if raw == "":
        return ""  # usa default del panel (ámbar)
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
    print("─── Color de fondo de página ───────────────────────────")
    print("  Colores clásicos:")
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
    Pide el texto de una página con soporte para insertar campos dinámicos.
    Usá | para nueva línea, y @N para insertar campo dinámico N.
    """
    print()
    print("  Campos dinámicos disponibles (usá @N para insertar):")
    for k, (tag, desc) in DYNAMIC_FIELDS.items():
        print(f"    @{k:<3} {desc}")
    print()
    print("  Separadores: | = nueva línea")
    print("  Ejemplo: TEMP: @3°C | HORA: @2")
    print()

    raw = input("  Texto: ").strip()
    if not raw:
        return ""

    # Reemplazar @N por el tag dinámico correspondiente
    for k, (tag, _) in sorted(DYNAMIC_FIELDS.items(), key=lambda x: -len(x[0])):
        raw = raw.replace(f"@{k}", tag)

    # Reemplazar | por [nl]
    raw = raw.replace("|", "[nl]")

    return raw


def build_message(driver: DaktronicsVFCDriver) -> str | None:
    """Guía al usuario para construir un mensaje MULTI completo."""
    clear_screen()
    print_header()
    print("─── Nuevo mensaje ──────────────────────────────────────\n")

    font_num = ask_font()
    font_name = FONTS[font_num][0]
    font_height = FONTS[font_num][1]
    lines_fit = 96 // font_height
    font_tag = f"[fo{font_num}]"
    print(f"\n  ✓ Fuente {font_num} ({font_name}, {font_height}px) — hasta {lines_fit} líneas\n")

    jl_tag = ask_justification()
    print()
    jp_tag = ask_page_justification()
    print()
    pt_tag = ask_page_time()
    print()
    cf_tag = ask_color_foreground()
    print()
    pb_tag = ask_color_background()
    print()

    # Contenido por páginas
    pages = []
    print("─── Contenido ──────────────────────────────────────────")
    page_num = 1
    while page_num <= 6:
        content = ask_content_with_dynamic_fields()
        if not content:
            if page_num == 1:
                print("  ✗ Necesitás al menos una página.")
                continue
            break
        pages.append(content)
        page_num += 1
        if page_num <= 6:
            otra = input(f"\n  ¿Agregar página {page_num}? [s/N]: ").strip().lower()
            if otra != "s":
                break

    if not pages:
        return None

    # Construir MULTI string
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
    validator = MultiValidator()
    result = validator.validate(multi)
    if not result:
        print(f"\n  ✗ MULTI inválido: {result}")
        input("  [Enter para volver]")
        return None

    print(f"\n  MULTI generado:\n  {multi}\n")
    confirm = input("  ¿Enviar? [S/n]: ").strip().lower()
    if confirm == "n":
        return None

    return multi


def show_messages(driver: DaktronicsVFCDriver):
    """Muestra todos los mensajes en la tabla."""
    print()
    print("─── Mensajes en tabla (memory_type=3, changeable) ──────")
    try:
        msgs = driver.get_messages()
        if not msgs:
            print("  (tabla vacía)")
        else:
            print(f"  {'Slot':<6} {'Status':<10} {'CRC':<8} MULTI")
            print(f"  {'────':<6} {'──────':<10} {'───':<8} ─────")
            for m in msgs:
                status_name = m.status.name if m.status else "?"
                crc_str = str(m.crc) if m.crc else "-"
                print(f"  {m.slot:<6} {status_name:<10} {crc_str:<8} {m.multi_string}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
    print()
    input("  [Enter para volver]")


def delete_message_menu(driver: DaktronicsVFCDriver):
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
        print(f"  ✗ Error leyendo mensajes: {e}")

    print()
    raw = input("  Slot a borrar [Enter=cancelar]: ").strip()
    if not raw:
        return

    try:
        slot = int(raw)
        result = driver.delete_message(slot)
        if result:
            print(f"  ✓ Slot {slot} borrado")
        else:
            print(f"  ✗ No se pudo borrar el slot {slot}")
    except ValueError:
        print("  ✗ Ingresá un número de slot.")

    input("  [Enter para continuar]")


def main_menu(driver: DaktronicsVFCDriver):
    while True:
        clear_screen()
        print_header()

        # Estado actual
        try:
            status = driver.get_status()
            current = driver.get_current_message()
            online_str = "✓ Online" if status.online else "✗ Offline"
            errors_str = f"Errores: {status.active_errors()}" if status.has_errors else "Sin errores"
            msg_str = current if current else "(vacío)"
            print(f"  Estado:  {online_str} | {errors_str}")
            print(f"  Mensaje: {msg_str}")
        except Exception as e:
            print(f"  ✗ Error leyendo estado: {e}")

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

        opcion = input("  Opción: ").strip()

        if opcion == "1":
            multi = build_message(driver)
            if multi:
                try:
                    result = driver.send_message(multi)
                    print(f"\n  ✓ Enviado — Slot: {result.slot} | CRC: {result.crc}")
                except Exception as e:
                    print(f"\n  ✗ Error: {e}")
                input("\n  [Enter para continuar]")

        elif opcion == "2":
            print()
            multi = input("  MULTI string: ").strip()
            if multi:
                validator = MultiValidator()
                vr = validator.validate(multi)
                if not vr:
                    print(f"  ✗ MULTI inválido: {vr}")
                else:
                    try:
                        result = driver.send_message(multi)
                        print(f"  ✓ Enviado — Slot: {result.slot} | CRC: {result.crc}")
                    except Exception as e:
                        print(f"  ✗ Error: {e}")
                input("\n  [Enter para continuar]")

        elif opcion == "3":
            driver.clear_message()
            print("\n  ✓ Panel limpio")
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
                print(f"  Último polling:  {status.last_polled}")
                print(f"  Mensaje activo:  {driver.get_current_message()}")
            except Exception as e:
                print(f"  ✗ Error: {e}")
            input("\n  [Enter para continuar]")

        elif opcion == "5":
            show_messages(driver)

        elif opcion == "6":
            delete_message_menu(driver)

        elif opcion == "0":
            print("\n  Hasta luego.\n")
            break


if __name__ == "__main__":
    driver = DaktronicsVFCDriver(ip=IP)
    main_menu(driver)