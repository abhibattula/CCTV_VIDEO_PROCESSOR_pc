"""
Phase 15 T013 — tests for app/utils/ai_device.py (opportunistic GPU for AI).
Written BEFORE the implementation (constitution III).
"""
import sys
import types

import pytest

import app.utils.ai_device as ai_device


@pytest.fixture(autouse=True)
def _reset():
    ai_device._reset_for_tests()
    yield
    ai_device._reset_for_tests()


def _fake_torch(cuda_available: bool, name: str = "FakeGPU"):
    torch = types.ModuleType("torch")
    cuda = types.SimpleNamespace(
        is_available=lambda: cuda_available,
        get_device_name=lambda idx=0: name,
    )
    torch.cuda = cuda
    return torch


def test_cpu_when_torch_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    assert ai_device.get_ai_device() == "cpu"
    assert ai_device.describe_ai_device() == "cpu"


def test_cpu_when_cuda_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(False))
    assert ai_device.get_ai_device() == "cpu"
    assert ai_device.describe_ai_device() == "cpu"


def test_cuda_when_available(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(True, "NVIDIA Test 3060"))
    assert ai_device.get_ai_device() == "cuda"
    assert ai_device.describe_ai_device() == "cuda:0 — NVIDIA Test 3060"


def test_result_is_cached(monkeypatch):
    calls = []
    torch = _fake_torch(True)
    orig = torch.cuda.is_available
    torch.cuda = types.SimpleNamespace(
        is_available=lambda: (calls.append(1), orig())[1],
        get_device_name=lambda idx=0: "FakeGPU",
    )
    monkeypatch.setitem(sys.modules, "torch", torch)
    ai_device.get_ai_device()
    ai_device.get_ai_device()
    assert len(calls) == 1


def test_never_raises_on_broken_torch(monkeypatch):
    torch = types.ModuleType("torch")

    class _BoomCuda:
        def is_available(self):
            raise RuntimeError("driver exploded")

    torch.cuda = _BoomCuda()
    monkeypatch.setitem(sys.modules, "torch", torch)
    assert ai_device.get_ai_device() == "cpu"


def test_on_this_machine_resolves_without_error():
    """Whatever the machine, the probe must return one of the two values."""
    assert ai_device.get_ai_device() in ("cpu", "cuda")
