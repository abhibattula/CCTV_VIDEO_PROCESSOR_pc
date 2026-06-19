import os
import shutil
import pytest
from app.utils.ffmpeg_path import get_ffmpeg, get_ffprobe

# Determine at collection time whether a ffprobe binary is reachable
def _ffprobe_available() -> bool:
    try:
        get_ffprobe()
        return True
    except RuntimeError:
        return False

HAS_FFPROBE = _ffprobe_available()


def test_get_ffmpeg_returns_existing_path():
    path = get_ffmpeg()
    assert isinstance(path, str)
    assert len(path) > 0
    assert os.path.isfile(path), f"ffmpeg binary not found at: {path}"


@pytest.mark.skipif(not HAS_FFPROBE, reason="No ffprobe binary available (imageio-ffmpeg only bundles ffmpeg on Windows)")
def test_get_ffprobe_returns_existing_path():
    path = get_ffprobe()
    assert isinstance(path, str)
    assert len(path) > 0
    assert os.path.isfile(path), f"ffprobe binary not found at: {path}"


def test_get_ffmpeg_is_executable():
    import subprocess
    path = get_ffmpeg()
    result = subprocess.run([path, "-version"], capture_output=True, timeout=10)
    assert result.returncode == 0


@pytest.mark.skipif(not HAS_FFPROBE, reason="No ffprobe binary available (imageio-ffmpeg only bundles ffmpeg on Windows)")
def test_get_ffprobe_is_executable():
    import subprocess
    path = get_ffprobe()
    result = subprocess.run([path, "-version"], capture_output=True, timeout=10)
    assert result.returncode == 0
