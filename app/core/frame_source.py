"""
FFmpeg-pipe frame source for sampled detection (Phase 15 Fast Scan).

FFmpeg decodes, samples (fps filter), and scales to the requested resolution
— on the GPU when the machine supports it — writing raw BGR frames to stdout.
Python only ever touches tiny pre-scaled frames, which is where the measured
4.8× speedup over the cv2.VideoCapture loop comes from.

Decoder chains are tried in order (qsv → cuda → software), each verified by a
short trial decode on the actual file; the winner is cached per codec for the
session. Hardware chains scale on-GPU before copy-back (vpp_qsv/scale_cuda) —
naive hwaccel with full-resolution copy-back measured *slower* than software
and is never used. `CCTV_FORCE_SW_DECODE=1` skips hardware candidates.
"""
import os
import queue
import subprocess
import threading
from typing import Callable, Iterator, Optional

import numpy as np

from app.utils.ffmpeg_path import get_ffmpeg

SAMPLE_FPS = {"balanced": 5.0, "fast": 2.0}
STALL_TIMEOUT_S = 30.0   # no bytes for this long while child alive → failure
KILL_GRACE_S = 3.0       # terminate → kill escalation window
TRIAL_SECONDS = 2.0      # how much of the file a candidate must prove it decodes

_QSV_DECODERS = {
    "h264": "h264_qsv",
    "hevc": "hevc_qsv",
    "vp9": "vp9_qsv",
    "av1": "av1_qsv",
    "mpeg2video": "mpeg2_qsv",
}
_CUDA_CODECS = {"h264", "hevc", "vp9", "av1", "mpeg2video", "mpeg4", "vc1"}

_lock = threading.Lock()
_selection_cache: dict[str, str] = {}
_hwaccels_cache: Optional[list[str]] = None


class FrameSourceError(RuntimeError):
    """Pipe failed (stall, decoder error) — caller should fall back."""


def _reset_for_tests() -> None:
    global _hwaccels_cache
    with _lock:
        _selection_cache.clear()
        _hwaccels_cache = None


# ── Preset helpers ────────────────────────────────────────────────────────────

def sample_fps_for(scan_speed: str, source_fps: float) -> float:
    """Preset rate capped at the source rate — never upsample."""
    rate = SAMPLE_FPS[scan_speed]
    if source_fps and source_fps > 0:
        return min(rate, float(source_fps))
    return rate


# ── Decoder chains ────────────────────────────────────────────────────────────

def candidate_chains(codec: str, rotation: int) -> list[str]:
    """Ordered decode candidates for this codec. Rotation metadata forces the
    software chain (autorotate across hw filter graphs is driver-fragile)."""
    if rotation or os.environ.get("CCTV_FORCE_SW_DECODE") == "1":
        return ["software"]
    chains = []
    if codec in _QSV_DECODERS:
        chains.append("qsv")
    if codec in _CUDA_CODECS:
        chains.append("cuda")
    chains.append("software")
    return chains


def build_command(chain: str, source_path: str, codec: str, sample_fps: float,
                  width: int, height: int, limit_s: Optional[float] = None,
                  max_frames: Optional[int] = None) -> list[str]:
    cmd = [get_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin"]
    if chain == "qsv":
        cmd += ["-hwaccel", "qsv", "-c:v", _QSV_DECODERS[codec]]
        vf = f"vpp_qsv=w={width}:h={height},hwdownload,format=nv12,fps={sample_fps}"
    elif chain == "cuda":
        cmd += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
        vf = f"fps={sample_fps},scale_cuda={width}:{height},hwdownload,format=nv12"
    else:
        vf = f"fps={sample_fps},scale={width}:{height}"
    cmd += ["-i", source_path, "-vf", vf]
    if limit_s is not None:
        cmd += ["-t", str(limit_s)]
    if max_frames is not None:
        cmd += ["-frames:v", str(max_frames)]
    cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "-an", "pipe:1"]
    return cmd


def _trial(chain: str, source_path: str, codec: str, sample_fps: float,
           width: int, height: int) -> bool:
    """A candidate passes if it decodes ≥1 frame from the actual file."""
    cmd = build_command(chain, source_path, codec, sample_fps, width, height,
                        limit_s=TRIAL_SECONDS, max_frames=1)
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0 and len(result.stdout) >= width * height * 3


def select_chain(source_path: str, codec: str, rotation: int, sample_fps: float,
                 width: int, height: int, logger: Callable[[str], None]) -> str:
    """Trial-verify candidates in order; cache the winner per codec."""
    if rotation == 0:
        with _lock:
            cached = _selection_cache.get(codec)
        if cached:
            return cached

    selected = "software"
    for chain in candidate_chains(codec, rotation):
        if _trial(chain, source_path, codec, sample_fps, width, height):
            selected = chain
            break
        logger(f"[FASTSCAN] decode candidate '{chain}' failed trial for {codec} — trying next")

    if rotation == 0:
        with _lock:
            _selection_cache[codec] = selected
    return selected


def _query_hwaccels() -> list[str]:
    result = subprocess.run([get_ffmpeg(), "-hide_banner", "-hwaccels"],
                            capture_output=True, timeout=15)
    lines = result.stdout.decode("utf-8", errors="replace").splitlines()
    return [ln.strip() for ln in lines[1:] if ln.strip()]


def get_acceleration_status() -> dict:
    global _hwaccels_cache
    with _lock:
        if _hwaccels_cache is None:
            try:
                _hwaccels_cache = _query_hwaccels()
            except Exception:
                _hwaccels_cache = []
        return {
            "methods_available": list(_hwaccels_cache),
            "selected": dict(_selection_cache),
        }


# ── Frame stream ──────────────────────────────────────────────────────────────

_EOF = ("eof", None)


class FrameStream:
    """Context-manager/iterator over an FFmpeg child yielding (frame, pts_s)."""

    def __init__(self, cmd: list[str], width: int, height: int,
                 sample_fps: float, decoder: str, logger: Callable[[str], None]):
        self.width = width
        self.height = height
        self.sample_fps = sample_fps
        self.decoder = decoder
        self.frames_delivered = 0
        self._logger = logger
        self._closed = False
        self._stderr_tail: list[str] = []
        self._queue: queue.Queue = queue.Queue(maxsize=16)

        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._drainer = threading.Thread(target=self._drain_stderr, daemon=True)
        self._drainer.start()

    # -- background threads ---------------------------------------------------

    def _read_loop(self) -> None:
        frame_size = self.width * self.height * 3
        try:
            while not self._closed:
                buf = b""
                while len(buf) < frame_size:
                    chunk = self._proc.stdout.read(frame_size - len(buf))
                    if not chunk:
                        self._put(_EOF)  # partial trailing bytes are discarded
                        return
                    buf += chunk
                self._put(("frame", buf))
            # closed mid-read: nothing more to do
        except Exception as exc:
            self._put(("error", exc))

    def _drain_stderr(self) -> None:
        try:
            for raw in self._proc.stderr:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    self._stderr_tail = (self._stderr_tail + [line])[-5:]
        except Exception:
            pass

    def _put(self, item) -> None:
        while not self._closed:
            try:
                self._queue.put(item, timeout=0.2)
                return
            except queue.Full:
                continue

    # -- iteration --------------------------------------------------------------

    def __iter__(self) -> Iterator[tuple[np.ndarray, float]]:
        frame_size = self.width * self.height * 3
        idx = 0
        while True:
            try:
                kind, payload = self._queue.get(timeout=STALL_TIMEOUT_S)
            except queue.Empty:
                self.close()
                raise FrameSourceError(
                    f"FFmpeg pipe stalled — no frames for {STALL_TIMEOUT_S}s "
                    f"({'; '.join(self._stderr_tail) or 'no stderr'})"
                )
            if kind == "eof":
                return
            if kind == "error":
                self.close()
                raise FrameSourceError(f"FFmpeg pipe read failed: {payload}")
            frame = np.frombuffer(payload, dtype=np.uint8).reshape(
                (self.height, self.width, 3)
            )
            pts = idx / self.sample_fps
            idx += 1
            self.frames_delivered += 1
            yield frame, pts

    @property
    def returncode(self) -> Optional[int]:
        return self._proc.poll()

    @property
    def stderr_tail(self) -> str:
        return "; ".join(self._stderr_tail)

    # -- lifecycle --------------------------------------------------------------

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._proc.terminate()
        except OSError:
            pass
        try:
            self._proc.wait(timeout=KILL_GRACE_S)
        except subprocess.TimeoutExpired:
            try:
                self._proc.kill()
            except OSError:
                pass
            try:
                self._proc.wait(timeout=KILL_GRACE_S)
            except subprocess.TimeoutExpired:
                pass
        # unblock a reader stuck on a full queue
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

    def __enter__(self) -> "FrameStream":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def open_frames(source_path: str, source_info: dict, sample_fps: float,
                width: int, height: int,
                logger: Callable[[str], None]) -> FrameStream:
    """Select a decode chain for this file and open the frame pipe."""
    codec = (source_info.get("codec") or "").lower()
    rotation = int(source_info.get("rotation") or 0)
    decoder = select_chain(source_path, codec, rotation, sample_fps,
                           width, height, logger)
    cmd = build_command(decoder, source_path, codec, sample_fps, width, height)
    logger(f"[FASTSCAN] decode: {codec or 'unknown'} via {decoder}, "
           f"{sample_fps:g} fps @ {width}×{height}")
    return FrameStream(cmd, width, height, sample_fps, decoder, logger)
