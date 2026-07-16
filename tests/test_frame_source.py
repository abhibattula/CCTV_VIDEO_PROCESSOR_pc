"""
Phase 15 T004 — tests for app/core/frame_source.py (FFmpeg pipe frame source).
Written BEFORE the implementation (constitution III).
"""
import io
import os
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import pytest

import app.core.frame_source as fs


@pytest.fixture(autouse=True)
def _reset():
    fs._reset_for_tests()
    yield
    fs._reset_for_tests()


# ── Fake FFmpeg process ───────────────────────────────────────────────────────

class FakeStdout:
    def __init__(self, data: bytes, block_forever: bool = False):
        self._buf = io.BytesIO(data)
        self._block = block_forever
        self._release = threading.Event()

    def read(self, n: int) -> bytes:
        if self._block:
            self._release.wait(timeout=10)
            return b""
        return self._buf.read(n)


class FakeProc:
    def __init__(self, stdout_data: bytes = b"", returncode: int = 0,
                 block_forever: bool = False):
        self.stdout = FakeStdout(stdout_data, block_forever)
        self.stderr = io.BytesIO(b"")
        self._returncode = returncode
        self.terminated = False
        self.killed = False
        self.wait_timeout = False  # set True to force kill-after-grace path

    def poll(self):
        return None if (self.stdout._block and not self.killed) else self._returncode

    def wait(self, timeout=None):
        if self.wait_timeout and not self.killed:
            raise subprocess.TimeoutExpired("ffmpeg", timeout)
        return self._returncode

    def terminate(self):
        self.terminated = True
        self.stdout._release.set()

    def kill(self):
        self.killed = True
        self.stdout._release.set()

    @property
    def returncode(self):
        return self._returncode


def _frames_bytes(n, w, h, fill=128):
    return bytes([fill]) * (w * h * 3 * n)


# ── (a) Command construction ─────────────────────────────────────────────────

def test_qsv_command_contains_gpu_scale_chain():
    cmd = fs.build_command("qsv", "C:/v.mp4", "hevc", 5.0, 320, 180)
    joined = " ".join(cmd)
    assert "-hwaccel qsv" in joined
    assert "hevc_qsv" in joined
    assert "vpp_qsv=w=320:h=180,hwdownload,format=nv12,fps=5.0" in joined
    assert "-f rawvideo" in joined and "-pix_fmt bgr24" in joined and "-an" in joined


def test_cuda_command_contains_scale_cuda():
    cmd = fs.build_command("cuda", "C:/v.mp4", "h264", 2.0, 320, 180)
    joined = " ".join(cmd)
    assert "-hwaccel cuda" in joined
    assert "scale_cuda" in joined and "hwdownload" in joined


def test_software_command_plain_fps_scale():
    cmd = fs.build_command("software", "C:/v.mp4", "h264", 5.0, 320, 180)
    joined = " ".join(cmd)
    assert "fps=5.0,scale=320:180" in joined
    assert "hwaccel" not in joined
    assert "-f rawvideo" in joined and "-pix_fmt bgr24" in joined


# ── (b) Candidate chains: codec map / rotation / env escape ──────────────────

def test_unsupported_codec_skips_hardware():
    assert fs.candidate_chains("mjpeg", rotation=0) == ["software"]


def test_supported_codec_offers_hw_first():
    chains = fs.candidate_chains("hevc", rotation=0)
    assert chains[0] == "qsv" and chains[-1] == "software"
    assert "cuda" in chains


def test_rotation_forces_software():
    assert fs.candidate_chains("hevc", rotation=90) == ["software"]


def test_force_sw_env_skips_hardware(monkeypatch):
    monkeypatch.setenv("CCTV_FORCE_SW_DECODE", "1")
    assert fs.candidate_chains("hevc", rotation=0) == ["software"]


# ── (c) Trial selection + per-codec cache ─────────────────────────────────────

def test_first_passing_trial_wins_and_is_cached(monkeypatch):
    calls = []

    def fake_trial(chain, *a, **kw):
        calls.append(chain)
        return chain == "cuda"  # qsv fails, cuda passes

    monkeypatch.setattr(fs, "_trial", fake_trial)
    sel = fs.select_chain("C:/v.mp4", "hevc", 0, 5.0, 320, 180, lambda m: None)
    assert sel == "cuda"
    assert calls == ["qsv", "cuda"]

    sel2 = fs.select_chain("C:/v.mp4", "hevc", 0, 5.0, 320, 180, lambda m: None)
    assert sel2 == "cuda"
    assert calls == ["qsv", "cuda"]  # no new trials — cache hit


def test_all_hw_trials_fail_falls_to_software(monkeypatch):
    monkeypatch.setattr(fs, "_trial", lambda chain, *a, **kw: chain == "software")
    sel = fs.select_chain("C:/v.mp4", "h264", 0, 5.0, 320, 180, lambda m: None)
    assert sel == "software"


# ── (d) Frame iteration from the pipe ─────────────────────────────────────────

def _patch_popen(monkeypatch, proc):
    monkeypatch.setattr(fs.subprocess, "Popen", lambda *a, **kw: proc)


def test_frames_and_pts(monkeypatch):
    w, h, n = 8, 4, 5
    proc = FakeProc(stdout_data=_frames_bytes(n, w, h))
    _patch_popen(monkeypatch, proc)
    monkeypatch.setattr(fs, "select_chain", lambda *a, **kw: "software")

    got = []
    with fs.open_frames("C:/v.mp4", {"codec": "h264", "fps": 30.0, "rotation": 0},
                        sample_fps=2.0, width=w, height=h, logger=lambda m: None) as stream:
        for frame, pts in stream:
            got.append((frame, pts))

    assert len(got) == n
    assert got[0][0].shape == (h, w, 3)
    assert got[0][0].dtype == np.uint8
    assert got[2][1] == pytest.approx(2 / 2.0)
    assert got[4][1] == pytest.approx(4 / 2.0)


def test_partial_trailing_frame_discarded(monkeypatch):
    w, h = 8, 4
    data = _frames_bytes(2, w, h) + b"\x00" * 10  # 2 full frames + garbage tail
    proc = FakeProc(stdout_data=data)
    _patch_popen(monkeypatch, proc)
    monkeypatch.setattr(fs, "select_chain", lambda *a, **kw: "software")

    with fs.open_frames("C:/v.mp4", {"codec": "h264", "fps": 30.0, "rotation": 0},
                        sample_fps=2.0, width=w, height=h, logger=lambda m: None) as stream:
        frames = list(stream)
    assert len(frames) == 2


# ── (e) Stall watchdog ────────────────────────────────────────────────────────

def test_stall_watchdog_raises_instead_of_hanging(monkeypatch):
    w, h = 8, 4
    proc = FakeProc(block_forever=True)
    _patch_popen(monkeypatch, proc)
    monkeypatch.setattr(fs, "select_chain", lambda *a, **kw: "software")
    monkeypatch.setattr(fs, "STALL_TIMEOUT_S", 0.3)

    t0 = time.monotonic()
    with pytest.raises(fs.FrameSourceError):
        with fs.open_frames("C:/v.mp4", {"codec": "h264", "fps": 30.0, "rotation": 0},
                            sample_fps=2.0, width=w, height=h,
                            logger=lambda m: None) as stream:
            list(stream)
    assert time.monotonic() - t0 < 5.0
    assert proc.killed or proc.terminated


# ── (f) close() semantics ─────────────────────────────────────────────────────

def test_close_terminates_then_kills_after_grace(monkeypatch):
    w, h = 8, 4
    proc = FakeProc(stdout_data=_frames_bytes(1, w, h))
    proc.wait_timeout = True  # refuses to die on terminate
    _patch_popen(monkeypatch, proc)
    monkeypatch.setattr(fs, "select_chain", lambda *a, **kw: "software")
    monkeypatch.setattr(fs, "KILL_GRACE_S", 0.05)

    stream = fs.open_frames("C:/v.mp4", {"codec": "h264", "fps": 30.0, "rotation": 0},
                            sample_fps=2.0, width=w, height=h, logger=lambda m: None)
    stream.close()
    assert proc.terminated and proc.killed
    stream.close()  # idempotent — no raise


def test_context_manager_closes_on_exception(monkeypatch):
    w, h = 8, 4
    proc = FakeProc(stdout_data=_frames_bytes(3, w, h))
    _patch_popen(monkeypatch, proc)
    monkeypatch.setattr(fs, "select_chain", lambda *a, **kw: "software")

    with pytest.raises(RuntimeError):
        with fs.open_frames("C:/v.mp4", {"codec": "h264", "fps": 30.0, "rotation": 0},
                            sample_fps=2.0, width=w, height=h,
                            logger=lambda m: None) as stream:
            next(iter(stream))
            raise RuntimeError("boom")
    assert proc.terminated or proc.killed


# ── (g) Acceleration status ───────────────────────────────────────────────────

def test_acceleration_status_shape(monkeypatch):
    monkeypatch.setattr(fs, "_query_hwaccels", lambda: ["qsv", "cuda"])
    monkeypatch.setattr(fs, "_trial", lambda chain, *a, **kw: chain == "qsv")
    fs.select_chain("C:/v.mp4", "hevc", 0, 5.0, 320, 180, lambda m: None)

    status = fs.get_acceleration_status()
    assert status["methods_available"] == ["qsv", "cuda"]
    assert status["selected"] == {"hevc": "qsv"}


def test_hwaccels_query_failure_yields_empty_list(monkeypatch):
    def boom():
        raise OSError("no ffmpeg")
    monkeypatch.setattr(fs, "_query_hwaccels", boom)
    status = fs.get_acceleration_status()
    assert status["methods_available"] == []


# ── sample_fps helper ─────────────────────────────────────────────────────────

def test_sample_fps_presets_and_cap():
    assert fs.sample_fps_for("balanced", 30.0) == 5.0
    assert fs.sample_fps_for("fast", 30.0) == 2.0
    assert fs.sample_fps_for("balanced", 2.0) == 2.0   # capped, never upsample
    assert fs.sample_fps_for("fast", 1.0) == 1.0


# ── (h) Real-decode integration on a generated clip ──────────────────────────

def _make_test_clip(tmp_path: Path) -> Path:
    from app.utils.ffmpeg_path import get_ffmpeg
    out = tmp_path / "testsrc.mp4"
    cmd = [get_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=10:duration=2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)]
    subprocess.run(cmd, capture_output=True, timeout=60, check=True)
    return out


@pytest.mark.skipif(os.environ.get("CI") == "true", reason="real decode — local only")
def test_real_software_decode_yields_expected_frames(tmp_path, monkeypatch):
    monkeypatch.setenv("CCTV_FORCE_SW_DECODE", "1")
    clip = _make_test_clip(tmp_path)
    source_info = {"codec": "h264", "fps": 10.0, "duration_s": 2.0, "rotation": 0}

    frames = []
    with fs.open_frames(str(clip), source_info, sample_fps=2.0,
                        width=160, height=120, logger=lambda m: None) as stream:
        for frame, pts in stream:
            frames.append((frame, pts))

    assert 3 <= len(frames) <= 6           # ~2 s @ 2 fps
    assert frames[0][0].shape == (120, 160, 3)
    assert frames[-1][1] == pytest.approx((len(frames) - 1) / 2.0)
    assert stream.decoder == "software"
