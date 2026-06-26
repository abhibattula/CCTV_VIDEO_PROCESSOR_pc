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


def render(context: dict) -> str:
    """Render the intelligence report template with the given context dict."""
    template = _env.get_template("intel_report.html")
    return template.render(**context)
