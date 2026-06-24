"""
Tests for app/core/thumbnail_gen.py.
T005 (Phase 5, 005-reporting-and-heatmap): new coverage for previously-untested,
already-correct code. Not a TDD red/green task — no production code changes.
"""
import os
import subprocess as _subprocess
from pathlib import Path

import pytest

from app.core import thumbnail_gen

TEST_VIDEO = str(
    Path(__file__).parent.parent
    / "OLD RASPBERRI PI VERSION"
    / "Test Video"
    / "20260507_012210 (1).mp4"
)
HAS_TEST_VIDEO = os.path.isfile(TEST_VIDEO)


def _events(n=3):
    """Fabricate n event dicts with event_index, start_s, end_s."""
    return [
        {"event_index": i, "start_s": float(i), "end_s": float(i + 1)}
        for i in range(n)
    ]


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_run_generates_thumbnail_per_event(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnail_gen, "JOBS_DIR", tmp_path)

    job_id = "test-job"
    events = _events(3)
    logs = []

    thumbnail_gen.run(job_id, TEST_VIDEO, events, logs.append)

    thumb_dir = tmp_path / job_id / "thumbnails"
    for ev in events:
        thumb_path = thumb_dir / f"{ev['event_index']}.jpg"
        assert thumb_path.is_file()
        assert thumb_path.stat().st_size > 0

    assert any("THUMBNAILS" in line for line in logs)


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_run_is_idempotent_skips_existing_thumbnails(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnail_gen, "JOBS_DIR", tmp_path)

    job_id = "test-job"
    events = _events(2)
    logs = []

    # First call: generates both thumbnails from scratch.
    thumbnail_gen.run(job_id, TEST_VIDEO, events, logs.append)

    thumb_dir = tmp_path / job_id / "thumbnails"
    for ev in events:
        assert (thumb_dir / f"{ev['event_index']}.jpg").is_file()

    # Second call: monkeypatch subprocess.run to count invocations and confirm
    # ffmpeg is not re-invoked for files that already exist.
    real_run = _subprocess.run
    call_count = {"n": 0}

    def counting_run(*args, **kwargs):
        call_count["n"] += 1
        return real_run(*args, **kwargs)

    monkeypatch.setattr("subprocess.run", counting_run)

    thumbnail_gen.run(job_id, TEST_VIDEO, events, logs.append)

    assert call_count["n"] == 0
