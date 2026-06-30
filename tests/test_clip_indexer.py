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
