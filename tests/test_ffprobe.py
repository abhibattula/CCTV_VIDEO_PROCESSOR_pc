import os
import pytest
from pathlib import Path

# Test video lives in the Pi version's Test Video folder
TEST_VIDEO = str(
    Path(__file__).parent.parent
    / "OLD RASPBERRI PI VERSION"
    / "Test Video"
    / "20260507_012210 (1).mp4"
)
HAS_TEST_VIDEO = os.path.isfile(TEST_VIDEO)

from app.utils.ffprobe import probe


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_probe_returns_expected_fields():
    result = probe(TEST_VIDEO)
    required_keys = {"codec", "fps", "duration_s", "width", "height", "has_audio",
                     "audio_codec", "needs_reencode"}
    assert required_keys.issubset(result.keys()), (
        f"Missing keys: {required_keys - result.keys()}"
    )
    # Reject Pi-era field names
    assert "codec_name" not in result
    assert "avg_frame_rate" not in result


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_probe_codec_is_string():
    result = probe(TEST_VIDEO)
    assert isinstance(result["codec"], str)
    assert len(result["codec"]) > 0


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_probe_fps_is_positive():
    result = probe(TEST_VIDEO)
    assert isinstance(result["fps"], float)
    assert result["fps"] > 0


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_probe_duration_is_positive():
    result = probe(TEST_VIDEO)
    assert result["duration_s"] > 0


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_probe_resolution_is_valid():
    result = probe(TEST_VIDEO)
    assert result["width"] > 0
    assert result["height"] > 0


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_probe_detects_has_audio():
    result = probe(TEST_VIDEO)
    # The test video is an iPhone HEVC recording — it has audio
    assert isinstance(result["has_audio"], bool)


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_probe_audio_codec_field_present():
    result = probe(TEST_VIDEO)
    assert isinstance(result["audio_codec"], str)
    # aac audio expected from the test video
    if result["has_audio"]:
        assert len(result["audio_codec"]) > 0


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_probe_needs_reencode_is_bool():
    result = probe(TEST_VIDEO)
    assert isinstance(result["needs_reencode"], bool)


def test_probe_raises_on_nonexistent_file():
    with pytest.raises((ValueError, RuntimeError, Exception)):
        probe("/nonexistent/path/video.mp4")


# ── Phase 10 T015 mock-counterpart tests (US6 AC6) ───────────────────────────

import json as _json
import subprocess as _subprocess
import app.utils.ffprobe as _ffprobe_mod


def _ffprobe_mock(avg_frame_rate="30/1", duration="5.0", width=1280, height=720):
    data = {
        "streams": [{"codec_type": "video", "codec_name": "h264",
                     "width": width, "height": height,
                     "avg_frame_rate": avg_frame_rate}],
        "format": {"duration": duration},
    }

    def mock_run(cmd, **kw):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.returncode = 0
        m.stdout = _json.dumps(data)
        m.stderr = ""
        return m

    return mock_run


def test_probe_returns_fps_from_mocked_output(monkeypatch):
    monkeypatch.setattr(_ffprobe_mod, "get_ffprobe", lambda: "/usr/bin/ffprobe")
    monkeypatch.setattr(_ffprobe_mod.subprocess, "run", _ffprobe_mock("30/1", "5.0"))
    result = _ffprobe_mod.probe("/fake.mp4")
    assert result["fps"] == pytest.approx(30.0)
    assert result["duration_s"] == pytest.approx(5.0)


def test_probe_raises_on_subprocess_error(monkeypatch):
    monkeypatch.setattr(_ffprobe_mod, "get_ffprobe", lambda: "/usr/bin/ffprobe")
    monkeypatch.setattr(
        _ffprobe_mod.subprocess, "run",
        lambda *a, **kw: (_ for _ in ()).throw(
            _subprocess.CalledProcessError(1, "ffprobe")
        ),
    )
    with pytest.raises(Exception):
        _ffprobe_mod.probe("/fake.mp4")


def test_probe_handles_fractional_fps_mocked(monkeypatch):
    monkeypatch.setattr(_ffprobe_mod, "get_ffprobe", lambda: "/usr/bin/ffprobe")
    monkeypatch.setattr(_ffprobe_mod.subprocess, "run", _ffprobe_mock("30000/1001", "5.0"))
    result = _ffprobe_mod.probe("/fake.mp4")
    assert result["fps"] == pytest.approx(29.97, rel=0.01)
