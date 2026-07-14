"""
Tests for app/core/search_index.py — the on-demand CLIP search index
(014-clip-event-search). No network, no real model: ClipIndexer is
monkeypatched throughout; vectors are synthetic.
"""
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from app.core import search_index as si
from app.core.clip_indexer import ClipIndexer


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _events(n):
    return [
        {"event_index": i, "start_s": float(i), "end_s": float(i) + 1.0, "included": True}
        for i in range(n)
    ]


def _unit(vec):
    v = np.asarray(vec, dtype="float32")
    return v / np.linalg.norm(v)


def _vec_for(i):
    """Deterministic distinct unit vector per event index."""
    v = np.zeros(512, dtype="float32")
    v[i % 512] = 1.0
    return v


@pytest.fixture(autouse=True)
def _clean_registry(tmp_path, monkeypatch):
    """Isolate every test: fresh registry, JOBS_DIR under tmp."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "JOBS_DIR", tmp_path / "jobs")
    si._reset_for_tests()
    yield
    si._reset_for_tests()


def _fake_embed_factory(job_dir: Path, fail_indices=()):
    """ClipIndexer.embed stand-in: writes a synthetic sidecar next to the thumb."""
    def _fake_embed(image_path: Path):
        idx = int(Path(image_path).stem)
        if idx in fail_indices:
            return None  # embed failure for this event
        sidecar = Path(image_path).parent / (Path(image_path).stem + ".clip.npy")
        np.save(str(sidecar), _vec_for(idx))
        return str(sidecar)
    return _fake_embed


def _prepare_thumbs(job_dir: Path, n):
    tdir = job_dir / "thumbnails"
    tdir.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (tdir / f"{i}.jpg").write_bytes(b"fakejpg")
    return tdir


def _wait_state(*states, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if si.get_status()["state"] in states:
            return si.get_status()
        time.sleep(0.02)
    raise AssertionError(f"registry never reached {states}: {si.get_status()}")


def _start(monkeypatch, job_id, events, job_dir, fail_indices=(), available=True):
    monkeypatch.setattr(ClipIndexer, "is_available", classmethod(lambda cls: available))
    monkeypatch.setattr(ClipIndexer, "embed",
                        staticmethod(_fake_embed_factory(job_dir, fail_indices)))
    monkeypatch.setattr(si, "_generate_thumbnails", lambda *a, **k: None)
    return si.start_background_index(job_id=job_id, source_path="/fake/video.mp4",
                                     events=events)


# ---------------------------------------------------------------------------
# Status registry lifecycle
# ---------------------------------------------------------------------------

def test_initial_status_idle():
    st = si.get_status()
    assert st["state"] == "idle"
    assert st["done"] == 0 and st["total"] == 0
    assert st["reason"] == ""


def test_index_builds_to_ready(tmp_path, monkeypatch):
    import app.config as cfg
    job_dir = cfg.JOBS_DIR / "job1"
    _prepare_thumbs(job_dir, 3)

    assert _start(monkeypatch, "job1", _events(3), job_dir) is True
    st = _wait_state("ready")
    assert st["done"] == 3 and st["total"] == 3


def test_concurrent_start_rejected(tmp_path, monkeypatch):
    import app.config as cfg
    job_dir = cfg.JOBS_DIR / "job1"
    _prepare_thumbs(job_dir, 2)

    release = threading.Event()
    real_factory = _fake_embed_factory(job_dir)

    def slow_embed(image_path):
        release.wait(timeout=5)
        return real_factory(image_path)

    monkeypatch.setattr(ClipIndexer, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(ClipIndexer, "embed", staticmethod(slow_embed))
    monkeypatch.setattr(si, "_generate_thumbnails", lambda *a, **k: None)

    assert si.start_background_index("job1", "/v.mp4", _events(2)) is True
    try:
        assert si.start_background_index("job1", "/v.mp4", _events(2)) is False
    finally:
        release.set()
        _wait_state("ready")


def test_staleness_different_job_rebuilds(tmp_path, monkeypatch):
    import app.config as cfg
    for jid, n in (("job1", 2), ("job2", 3)):
        job_dir = cfg.JOBS_DIR / jid
        _prepare_thumbs(job_dir, n)
        assert _start(monkeypatch, jid, _events(n), job_dir) is True
        st = _wait_state("ready")
    assert st["total"] == 3  # second build reflects job2's events


def test_staleness_changed_event_count_rebuilds(tmp_path, monkeypatch):
    import app.config as cfg
    job_dir = cfg.JOBS_DIR / "job1"
    _prepare_thumbs(job_dir, 4)

    assert _start(monkeypatch, "job1", _events(2), job_dir) is True
    _wait_state("ready")
    # Detection re-ran: same job_id, more events → must start a fresh build
    assert _start(monkeypatch, "job1", _events(4), job_dir) is True
    st = _wait_state("ready")
    assert st["total"] == 4


def test_ready_same_job_does_not_rebuild(tmp_path, monkeypatch):
    import app.config as cfg
    job_dir = cfg.JOBS_DIR / "job1"
    _prepare_thumbs(job_dir, 2)

    assert _start(monkeypatch, "job1", _events(2), job_dir) is True
    _wait_state("ready")
    assert _start(monkeypatch, "job1", _events(2), job_dir) is False  # warm no-op


def test_per_event_embed_failure_skips_event(tmp_path, monkeypatch):
    import app.config as cfg
    job_dir = cfg.JOBS_DIR / "job1"
    _prepare_thumbs(job_dir, 3)

    assert _start(monkeypatch, "job1", _events(3), job_dir, fail_indices=(1,)) is True
    _wait_state("ready")
    results = si.rank_with_vector(_vec_for(1))
    assert [r[0] for r in results] == [0, 2]  # event 1 absent, run still ready


def test_unavailable_when_clip_missing(tmp_path, monkeypatch):
    import app.config as cfg
    job_dir = cfg.JOBS_DIR / "job1"
    _prepare_thumbs(job_dir, 1)

    assert _start(monkeypatch, "job1", _events(1), job_dir, available=False) is False
    st = si.get_status()
    assert st["state"] == "unavailable"
    assert st["reason"] != ""


def test_unavailable_recovers_after_models_downloaded(tmp_path, monkeypatch):
    """US3-AC3: CLIP downloaded mid-session (via the AI Models card) must make
    search usable without an app restart — is_available() is re-checked on
    every index request, so a previous 'unavailable' verdict never sticks."""
    import app.config as cfg
    job_dir = cfg.JOBS_DIR / "job1"
    _prepare_thumbs(job_dir, 1)

    assert _start(monkeypatch, "job1", _events(1), job_dir, available=False) is False
    assert si.get_status()["state"] == "unavailable"

    # Models arrive mid-session → the next request proceeds normally
    assert _start(monkeypatch, "job1", _events(1), job_dir, available=True) is True
    st = _wait_state("ready")
    assert st["done"] == 1


def test_error_state_is_recoverable(tmp_path, monkeypatch):
    import app.config as cfg
    job_dir = cfg.JOBS_DIR / "job1"
    _prepare_thumbs(job_dir, 1)

    monkeypatch.setattr(ClipIndexer, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(si, "_generate_thumbnails",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk on fire")))
    monkeypatch.setattr(si, "_load_or_embed",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk on fire")))
    assert si.start_background_index("job1", "/v.mp4", _events(1)) is True
    st = _wait_state("ready", "error")
    if st["state"] == "error":
        assert st["reason"] != ""
        # A new request from error retries with a fresh build (contract)
        assert _start(monkeypatch, "job1", _events(1), job_dir) is True
        _wait_state("ready")


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def test_rank_orders_by_cosine_desc_with_index_tiebreak(monkeypatch):
    q = _unit(np.ones(512))
    vectors = {
        0: _unit(np.ones(512)),                      # cos = 1.0
        1: _vec_for(1),                               # cos small
        2: _unit(np.ones(512)),                      # cos = 1.0 (tie with 0)
    }
    si._set_ready_index_for_tests("jobX", vectors)
    results = si.rank_with_vector(q)
    assert [r[0] for r in results] == [0, 2, 1]      # desc score, asc index tiebreak
    assert results[0][1] == pytest.approx(1.0, abs=1e-5)


def test_rank_ready_with_zero_vectors_returns_empty():
    si._set_ready_index_for_tests("jobX", {})
    assert si.rank_with_vector(_unit(np.ones(512))) == []


def test_rank_text_uses_embed_text_once(monkeypatch):
    calls = []

    def fake_embed_text(text):
        calls.append(text)
        return _unit(np.ones(512))

    monkeypatch.setattr(ClipIndexer, "embed_text", staticmethod(fake_embed_text))
    si._set_ready_index_for_tests("jobX", {0: _vec_for(0)})
    results = si.rank("red jacket")
    assert calls == ["red jacket"]
    assert len(results) == 1


def test_rank_text_returns_none_when_embed_text_unavailable(monkeypatch):
    monkeypatch.setattr(ClipIndexer, "embed_text", staticmethod(lambda t: None))
    si._set_ready_index_for_tests("jobX", {0: _vec_for(0)})
    assert si.rank("query") is None


# ---------------------------------------------------------------------------
# Sidecar reuse (T012)
# ---------------------------------------------------------------------------

def test_index_reuses_existing_sidecars(tmp_path, monkeypatch):
    import app.config as cfg
    job_dir = cfg.JOBS_DIR / "job1"
    tdir = _prepare_thumbs(job_dir, 3)

    # Event 0 already embedded by a prior Intelligence Report run
    np.save(str(tdir / "0.clip.npy"), _vec_for(0))

    embed_calls = []
    real_factory = _fake_embed_factory(job_dir)

    def counting_embed(image_path):
        embed_calls.append(Path(image_path).stem)
        return real_factory(image_path)

    monkeypatch.setattr(ClipIndexer, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(ClipIndexer, "embed", staticmethod(counting_embed))
    monkeypatch.setattr(si, "_generate_thumbnails", lambda *a, **k: None)

    assert si.start_background_index("job1", "/v.mp4", _events(3)) is True
    _wait_state("ready")
    assert sorted(embed_calls) == ["1", "2"]  # 0 was reused, not re-embedded
    # And the reused vector is actually in the index
    results = si.rank_with_vector(_vec_for(0))
    assert results[0][0] == 0


def test_reset_index_returns_to_idle(tmp_path, monkeypatch):
    si._set_ready_index_for_tests("jobX", {0: _vec_for(0)})
    si.reset_index()
    assert si.get_status()["state"] == "idle"
    assert si.rank_with_vector(_vec_for(0)) is None  # no index → None
