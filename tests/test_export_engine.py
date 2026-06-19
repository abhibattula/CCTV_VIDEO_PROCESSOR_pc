"""
Tests for export_engine.run() — individual clips mode (T058) and quality scaling (T059).
Uses monkeypatching to avoid needing real FFmpeg.
"""
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_ffmpeg(calls: list):
    """Return a _run_ffmpeg replacement that records commands and touches outputs."""
    def fake(cmd, logger=None):
        calls.append(list(cmd))
        # The last element is the output path — touch it so stat() works
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00" * 100)  # non-zero size
    return fake


def _base_source_info(has_audio=False):
    return {
        "has_audio": has_audio,
        "audio_codec": "",
        "needs_reencode": False,
    }


def _two_events():
    return [
        {"start_s": 0.0, "end_s": 5.0, "included": True},
        {"start_s": 10.0, "end_s": 15.0, "included": True},
    ]


def _three_events_one_excluded():
    return [
        {"start_s": 0.0, "end_s": 5.0, "included": True},
        {"start_s": 10.0, "end_s": 15.0, "included": True},
        {"start_s": 20.0, "end_s": 22.0, "included": False},
    ]


# ---------------------------------------------------------------------------
# T058 — individual clips mode
# ---------------------------------------------------------------------------

class TestIndividualClipsMode:
    def test_creates_one_mp4_per_included_event(self, tmp_path, monkeypatch):
        import app.core.export_engine as eng
        calls = []
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg(calls))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "individual",
            "output_quality": "original",
        }
        result = eng.run(
            _three_events_one_excluded(), _base_source_info(),
            settings, out_dir, lambda p: None, job_dir,
        )

        mp4s = sorted(out_dir.glob("*.mp4"))
        assert len(mp4s) == 2, f"expected 2 clips, got {[f.name for f in mp4s]}"
        # Two ffmpeg encode calls (no merge step in individual mode)
        assert len(calls) == 2

    def test_filenames_contain_event_index(self, tmp_path, monkeypatch):
        import app.core.export_engine as eng
        calls = []
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg(calls))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "individual",
            "output_quality": "original",
        }
        eng.run(
            _two_events(), _base_source_info(),
            settings, out_dir, lambda p: None, job_dir,
        )

        names = sorted(f.name for f in out_dir.glob("*.mp4"))
        assert any("_event_001_" in n for n in names), names
        assert any("_event_002_" in n for n in names), names

    def test_excluded_events_not_exported(self, tmp_path, monkeypatch):
        import app.core.export_engine as eng
        calls = []
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg(calls))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        events = [
            {"start_s": 0.0, "end_s": 5.0, "included": False},
            {"start_s": 10.0, "end_s": 15.0, "included": True},
        ]
        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "individual",
            "output_quality": "original",
        }
        eng.run(events, _base_source_info(), settings, out_dir, lambda p: None, job_dir)

        mp4s = list(out_dir.glob("*.mp4"))
        assert len(mp4s) == 1

    def test_return_value_is_output_dir(self, tmp_path, monkeypatch):
        """run() in individual mode returns (output_dir, ...) so Open Folder works."""
        import app.core.export_engine as eng
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg([]))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "individual",
            "output_quality": "original",
        }
        result = eng.run(
            _two_events(), _base_source_info(), settings,
            out_dir, lambda p: None, job_dir,
        )
        assert Path(result[0]) == out_dir

    def test_sentinel_deleted_on_success(self, tmp_path, monkeypatch):
        import app.core.export_engine as eng
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg([]))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "individual",
            "output_quality": "original",
        }
        eng.run(
            _two_events(), _base_source_info(), settings,
            out_dir, lambda p: None, job_dir,
        )
        assert not (job_dir / "export.writing").exists()

    def test_wall_clock_filename_when_recording_start_set(self, tmp_path, monkeypatch):
        """When recording_start is given, filenames use wall-clock times."""
        import app.core.export_engine as eng
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg([]))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        # events start at 0s and 3600s (= 1h offset from recording_start "08:00:00")
        events = [
            {"start_s": 0.0, "end_s": 5.0, "included": True},
            {"start_s": 3600.0, "end_s": 3605.0, "included": True},
        ]
        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "individual",
            "output_quality": "original",
            "recording_start": "08:00:00",
        }
        eng.run(events, _base_source_info(), settings, out_dir, lambda p: None, job_dir)

        names = sorted(f.name for f in out_dir.glob("*.mp4"))
        # First clip: recording_start + 0s = 08:00:00
        assert any("080000" in n for n in names), names
        # Second clip: recording_start + 3600s = 09:00:00
        assert any("090000" in n for n in names), names


# ---------------------------------------------------------------------------
# T059 — quality scaling (already implemented; these confirm behaviour)
# ---------------------------------------------------------------------------

class TestQualityScaling:
    def _get_video_flags(self, calls, event_index=0):
        """Extract the video-codec portion of the ffmpeg command for a segment."""
        cmd = calls[event_index]
        return " ".join(cmd)

    def test_720p_adds_scale_filter(self, tmp_path, monkeypatch):
        import app.core.export_engine as eng
        calls = []
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg(calls))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "merged",
            "output_quality": "720p",
        }
        eng.run(
            _two_events(), _base_source_info(has_audio=False),
            settings, out_dir, lambda p: None, job_dir,
        )
        # Segment encode call should contain scale=-2:720
        cmd_str = " ".join(calls[0])
        assert "scale=-2:720" in cmd_str, cmd_str

    def test_480p_adds_scale_filter(self, tmp_path, monkeypatch):
        import app.core.export_engine as eng
        calls = []
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg(calls))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "merged",
            "output_quality": "480p",
        }
        eng.run(
            _two_events(), _base_source_info(has_audio=False),
            settings, out_dir, lambda p: None, job_dir,
        )
        cmd_str = " ".join(calls[0])
        assert "scale=-2:480" in cmd_str, cmd_str

    def test_original_quality_no_scale_filter(self, tmp_path, monkeypatch):
        import app.core.export_engine as eng
        calls = []
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg(calls))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "merged",
            "output_quality": "original",
        }
        eng.run(
            _two_events(), _base_source_info(has_audio=False),
            settings, out_dir, lambda p: None, job_dir,
        )
        # stream copy when no reencode needed → no scale filter
        cmd_str = " ".join(calls[0])
        assert "scale=" not in cmd_str, cmd_str

    def test_720p_individual_clips_also_scales(self, tmp_path, monkeypatch):
        """Quality scaling applies in individual clips mode too."""
        import app.core.export_engine as eng
        calls = []
        monkeypatch.setattr(eng, "_run_ffmpeg", _make_fake_ffmpeg(calls))
        monkeypatch.setattr(eng, "get_ffmpeg", lambda: "ffmpeg")

        job_dir = tmp_path / "job"; job_dir.mkdir()
        out_dir = tmp_path / "out"; out_dir.mkdir()

        settings = {
            "source_path": str(tmp_path / "myvideo.mp4"),
            "output_type": "individual",
            "output_quality": "720p",
        }
        eng.run(
            _two_events(), _base_source_info(has_audio=False),
            settings, out_dir, lambda p: None, job_dir,
        )
        for cmd in calls:
            assert "scale=-2:720" in " ".join(cmd), calls
