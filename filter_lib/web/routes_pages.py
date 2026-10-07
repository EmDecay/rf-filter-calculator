"""Page routes: the design page, the per-category form fragment, and a health check."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..design.design_request import CATEGORIES
from .form_parsing import require_category
from .responses import page_context, render_page, templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, category: str = CATEGORIES[0]) -> HTMLResponse:
    """Full page; ``?category=`` selects the tab so tabs work as plain links."""
    return render_page(request, require_category(category))


@router.get("/form/{category}", response_class=HTMLResponse)
async def form_fragment(request: Request, category: str) -> HTMLResponse:
    """The form for one category, swapped in by the tabs; it also resets the result."""
    return templates(request).TemplateResponse(
        request,
        "partials/design_form.html",
        page_context(require_category(category), reset_result=True),
    )


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
