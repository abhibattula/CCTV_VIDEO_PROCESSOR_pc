import pytest
from pathlib import Path


def test_import_frame_analyzer():
    """Will fail with ImportError until T003 creates frame_analyzer.py"""
    from app.core.frame_analyzer import FrameAnalyzer  # noqa: F401


def test_is_available_returns_bool():
    """is_available() must return a bool (not raise)"""
    from app.core.frame_analyzer import FrameAnalyzer
    result = FrameAnalyzer.is_available()
    assert isinstance(result, bool)


def test_analyze_absent_returns_empty_dict_shape(monkeypatch):
    """When Florence-2 is absent, analyze() returns exact shape with empty strings/lists"""
    from app.core.frame_analyzer import FrameAnalyzer
    monkeypatch.setattr(FrameAnalyzer, "is_available", staticmethod(lambda: False))
    result = FrameAnalyzer.analyze(Path("nonexistent.jpg"))
    assert isinstance(result, dict)
    assert set(result.keys()) == {"caption", "object_caption", "detections", "clip_embedding_path"}
    assert result["caption"] == ""           # must be "" not None
    assert result["object_caption"] == ""    # must be "" not None
    assert result["detections"] == []        # must be [] not None
    assert result["clip_embedding_path"] is None


def test_analyze_caption_is_str_not_none(monkeypatch):
    """caption field must be str (empty string), never None"""
    from app.core.frame_analyzer import FrameAnalyzer
    monkeypatch.setattr(FrameAnalyzer, "is_available", staticmethod(lambda: False))
    result = FrameAnalyzer.analyze(Path("nonexistent.jpg"))
    assert isinstance(result["caption"], str)
    assert result["caption"] is not None


def test_analyze_detections_is_list_not_none(monkeypatch):
    """detections field must be list, never None"""
    from app.core.frame_analyzer import FrameAnalyzer
    monkeypatch.setattr(FrameAnalyzer, "is_available", staticmethod(lambda: False))
    result = FrameAnalyzer.analyze(Path("nonexistent.jpg"))
    assert isinstance(result["detections"], list)
    assert result["detections"] is not None


# ── Phase 8 tests (T002) ────────────────────────────────────────────────────

def test_task_timeout_value():
    """_TASK_TIMEOUT inside _run_analysis must be reduced to 90 s."""
    import inspect
    from app.core.frame_analyzer import FrameAnalyzer
    source = inspect.getsource(FrameAnalyzer._run_analysis)
    assert "_TASK_TIMEOUT = 90" in source, (
        "_TASK_TIMEOUT is not 90 — set it in app/core/frame_analyzer.py"
    )


def test_max_new_tokens_value():
    """All model.generate() calls must use max_new_tokens=64 (not 128)."""
    import inspect
    from app.core.frame_analyzer import FrameAnalyzer
    source = inspect.getsource(FrameAnalyzer._run_analysis)
    assert "max_new_tokens=64" in source, (
        "max_new_tokens is not 64 — fix all model.generate() call sites in _run_analysis"
    )
    assert "max_new_tokens=128" not in source, (
        "Old max_new_tokens=128 still present — update all call sites"
    )


def test_analyze_returns_empty_dict_on_timeout(monkeypatch, tmp_path):
    """When _run_in_daemon times out on all tasks, _run_analysis returns empty-caption
    dict without raising (covers FR-002 fallback behavior)."""
    from app.core.frame_analyzer import FrameAnalyzer
    from PIL import Image

    img_path = tmp_path / "thumb.jpg"
    Image.new("RGB", (64, 64), color=(80, 80, 80)).save(img_path)

    monkeypatch.setattr(
        "app.core.frame_analyzer._run_in_daemon",
        lambda fn, timeout: (None, TimeoutError(f"mocked timeout at {timeout}s")),
    )
    # Pre-set model/processor to non-None so the load block is skipped
    monkeypatch.setattr(FrameAnalyzer, "_model", object())
    monkeypatch.setattr(FrameAnalyzer, "_processor", object())

    result = FrameAnalyzer._run_analysis(img_path)

    assert result["caption"] == "", f"Expected empty caption on timeout, got {result['caption']!r}"
    assert result["detections"] == []
    assert result["object_caption"] == ""
