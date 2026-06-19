"""
Post-detection thumbnail generation — PC version.
Runs after detection completes. Events come from session state, not database.
"""
import subprocess
from pathlib import Path
from typing import Callable

from app.config import JOBS_DIR
from app.utils.ffmpeg_path import get_ffmpeg


def run(
    job_id: str,
    source_path: str,
    events: list,
    logger: Callable[[str], None],
) -> None:
    """Generate 320x180 JPEG thumbnails for all events in this job."""
    if not events:
        return

    job_dir   = JOBS_DIR / job_id
    thumb_dir = job_dir / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    logger(f"[THUMBNAILS] Generating {len(events)} thumbnails…")

    for ev in events:
        idx     = ev.get("event_index", 0)
        mid_s   = (float(ev["start_s"]) + float(ev["end_s"])) / 2
        out_path = thumb_dir / f"{idx}.jpg"

        if out_path.exists():
            continue

        cmd = [
            get_ffmpeg(), "-hide_banner", "-loglevel", "error",
            "-ss", str(mid_s),
            "-i", source_path,
            "-frames:v", "1",
            "-vf", "scale=320:180",
            "-q:v", "5",
            "-y",
            str(out_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=15)

    logger("[THUMBNAILS] Done")
