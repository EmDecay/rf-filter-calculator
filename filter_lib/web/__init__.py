"""Local web UI for the filter calculator (optional ``web`` extra).

``filter-calc web`` serves it; ``create_app`` builds the FastAPI application. Only
``create_app`` needs the extra, so the settings stay importable without it.
"""

from .settings import WebSettings


def create_app(settings: WebSettings | None = None):
    """Return the FastAPI app; raises ``ImportError`` when the extra is missing."""
    from .app import create_app as build_app

    return build_app(settings)


__all__ = ["WebSettings", "create_app"]
