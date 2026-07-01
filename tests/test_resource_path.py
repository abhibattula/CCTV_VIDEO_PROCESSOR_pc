"""
Tests for app/utils/resource_path.py (Phase 12 — frozen-bundle path resolution).
TDD: written BEFORE implementation; these tests must fail first.
All tests run without PyInstaller or a real frozen bundle.
"""
import sys
from pathlib import Path

import pytest


def test_dev_mode_returns_project_root_path(tmp_path):
    """In dev mode (no sys.frozen), returns path relative to project root."""
    from app.utils.resource_path import get_resource_path

    result = get_resource_path("static")
    # In dev mode the result must point to the actual static/ directory
    assert result.is_dir(), f"Expected static/ to exist at {result}"
    assert result.name == "static"


def test_dev_mode_returns_path_object():
    """Return type is always pathlib.Path."""
    from app.utils.resource_path import get_resource_path

    result = get_resource_path("static")
    assert isinstance(result, Path)


def test_frozen_mode_uses_meipass(tmp_path, monkeypatch):
    """In frozen mode, returns sys._MEIPASS / relative (not project root)."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    # Re-import to pick up the monkeypatched sys attributes
    import importlib
    import app.utils.resource_path as rp_module
    importlib.reload(rp_module)

    result = rp_module.get_resource_path("static")
    assert result == tmp_path / "static"
    assert str(tmp_path) in str(result)


def test_frozen_mode_cleanup(monkeypatch):
    """After test teardown, sys.frozen and sys._MEIPASS must not leak."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/fake/meipass", raising=False)
    # monkeypatch fixture handles cleanup automatically; this test verifies the
    # pattern is sound by checking the attributes are set during the test
    assert getattr(sys, "frozen", False) is True
    assert getattr(sys, "_MEIPASS", None) == "/fake/meipass"
    # After this test, monkeypatch fixture will delete these attrs


def test_frozen_mode_no_leak_after_previous_test():
    """sys.frozen should not be set after the previous test's cleanup."""
    assert not getattr(sys, "frozen", False), "sys.frozen leaked from previous test"


def test_get_resource_path_different_relatives():
    """Different relative paths return distinct results."""
    from app.utils.resource_path import get_resource_path

    p1 = get_resource_path("static")
    p2 = get_resource_path("app/templates")
    assert p1 != p2
    assert p1.name == "static"
    assert p2.name == "templates"
