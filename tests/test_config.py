import pathlib
import pytest
from app.config import (
    DETECT_WIDTH, DETECT_HEIGHT,
    BACKEND_PORT,
    PREVIEW_DIR, JOBS_DIR, MODEL_DIR,
    BATCH_SIZE, LOG_RING_SIZE,
    STREAM_COPY_SAFE, FFMPEG_THREADS,
    RAM_GUARD_PERCENT,
)


def test_detect_resolution_is_valid():
    assert DETECT_WIDTH in (320, 480, 640)
    assert DETECT_HEIGHT in (180, 270, 360)


def test_detect_resolution_ratio():
    ratio = DETECT_WIDTH / DETECT_HEIGHT
    assert abs(ratio - (16 / 9)) < 0.1


def test_backend_port():
    assert BACKEND_PORT == 5151


def test_paths_are_pathlib():
    assert isinstance(PREVIEW_DIR, pathlib.Path)
    assert isinstance(JOBS_DIR, pathlib.Path)
    assert isinstance(MODEL_DIR, pathlib.Path)


def test_model_dir_under_home():
    assert ".cctv_processor" in str(MODEL_DIR)


def test_batch_size_is_int():
    assert isinstance(BATCH_SIZE, int)
    assert BATCH_SIZE > 0


def test_log_ring_size():
    assert LOG_RING_SIZE == 2000


def test_stream_copy_safe_contains_common_codecs():
    assert "h264" in STREAM_COPY_SAFE
    assert "hevc" in STREAM_COPY_SAFE


def test_ffmpeg_threads_positive():
    assert isinstance(FFMPEG_THREADS, int)
    assert FFMPEG_THREADS >= 1


def test_ram_guard_percent_sensible():
    assert 50 <= RAM_GUARD_PERCENT <= 95
