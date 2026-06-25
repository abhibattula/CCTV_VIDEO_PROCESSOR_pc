"""
Phase 6 — Video Intelligence Export
TDD fail-first tests for narrative_synthesizer, frame_describer, and intel-report endpoints.
ALL 12 tests must FAIL before any implementation exists.

Imports of non-existent modules are placed inside each test function so pytest
can collect all 12 tests individually and report each one as FAILED/ERROR.
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixture — same pattern as tests/test_api_job.py
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

def _seed_intel_events(n=2, output_dir=None):
    import app.session as session
    session.reset()
    session.update(
        status="completed",
        job_id="test-job",
        source_path="/fake/video.mp4",
        source_info={"duration_s": 60.0, "width": 1920, "height": 1080},
        settings={"mode": "mog2", "sensitivity": 50},
        output_dir=str(output_dir) if output_dir else None,
    )
    for i in range(n):
        session.append_event({
            "event_index": i,
            "start_s": float(i * 5),
            "end_s": float(i * 5 + 3),
            "start_clock": f"00:00:0{i*5}",
            "end_clock": f"00:00:0{i*5+3}",
            "peak_motion_score": 0.6 + i * 0.1,
            "zone_label": None,  # MOG2 — zone_label is None
            "included": True,
        })


# ---------------------------------------------------------------------------
# Tests 1–6: narrative_synthesizer unit tests
# ---------------------------------------------------------------------------

def test_executive_summary_yolo_mentions_objects():
    from app.core.narrative_synthesizer import executive_summary
    events = [{"zone_label": "person", "start_s": 0, "end_s": 2,
               "peak_motion_score": 0.8, "included": True, "event_index": 0,
               "start_clock": "00:00:00", "end_clock": "00:00:02"}]
    result = executive_summary(events, {"duration_s": 60}, {"mode": "yolo"})
    assert isinstance(result, str) and "person" in result.lower()


def test_executive_summary_mog2_mentions_motion():
    from app.core.narrative_synthesizer import executive_summary
    events = [{"zone_label": None, "start_s": 0, "end_s": 2,
               "peak_motion_score": 0.6, "included": True, "event_index": 0,
               "start_clock": "00:00:00", "end_clock": "00:00:02"}]
    result = executive_summary(events, {"duration_s": 60}, {"mode": "mog2"})
    assert isinstance(result, str) and "motion" in result.lower()


def test_executive_summary_no_events_safe_fallback():
    from app.core.narrative_synthesizer import executive_summary
    result = executive_summary([], {"duration_s": 60}, {"mode": "mog2"})
    assert isinstance(result, str) and len(result) > 0


def test_object_inventory_counts_classes():
    from app.core.narrative_synthesizer import object_inventory
    events = (
        [{"zone_label": "person", "start_s": i, "end_s": i + 1,
          "peak_motion_score": 0.5, "included": True, "event_index": i,
          "start_clock": "00:00:00", "end_clock": "00:00:01"} for i in range(3)]
        + [{"zone_label": "car", "start_s": i, "end_s": i + 1,
            "peak_motion_score": 0.5, "included": True, "event_index": 3 + i,
            "start_clock": "00:00:00", "end_clock": "00:00:01"} for i in range(2)]
    )
    result = object_inventory(events)
    assert result[0]["label"] == "person" and result[0]["count"] == 3
    assert result[1]["label"] == "car" and result[1]["count"] == 2


def test_object_inventory_empty_for_mog2():
    from app.core.narrative_synthesizer import object_inventory
    events = [{"zone_label": None, "start_s": 0, "end_s": 2,
               "peak_motion_score": 0.6, "included": True, "event_index": 0,
               "start_clock": "00:00:00", "end_clock": "00:00:02"}]
    assert object_inventory(events) == []


def test_activity_stats_correct_percentages():
    from app.core.narrative_synthesizer import activity_stats
    # 2 events each 3s long = 6s active out of 60s = 10%
    events = [
        {"start_s": 0, "end_s": 3, "peak_motion_score": 0.5, "zone_label": None,
         "included": True, "event_index": 0, "start_clock": "00:00:00", "end_clock": "00:00:03"},
        {"start_s": 10, "end_s": 13, "peak_motion_score": 0.7, "zone_label": None,
         "included": True, "event_index": 1, "start_clock": "00:00:10", "end_clock": "00:00:13"},
    ]
    stats = activity_stats(events, {"duration_s": 60.0})
    assert stats["event_count"] == 2
    assert abs(stats["active_pct"] - 10.0) < 0.1


# ---------------------------------------------------------------------------
# Tests 7–8: frame_describer unit tests
# ---------------------------------------------------------------------------

def test_frame_describer_absent_returns_empty(monkeypatch, tmp_path):
    from app.core.frame_describer import FrameDescriber
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "moondream":
            raise ImportError("moondream not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    FrameDescriber._model = None
    result = FrameDescriber.describe(tmp_path / "fake.jpg")
    assert result == ""


def test_frame_describer_missing_file_returns_empty(tmp_path):
    from app.core.frame_describer import FrameDescriber
    # Only applies when moondream IS importable — test the file-not-found path.
    # If moondream is not installed this also returns "" from is_available() check.
    result = FrameDescriber.describe(tmp_path / "nonexistent_12345.jpg")
    assert result == ""


# ---------------------------------------------------------------------------
# Tests 9–12: API endpoint tests
# ---------------------------------------------------------------------------

def test_intel_report_html_400_no_job(client):
    import app.session as session
    session.reset()  # idle state, no job_id
    resp = client.get("/api/job/intel-report.html")
    assert resp.status_code == 400


def test_intel_report_html_400_no_included_events(client):
    import app.session as session
    session.reset()
    session.update(status="completed", job_id="test-job", source_path="/fake/video.mp4",
                   source_info={"duration_s": 60.0}, settings={"mode": "mog2"})
    # Add an event but mark it excluded
    session.append_event({"event_index": 0, "start_s": 0, "end_s": 2,
                          "peak_motion_score": 0.5, "zone_label": None,
                          "included": False, "start_clock": "00:00:00", "end_clock": "00:00:02"})
    resp = client.get("/api/job/intel-report.html")
    assert resp.status_code == 400


def test_intel_report_export_writes_md_file(client, tmp_path, monkeypatch):
    import app.session as session
    session.reset()
    session.update(status="completed", job_id="test-job", source_path="/fake/video.mp4",
                   source_info={"duration_s": 60.0}, settings={"mode": "mog2"},
                   output_dir=str(tmp_path))
    session.append_event({"event_index": 0, "start_s": 0, "end_s": 3,
                          "peak_motion_score": 0.6, "zone_label": None,
                          "included": True, "start_clock": "00:00:00", "end_clock": "00:00:03"})
    # Monkeypatch thumbnail_gen.run to no-op (thumbnails don't exist)
    monkeypatch.setattr("app.api.job.thumbnail_gen.run", lambda *a, **kw: None)
    resp = client.post("/api/job/intel-report/export")
    assert resp.status_code == 200
    data = resp.json()
    assert "md_path" in data and "moondream_available" in data
    assert Path(data["md_path"]).exists()


def test_intel_report_markdown_has_json_appendix(client, tmp_path, monkeypatch):
    import app.session as session
    session.reset()
    session.update(status="completed", job_id="test-job", source_path="/fake/video.mp4",
                   source_info={"duration_s": 60.0}, settings={"mode": "mog2"},
                   output_dir=str(tmp_path))
    session.append_event({"event_index": 0, "start_s": 0, "end_s": 3,
                          "peak_motion_score": 0.6, "zone_label": None,
                          "included": True, "start_clock": "00:00:00", "end_clock": "00:00:03"})
    monkeypatch.setattr("app.api.job.thumbnail_gen.run", lambda *a, **kw: None)
    resp = client.post("/api/job/intel-report/export")
    assert resp.status_code == 200
    import json
    import re
    content = Path(resp.json()["md_path"]).read_text(encoding="utf-8")
    match = re.search(r'```json\n(.*?)```', content, re.DOTALL)
    assert match, "No JSON appendix found in Markdown"
    events = json.loads(match.group(1))
    assert len(events) > 0
    assert "event_index" in events[0]
