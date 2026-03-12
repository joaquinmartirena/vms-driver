"""
Conversión de imagen a GraphicPayload listo para enviar al panel.
"""

from dataclasses import dataclass

from driver.graphics.bitmap import split_into_blocks
from driver.graphics.image import load_image, resize_to_sign, to_ntcip_bitmap


@dataclass
class GraphicPayload:
    slot: int
    width: int
    height: int
    color_type: int
    blocks: list[bytes]
    total_bytes: int


def convert_image(
    path: str,
    width: int,
    height: int,
    slot: int,
    block_size: int = 1024,
    color_type: int = 4,
    crop: str = "left",
) -> GraphicPayload:
    """
    Carga una imagen, la escala al tamaño del panel y devuelve un GraphicPayload
    con el bitmap dividido en bloques SNMP.
    """
    img    = load_image(path)
    img    = resize_to_sign(img, width, height, crop)
    bitmap = to_ntcip_bitmap(img, color_type)
    blocks = split_into_blocks(bitmap, block_size)
    return GraphicPayload(
        slot=slot,
        width=img.width,
        height=img.height,
        color_type=color_type,
        blocks=blocks,
        total_bytes=len(bitmap),
    )
