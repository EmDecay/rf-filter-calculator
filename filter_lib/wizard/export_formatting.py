"""Component and response export formatting for the wizard results screen."""

from __future__ import annotations

import os
from datetime import datetime

from .state import CSV_DOCUMENT, JSON_DOCUMENT, FilterState

EXPORT_FOLDER_MISSING_MESSAGE = (
    "The folder the wizard was started from no longer exists. "
    "Restart the wizard from an existing folder to save files."
)


def export_folder() -> str:
    """Return the folder exports are saved in (the folder the wizard was started from).

    ``os.getcwd()`` raises ``OSError`` when that folder was deleted or became
    unreadable after the wizard started; report it as a plain ``ValueError`` so
    the results screen can show it like any other export problem.
    """
    try:
        return os.getcwd()
    except OSError as error:
        raise ValueError(EXPORT_FOLDER_MISSING_MESSAGE) from error


def format_response_export(state: FilterState, fmt: str) -> str:
    """Return response data in the shared CLI-compatible export schema.

    A saved file ends with one LF, byte-identical to the CLI's --plot-data output. The
    document leaves out resonator Q and the build (``FilterState.document_options``):
    Qu, QL, and QC only add a loss estimate and never change the ideal response, so the
    stored result gives the ``--plot-data`` output of the same design without them.
    """
    from filter_lib.design import export_response_data

    return export_response_data(state.design_result(f"response-{fmt}"), fmt) + "\n"


def _component_document(state: FilterState, document: str) -> str:
    """Render the result as a saved JSON or CSV document ending with one LF.

    The document uses each visible choice that applies to it (``FilterState``), so it is
    the CLI's ``--format json``/``csv`` output for those choices.
    """
    from filter_lib.design import render_lines

    refusal = state.document_refusal(document)
    if refusal:
        raise ValueError(refusal)
    outcome = state.design_result(document)
    return render_lines(outcome, state.document_render_options(document))[0] + "\n"


def format_component_json(state: FilterState) -> str:
    """Return category JSON, reusing the stored result and build simulation.

    When the JSON uses a build or resonator Q the result shown did not, its own design
    must already be in ``state.json_design`` (the results screen calculates it on Save).

    The document ends with one LF, byte-identical to the CLI's ``--format json``.
    """
    return _component_document(state, JSON_DOCUMENT)


def format_component_csv(state: FilterState) -> str:
    """Return the category CSV file, refusing a build simulation or resonator Q shown.

    The document ends with one LF, byte-identical to the CLI's ``--format csv``.
    """
    return _component_document(state, CSV_DOCUMENT)


def prepare_export_payloads(
    state: FilterState, format_id: str, *, include_component: bool = True
) -> list[tuple[str, str]]:
    """Format all requested files before the results screen writes any of them.

    ``include_component=False`` leaves out the results file itself (the screen does so
    when the JSON it asked for could not be calculated) and keeps the response file.
    """
    folder = export_folder()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    category = state.category or "filter"

    files = []
    if include_component:
        if format_id == "export-txt":
            extension = "txt"
            content = state.output_text
        elif format_id == "export-json":
            extension = "json"
            content = format_component_json(state)
        else:
            extension = "csv"
            content = format_component_csv(state)
        files.append((os.path.join(folder, f"{category}-{timestamp}.{extension}"), content))
    response_format = state.export_format
    if response_format in ("json", "csv"):
        response_name = f"{category}-{timestamp}-response.{response_format}"
        files.append(
            (
                os.path.join(folder, response_name),
                format_response_export(state, response_format),
            )
        )
    return files
