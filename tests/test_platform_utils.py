"""
Tests for app/utils/platform.py — get_desktop_path() cross-platform resolution.
All tests run without display server.
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Linux: XDG_DESKTOP_DIR set and directory exists
# ---------------------------------------------------------------------------

def test_get_desktop_path_linux_xdg(tmp_path, monkeypatch):
    """On Linux with XDG_DESKTOP_DIR set to an existing dir, return that dir."""
    xdg_dir = tmp_path / "xdg_desktop"
    xdg_dir.mkdir()

    monkeypatch.setenv("XDG_DESKTOP_DIR", str(xdg_dir))

    with patch("platform.system", return_value="Linux"):
        from importlib import reload
        import app.utils.platform as pu
        result = pu.get_desktop_path()

    assert result == str(xdg_dir)


# ---------------------------------------------------------------------------
# Linux: no XDG, no ~/Desktop, ~/Downloads exists
# ---------------------------------------------------------------------------

def test_get_desktop_path_linux_no_desktop(tmp_path, monkeypatch):
    """On Linux without ~/Desktop, fall through to ~/Downloads when it exists."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    downloads = fake_home / "Downloads"
    downloads.mkdir()
    # Deliberately do NOT create fake_home/Desktop

    monkeypatch.delenv("XDG_DESKTOP_DIR", raising=False)

    with patch("platform.system", return_value="Linux"), \
         patch("pathlib.Path.home", return_value=fake_home):
        from importlib import reload
        import app.utils.platform as pu
        result = pu.get_desktop_path()

    assert result == str(downloads)


# ---------------------------------------------------------------------------
# macOS: returns ~/Desktop
# ---------------------------------------------------------------------------

def test_get_desktop_path_macos():
    """On macOS, always return str(Path.home() / 'Desktop')."""
    with patch("platform.system", return_value="Darwin"):
        from importlib import reload
        import app.utils.platform as pu
        result = pu.get_desktop_path()

    assert result == str(Path.home() / "Desktop")
