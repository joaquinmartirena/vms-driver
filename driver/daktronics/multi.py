"""
Builder y validator de MULTI strings para Daktronics VFC.

MULTI es el lenguaje de markup de NTCIP 1203 para mensajes en paneles DMS.
Referencia: NTCIP 1203 v03, sección 6.

Valores confirmados contra dispositivo real (IP 66.17.99.157):
    - dmsMaxMultiStringLength  = 1500
    - dmsMaxNumberPages        = 6
    - defaultFont              = 24
    - defaultPageOnTime        = 30 (3.0 s)
    - defaultPageOffTime       = 0
    - defaultJustificationLine = 3 (center)
    - defaultJustificationPage = 3 (middle)
    - dmsSupportedMultiTags    = FF FF FF 3F (bits 0-29 activos)

Tags soportados confirmados por dmsSupportedMultiTags = FF FF FF 3F:
    Bit  0: [cb]  color background
    Bit  1: [cf]  color foreground
    Bit  2: [fl]  flashing
    Bit  3: [fo]  font
    Bit  4: [g]   graphic
    Bit  5: [hc]  hexadecimal character
    Bit  6: [jl]  justification line
    Bit  7: [jp]  justification page
    Bit  8: [ms]  manufacturer specific
    Bit  9: [mv]  moving text
    Bit 10: [nl]  new line
    Bit 11: [np]  new page
    Bit 12: [pt]  page time
    Bit 13: [sc]  spacing character
    Bit 14: [f1]  field local time 12 hour
    Bit 15: [f2]  field local time 24 hour
    Bit 16: [f3]  ambient temperature Celsius
    Bit 17: [f4]  ambient temperature Fahrenheit
    Bit 18: [f5]  speed km/h
    Bit 19: [f6]  speed mph
    Bit 20: [f7]  day of week
    Bit 21: [f8]  date mm/dd/yy
    Bit 22: [f9]  date dd/mm/yy
    Bit 23: [f10] year yyyy
    Bit 24: [f11] local time 12 hour (no seconds)
    Bit 25: [f12] local time 24 hour (no seconds)
    Bit 26: [tr]  text rectangle
    Bit 27: [cr]  color rectangle
    Bit 28: [pb]  page background
    Bit 29: [sl]  spacing line
    Bits 30-31: NO soportados
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ─── Constantes confirmadas del dispositivo real ──────────────────────────────

MAX_MULTI_STRING_LENGTH = 1500   # dmsMaxMultiStringLength confirmado
MAX_NUMBER_PAGES        = 6      # dmsMaxNumberPages confirmado
DEFAULT_FONT            = 24     # defaultFont confirmado
MAX_FONT_NUMBER         = 255    # rango NTCIP 1203


# ─── Tags soportados — confirmados por dmsSupportedMultiTags = FF FF FF 3F ────

_TAG_PATTERNS: dict[str, str] = {
    # Bit 0 — color background: [cbx] o [cbr,g,b]
    "color_background_classic": r"\[cb\d\]",
    "color_background_rgb":     r"\[cb\d{1,3},\d{1,3},\d{1,3}\]",

    # Bit 1 — color foreground: [cfx] o [cfr,g,b]
    "color_foreground_classic": r"\[cf\d\]",
    "color_foreground_rgb":     r"\[cf\d{1,3},\d{1,3},\d{1,3}\]",

    # Bit 2 — flashing: [fl] / [fltXoY] / [floYtX] / [/fl]
    "flash_default":            r"\[fl\]",
    "flash_ton_toff":           r"\[flt\d+o\d+\]",
    "flash_toff_ton":           r"\[flo\d+t\d+\]",
    "flash_end":                r"\[/fl\]",

    # Bit 3 — font: [foN] o [foN,XXXX]
    "font":                     r"\[fo\d{1,3}\]",
    "font_versioned":           r"\[fo\d{1,3},[0-9A-Fa-f]{4}\]",

    # Bit 4 — graphic: [gN] o [gN,x,y] o [gN,x,y,XXXX]
    "graphic":                  r"\[g\d{1,3}\]",
    "graphic_xy":               r"\[g\d{1,3},\d+,\d+\]",
    "graphic_xy_ver":           r"\[g\d{1,3},\d+,\d+,[0-9A-Fa-f]{4}\]",

    # Bit 5 — hexadecimal character: [hcXX]
    "hex_char":                 r"\[hc[0-9A-Fa-f]{2}\]",

    # Bit 6 — justification line: [jlN] N=2(left),3(center),4(right),5(full)
    "justification_line":       r"\[jl[2-5]\]",

    # Bit 7 — justification page: [jpN] N=2(top),3(middle),4(bottom)
    "justification_page":       r"\[jp[2-4]\]",

    # Bit 8 — manufacturer specific: [msX,Y]
    "manufacturer_specific":    r"\[ms\d+,\d+\]",

    # Bit 9 — moving text: [mvtdw,s,r,text]
    "moving_text":              r"\[mv[lrciu]\d+,\d+,\d+,[^\]]*\]",

    # Bit 10 — new line: [nl] o [nlN]
    "new_line":                 r"\[nl\d*\]",

    # Bit 11 — new page: [np]
    "new_page":                 r"\[np\]",

    # Bit 12 — page time: [ptXoY]
    "page_time":                r"\[pt\d+o\d*\]",

    # Bit 13 — spacing character: [scN]
    "char_spacing":             r"\[sc\d+\]",

    # Bits 14-25 — campos dinámicos: [fN] donde N = 1..12
    "field":                    r"\[f(?:1[0-2]|[1-9])\]",

    # Bit 26 — text rectangle: [trX,Y,W,H]
    "text_rect":                r"\[tr\d+,\d+,\d+,\d+\]",

    # Bit 27 — color rectangle: [crX,Y,W,H,R,G,B]
    "color_rect":               r"\[cr\d+,\d+,\d+,\d+,\d{1,3},\d{1,3},\d{1,3}\]",

    # Bit 28 — page background: [pbR,G,B] o [pbX]
    "page_background_rgb":      r"\[pb\d{1,3},\d{1,3},\d{1,3}\]",
    "page_background_classic":  r"\[pb\d\]",

    # Bit 29 — spacing line: [slN]
    "line_spacing":             r"\[sl\d+\]",
}

_VALID_TAG_RE = re.compile(
    "(" + "|".join(_TAG_PATTERNS.values()) + ")",
    re.IGNORECASE
)

_ANY_TAG_RE = re.compile(r"\[[^\]]*\]")


# ═══════════════════════════════════════════════════════════════════════════════
# Resultado de validación
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """Resultado de validar un MULTI string."""
    valid: bool
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid

    def __str__(self) -> str:
        if self.valid:
            return "OK"
        return "; ".join(self.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# Validador
# ═══════════════════════════════════════════════════════════════════════════════

class MultiValidator:
    """
    Valida MULTI strings antes de enviarlos al panel.

    No hace llamadas SNMP — trabaja solo con el string.
    Validaciones que requieren SNMP (fuente existe, gráfico existe)
    se realizan en el driver antes de llamar send_message().
    """

    def validate(self, multi: str) -> ValidationResult:
        """
        Valida un MULTI string completo.

        Chequeos:
            1. No vacío
            2. Longitud dentro del límite (1500 bytes)
            3. No supera máximo de páginas (6)
            4. Solo tags confirmados por dmsSupportedMultiTags = FF FF FF 3F
            5. Números de fuente en rango 1-255
            6. Números de gráfico en rango 1-255
        """
        errors = []

        if not multi or not multi.strip():
            return ValidationResult(valid=False, errors=["MULTI string vacío"])

        if len(multi) > MAX_MULTI_STRING_LENGTH:
            errors.append(
                f"MULTI string demasiado largo: {len(multi)} bytes "
                f"(máximo {MAX_MULTI_STRING_LENGTH})"
            )

        page_count = len(re.split(r"\[np\]", multi, flags=re.IGNORECASE))
        if page_count > MAX_NUMBER_PAGES:
            errors.append(
                f"Demasiadas páginas: {page_count} (máximo {MAX_NUMBER_PAGES})"
            )

        for tag in _ANY_TAG_RE.findall(multi):
            if not _VALID_TAG_RE.fullmatch(tag):
                errors.append(f"Tag MULTI no soportado o mal formado: '{tag}'")

        for match in re.finditer(r"\[fo(\d{1,3})(?:,[0-9A-Fa-f]{4})?\]", multi, re.IGNORECASE):
            n = int(match.group(1))
            if n < 1 or n > MAX_FONT_NUMBER:
                errors.append(f"Número de fuente inválido: {n} (rango 1-255)")

        for match in re.finditer(r"\[g(\d{1,3})(?:,\d+,\d+(?:,[0-9A-Fa-f]{4})?)?\]", multi, re.IGNORECASE):
            n = int(match.group(1))
            if n < 1 or n > 255:
                errors.append(f"Número de gráfico inválido: {n} (rango 1-255)")

        return ValidationResult(valid=len(errors) == 0, errors=errors)


# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════

class MultiBuilder:
    """
    Construye MULTI strings de forma segura para el Daktronics VFC.

    Defaults del dispositivo real:
    - Fuente 24, justificación centrada, tiempo de página 3.0 s

    Ejemplo:
        msg = MultiBuilder().center().text("DESVIO").new_page().center().text("RUTA 9").build()
        # "[jl3]DESVIO[np][jl3]RUTA 9"
    """

    def __init__(self):
        self._parts: list[str] = []
        self._validator = MultiValidator()

    def text(self, content: str) -> "MultiBuilder":
        self._parts.append(content)
        return self

    def center(self) -> "MultiBuilder":
        """[jl3] — default del VFC."""
        self._parts.append("[jl3]")
        return self

    def left(self) -> "MultiBuilder":
        self._parts.append("[jl2]")
        return self

    def right(self) -> "MultiBuilder":
        self._parts.append("[jl4]")
        return self

    def page_top(self) -> "MultiBuilder":
        self._parts.append("[jp2]")
        return self

    def page_middle(self) -> "MultiBuilder":
        """[jp3] — default del VFC."""
        self._parts.append("[jp3]")
        return self

    def page_bottom(self) -> "MultiBuilder":
        self._parts.append("[jp4]")
        return self

    def new_page(self) -> "MultiBuilder":
        self._parts.append("[np]")
        return self

    def new_line(self) -> "MultiBuilder":
        self._parts.append("[nl]")
        return self

    def font(self, number: int) -> "MultiBuilder":
        if number < 1 or number > MAX_FONT_NUMBER:
            raise ValueError(f"Número de fuente inválido: {number} (rango 1-255)")
        self._parts.append(f"[fo{number}]")
        return self

    def graphic(self, number: int, x: Optional[int] = None, y: Optional[int] = None) -> "MultiBuilder":
        if number < 1 or number > 255:
            raise ValueError(f"Número de gráfico inválido: {number} (rango 1-255)")
        if x is not None and y is not None:
            self._parts.append(f"[g{number},{x},{y}]")
        else:
            self._parts.append(f"[g{number}]")
        return self

    def page_time(self, on_tenths: int, off_tenths: int = 0) -> "MultiBuilder":
        """on_tenths=30 → 3.0 s (default del VFC)."""
        self._parts.append(f"[pt{on_tenths}o{off_tenths}]")
        return self

    def color_foreground(self, r: int, g: int, b: int) -> "MultiBuilder":
        self._parts.append(f"[cf{r},{g},{b}]")
        return self

    def color_background(self, r: int, g: int, b: int) -> "MultiBuilder":
        self._parts.append(f"[cb{r},{g},{b}]")
        return self

    def build(self) -> str:
        """Construye y valida. Lanza ValueError si es inválido."""
        result = "".join(self._parts)
        validation = self._validator.validate(result)
        if not validation:
            raise ValueError(f"MULTI string inválido: {validation}")
        return result

    def build_unsafe(self) -> str:
        """Construye sin validar — solo para tests."""
        return "".join(self._parts)