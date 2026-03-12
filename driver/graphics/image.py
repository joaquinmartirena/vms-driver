"""
Carga y conversión de imágenes para paneles VMS NTCIP 1203.
"""

from PIL import Image


def load_image(path: str) -> Image.Image:
    """Abre una imagen y la convierte a RGB."""
    return Image.open(path).convert("RGB")


def resize_to_sign(img: Image.Image, width: int, height: int, crop: str = "left") -> Image.Image:
    """
    Escala la imagen preservando aspect ratio (fill) y recorta al tamaño exacto.

    crop: "left" | "center" | "right" — lado desde el que se recorta horizontalmente.
    El recorte vertical siempre es centrado.
    """
    src_w, src_h = img.size
    scale = max(width / src_w, height / src_h)
    new_w = round(src_w * scale)
    new_h = round(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    if crop == "left":
        left = 0
    elif crop == "right":
        left = new_w - width
    else:  # center
        left = (new_w - width) // 2

    top = (new_h - height) // 2
    return img.crop((left, top, left + width, top + height))


def to_ntcip_bitmap(img: Image.Image, color_type: int = 4) -> bytes:
    """
    Convierte una imagen RGB a bitmap NTCIP 1203.

    color_type 4 (color24bit): cada pixel RGB → BGR, fila a fila.
    color_type 1 (mono1bit):   1 bit/pixel MSB-first, filas padded a byte boundary.
    """
    if color_type == 4:
        buf = bytearray()
        for r, g, b in img.getdata():
            buf += bytes([b, g, r])
        return bytes(buf)

    elif color_type == 1:
        w, h = img.size
        row_bytes = (w + 7) // 8
        buf = bytearray(row_bytes * h)
        pixels = list(img.getdata())
        for y in range(h):
            for x in range(w):
                r, g, b = pixels[y * w + x]
                if (r + g + b) > 382:  # luminancia simple: > 50% blanco
                    buf[y * row_bytes + x // 8] |= (0x80 >> (x % 8))
        return bytes(buf)

    else:
        raise ValueError(f"color_type no soportado: {color_type}")
