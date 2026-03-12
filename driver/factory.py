"""
Factory de drivers VMS.

Instancia el driver correcto a partir de un DeviceInfo sin exponer
el tipo concreto al caller. El caller siempre recibe VMSDriver.

Para agregar soporte a un fabricante nuevo:
    1. Crear driver/fabricante/__init__.py
    2. Crear driver/fabricante/driver.py  (subclase de VMSDriver)
    3. Agregar una entrada en _REGISTRY con la ruta "modulo.Clase"
"""

from models.device import DeviceInfo
from driver.base import VMSDriver

# Registro de drivers disponibles.
# Los módulos se importan dinámicamente para evitar cargar todas las
# dependencias de todos los fabricantes en cada arranque.
_REGISTRY: dict[str, str] = {
    "daktronics_vfc": "driver.daktronics.driver.DaktronicsVFCDriver",
    "fixalia":        "driver.fixalia.driver.FixaliaDriver",
    "chainzone":      "driver.chainzone.driver.ChainZoneDriver",
}


def create_driver(device_info: DeviceInfo) -> VMSDriver:
    """
    Instancia el driver correcto según device_info.device_type.

    Args:
        device_info: configuración del dispositivo.

    Returns:
        Instancia de VMSDriver lista para usar.

    Raises:
        NotImplementedError: si device_type no tiene un driver registrado.
    """
    driver_path = _REGISTRY.get(device_info.device_type)
    if not driver_path:
        raise NotImplementedError(
            f"No hay driver disponible para: '{device_info.device_type}'. "
            f"Disponibles: {list(_REGISTRY.keys())}"
        )

    module_path, class_name = driver_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    driver_class = getattr(module, class_name)

    return driver_class(ip=device_info.ip, port=device_info.port)


def available_drivers() -> list[str]:
    """Devuelve la lista de device_types registrados."""
    return list(_REGISTRY.keys())
