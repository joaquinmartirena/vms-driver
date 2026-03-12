"""
Utilidades para dividir bitmaps NTCIP en bloques SNMP.
"""

import math


def split_into_blocks(bitmap: bytes, block_size: int) -> list[bytes]:
    """
    Divide el bitmap en bloques de block_size bytes.
    El último bloque se zero-padea hasta block_size si es más corto.
    """
    blocks = []
    for i in range(0, len(bitmap), block_size):
        chunk = bitmap[i:i + block_size]
        if len(chunk) < block_size:
            chunk = chunk.ljust(block_size, b'\x00')
        blocks.append(chunk)
    return blocks


def calculate_total_blocks(width: int, height: int, color_type: int, block_size: int = 1024) -> int:
    """
    Calcula el número de bloques necesarios para un gráfico.

    color_type 4 (color24bit): 3 bytes/pixel.
    color_type 1 (mono1bit):   ceil(width/8) bytes/fila.
    """
    if color_type == 4:
        total_bytes = width * height * 3
    elif color_type == 1:
        total_bytes = ((width + 7) // 8) * height
    else:
        raise ValueError(f"color_type no soportado: {color_type}")
    return math.ceil(total_bytes / block_size)
