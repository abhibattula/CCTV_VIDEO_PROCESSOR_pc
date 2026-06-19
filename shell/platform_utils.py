"""
Platform-specific utilities for the PyQt6 shell.
Canonical location for OS-specific dispatch (T070's system.py delegates here).
"""
import platform
import subprocess


def get_platform() -> str:
    return platform.system()


def open_folder(path: str) -> None:
    """Open a folder in the OS native file manager."""
    system = get_platform()
    if system == "Windows":
        subprocess.Popen(["explorer", path])
    elif system == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
