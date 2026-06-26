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
