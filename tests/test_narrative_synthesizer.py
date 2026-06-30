"""
Phase 7 — UI/AI Overhaul
TDD fail-first tests for new NarrativeSynthesizer class methods.
These tests must FAIL until T004 adds temporal_analysis() and trend_direction()
to the NarrativeSynthesizer class in narrative_synthesizer.py.
"""
import pytest


def test_temporal_analysis_returns_correct_keys():
    """temporal_analysis() must return dict with early/middle/late/peak_third"""
    from app.core.narrative_synthesizer import NarrativeSynthesizer
    ns = NarrativeSynthesizer()
    events = [{"start_s": 5.0}, {"start_s": 35.0}, {"start_s": 55.0}]
    result = ns.temporal_analysis(events, duration_s=60.0)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"early", "middle", "late", "peak_third"}
    assert isinstance(result["early"], int)
    assert isinstance(result["middle"], int)
    assert isinstance(result["late"], int)
    assert result["peak_third"] in ("early", "middle", "late")


def test_temporal_analysis_distributes_into_thirds():
    """Events at 5s/35s/55s with duration=60 → one in each third"""
    from app.core.narrative_synthesizer import NarrativeSynthesizer
    ns = NarrativeSynthesizer()
    # 0-20s = early, 20-40s = middle, 40-60s = late
    events = [{"start_s": 5.0}, {"start_s": 35.0}, {"start_s": 55.0}]
    result = ns.temporal_analysis(events, duration_s=60.0)
    assert result["early"] == 1
    assert result["middle"] == 1
    assert result["late"] == 1


def test_trend_direction_returns_valid_string():
    """trend_direction() returns one of rising/falling/sporadic/uniform"""
    from app.core.narrative_synthesizer import NarrativeSynthesizer
    ns = NarrativeSynthesizer()
    events = [{"start_s": 5.0}, {"start_s": 15.0}]
    result = ns.trend_direction(events, duration_s=60.0)
    assert result in ("rising", "falling", "sporadic", "uniform")


def test_trend_direction_rising():
    """0 events in first half, 4 in second half → rising"""
    from app.core.narrative_synthesizer import NarrativeSynthesizer
    ns = NarrativeSynthesizer()
    # duration=60; first half=0-30s, second half=30-60s
    events = [
        {"start_s": 35.0}, {"start_s": 40.0},
        {"start_s": 50.0}, {"start_s": 55.0},
    ]
    result = ns.trend_direction(events, duration_s=60.0)
    assert result == "rising"


# Phase 10 additions — US4

def test_seconds_to_clock_zero():
    from app.core.narrative_synthesizer import seconds_to_clock
    assert seconds_to_clock(0) == "00:00"


def test_seconds_to_clock_90s():
    from app.core.narrative_synthesizer import seconds_to_clock
    assert seconds_to_clock(90) == "01:30"


def test_seconds_to_clock_over_hour():
    from app.core.narrative_synthesizer import seconds_to_clock
    assert seconds_to_clock(3661) == "01:01:01"


def test_seconds_to_clock_boundary_one_hour():
    from app.core.narrative_synthesizer import seconds_to_clock
    assert seconds_to_clock(3600) == "01:00:00"


def test_timeline_entries_returns_correct_structure():
    from app.core.narrative_synthesizer import timeline_entries
    events = [{"start_s": 0.0, "end_s": 1.0, "zone_label": None,
               "peak_motion_score": 0.8, "event_index": 0}]
    result = timeline_entries(events, {})
    assert len(result) == 1
    entry = result[0]
    for key in ("event_num", "start_clock", "end_clock", "duration_s",
                "label", "confidence_pct", "description"):
        assert key in entry


def test_timeline_entries_empty_list():
    from app.core.narrative_synthesizer import timeline_entries
    assert timeline_entries([], {}) == []


def test_timeline_entries_uses_description():
    from app.core.narrative_synthesizer import timeline_entries
    events = [{"start_s": 0.0, "end_s": 1.0, "zone_label": None,
               "peak_motion_score": 0.5, "event_index": 0}]
    result = timeline_entries(events, {0: "a person entered"})
    assert result[0]["description"] == "a person entered"


def test_timeline_entries_missing_description_defaults_to_na():
    from app.core.narrative_synthesizer import timeline_entries
    events = [{"start_s": 0.0, "end_s": 1.0, "zone_label": None,
               "peak_motion_score": 0.5, "event_index": 0}]
    result = timeline_entries(events, {})
    assert result[0]["description"] == "N/A"


def test_narrative_synthesizer_temporal_analysis():
    from app.core.narrative_synthesizer import NarrativeSynthesizer
    ns = NarrativeSynthesizer()
    events = [{"start_s": s} for s in [1, 2, 10, 11, 20, 21]]
    result = ns.temporal_analysis(events, 30)
    assert set(result.keys()) == {"early", "middle", "late", "peak_third"}


def test_narrative_synthesizer_trend_direction_rising():
    from app.core.narrative_synthesizer import NarrativeSynthesizer
    ns = NarrativeSynthesizer()
    events = [{"start_s": 60}, {"start_s": 70}, {"start_s": 80}]
    result = ns.trend_direction(events, 100)
    assert result == "rising"
