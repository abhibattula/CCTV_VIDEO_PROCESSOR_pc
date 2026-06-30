"""
Tests for LogBuffer pub/sub mechanics (US3, Phase 10).
Each test uses a fresh LogBuffer() instance — not the module-level singleton.
"""
import asyncio
from unittest.mock import MagicMock

import pytest

import app.core.log_buffer as log_buffer_mod
from app.core.log_buffer import LogBuffer

_JOB = "job-test"
_JOB_A = "job-a"
_JOB_B = "job-b"


def test_subscribe_replays_history():
    buf = LogBuffer()
    buf.append(_JOB, "line1")
    buf.append(_JOB, "line2")
    buf.append(_JOB, "line3")
    q = buf.subscribe(_JOB)
    assert q.qsize() == 3


def test_append_calls_call_soon_threadsafe():
    buf = LogBuffer()
    q = buf.subscribe(_JOB)
    mock_loop = MagicMock()
    buf._loop = mock_loop
    buf.append(_JOB, "hello")
    mock_loop.call_soon_threadsafe.assert_called_once_with(q.put_nowait, "hello")


def test_ring_buffer_cap(monkeypatch):
    monkeypatch.setattr(log_buffer_mod, "LOG_RING_SIZE", 3)
    buf = LogBuffer()
    for i in range(4):
        buf.append(_JOB, f"line{i}")
    q = buf.subscribe(_JOB)
    assert q.qsize() == 3


def test_reset_clears_only_target_job():
    buf = LogBuffer()
    buf.append(_JOB_A, "a1")
    buf.append(_JOB_B, "b1")
    buf.append(_JOB_B, "b2")
    buf.reset(_JOB_A)
    q_b = buf.subscribe(_JOB_B)
    assert q_b.qsize() == 2
    q_a = buf.subscribe(_JOB_A)
    assert q_a.qsize() == 0


def test_close_sends_done_sentinel():
    buf = LogBuffer()
    q = buf.subscribe(_JOB)
    mock_loop = MagicMock()
    buf._loop = mock_loop
    buf.close(_JOB)
    mock_loop.call_soon_threadsafe.assert_called_once_with(q.put_nowait, "__DONE__")
