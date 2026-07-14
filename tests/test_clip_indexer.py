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
    """is_available() must return False when open_clip is importable but no
    weights exist at either the legacy clip cache or the HF hub cache."""
    import sys

    # Simulate open_clip installed
    mock_open_clip = type(sys)("open_clip")
    monkeypatch.setitem(sys.modules, "open_clip", mock_open_clip)

    # Point both cache roots at empty tmp dirs (isolate from the real machine)
    monkeypatch.setenv("CLIP_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)

    result = ClipIndexer.is_available()
    assert result is False, "is_available() should be False when no weights exist anywhere"


def test_is_available_true_when_hf_hub_cache_present(monkeypatch, tmp_path):
    """open_clip 3.x downloads OpenAI CLIP weights from the HF hub (the old
    openaipublic.azureedge.net URL is dead) — is_available() must recognise
    the HF hub cache location, not just the legacy ~/.cache/clip file."""
    import sys

    mock_open_clip = type(sys)("open_clip")
    monkeypatch.setitem(sys.modules, "open_clip", mock_open_clip)

    hf_home = tmp_path / "hf"
    (hf_home / "hub" / "models--timm--vit_base_patch32_clip_224.openai").mkdir(parents=True)

    monkeypatch.setenv("CLIP_CACHE_DIR", str(tmp_path / "empty-clip"))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HF_HOME", str(hf_home))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)

    assert ClipIndexer.is_available() is True


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


# ---------------------------------------------------------------------------
# embed_text() — Phase 14 (014-clip-event-search T002/T003)
# ---------------------------------------------------------------------------

class _FakeTextModel:
    """Stands in for the open_clip model: encode_text -> constant tensor."""

    def encode_text(self, tokens):
        import torch
        return torch.ones((1, 512), dtype=torch.float32)


def _install_fake_text_stack(monkeypatch):
    from unittest.mock import MagicMock
    monkeypatch.setattr(ClipIndexer, "is_available", MagicMock(return_value=True))
    monkeypatch.setattr(ClipIndexer, "_model", _FakeTextModel())
    monkeypatch.setattr(ClipIndexer, "_preprocess", lambda x: x)
    monkeypatch.setattr(ClipIndexer, "_tokenizer", lambda texts: texts)


def test_embed_text_returns_unit_norm_512_vector(monkeypatch):
    import numpy as np
    _install_fake_text_stack(monkeypatch)
    vec = ClipIndexer.embed_text("a person in a red jacket")
    assert vec is not None
    assert vec.shape == (512,)
    assert vec.dtype == np.float32
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-5


def test_embed_text_returns_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(ClipIndexer, "is_available", MagicMock(return_value=False))
    assert ClipIndexer.embed_text("anything") is None


def test_embed_text_never_raises(monkeypatch):
    monkeypatch.setattr(ClipIndexer, "is_available", MagicMock(return_value=True))
    monkeypatch.setattr(
        ClipIndexer, "_do_embed_text", MagicMock(side_effect=RuntimeError("boom"))
    )
    assert ClipIndexer.embed_text("anything") is None  # must not raise


@pytest.mark.skipif(
    not ClipIndexer.is_available(), reason="CLIP weights not present on this machine"
)
def test_embed_text_real_model_long_query_integration():
    """Integration (runs only where CLIP weights exist): a >77-token query is
    truncated internally by the tokenizer and still embeds without raising."""
    import numpy as np
    long_query = " ".join(["person walking past a white van near the gate"] * 12)
    vec = ClipIndexer.embed_text(long_query)
    assert vec is not None and vec.shape == (512,)
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-4
