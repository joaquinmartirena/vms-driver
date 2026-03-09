"""
Shim de compatibilidad — MultiBuilder y MultiValidator se movieron a driver.multi.

MULTI es parte del estándar NTCIP 1203, no de Daktronics.
Importar desde driver.multi directamente.
"""

# noqa: F401
from driver.multi import (
    MultiBuilder,
    MultiValidator,
    ValidationResult,
    MAX_MULTI_STRING_LENGTH,
    MAX_NUMBER_PAGES,
    MAX_FONT_NUMBER,
)

__all__ = [
    "MultiBuilder",
    "MultiValidator",
    "ValidationResult",
    "MAX_MULTI_STRING_LENGTH",
    "MAX_NUMBER_PAGES",
    "MAX_FONT_NUMBER",
]
