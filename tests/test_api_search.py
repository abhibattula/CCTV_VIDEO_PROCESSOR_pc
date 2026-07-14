"""
Endpoint contract tests for /api/search/* (014-clip-event-search).
Contracts: specs/014-clip-event-search/contracts/search-api.md
No model, no network — search_index internals are injected/monkeypatched.
"""
import numpy as np
import pytest

import app.session as session
from app.core import search_index as si


def _unit(vec):
    v = np.asarray(vec, dtype="float32")
    return v / np.linalg.norm(v)


def _vec_for(i):
    v = np.zeros(512, dtype="float32")
    v[i % 512] = 1.0
    return v


@pytest.fixture(autouse=True)
def _clean_index():
    si._reset_for_tests()
    yield
    si._reset_for_tests()


def _completed_job(n_events=3):
    session.reset()
    session.update(
        job_id="job-s1",
        source_path="/fake/video.mp4",
        status="completed",
        events=[
            {"event_index": i, "start_s": float(i), "end_s": float(i) + 1.0,
             "included": True}
            for i in range(n_events)
        ],
        event_count=n_events,
    )


# ---------------------------------------------------------------------------
# GET /api/search/status  (T006)
# ---------------------------------------------------------------------------

def test_status_shape(client):
    r = client.get("/api/search/status")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"state", "done", "total", "reason"}
    assert data["state"] == "idle"


# ---------------------------------------------------------------------------
# POST /api/search/index  (T010)
# ---------------------------------------------------------------------------

def test_index_400_when_no_job(client):
    r = client.post("/api/search/index")
    assert r.status_code == 400


def test_index_400_while_detecting(client):
    _completed_job()
    session.update(status="detecting")
    r = client.post("/api/search/index")
    assert r.status_code == 400


def test_index_starts_build(client, monkeypatch):
    _completed_job()
    calls = []
    monkeypatch.setattr(si, "start_background_index",
                        lambda job_id, source_path, events: calls.append(job_id) or True)
    r = client.post("/api/search/index")
    assert r.status_code == 200
    body = r.json()
    assert body["started"] is True
    assert "status" in body and "state" in body["status"]
    assert calls == ["job-s1"]


def test_index_reports_already_running(client, monkeypatch):
    _completed_job()
    monkeypatch.setattr(si, "start_background_index", lambda **kw: False)
    r = client.post("/api/search/index")
    assert r.status_code == 200
    assert r.json()["started"] is False


# ---------------------------------------------------------------------------
# POST /api/search/query  (T007/T008)
# ---------------------------------------------------------------------------

def test_query_400_when_no_job(client):
    r = client.post("/api/search/query", json={"text": "person"})
    assert r.status_code == 400


def test_query_400_on_empty_text(client):
    _completed_job()
    si._set_ready_index_for_tests("job-s1", {0: _vec_for(0)})
    for bad in ("", "   "):
        r = client.post("/api/search/query", json={"text": bad})
        assert r.status_code == 400


def test_query_409_when_index_not_ready(client):
    _completed_job()  # registry stays idle
    r = client.post("/api/search/query", json={"text": "person"})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["status"]["state"] == "idle"


def test_query_409_when_unavailable(client, monkeypatch):
    _completed_job()
    with si._lock:
        si._status.update(state="unavailable", reason="CLIP weights missing")
    r = client.post("/api/search/query", json={"text": "person"})
    assert r.status_code == 409
    assert r.json()["detail"]["status"]["state"] == "unavailable"


def test_query_returns_sorted_results(client, monkeypatch):
    _completed_job()
    si._set_ready_index_for_tests("job-s1", {
        0: _unit(np.ones(512)),   # cos 1.0 vs query
        1: _vec_for(1),           # low
        2: _unit(np.ones(512)),   # cos 1.0 — tie with 0
    })
    from app.core.clip_indexer import ClipIndexer
    monkeypatch.setattr(
        ClipIndexer, "embed_text", staticmethod(lambda t: _unit(np.ones(512)))
    )
    r = client.post("/api/search/query", json={"text": "bright scene"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert [x["event_index"] for x in results] == [0, 2, 1]
    assert results[0]["score"] == pytest.approx(1.0, abs=1e-5)
    # Failed-embed events simply absent: only the 3 indexed events appear
    assert len(results) == 3


def test_query_encodes_text_exactly_once(client, monkeypatch):
    _completed_job()
    si._set_ready_index_for_tests("job-s1", {0: _vec_for(0)})
    calls = []
    from app.core.clip_indexer import ClipIndexer

    def counting(t):
        calls.append(t)
        return _unit(np.ones(512))

    monkeypatch.setattr(ClipIndexer, "embed_text", staticmethod(counting))
    r = client.post("/api/search/query", json={"text": "one encode"})
    assert r.status_code == 200
    assert calls == ["one encode"]  # FR-013: exactly one text encode per query
