"""
FFmpeg-based export engine — PC version.

Events come in as a list of dicts (from session state), not from a database.
Progress is surfaced via on_progress callback.
Write-in-progress sentinel written at job_dir/export.writing (FR-016).
"""
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from app.config import FFMPEG_THREADS, JOBS_DIR, PREVIEW_DIR, MP4_AUDIO_SAFE
from app.utils.ffmpeg_path import get_ffmpeg


def _run_ffmpeg(cmd: list, logger: Optional[Callable] = None) -> None:
    """Run an ffmpeg command, streaming stderr to logger."""
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    if logger:
        for line in proc.stderr:
            line = line.strip()
            if line:
                logger(f"[ffmpeg] {line}")
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg exited with code {proc.returncode}")


def run(
    events: list,
    source_info: dict,
    settings: dict,
    output_dir: Path,
    on_progress: Callable[[float], None],
    job_dir: Path,
    logger: Optional[Callable[[str], None]] = None,
) -> tuple:
    """
    Export included events to a merged MP4.
    Returns (output_path, output_name, output_size_bytes).

    Write-in-progress sentinel: job_dir/export.writing (contains output path as text).
    Deleted on successful completion so the startup crash-recovery scan ignores it.
    """
    if not events:
        raise ValueError("No events selected — include at least one event to export.")

    included = [ev for ev in events if ev.get("included", True)]
    if not included:
        raise ValueError("All events are excluded — toggle at least one event on.")

    source_path    = str(settings.get("source_path", ""))
    source_name    = Path(source_path).stem if source_path else "video"
    output_quality = settings.get("output_quality", "original")
    output_type    = settings.get("output_type", "merged")

    # Audio codec safety: always copy-safe formats; re-encode PCM/G.711/etc.
    audio_codec     = source_info.get("audio_codec", "").lower()
    has_audio       = bool(source_info.get("has_audio", False))
    needs_reencode  = bool(source_info.get("needs_reencode", False))

    if not has_audio:
        audio_flags = ["-an"]
    elif audio_codec in MP4_AUDIO_SAFE:
        audio_flags = ["-c:a", "copy"]
    else:
        # PCM, G.711, or unknown — re-encode to AAC to keep valid MP4 container
        audio_flags = ["-c:a", "aac", "-b:a", "128k"]

    # Re-encode trigger: unsafe codec OR non-original quality
    do_reencode = needs_reencode or (output_quality != "original")

    job_dir    = Path(job_dir)
    output_dir = Path(output_dir)
    seg_dir    = job_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_name = f"{source_name}_activity_{timestamp}.mp4"
    output_path = output_dir / output_name

    # ── Write-in-progress sentinel (FR-016) ──────────────────────────────────
    sentinel = job_dir / "export.writing"
    sentinel.write_text(str(output_path), encoding="utf-8")

    if logger:
        logger(f"[EXPORT] Exporting {len(included)} events — "
               f"{'re-encode' if do_reencode else 'stream copy'}")

    try:
        # ── Individual clips mode (T058) ──────────────────────────────────────
        if output_type == "individual":
            from app.utils.time_utils import seconds_to_clock
            recording_start = settings.get("recording_start")
            total_size = 0

            for i, ev in enumerate(included):
                start_s  = float(ev["start_s"])
                duration = float(ev["end_s"]) - start_s

                if recording_start:
                    clock    = seconds_to_clock(start_s, recording_start)  # "HH:MM:SS"
                    ts_label = clock.replace(":", "")                       # "HHMMSS"
                else:
                    ts_label = f"{int(start_s):05d}s"

                out_name = f"{source_name}_event_{i+1:03d}_{ts_label}.mp4"
                out_path = output_dir / out_name

                if do_reencode:
                    clip_video_flags = ["-c:v", "libx264", "-preset", "veryfast"]
                    if output_quality == "720p":
                        clip_video_flags += ["-vf", "scale=-2:720", "-crf", "28"]
                    elif output_quality == "480p":
                        clip_video_flags += ["-vf", "scale=-2:480", "-crf", "32"]
                    else:
                        clip_video_flags += ["-crf", "23"]
                else:
                    clip_video_flags = ["-c:v", "copy"]

                cmd = [
                    get_ffmpeg(), "-hide_banner", "-loglevel", "error",
                    "-fflags", "+genpts+igndts",
                    "-ss", str(start_s),
                    "-i", source_path,
                    "-t", str(duration),
                    *clip_video_flags,
                    *audio_flags,
                    "-avoid_negative_ts", "make_zero",
                    "-threads", str(FFMPEG_THREADS),
                    "-movflags", "+faststart",
                    "-y",
                    str(out_path),
                ]
                if logger:
                    logger(f"[EXPORT] Clip {i+1}/{len(included)}: "
                           f"{start_s:.1f}s–{start_s+duration:.1f}s → {out_name}")
                _run_ffmpeg(cmd, logger)
                on_progress((i + 1) / len(included))
                total_size += out_path.stat().st_size

            if logger:
                logger(f"[EXPORT] Done — {len(included)} clips in {output_dir.name}")
            sentinel.unlink(missing_ok=True)
            return output_dir, f"{len(included)}_clips", total_size

        # ── Step 1: Extract each event as .ts intermediate ────────────────────
        seg_files = []
        for i, ev in enumerate(included):
            seg_path = seg_dir / f"seg_{i:04d}.ts"
            seg_files.append(seg_path)
            start_s  = float(ev["start_s"])
            duration = float(ev["end_s"]) - start_s

            if do_reencode:
                video_flags = ["-c:v", "libx264", "-preset", "veryfast"]
                if output_quality == "720p":
                    video_flags += ["-vf", "scale=-2:720", "-crf", "28"]
                elif output_quality == "480p":
                    video_flags += ["-vf", "scale=-2:480", "-crf", "32"]
                else:
                    video_flags += ["-crf", "23"]
            else:
                video_flags = ["-c:v", "copy"]

            cmd = [
                get_ffmpeg(), "-hide_banner", "-loglevel", "error",
                "-fflags", "+genpts+igndts",
                "-ss", str(start_s),
                "-i", source_path,
                "-t", str(duration),
                *video_flags,
                *audio_flags,
                "-avoid_negative_ts", "make_zero",
                "-threads", str(FFMPEG_THREADS),
                "-y",
                str(seg_path),
            ]
            if logger:
                logger(f"[EXPORT] Segment {i+1}/{len(included)}: {start_s:.1f}s–{start_s+duration:.1f}s")
            _run_ffmpeg(cmd, logger)

            on_progress(0.5 + (i + 1) / len(included) * 0.4)

        # ── Step 2: Write concat.txt ──────────────────────────────────────────
        # Windows fix: use as_posix() so backslashes don't break FFmpeg concat demuxer
        concat_path = job_dir / "concat.txt"
        with open(concat_path, "w", encoding="utf-8") as f:
            for seg in seg_files:
                f.write(f"file '{seg.resolve().as_posix()}'\n")

        # ── Step 3: Write ffmetadata.txt (chapter markers) ───────────────────
        meta_path = job_dir / "ffmetadata.txt"
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(";FFMETADATA1\n")
            cumulative_ms = 0
            for i, ev in enumerate(included):
                dur_ms      = int((float(ev["end_s"]) - float(ev["start_s"])) * 1000)
                start_clock = ev.get("start_clock") or f"{float(ev['start_s']):.0f}s"
                f.write("[CHAPTER]\n")
                f.write("TIMEBASE=1/1000\n")
                f.write(f"START={cumulative_ms}\n")
                f.write(f"END={cumulative_ms + dur_ms}\n")
                f.write(f"title=Event {i+1} — {start_clock}\n")
                cumulative_ms += dur_ms

        # ── Step 4: Merge with concat demuxer ────────────────────────────────
        merge_cmd = [
            get_ffmpeg(), "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-i", str(meta_path),
            "-map_metadata", "1",
            "-c", "copy",
            "-threads", str(FFMPEG_THREADS),
            "-movflags", "+faststart",
            "-y",
            str(output_path),
        ]
        if logger:
            logger(f"[EXPORT] Merging segments into {output_name}")
        _run_ffmpeg(merge_cmd, logger)

        # ── Cleanup segments ──────────────────────────────────────────────────
        for seg in seg_files:
            seg.unlink(missing_ok=True)
        try:
            seg_dir.rmdir()
        except OSError:
            pass

        output_size = output_path.stat().st_size
        if logger:
            logger(f"[EXPORT] Done — {output_name} ({output_size / 1e6:.1f} MB)")

        on_progress(1.0)

        # ── Delete sentinel on success (FR-016) ───────────────────────────────
        sentinel.unlink(missing_ok=True)

        return output_path, output_name, output_size

    except Exception:
        # Sentinel intentionally NOT deleted on failure — startup scan will clean up
        raise


def generate_preview(
    source_path: str,
    start_s: float,
    end_s: float,
    token: str,
) -> str:
    """
    Extract a short clip for in-browser preview, always re-encoded to H.264/AAC.

    WHY re-encode instead of stream-copy:
    QWebEngineView embeds Chromium, which does NOT support HEVC/H.265, AV1, or
    many CCTV-specific codecs. Stream-copying an HEVC source produces a clip that
    "loads" (HTTP 200) but the <video> element silently fails to play.
    H.264 + AAC is universally supported by every Chromium version.
    ultrafast preset + crf 28 keeps re-encode time < 2s for a 15s preview clip.
    """
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out_path   = PREVIEW_DIR / f"{token}.mp4"
    clip_start = max(0.0, start_s - 2)
    clip_dur   = (end_s - start_s) + 4

    cmd = [
        get_ffmpeg(), "-hide_banner", "-loglevel", "error",
        "-ignore_editlist", "1",
        "-fflags", "+igndts+genpts",
        "-ss", str(clip_start),
        "-i", source_path,
        "-t", str(clip_dur),
        # Always encode to H.264 + AAC — the only codec pair guaranteed to work
        # in QWebEngineView / embedded Chromium regardless of source codec.
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-avoid_negative_ts", "make_zero",
        "-movflags", "faststart",
        "-y",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Preview generation failed: {proc.stderr.decode()[:400]}"
        )

    return str(out_path)
