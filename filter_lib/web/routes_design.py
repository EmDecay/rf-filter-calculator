"""Design routes: the rendered result for the page and the CLI JSON document."""

from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from ..design import design, render_lines, response_series
from .form_parsing import parse_design_form
from .responses import (
    design_error,
    failure_message,
    failure_status,
    form_fields,
    is_htmx,
    render_page,
    runner,
    templates,
)
from .svg_plot import render_response_svg

router = APIRouter()


@router.post("/design/{category}", response_class=HTMLResponse)
async def design_view(request: Request, category: str) -> HTMLResponse:
    """Render the CLI's text for the submitted design, plus the SVG plot if asked."""
    fields = await form_fields(request)
    try:
        submitted = parse_design_form(category, fields)
        if submitted.request.build is not None:
            submitted.options.validate_for_build()
        if submitted.options.output_format in ("quiet", "csv"):
            submitted.request.reject_loss_q()

        def work(should_cancel) -> dict:
            outcome = design(submitted.request, should_cancel=should_cancel)
            svg = None
            if submitted.svg_plot:
                svg = render_response_svg(*response_series(outcome), category)
            return {
                "category": category,
                "output": "\n".join(render_lines(outcome, submitted.options)),
                "svg": svg,
                "warnings": outcome.warnings,
            }

        result = await runner(request).run(work)
    except Exception as exc:
        status = failure_status(exc)
        if status is None:
            raise
        return design_error(request, category, fields, failure_message(exc), status)

    if is_htmx(request):
        return templates(request).TemplateResponse(request, "partials/result.html", result)
    return render_page(request, form=fields, **result)


@router.post("/api/design/{category}")
async def design_json(request: Request, category: str) -> Response:
    """Return exactly what ``filter-calc <category> ... --format json`` prints."""
    submitted = parse_design_form(category, await form_fields(request))
    options = replace(submitted.options, output_format="json", raw=False, show_plot=False)

    def work(should_cancel) -> str:
        outcome = design(submitted.request, should_cancel=should_cancel)
        return render_lines(outcome, options)[0] + "\n"

    return Response(content=await runner(request).run(work), media_type="application/json")
