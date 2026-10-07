"""Download routes: the CLI's machine-readable documents as attachments.

Each body is byte-identical to the CLI's stdout for the same design: JSON and CSV
end with the newline ``print`` adds, a SPICE deck carries its own final newline, and
response data matches ``--plot-data``. Only the JSON document carries a realized-build
analysis; the other downloads describe the synthesized design.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ..design import design, export_response_data, export_spice, render_lines
from .form_parsing import DesignForm, parse_design_form
from .responses import form_fields, runner

router = APIRouter()


@dataclass(frozen=True)
class ExportKind:
    extension: str
    media_type: str


EXPORT_KINDS = {
    "json": ExportKind("json", "application/json"),
    "csv": ExportKind("csv", "text/csv; charset=utf-8"),
    "spice-exact": ExportKind("cir", "text/plain; charset=utf-8"),
    "spice-nominal": ExportKind("cir", "text/plain; charset=utf-8"),
    "response-json": ExportKind("json", "application/json"),
    "response-csv": ExportKind("csv", "text/csv; charset=utf-8"),
}
# Downloads that cannot show the resonator-loss model, as in the CLI.
LOSS_Q_HIDDEN = frozenset({"csv", "spice-exact", "response-json", "response-csv"})
NOMINAL_SPICE_NEEDS_ESERIES = (
    "Nominal-build SPICE requires selected capacitor values; choose an E-series "
    "or download the exact deck"
)


def _document(kind: str, submitted: DesignForm, should_cancel) -> str:
    request = submitted.request if kind == "json" else replace(submitted.request, build=None)
    outcome = design(request, should_cancel=should_cancel)
    if kind in ("json", "csv"):
        options = replace(submitted.options, output_format=kind, raw=False, show_plot=False)
        return render_lines(outcome, options)[0] + "\n"
    if kind.startswith("spice-"):
        realization = "exact" if kind == "spice-exact" else "nominal_build"
        return export_spice(outcome, realization, submitted.spice_config)
    return export_response_data(outcome, kind.removeprefix("response-")) + "\n"


@router.post("/export/{category}/{kind}")
async def export(request: Request, category: str, kind: str) -> Response:
    """Return one export document as a download named ``<category>-<kind>.<ext>``."""
    if kind not in EXPORT_KINDS:
        raise ValueError(f"Unknown export: {kind}")
    submitted = parse_design_form(category, await form_fields(request))
    if kind == "spice-nominal" and submitted.options.eseries is None:
        raise ValueError(NOMINAL_SPICE_NEEDS_ESERIES)
    if kind in LOSS_Q_HIDDEN:
        submitted.request.reject_loss_q()

    body = await runner(request).run(
        lambda should_cancel: _document(kind, submitted, should_cancel)
    )
    export_kind = EXPORT_KINDS[kind]
    filename = f"{category}-{kind}.{export_kind.extension}"
    return Response(
        content=body,
        media_type=export_kind.media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
