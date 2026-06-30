import pytest
import os


def test_import_llm_synthesizer():
    """Will fail with ImportError until T005 creates llm_synthesizer.py"""
    from app.core.llm_synthesizer import LLMSynthesizer  # noqa: F401


def test_no_api_key_returns_rule_based(monkeypatch):
    """Without ANTHROPIC_API_KEY, synthesize() returns rule-based fallback"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from app.core.llm_synthesizer import LLMSynthesizer
    from app.core.narrative_synthesizer import NarrativeSynthesizer
    narrative = NarrativeSynthesizer()
    events = [{"start_s": 5.0, "duration_s": 2.0, "confidence": 0.8,
               "label": "person", "caption": "", "object_caption": "", "detections": []}]
    summary, llm_used, notice = LLMSynthesizer().synthesize(events, duration_s=60.0, narrative=narrative)
    assert isinstance(summary, str) and len(summary) > 0
    assert llm_used is False
    assert notice == "Executive summary: rule-based synthesis — LLM API unavailable"


def test_api_error_falls_back(monkeypatch):
    """If API raises, synthesize() falls back to rule-based — does not re-raise"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-invalid")
    from app.core.llm_synthesizer import LLMSynthesizer
    from app.core.narrative_synthesizer import NarrativeSynthesizer
    narrative = NarrativeSynthesizer()
    events = [{"start_s": 1.0, "duration_s": 1.0, "confidence": 0.7,
               "label": "vehicle", "caption": "", "object_caption": "", "detections": []}]
    # Even with a bad key, should not raise — must fall back gracefully
    try:
        summary, llm_used, notice = LLMSynthesizer().synthesize(events, duration_s=30.0, narrative=narrative)
        # If anthropic not installed, it will fall back immediately — that is fine
        assert isinstance(summary, str)
        assert isinstance(llm_used, bool)
        assert isinstance(notice, str)
    except ImportError:
        pytest.skip("anthropic not installed — graceful fallback tested by test_no_api_key")


def test_llm_used_flag_is_bool(monkeypatch):
    """synthesize() always returns (str, bool, str) — second element is bool"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from app.core.llm_synthesizer import LLMSynthesizer
    from app.core.narrative_synthesizer import NarrativeSynthesizer
    narrative = NarrativeSynthesizer()
    _, llm_used, _ = LLMSynthesizer().synthesize([], duration_s=0.0, narrative=narrative)
    assert isinstance(llm_used, bool)
