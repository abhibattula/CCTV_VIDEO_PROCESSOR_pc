"""
Tests for frame_analyzer.py — Phase 11 fixes.
TDD: written before implementation; tests verify sanitiser, AI gate, squaring removal, warning suppression.

All tests run without GPU, real video, or display server.
"""
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_clean_caption():
    import app.core.frame_analyzer as fa
    return fa._clean_caption


# ---------------------------------------------------------------------------
# Caption sanitiser
# ---------------------------------------------------------------------------

def test_clean_caption_strips_special_tokens():
    _clean_caption = _get_clean_caption()
    raw = "</s>A person walks<loc_123> down the street<s>."
    result = _clean_caption(raw)
    assert "</s>" not in result
    assert "<s>" not in result
    assert "<loc_123>" not in result
    assert "A person walks" in result
    assert "down the street" in result


def test_clean_caption_handles_empty():
    _clean_caption = _get_clean_caption()
    assert _clean_caption("") == ""


def test_clean_caption_handles_none_input():
    _clean_caption = _get_clean_caption()
    result = _clean_caption(None)  # type: ignore[arg-type]
    assert result == ""


def test_clean_caption_preserves_clean_text():
    _clean_caption = _get_clean_caption()
    clean = "A dog runs across the car park."
    assert _clean_caption(clean) == clean


# ---------------------------------------------------------------------------
# AI_FEATURES_ENABLED gate
# ---------------------------------------------------------------------------

def test_is_available_false_when_ai_features_disabled(monkeypatch):
    """When AI_FEATURES_ENABLED=False, is_available() returns False immediately."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "AI_FEATURES_ENABLED", False)

    from app.core.frame_analyzer import FrameAnalyzer
    FrameAnalyzer._availability_cache = None

    result = FrameAnalyzer.is_available()
    assert result is False
    assert FrameAnalyzer._availability_cache is False


# ---------------------------------------------------------------------------
# Squaring removed
# ---------------------------------------------------------------------------

def test_squaring_removed(monkeypatch, tmp_path):
    """_run_analysis must NOT pad a 1920x1080 image to a square before processor call."""
    from PIL import Image as PILImage

    test_img_path = tmp_path / "frame.jpg"
    img = PILImage.new("RGB", (1920, 1080), color=(128, 64, 32))
    img.save(str(test_img_path))

    received_sizes: list = []

    def capture_size(text, images, **kwargs):
        received_sizes.append(images.size)
        result = MagicMock()
        result.to.return_value = result
        return result

    mock_proc = MagicMock()
    mock_proc.side_effect = capture_size
    mock_proc.batch_decode = MagicMock(return_value=["<MORE_DETAILED_CAPTION>A scene</MORE_DETAILED_CAPTION>"])
    mock_proc.post_process_generation = MagicMock(return_value={"<MORE_DETAILED_CAPTION>": "A scene"})
    mock_model = MagicMock()
    mock_model.generate.return_value = MagicMock()

    import app.core.frame_analyzer as fa

    def immediate_run(fn, timeout):
        try:
            return fn(), None
        except Exception as exc:
            return None, exc

    monkeypatch.setattr(fa, "_run_in_daemon", immediate_run)
    monkeypatch.setattr(fa.FrameAnalyzer, "_get_clip_embedding", lambda cls, p: None)
    fa.FrameAnalyzer._model = mock_model
    fa.FrameAnalyzer._processor = mock_proc

    try:
        fa.FrameAnalyzer._run_analysis(test_img_path)
    except Exception:
        pass
    finally:
        fa.FrameAnalyzer._model = None
        fa.FrameAnalyzer._processor = None
        fa.FrameAnalyzer._availability_cache = None

    if received_sizes:
        w, h = received_sizes[0]
        assert not (w == h and w == 1920), (
            f"Image was padded to square {w}x{h} — squaring code was not removed"
        )


# ---------------------------------------------------------------------------
# Warning suppression
# ---------------------------------------------------------------------------

def test_no_warnings_during_inference(monkeypatch, tmp_path):
    """UserWarning and DeprecationWarning must be suppressed inside _run_task().

    Uses a mock processor that emits warnings from inside the processor call —
    i.e., inside _run_task()'s catch_warnings block. Uses immediate_run so
    warnings flow through the same thread as the outer recorder.
    """
    from PIL import Image as PILImage

    test_img_path = tmp_path / "frame2.jpg"
    PILImage.new("RGB", (640, 480)).save(str(test_img_path))

    import app.core.frame_analyzer as fa

    # Run synchronously so warning state is visible to the outer catch_warnings
    def immediate_run(fn, timeout):
        try:
            return fn(), None
        except Exception as exc:
            return None, exc

    monkeypatch.setattr(fa, "_run_in_daemon", immediate_run)
    monkeypatch.setattr(fa.FrameAnalyzer, "_get_clip_embedding", lambda cls, p: None)

    # Processor that emits warnings — called INSIDE _run_task()'s catch_warnings block
    def proc_with_warnings(text, images, **kwargs):
        warnings.warn("Attention mask not set", UserWarning, stacklevel=1)
        warnings.warn("numpy version mismatch", DeprecationWarning, stacklevel=1)
        result = MagicMock()
        result.to.return_value = result
        return result

    mock_proc = MagicMock()
    mock_proc.side_effect = proc_with_warnings
    mock_proc.batch_decode.return_value = ["<MORE_DETAILED_CAPTION>A scene</MORE_DETAILED_CAPTION>"]
    mock_proc.post_process_generation.return_value = {"<MORE_DETAILED_CAPTION>": "A scene"}
    mock_model = MagicMock()
    mock_model.generate.return_value = MagicMock()

    fa.FrameAnalyzer._model = mock_model
    fa.FrameAnalyzer._processor = mock_proc

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            fa.FrameAnalyzer._run_analysis(test_img_path)
        except Exception:
            pass

    fa.FrameAnalyzer._model = None
    fa.FrameAnalyzer._processor = None
    fa.FrameAnalyzer._availability_cache = None

    user_or_dep = [x for x in w if issubclass(x.category, (UserWarning, DeprecationWarning))]
    assert len(user_or_dep) == 0, (
        f"Inference warnings not suppressed: {[str(x.message) for x in user_or_dep]}"
    )


# ---------------------------------------------------------------------------
# HF_HOME / HUGGINGFACE_HUB_CACHE env var (Phase 12 — FR-016)
# ---------------------------------------------------------------------------

def test_is_available_respects_hf_home(monkeypatch, tmp_path):
    """is_available() must use HF_HOME env var instead of hardcoded ~/.cache/huggingface."""
    import app.core.frame_analyzer as fa
    import app.config as cfg

    # Ensure AI features appear enabled so the RAM gate doesn't short-circuit
    monkeypatch.setattr(cfg, "AI_FEATURES_ENABLED", True)

    # Simulate transformers being importable
    monkeypatch.setattr(fa, "_clean_caption", fa._clean_caption)  # no-op, just ensure module loaded

    # Create a fake weights directory under a custom HF_HOME
    fake_hf_home = tmp_path / "custom_hf_home"
    weights_dir = fake_hf_home / "hub" / "models--microsoft--Florence-2-base"
    weights_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HF_HOME", str(fake_hf_home))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)

    # Patch import of transformers so we don't need it installed
    import sys
    mock_transformers = type(sys)("transformers")
    mock_transformers.AutoModelForCausalLM = object
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    fa.FrameAnalyzer._availability_cache = None
    result = fa.FrameAnalyzer.is_available()
    fa.FrameAnalyzer._availability_cache = None  # reset after test

    assert result is True, (
        f"is_available() returned False despite weights at {weights_dir}; "
        "HF_HOME env var was not respected"
    )


def test_is_available_false_when_weights_absent_in_hf_home(monkeypatch, tmp_path):
    """is_available() returns False when HF_HOME is set but weights dir absent."""
    import app.core.frame_analyzer as fa
    import app.config as cfg

    monkeypatch.setattr(cfg, "AI_FEATURES_ENABLED", True)

    empty_hf_home = tmp_path / "empty_hf_home"
    empty_hf_home.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HF_HOME", str(empty_hf_home))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)

    import sys
    mock_transformers = type(sys)("transformers")
    mock_transformers.AutoModelForCausalLM = object
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    fa.FrameAnalyzer._availability_cache = None
    result = fa.FrameAnalyzer.is_available()
    fa.FrameAnalyzer._availability_cache = None

    assert result is False


def test_is_available_respects_huggingface_hub_cache(monkeypatch, tmp_path):
    """Falls back to HUGGINGFACE_HUB_CACHE when HF_HOME is absent."""
    import app.core.frame_analyzer as fa
    import app.config as cfg

    monkeypatch.setattr(cfg, "AI_FEATURES_ENABLED", True)

    fake_hub_cache = tmp_path / "hub_cache"
    weights_dir = fake_hub_cache / "hub" / "models--microsoft--Florence-2-base"
    weights_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(fake_hub_cache))

    import sys
    mock_transformers = type(sys)("transformers")
    mock_transformers.AutoModelForCausalLM = object
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    fa.FrameAnalyzer._availability_cache = None
    result = fa.FrameAnalyzer.is_available()
    fa.FrameAnalyzer._availability_cache = None

    assert result is True


# ── Phase 15 T015: AI device helper ───────────────────────────────────────────

def test_frame_analyzer_device_follows_ai_device(monkeypatch):
    import app.utils.ai_device as ai_device
    from app.core.frame_analyzer import FrameAnalyzer

    monkeypatch.setattr(ai_device, "get_ai_device", lambda: "sentinel-device")
    assert FrameAnalyzer._device() == "sentinel-device"
