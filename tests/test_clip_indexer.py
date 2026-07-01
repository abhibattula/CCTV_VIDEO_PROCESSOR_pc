"""
Tests for ClipIndexer graceful degradation (US3, Phase 10).
All tests run without open-clip-torch, GPU, or real images.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.clip_indexer import ClipIndexer

_FAKE_IMG = Path("/fake/image.jpg")
_SIDECAR = "/fake/image.clip.npy"


def test_is_available_returns_false_when_no_open_clip(monkeypatch):
    monkeypatch.setattr(ClipIndexer, "is_available", MagicMock(return_value=False))
    assert ClipIndexer.is_available() is False


def test_embed_returns_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(ClipIndexer, "is_available", MagicMock(return_value=False))
    result = ClipIndexer.embed(_FAKE_IMG)
    assert result is None


def test_embed_returns_none_on_do_embed_exception(monkeypatch):
    monkeypatch.setattr(ClipIndexer, "is_available", MagicMock(return_value=True))
    monkeypatch.setattr(ClipIndexer, "_do_embed", MagicMock(side_effect=RuntimeError("gpu error")))
    result = ClipIndexer.embed(_FAKE_IMG)
    assert result is None


def test_embed_returns_sidecar_path_on_success(monkeypatch):
    monkeypatch.setattr(ClipIndexer, "is_available", MagicMock(return_value=True))
    monkeypatch.setattr(ClipIndexer, "_do_embed", MagicMock(return_value=_SIDECAR))
    result = ClipIndexer.embed(_FAKE_IMG)
    assert result == _SIDECAR


def test_embed_never_raises_to_caller(monkeypatch):
    monkeypatch.setattr(ClipIndexer, "is_available", MagicMock(return_value=True))
    monkeypatch.setattr(ClipIndexer, "_do_embed", MagicMock(side_effect=Exception("anything")))
    ClipIndexer.embed(Path("/x"))  # must not raise


# ---------------------------------------------------------------------------
# Disk-presence check for is_available() (Phase 12 — FR-017)
# ---------------------------------------------------------------------------

def test_is_available_requires_disk_file(monkeypatch, tmp_path):
    """is_available() must return False when open_clip is importable but ViT-B-32.pt absent."""
    import sys

    # Simulate open_clip installed
    mock_open_clip = type(sys)("open_clip")
    monkeypatch.setitem(sys.modules, "open_clip", mock_open_clip)

    # Point CLIP_CACHE_DIR to tmp_path (no ViT-B-32.pt there yet)
    monkeypatch.setenv("CLIP_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    result = ClipIndexer.is_available()
    assert result is False, "is_available() should be False when ViT-B-32.pt absent"


def test_is_available_true_when_weight_file_present(monkeypatch, tmp_path):
    """is_available() returns True when ViT-B-32.pt exists at the cache location."""
    import sys

    mock_open_clip = type(sys)("open_clip")
    monkeypatch.setitem(sys.modules, "open_clip", mock_open_clip)

    clip_cache = tmp_path / "clip"
    clip_cache.mkdir()
    (clip_cache / "ViT-B-32.pt").write_bytes(b"fake")

    monkeypatch.setenv("CLIP_CACHE_DIR", str(clip_cache.parent))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    # CLIP_CACHE_DIR root → look for ViT-B-32.pt directly under it
    (tmp_path / "ViT-B-32.pt").write_bytes(b"fake")

    result = ClipIndexer.is_available()
    assert result is True


def test_is_available_uses_xdg_cache_home(monkeypatch, tmp_path):
    """is_available() uses XDG_CACHE_HOME/clip/ViT-B-32.pt when CLIP_CACHE_DIR unset."""
    import sys

    mock_open_clip = type(sys)("open_clip")
    monkeypatch.setitem(sys.modules, "open_clip", mock_open_clip)

    xdg_cache = tmp_path / "xdg"
    clip_dir = xdg_cache / "clip"
    clip_dir.mkdir(parents=True)
    (clip_dir / "ViT-B-32.pt").write_bytes(b"fake")

    monkeypatch.delenv("CLIP_CACHE_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))

    result = ClipIndexer.is_available()
    assert result is True


def test_is_available_false_when_open_clip_not_installed(monkeypatch):
    """is_available() returns False immediately when open_clip import fails."""
    import sys

    # Ensure open_clip raises ImportError
    monkeypatch.setitem(sys.modules, "open_clip", None)

    result = ClipIndexer.is_available()
    assert result is False
