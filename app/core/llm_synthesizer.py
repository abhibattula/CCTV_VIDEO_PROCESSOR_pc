"""Claude Haiku API wrapper for executive summary generation. Falls back gracefully."""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.narrative_synthesizer import NarrativeSynthesizer

logger = logging.getLogger(__name__)

_FALLBACK_NOTICE = "Executive summary: rule-based synthesis — LLM API unavailable"


class LLMSynthesizer:
    """Uses Claude Haiku API when key is set; falls back to NarrativeSynthesizer."""

    @staticmethod
    def is_available() -> bool:
        """Return True if anthropic is installed AND ANTHROPIC_API_KEY env var is non-empty."""
        try:
            import anthropic  # noqa: F401
        except Exception:
            return False
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    def synthesize(
        self,
        events: list,
        duration_s: float,
        narrative: "NarrativeSynthesizer",
    ) -> tuple[str, bool, str]:
        """
        Generate executive summary.

        Returns (summary_text, llm_used, notice_text):
          - (LLM text, True, "")           when Haiku API succeeds
          - (rule-based text, False, _FALLBACK_NOTICE)  when unavailable or error
        """
        if not self.is_available():
            return self._fallback(events, duration_s, narrative)

        try:
            return self._call_haiku(events, duration_s)
        except Exception as exc:
            logger.warning("LLM synthesis failed, using rule-based fallback: %s", exc)
            return self._fallback(events, duration_s, narrative)

    def _call_haiku(self, events: list, duration_s: float) -> tuple[str, bool, str]:
        import json
        from anthropic import Anthropic

        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        event_data = [
            {
                "timestamp": _fmt_ts(e.get("start_s", 0)),
                "confidence": e.get("confidence", 0),
                "label": e.get("label", ""),
                "caption": e.get("caption", ""),
                "object_caption": e.get("object_caption", ""),
                "detections": e.get("detections", []),
            }
            for e in events
        ]
        prompt = (
            f"You are analysing CCTV security camera footage. "
            f"Video duration: {int(duration_s)}s. "
            f"Detected {len(events)} event(s).\n\n"
            f"Events:\n{json.dumps(event_data, indent=2)}\n\n"
            "Write a concise 2-3 sentence executive summary of the security activity. "
            "Focus on what happened, when, and any notable patterns."
        )
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text, True, ""

    def _fallback(
        self, events: list, duration_s: float, narrative: "NarrativeSynthesizer"
    ) -> tuple[str, bool, str]:
        text = narrative.executive_summary(events)
        return text, False, _FALLBACK_NOTICE


def _fmt_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
