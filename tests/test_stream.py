"""Tests for new SSE event types in app/api/stream.py (Phase 7 report progress)."""
import json
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
import app.session as session_module

@pytest.fixture(autouse=True)
def reset_session():
    session_module.session.reset()
    yield
    session_module.session.reset()


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


def _read_sse_events(client, n=5):
    """Read the first n SSE data lines from /api/stream, return parsed dicts."""
    events = []
    with client.stream("GET", "/api/stream") as response:
        for line in response.iter_lines():
            if line.startswith("data:"):
                raw = line[5:].strip()
                try:
                    events.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
            if len(events) >= n:
                break
    return events


def test_report_stage_event_emitted_when_stage_set(client):
    """When report_stage is set in session, SSE emits report_stage event"""
    session_module.session.update(
        report_stage="thumbnails",
        report_stage_current=3,
        report_stage_total=10,
        report_stage_timestamp="",
    )
    events = _read_sse_events(client, n=10)
    stage_events = [e for e in events if e.get("type") == "report_stage"]
    assert len(stage_events) >= 1
    ev = stage_events[0]
    assert ev["stage"] == "thumbnails"
    assert "current" in ev
    assert "total" in ev
    assert "ts" in ev


def test_report_done_event_emitted_when_pending(client):
    """When report_done_pending=True, SSE emits report_done and resets flag"""
    session_module.session.update(
        report_done_pending=True,
        report_stage="",
        report_stage_current=0,
        report_stage_total=0,
        report_stage_timestamp="",
    )
    events = _read_sse_events(client, n=10)
    done_events = [e for e in events if e.get("type") == "report_done"]
    assert len(done_events) >= 1
    # After emission the flag must be reset
    snap = session_module.session.snapshot()
    assert snap.get("report_done_pending") is False


def test_no_report_events_when_idle(client):
    """When session is idle (default state), no report_stage or report_done events emitted"""
    # Session is in default state (reset by autouse fixture)
    events = _read_sse_events(client, n=8)
    report_events = [e for e in events if e.get("type") in ("report_stage", "report_done")]
    assert len(report_events) == 0


# ── Phase 8 test (T006) ──────────────────────────────────────────────────────

def test_sse_generator_handles_client_disconnect():
    """Generator must terminate cleanly when ConnectionResetError is thrown into it
    at a yield point (simulates Starlette propagating a socket-send failure)."""
    import asyncio
    from app.api.stream import _event_generator
    import app.session as session_module
    session_module.session.reset()

    async def _run():
        gen = _event_generator("test-job")
        # Prime the generator — returns the first keepalive chunk
        first = await gen.__anext__()
        assert "data:" in first

        # Throw a connection error at the current yield suspension point
        try:
            await gen.athrow(ConnectionResetError("peer closed connection"))
        except StopAsyncIteration:
            return  # Generator terminated cleanly — correct after fix
        except ConnectionResetError:
            raise AssertionError(
                "Generator propagated ConnectionResetError instead of handling it. "
                "Fix: wrap yield statements in try/except Exception in stream.py"
            )
        # If athrow() returned a value (generator yielded again), that is also acceptable

    asyncio.run(_run())
