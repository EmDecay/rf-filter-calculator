"""Shared request and response helpers for the web routes."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..design.design_request import CATEGORIES
from ..shared.build_types import BuildAnalysisCancelled
from .execution import CalculationRunner, CalculationTimeout
from .form_parsing import form_defaults
from .form_values import FormData

CATEGORY_LABELS = {"lowpass": "Low-pass", "highpass": "High-pass", "bandpass": "Band-pass"}


def templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


def runner(request: Request) -> CalculationRunner:
    return request.app.state.runner


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


async def form_fields(request: Request) -> FormData:
    """Return the submitted text fields; file parts are ignored."""
    form = await request.form()
    return {name: value for name, value in form.items() if isinstance(value, str)}


def page_context(category: str, form: FormData | None = None, **extra) -> dict:
    """Context shared by the full page and its partials.

    ``values`` fills the inputs: the submitted fields when there are any (so a failed
    or non-JavaScript submission keeps the user's input), else the fresh defaults.
    """
    return {
        "category": category,
        "categories": CATEGORIES,
        "category_labels": CATEGORY_LABELS,
        "values": dict(form) if form else form_defaults(category),
        **extra,
    }


def render_page(
    request: Request, category: str, *, status_code: int = 200, **extra
) -> HTMLResponse:
    return templates(request).TemplateResponse(
        request, "index.html", page_context(category, **extra), status_code=status_code
    )


def failure_status(exc: Exception) -> int | None:
    """Return the HTTP status for an expected failure, or ``None`` for a bug."""
    if isinstance(exc, ValueError):
        return 400
    if isinstance(exc, (CalculationTimeout, BuildAnalysisCancelled)):
        return 503
    return None


def failure_message(exc: Exception) -> str:
    if isinstance(exc, BuildAnalysisCancelled):
        return "Calculation cancelled"
    return str(exc).strip() or type(exc).__name__


def json_error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def design_error(
    request: Request, category: str, fields: FormData, message: str, status_code: int
) -> HTMLResponse:
    """Show a design failure as the result fragment, or as the page without JavaScript."""
    if is_htmx(request):
        return templates(request).TemplateResponse(
            request, "partials/error.html", {"message": message}, status_code=status_code
        )
    return render_page(
        request,
        category if category in CATEGORIES else CATEGORIES[0],
        status_code=status_code,
        form=fields,
        error=message,
    )
