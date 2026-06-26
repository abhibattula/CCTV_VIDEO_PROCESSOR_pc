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
