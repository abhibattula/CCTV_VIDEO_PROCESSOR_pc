"""
Phase 6/7 — Video Intelligence Export
TDD tests for narrative_synthesizer and intel-report endpoints.
FrameDescriber tests removed in Phase 7 (T012) — replaced by FrameAnalyzer (Florence-2).
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
# Tests 7–12: API endpoint tests
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
    assert "md_path" in data and "florence_available" in data
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


# ---- ADD AT END OF FILE (C1 + M2 FIX) ----

def test_export_endpoint_accepts_formats_md_only(client, tmp_path, monkeypatch):
    """formats=["md"] → pdf_path is null in response"""
    import app.session as session_module
    # Put job in completed state with at least 1 event
    session_module.session.reset()
    session_module.session.update(
        job_id="test-job",
        status="completed",
        events=[{
            "event_index": 0, "start_s": 1.0, "duration_s": 1.0,
            "confidence": 0.8, "label": "person", "included": True,
            "thumbnail_path": str(tmp_path / "thumb_001.jpg"),
        }],
        output_path=str(tmp_path),
        source_path="test.mp4",
        source_info={"duration_s": 10.0, "fps": 25.0, "width": 1280, "height": 720},
    )
    # Create a dummy thumbnail so renderer doesn't crash
    (tmp_path / "thumb_001.jpg").write_bytes(b"")
    # Mock heavy operations to avoid actual Florence-2 / PDF generation
    monkeypatch.setattr("app.api.job.FrameAnalyzer", type("FA", (), {"is_available": staticmethod(lambda: False), "analyze": staticmethod(lambda p: {"caption": "", "object_caption": "", "detections": [], "clip_embedding_path": None})}), raising=False)
    monkeypatch.setattr("app.api.job.LLMSynthesizer", type("LS", (), {"is_available": staticmethod(lambda: False)}), raising=False)
    response = client.post("/api/job/intel-report/export", json={"formats": ["md"]})
    assert response.status_code == 200
    data = response.json()
    assert data["pdf_path"] is None


def test_export_response_has_required_ai_fields(client, tmp_path, monkeypatch):
    """Response must have florence_available (bool), llm_used (bool), llm_notice (str)"""
    import app.session as session_module
    session_module.session.reset()
    session_module.session.update(
        job_id="test-job2",
        status="completed",
        events=[{
            "event_index": 0, "start_s": 2.0, "duration_s": 1.0,
            "confidence": 0.7, "label": "vehicle", "included": True,
            "thumbnail_path": str(tmp_path / "thumb_002.jpg"),
        }],
        output_path=str(tmp_path),
        source_path="test.mp4",
        source_info={"duration_s": 15.0, "fps": 25.0, "width": 1280, "height": 720},
    )
    (tmp_path / "thumb_002.jpg").write_bytes(b"")
    monkeypatch.setattr("app.api.job.FrameAnalyzer", type("FA", (), {"is_available": staticmethod(lambda: False), "analyze": staticmethod(lambda p: {"caption": "", "object_caption": "", "detections": [], "clip_embedding_path": None})}), raising=False)
    monkeypatch.setattr("app.api.job.LLMSynthesizer", type("LS", (), {"is_available": staticmethod(lambda: False)}), raising=False)
    response = client.post("/api/job/intel-report/export", json={"formats": ["md"]})
    assert response.status_code == 200
    data = response.json()
    assert "florence_available" in data and isinstance(data["florence_available"], bool)
    assert "llm_used" in data and isinstance(data["llm_used"], bool)
    assert "llm_notice" in data and isinstance(data["llm_notice"], str)


def test_build_svg_timeline_returns_svg_string():
    """_build_svg_timeline returns string starting with <svg containing at least one <rect"""
    from app.core.intel_report_renderer import IntelReportRenderer
    renderer = IntelReportRenderer()
    events = [
        {"start_s": 5.0, "confidence": 0.9, "label": "person"},
        {"start_s": 30.0, "confidence": 0.5, "label": "vehicle"},
    ]
    result = renderer._build_svg_timeline(events, duration_s=60.0)
    assert isinstance(result, str)
    assert result.strip().startswith("<svg")
    assert "<rect" in result


def test_annotate_thumbnail_returns_base64_string(tmp_path):
    """_annotate_thumbnail returns non-empty base64 string; fallback when file missing"""
    from app.core.intel_report_renderer import IntelReportRenderer
    renderer = IntelReportRenderer()
    # Case 1: file missing — must return fallback base64 (not crash)
    result = renderer._annotate_thumbnail(tmp_path / "nonexistent.jpg", detections=[])
    assert isinstance(result, str) and len(result) > 0


def test_build_scene_breakdown_length(tmp_path):
    """_build_scene_breakdown: top 5 from 7 events; all 3 from 3 events; each entry has required keys"""
    from app.core.intel_report_renderer import IntelReportRenderer
    renderer = IntelReportRenderer()

    def make_event(i, conf):
        p = tmp_path / f"thumb_{i:03d}.jpg"
        p.write_bytes(b"")
        return {"event_index": i, "start_s": float(i), "duration_s": 1.0,
                "confidence": conf, "label": "person", "included": True,
                "thumbnail_path": str(p), "caption": "", "object_caption": "", "detections": []}

    events_7 = [make_event(i, 0.5 + i * 0.03) for i in range(7)]
    result_7 = renderer._build_scene_breakdown(events_7)
    assert len(result_7) == 5

    events_3 = [make_event(i, 0.6 + i * 0.1) for i in range(3)]
    result_3 = renderer._build_scene_breakdown(events_3)
    assert len(result_3) == 3

    required_keys = {"event_index", "start_clock", "end_clock", "caption", "object_caption", "detections", "annotated_thumb_b64"}
    for entry in result_3:
        assert required_keys.issubset(set(entry.keys()))


# ── Phase 8 test (T003) ──────────────────────────────────────────────────────

def test_scene_card_no_broken_img_when_b64_empty():
    """intel_report.html must NOT render a broken <img src="data:image/jpeg;base64,">
    when annotated_thumb_b64 is an empty string (FR-005)."""
    from app.core.intel_report_renderer import render as render_intel

    context = {
        "source_name": "test_video",
        "source_path": "/test/video.mp4",
        "generated_at": "2026-06-29 12:00:00",
        "detection_mode": "mog2",
        "duration_fmt": "00:01:00",
        "executive_summary": "Test summary.",
        "llm_notice": "",
        "stats": {
            "event_count": 1,
            "active_s": 3.0,
            "active_pct": 5.0,
            "busiest_period": "00:00:00",
            "avg_confidence": 0.6,
            "detection_mode": "mog2",
        },
        "object_inventory": [],
        "svg_timeline": "<svg width='100' height='20'></svg>",
        "timeline": [],
        "scene_breakdown": [{
            "event_index": 0,
            "start_clock": "00:00:00",
            "end_clock": "00:00:03",
            "caption": "",
            "object_caption": "",
            "detections": [],
            "annotated_thumb_b64": "",  # ← empty: triggers the bug
        }],
        "key_moments": [],
        "heatmap_b64": "",
        "settings": {"mode": "mog2", "sensitivity": 50},
        "florence_available": False,
        "events_json": "[]",
    }

    html = render_intel(context)

    broken = 'src="data:image/jpeg;base64,"'
    assert broken not in html, (
        "intel_report.html renders a broken img tag when annotated_thumb_b64 is ''. "
        "Fix: wrap the <img> in {% if entry.annotated_thumb_b64 %} in intel_report.html"
    )
