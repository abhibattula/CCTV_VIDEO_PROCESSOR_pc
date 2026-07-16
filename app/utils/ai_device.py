"""
Opportunistic GPU selection for the AI stages (YOLO, Florence-2, CLIP).

CPU-only machines (including every shipped installer, which bundles CPU-only
torch) resolve to "cpu" and behave exactly as before — the probe must never
change behavior or raise on a machine without CUDA.
"""
import threading
from typing import Optional

_lock = threading.Lock()
_device: Optional[str] = None
_description: Optional[str] = None


def _reset_for_tests() -> None:
    global _device, _description
    with _lock:
        _device = None
        _description = None


def _probe() -> tuple[str, str]:
    try:
        import torch
        if torch.cuda.is_available():
            try:
                name = torch.cuda.get_device_name(0)
            except Exception:
                name = "CUDA GPU"
            return "cuda", f"cuda:0 — {name}"
    except Exception:
        pass
    return "cpu", "cpu"


def get_ai_device() -> str:
    """"cuda" iff torch is importable and CUDA is available, else "cpu"."""
    global _device, _description
    with _lock:
        if _device is None:
            _device, _description = _probe()
        return _device


def describe_ai_device() -> str:
    """Human-readable device string for the capabilities endpoint."""
    global _device, _description
    with _lock:
        if _description is None:
            _device, _description = _probe()
        return _description
