"""
Intelligence report HTML rendering — PC version.

Pure rendering layer: takes a context dict already assembled by the caller
and renders it through the intel_report.html Jinja2 template into a single
self-contained HTML document string. No file I/O, no session access, no
business logic lives here — that all belongs to the caller, matching the same
separation-of-concerns style export_engine.py and thumbnail_gen.py already follow.
"""
from pathlib import Path

import jinja2

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
)


def _fmt_ts(seconds: float) -> str:
    """Format seconds as HH:MM:SS clock string."""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


class IntelReportRenderer:
    """Stateless renderer for the intelligence report HTML template."""

    def _build_svg_timeline(self, events: list, duration_s: float) -> str:
        """Build inline SVG activity timeline."""
        COLOURS = {
            "person": "#3b82f6",
            "vehicle": "#f97316",
        }
        DEFAULT_MOG2 = "#6b7280"
        OTHER_YOLO = "#8b5cf6"

        ticks = []
        for event in events:
            if duration_s <= 0:
                continue
            x = int(event.get("start_s", 0) / duration_s * 800)
            confidence = event.get("confidence", 0.5)
            h = max(8, int(confidence * 32))
            y = 20 - h // 2
            label = event.get("label", "").lower()
            if label == "mog2":
                fill = DEFAULT_MOG2
            elif label == "person":
                fill = COLOURS["person"]
            elif label in ("vehicle", "car", "truck", "bus", "motorbike"):
                fill = COLOURS["vehicle"]
            else:
                fill = OTHER_YOLO
            ticks.append(
                f'<rect x="{x}" y="{y}" width="4" height="{h}" rx="2" fill="{fill}"/>'
            )

        ticks_svg = "\n  ".join(ticks)
        return (
            '<svg viewBox="0 0 800 48" xmlns="http://www.w3.org/2000/svg" '
            'width="100%" height="48">\n'
            '  <rect x="0" y="20" width="800" height="8" rx="4" fill="#2e3147"/>\n'
            f'  {ticks_svg}\n'
            '</svg>'
        )

    def _annotate_thumbnail(self, thumb_path, detections: list) -> str:
        """Draw bounding boxes on thumbnail; return base64-encoded JPEG string."""
        import base64
        from pathlib import Path as _Path
        from io import BytesIO

        path = _Path(thumb_path) if thumb_path else None

        def _encode(img) -> str:
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode()

        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
            if path is None or not path.exists():
                # Return a tiny 1x1 placeholder encoded as JPEG
                img = Image.new("RGB", (1, 1), color=(46, 49, 71))
                return _encode(img)

            img = Image.open(path).convert("RGB")
            if detections:
                draw = ImageDraw.Draw(img)
                for det in detections:
                    bbox = det.get("bbox", [])
                    label = det.get("label", "")
                    if len(bbox) == 4:
                        draw.rectangle(
                            [bbox[0], bbox[1], bbox[2], bbox[3]],
                            outline="#4f8ef7",
                            width=2,
                        )
                        draw.text((bbox[0] + 2, bbox[1] + 2), label, fill="#4f8ef7")
            return _encode(img)
        except Exception:
            # Fallback: return original thumbnail bytes if PIL fails
            try:
                if path and path.exists():
                    return base64.b64encode(path.read_bytes()).decode()
            except Exception:
                pass
            try:
                from PIL import Image
                img = Image.new("RGB", (320, 180), color=(46, 49, 71))
                return _encode(img)
            except Exception:
                return ""

    def _build_scene_breakdown(self, events: list) -> list:
        """Return top-5 events by confidence with annotated thumbnails."""
        sorted_events = sorted(events, key=lambda e: e.get("confidence", 0), reverse=True)
        top = sorted_events[:5]

        result = []
        for rank, event in enumerate(top, start=1):
            thumb_path = event.get("thumbnail_path") or event.get("thumb_path")
            detections = event.get("detections", [])
            thumbnail_b64 = self._annotate_thumbnail(thumb_path, detections)
            result.append({
                "rank": rank,
                "timestamp": _fmt_ts(event.get("start_s", 0)),
                "confidence": event.get("confidence", 0),
                "caption": event.get("caption", ""),
                "object_caption": event.get("object_caption", ""),
                "detections": detections,
                "thumbnail_b64": thumbnail_b64,
                "thumbnail_b64_original": thumbnail_b64,
            })
        return result


def render(context: dict) -> str:
    """Render the intelligence report template with the given context dict."""
    template = _env.get_template("intel_report.html")
    return template.render(**context)
