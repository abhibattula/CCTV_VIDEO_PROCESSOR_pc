"""
System metrics utilities — CPU, RAM, optional temperature.
`open_folder` delegates to shell.platform_utils (canonical implementation).
"""
from typing import Optional

import psutil


def get_cpu_percent() -> float:
    return psutil.cpu_percent(interval=None)


def get_ram_percent() -> float:
    return psutil.virtual_memory().percent


def get_cpu_temp() -> Optional[float]:
    """Return CPU temperature in °C, or None on platforms that don't expose it (e.g. Windows)."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        for key in ("coretemp", "cpu_thermal", "k10temp", "acpitz"):
            if key in temps:
                readings = temps[key]
                if readings:
                    return readings[0].current
        return None
    except (AttributeError, NotImplementedError):
        return None


def open_folder(path: str) -> None:
    from shell.platform_utils import open_folder as _open_folder
    _open_folder(path)
