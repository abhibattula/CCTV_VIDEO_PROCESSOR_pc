"""
Video file probing.

Primary strategy: use the bundled ffprobe binary if available.
Fallback strategy: parse `ffmpeg -i` stderr output (imageio-ffmpeg bundles
ffmpeg but not ffprobe on all platforms).

Returns a SourceInfo dict matching data-model.md.
"""
import json
import re
import subprocess
from pathlib import Path
from typing import Optional

from app.config import STREAM_COPY_SAFE
from app.utils.ffmpeg_path import get_ffmpeg, get_ffprobe


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_duration_str(s: str) -> float:
    """'HH:MM:SS.ms' → float seconds."""
    parts = s.strip().split(":")
    try:
        h, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
        return h * 3600 + m * 60 + sec
    except (IndexError, ValueError):
        return 0.0


def _estimate_duration(file_path: str) -> float:
    """Estimate duration from file size and bitrate (MJPEG AVI fallback)."""
    try:
        size_bytes = Path(file_path).stat().st_size
        result = subprocess.run(
            [get_ffmpeg(), "-i", file_path],
            capture_output=True, timeout=30,
        )
        stderr = result.stderr.decode("utf-8", errors="replace")
        m = re.search(r"bitrate:\s*(\d+)\s*kb/s", stderr)
        if m:
            bitrate_bps = int(m.group(1)) * 1000
            if bitrate_bps > 0:
                return (size_bytes * 8) / bitrate_bps
    except Exception:
        pass
    return 0.0


# ── Primary probe via ffprobe JSON ────────────────────────────────────────────

def _probe_via_ffprobe(source_path: str) -> dict:
    try:
        probe_bin = get_ffprobe()
    except RuntimeError:
        raise RuntimeError("ffprobe_unavailable")

    cmd = [
        probe_bin, "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        source_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        raise RuntimeError("ffprobe_unavailable")

    if result.returncode != 0:
        raise ValueError(f"ffprobe failed: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError("ffprobe returned invalid JSON")

    return data


# ── Fallback probe via ffmpeg -i stderr parsing ───────────────────────────────

def _probe_via_ffmpeg_stderr(source_path: str) -> dict:
    """
    Parse `ffmpeg -i` stderr to extract video metadata.
    Works with ffmpeg v4+ output format.
    """
    result = subprocess.run(
        [get_ffmpeg(), "-i", source_path],
        capture_output=True, timeout=60,
    )
    stderr = result.stderr.decode("utf-8", errors="replace")

    if not stderr:
        raise ValueError(f"ffmpeg produced no output for: {source_path}")

    if "No such file or directory" in stderr or "Invalid data found" in stderr:
        raise ValueError(f"Cannot open file: {source_path}")

    # Duration: "Duration: HH:MM:SS.ms"
    dur_match = re.search(r"Duration:\s*(\d+:\d+:\d+\.?\d*)", stderr)
    duration_s = _parse_duration_str(dur_match.group(1)) if dur_match else 0.0

    # Overall bitrate for duration estimation fallback
    bitrate_match = re.search(r"bitrate:\s*(\d+)\s*kb/s", stderr)

    # Video stream line examples (ffmpeg v4–v7):
    #   Stream #0:0: Video: h264 (High), yuv420p, 1920x1080, 30 fps, ...
    #   Stream #0:0[0x1](eng): Video: hevc (Main) (hvc1 / ...), ..., 1920x1080, 15990 kb/s, 59.62 fps, ...
    # Strategy: split the stream line on commas, find resolution token (WxH) and fps token
    video_line = None
    audio_line = None
    for line in stderr.splitlines():
        stripped = line.strip()
        if ": Video:" in stripped and video_line is None:
            video_line = stripped
        if ": Audio:" in stripped and audio_line is None:
            audio_line = stripped

    if video_line is None:
        raise ValueError("No video stream found in file")

    # Extract codec: first word after "Video: "
    codec_match = re.search(r"Video:\s+(\w+)", video_line)
    codec_name = codec_match.group(1).lower() if codec_match else "unknown"

    # Extract resolution: first NxM token with reasonable sizes
    res_match = re.search(r"\b(\d{2,5})x(\d{2,5})\b", video_line)
    width = int(res_match.group(1)) if res_match else 0
    height = int(res_match.group(2)) if res_match else 0

    # Extract FPS: look for "<number> fps" or "<number> tbr"
    fps_match = re.search(r"([\d.]+)\s+fps", video_line)
    if not fps_match:
        fps_match = re.search(r"([\d.]+)\s+tbr", video_line)
    fps = float(fps_match.group(1)) if fps_match else 0.0

    # Audio
    has_audio = audio_line is not None
    audio_codec = ""
    if audio_line:
        audio_codec_match = re.search(r"Audio:\s+(\w+)", audio_line)
        audio_codec = audio_codec_match.group(1).lower() if audio_codec_match else ""

    # Build normalised output (same shape as ffprobe JSON after parsing)
    streams = [{
        "codec_type": "video",
        "codec_name": codec_name,
        "width": width,
        "height": height,
        "avg_frame_rate": f"{int(fps * 1000)}/1000" if fps else "0/1",
        "duration": str(duration_s),
    }]
    if has_audio:
        streams.append({
            "codec_type": "audio",
            "codec_name": audio_codec,
        })

    fmt = {
        "duration": str(duration_s),
        "bit_rate": str((int(bitrate_match.group(1)) * 1000) if bitrate_match else 0),
        "tags": {},
    }

    return {"streams": streams, "format": fmt}


# ── Unified probe + normalization ─────────────────────────────────────────────

def probe(source_path: str) -> dict:
    """
    Probe a video file and return a SourceInfo-compatible dict.
    Tries ffprobe JSON first; falls back to ffmpeg stderr parsing.
    """
    # Try ffprobe
    try:
        data = _probe_via_ffprobe(source_path)
    except RuntimeError as e:
        if "ffprobe_unavailable" in str(e):
            # Bundled ffprobe not available — use ffmpeg stderr fallback
            data = _probe_via_ffmpeg_stderr(source_path)
        else:
            raise

    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError("No video stream found in file")

    # FPS from avg_frame_rate fraction
    avg_fps_str = video.get("avg_frame_rate", "0/1")
    try:
        num, den = avg_fps_str.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    # Duration — prefer format-level, then stream-level
    duration_s: float = float(
        fmt.get("duration") or video.get("duration") or 0
    )

    # Duration fallback for MJPEG AVI and other files with no duration atom
    if duration_s <= 0:
        duration_s = _estimate_duration(source_path)

    if duration_s <= 0:
        raise ValueError(
            "Cannot determine video duration. File may be corrupt or truncated."
        )

    width: int = int(video.get("width", 0))
    height: int = int(video.get("height", 0))
    codec: str = video.get("codec_name", "").lower()

    has_audio: bool = any(s.get("codec_type") == "audio" for s in streams)
    audio_codec: str = next(
        (s.get("codec_name", "").lower() for s in streams
         if s.get("codec_type") == "audio"),
        "",
    )

    needs_reencode: bool = codec not in STREAM_COPY_SAFE

    return {
        "codec": codec,
        "fps": fps,
        "width": width,
        "height": height,
        "duration_s": duration_s,
        "has_audio": has_audio,
        "audio_codec": audio_codec,
        "needs_reencode": needs_reencode,
    }
