"""
Wall-clock and elapsed time utilities for the PC version.

PC version receives recording_start as "HH:MM:SS" string typed by the user,
NOT as ISO 8601 timestamp from NVR metadata (that was the Pi version).
"""


def clock_to_seconds(hms: str) -> int:
    """Convert 'HH:MM:SS' string to total integer seconds."""
    parts = hms.strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"Expected HH:MM:SS, got: {hms!r}")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return h * 3600 + m * 60 + s


def seconds_to_clock(offset_s: float, recording_start: str | None = None) -> str:
    """
    Convert an offset in seconds to a display clock string.

    If recording_start ('HH:MM:SS') is provided, return the absolute wall-clock
    time at that offset.  Otherwise return the elapsed time HH:MM:SS.

    Examples:
      seconds_to_clock(3661, None)        == "01:01:01"
      seconds_to_clock(600, "08:00:00")   == "08:10:00"
    """
    total = int(offset_s)
    if recording_start is not None:
        base = clock_to_seconds(recording_start)
        total = base + total

    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
