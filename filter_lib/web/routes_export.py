"""Download routes: the CLI's machine-readable documents as attachments.

Each body is byte-identical to the CLI's stdout for the same design: JSON and CSV
end with the newline ``print`` adds, a SPICE deck carries its own final newline, and
response data matches ``--plot-data``. Only the JSON document carries the build
simulation; the other downloads describe the calculated design.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ..design import design, export_response_data, export_spice, render_lines
from ..design.option_applicability import LOSS_Q, RESPONSE_DOCUMENTS, document_reason
from ..design.render_options import needs_eseries_message
from .download_inputs import download_fields
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
# Downloads whose document cannot show the resonator-loss model (the shared rule).
_LOSS_Q_UNUSED = frozenset(kind for kind in EXPORT_KINDS if document_reason(kind, LOSS_Q))
# Response data is the ideal response, which Qu/QL/QC never change; the wizard's
# response file and these downloads therefore leave them out instead of refusing.
LOSS_Q_DROPPED = _LOSS_Q_UNUSED & RESPONSE_DOCUMENTS
# The others refuse them, as in the CLI.
LOSS_Q_HIDDEN = _LOSS_Q_UNUSED - RESPONSE_DOCUMENTS
NOMINAL_SPICE_NEEDS_ESERIES = (
    needs_eseries_message('"SPICE – chosen parts"') + '; or download "SPICE – calculated values"'
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
    # The inputs of the result shown, with the visible values of controls it could not use.
    submitted = parse_design_form(category, download_fields(await form_fields(request), kind))
    if kind == "spice-nominal" and submitted.options.eseries is None:
        raise ValueError(NOMINAL_SPICE_NEEDS_ESERIES)
    if kind in LOSS_Q_HIDDEN:
        submitted.request.reject_loss_q()
    if kind in LOSS_Q_DROPPED:
        submitted = replace(
            submitted, request=replace(submitted.request, qu=None, ql=None, qc=None)
        )

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
