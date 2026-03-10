"""
Builder y validador de MULTI strings — estándar NTCIP 1203 DMS.

MULTI es el lenguaje de markup definido en NTCIP 1203 para mensajes
en señales de mensaje variable (DMS/VMS). Este módulo es independiente
del fabricante y puede ser reutilizado por cualquier driver que implemente VMSDriver.

Tags reconocidos: todos los definidos en NTCIP 1203 v03, bits 0–29 del objeto
dmsSupportedMultiTags. La restricción a los tags soportados por un dispositivo
específico la aplica el driver al inicializar el validador (leyendo
dmsSupportedMultiTags y las dimensiones del panel vía SNMP).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ─── Límites NTCIP 1203 ───────────────────────────────────────────────────────
# Valores conservadores usados como fallback si el driver no puede consultar
# el panel al arrancar. Los valores reales se leen del dispositivo vía SNMP.

MAX_MULTI_STRING_LENGTH = 1500   # dmsMaxMultiStringLength
MAX_NUMBER_PAGES        = 6      # dmsMaxNumberPages
MAX_FONT_NUMBER         = 255    # rango NTCIP 1203


# ─── Tags NTCIP 1203 v03 — bits 0–29 de dmsSupportedMultiTags ─────────────────

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
    Las dimensiones y límites del panel se pasan en el constructor;
    el driver los obtiene vía SNMP en la inicialización.
    """

    def __init__(
        self,
        width: int = 144,
        height: int = 96,
        max_string_length: int = MAX_MULTI_STRING_LENGTH,
        max_pages: int = MAX_NUMBER_PAGES,
        supported_tags: set[str] | None = None,
    ):
        self.width = width
        self.height = height
        self.max_string_length = max_string_length
        self.max_pages = max_pages
        self._supported_tags: set[str] | None = supported_tags

    def set_supported_tags(self, tags: set[str]) -> None:
        """Actualiza la lista de tags soportados por el panel."""
        self._supported_tags = tags

    def validate(self, multi: str) -> ValidationResult:
        """
        Valida un MULTI string completo.
        Chequeos:
            1. No vacío
            2. Longitud dentro del límite
            3. No supera máximo de páginas
            4. Solo tags definidos en NTCIP 1203 v03 (bits 0–29 de dmsSupportedMultiTags)
            5. Números de fuente en rango 1-255
            6. Números de gráfico en rango 1-255
            7. Coordenadas de [tr] y [cr] dentro de las dimensiones del panel
        """
        errors = []

        if not multi or not multi.strip():
            return ValidationResult(valid=False, errors=["MULTI string vacío"])

        if len(multi) > self.max_string_length:
            errors.append(
                f"MULTI string demasiado largo: {len(multi)} bytes "
                f"(máximo {self.max_string_length})"
            )

        page_count = len(re.split(r"\[np\]", multi, flags=re.IGNORECASE))
        if page_count > self.max_pages:
            errors.append(
                f"Demasiadas páginas: {page_count} (máximo {self.max_pages})"
            )

        for tag in _ANY_TAG_RE.findall(multi):
            if not _VALID_TAG_RE.fullmatch(tag):
                errors.append(f"Tag MULTI no soportado o mal formado: '{tag}'")

        if self._supported_tags is not None:
            used = {re.match(r'\[/?([a-zA-Z]+)', t).group(1).lower()
                    for t in _ANY_TAG_RE.findall(multi)
                    if re.match(r'\[/?([a-zA-Z]+)', t)}
            unsupported = used - self._supported_tags
            if unsupported:
                errors.append(
                    f"Tags no soportados por este panel: {', '.join(f'[{t}]' for t in sorted(unsupported))}"
                )

        for match in re.finditer(r"\[fo(\d{1,3})(?:,[0-9A-Fa-f]{4})?\]", multi, re.IGNORECASE):
            n = int(match.group(1))
            if n < 1 or n > MAX_FONT_NUMBER:
                errors.append(f"Número de fuente inválido: {n} (rango 1-255)")

        for match in re.finditer(r"\[g(\d{1,3})(?:,\d+,\d+(?:,[0-9A-Fa-f]{4})?)?\]", multi, re.IGNORECASE):
            n = int(match.group(1))
            if n < 1 or n > 255:
                errors.append(f"Número de gráfico inválido: {n} (rango 1-255)")

        for match in re.finditer(r"\[tr(\d+),(\d+),(\d+),(\d+)\]", multi, re.IGNORECASE):
            x, y, w, h = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
            if x + w - 1 > self.width:
                errors.append(
                    f"[tr] desborda el ancho del panel: x={x} + w={w} - 1 = {x+w-1} > {self.width}"
                )
            if y + h - 1 > self.height:
                errors.append(
                    f"[tr] desborda el alto del panel: y={y} + h={h} - 1 = {y+h-1} > {self.height}"
                )

        for match in re.finditer(r"\[cr(\d+),(\d+),(\d+),(\d+),\d{1,3},\d{1,3},\d{1,3}\]", multi, re.IGNORECASE):
            x, y, w, h = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
            if x + w - 1 > self.width:
                errors.append(
                    f"[cr] desborda el ancho del panel: x={x} + w={w} - 1 = {x+w-1} > {self.width}"
                )
            if y + h - 1 > self.height:
                errors.append(
                    f"[cr] desborda el alto del panel: y={y} + h={h} - 1 = {y+h-1} > {self.height}"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors)

# ═══════════════════════════════════════════════════════════════════════════════
# Builder
# ═══════════════════════════════════════════════════════════════════════════════

class MultiBuilder:
    """
    Construye MULTI strings de forma segura para cualquier panel NTCIP 1203.

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
        """[jl3]"""
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
        """[jp3]"""
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
        """on_tenths=30 → 3.0 s"""
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

    def text_rect(self, x: int, y: int, w: int, h: int) -> "MultiBuilder":
        """[trX,Y,W,H] — define zona de texto."""
        self._parts.append(f"[tr{x},{y},{w},{h}]")
        return self

    def color_rect(self, x: int, y: int, w: int, h: int, r: int, g: int, b: int) -> "MultiBuilder":
        """[crX,Y,W,H,R,G,B] — rectángulo de color."""
        self._parts.append(f"[cr{x},{y},{w},{h},{r},{g},{b}]")
        return self

    def page_background(self, r: int, g: int, b: int) -> "MultiBuilder":
        """[pbR,G,B] — color de fondo de página."""
        self._parts.append(f"[pb{r},{g},{b}]")
        return self

    def flash(self, on_tenths: int, off_tenths: int) -> "MultiBuilder":
        """[fltXoY] — inicia flash con tiempos en décimas de segundo."""
        self._parts.append(f"[flt{on_tenths}o{off_tenths}]")
        return self

    def flash_end(self) -> "MultiBuilder":
        """[/fl] — termina zona de flash."""
        self._parts.append("[/fl]")
        return self

    def field(self, n: int) -> "MultiBuilder":
        """[fN] — campo dinámico (n = 1..12)."""
        if n < 1 or n > 12:
            raise ValueError(f"Número de campo inválido: {n} (rango 1-12)")
        self._parts.append(f"[f{n}]")
        return self

    def char_spacing(self, n: int) -> "MultiBuilder":
        """[scN] — espaciado entre caracteres."""
        self._parts.append(f"[sc{n}]")
        return self

    def line_spacing(self, n: int) -> "MultiBuilder":
        """[slN] — espaciado entre líneas."""
        self._parts.append(f"[sl{n}]")
        return self
