"""
Resolves the bundled FFmpeg and FFprobe binaries from imageio-ffmpeg.
Falls back to system FFmpeg if the bundle is unavailable.
"""
import shutil
from functools import lru_cache


@lru_cache(maxsize=1)
def get_ffmpeg() -> str:
    """Return absolute path to ffmpeg binary. Raises RuntimeError if not found."""
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path:
            return path
    except Exception:
        pass

    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path

    raise RuntimeError(
        "FFmpeg not found. Install imageio-ffmpeg: pip install imageio-ffmpeg"
    )


@lru_cache(maxsize=1)
def get_ffprobe() -> str:
    """Return absolute path to ffprobe binary. Raises RuntimeError if not found."""
    try:
        import imageio_ffmpeg
        # imageio-ffmpeg bundles ffprobe alongside ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_path:
            import os
            stem = os.path.splitext(ffmpeg_path)[0]
            ext = ".exe" if os.name == "nt" else ""
            # Replace "ffmpeg" with "ffprobe" in the binary name
            probe_path = stem.replace("ffmpeg", "ffprobe") + ext
            if os.path.isfile(probe_path):
                return probe_path
    except Exception:
        pass

    system_path = shutil.which("ffprobe")
    if system_path:
        return system_path

    raise RuntimeError(
        "ffprobe not found. Install imageio-ffmpeg: pip install imageio-ffmpeg"
    )
