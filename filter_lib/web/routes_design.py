"""Design routes: the rendered result for the page and the CLI JSON document."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from ..design import design, render_lines, response_series
from .download_inputs import download_fields
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
from .routes_export import document_body
from .svg_plot import render_response_svg

router = APIRouter()


@router.post("/design/{category}", response_class=HTMLResponse)
async def design_view(request: Request, category: str) -> HTMLResponse:
    """Render the CLI's text for the submitted design, plus the SVG plot if asked."""
    fields = await form_fields(request)
    try:
        submitted = parse_design_form(category, fields)
        # The output shown must be able to use every option ticked, as in the CLI;
        # downloads are checked against the document each one produces instead.
        submitted.require_applicable_options()

        def work(should_cancel) -> dict:
            outcome = design(submitted.request, should_cancel=should_cancel)
            svg = None
            if submitted.svg_plot:
                svg = render_response_svg(*response_series(outcome), category)
            return {
                "category": category,
                "output": "\n".join(render_lines(outcome, submitted.options)),
                "svg": svg,
                # The table lists the design warnings itself; show them apart only
                # when the output does not (the CLI prints them once the same way).
                "warnings": (() if submitted.options.shows_design_warnings else outcome.warnings),
                # The inputs of this result; the downloads post them, not the live form,
                # so a download always matches the result on screen.
                "snapshot": fields,
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
    """Return exactly what ``filter-calc <category> ... --format json`` prints.

    This is the Design JSON download under another address: the same fields give the same
    bytes. Display-only fields (format, raw units, text plot, the table-only inductor
    detail) are left out, as for that download, and a ``visible.<name>`` value is used
    where it applies to the JSON document.
    """
    fields = download_fields(await form_fields(request), "json")
    submitted = parse_design_form(category, fields)
    body = await runner(request).run(
        lambda should_cancel: document_body("json", submitted, should_cancel)
    )
    return Response(content=body, media_type="application/json")
