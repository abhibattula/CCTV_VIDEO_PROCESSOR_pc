"""Resolve paths to bundled resources in both dev and PyInstaller frozen mode."""
import sys
from pathlib import Path


def get_resource_path(relative: str) -> Path:
    """Return absolute path to a bundled resource.

    In frozen mode (PyInstaller): returns sys._MEIPASS / relative.
    In dev mode: returns project_root / relative (3 levels above this file).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent.parent.parent / relative
