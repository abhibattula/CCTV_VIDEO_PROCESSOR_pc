"""Canonical platform utilities — desktop path resolution for all target OS."""
import os
import platform
from pathlib import Path


def get_desktop_path() -> str:
    """Return a writable directory suitable for saving exported files.

    Resolution order:
      Windows: SHGetFolderPathW → ~/Desktop
      macOS:   ~/Desktop
      Linux:   $XDG_DESKTOP_DIR → ~/Desktop → ~/Downloads → ~/
    """
    system = platform.system()
    if system == "Windows":
        try:
            import ctypes
            import ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(0, 0, 0, 0, buf)
            if buf.value:
                return buf.value
        except Exception:
            pass
        return str(Path.home() / "Desktop")
    elif system == "Darwin":
        return str(Path.home() / "Desktop")
    else:  # Linux, Raspberry Pi
        xdg = os.environ.get("XDG_DESKTOP_DIR", "").strip()
        if xdg and Path(xdg).is_dir():
            return xdg
        desktop = Path.home() / "Desktop"
        if desktop.is_dir():
            return str(desktop)
        downloads = Path.home() / "Downloads"
        return str(downloads if downloads.is_dir() else Path.home())
