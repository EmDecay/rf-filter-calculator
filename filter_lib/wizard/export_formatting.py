"""Component and response export formatting for the wizard results screen."""

from __future__ import annotations

import os
from datetime import datetime

from .state import FilterState


def format_response_export(state: FilterState, fmt: str) -> str:
    """Return response data in the shared CLI-compatible export schema.

    A saved file ends with one LF, byte-identical to the CLI's --plot-data output.
    """
    from filter_lib.design import export_response_data

    return export_response_data(state.design_result(), fmt) + "\n"


def _component_document(state: FilterState, output_format: str) -> str:
    """Render the stored result as a JSON or CSV document ending with one LF."""
    from filter_lib.design import RenderOptions, render_lines

    options = RenderOptions(
        output_format=output_format,
        eseries=None if state.eseries == "none" else state.eseries,
    )
    return render_lines(state.design_result(), options)[0] + "\n"


def format_component_json(state: FilterState) -> str:
    """Return category JSON, reusing the analysis stored by the worker.

    The document ends with one LF, byte-identical to the CLI's ``--format json``.
    """
    return _component_document(state, "json")


def format_component_csv(state: FilterState) -> str:
    """Return the category CSV file, rejecting the unsupported analysis combination.

    The document ends with one LF, byte-identical to the CLI's ``--format csv``.
    """
    if state.build_analysis_enabled or state.build_analysis is not None:
        raise ValueError("realized-build analysis is not supported in component CSV")
    return _component_document(state, "csv")


def prepare_export_payloads(state: FilterState, format_id: str) -> list[tuple[str, str]]:
    """Format all requested files before the results screen writes any of them."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    category = state.category or "filter"

    if format_id == "export-txt":
        extension = "txt"
        content = state.output_text
    elif format_id == "export-json":
        extension = "json"
        content = format_component_json(state)
    else:
        extension = "csv"
        content = format_component_csv(state)

    files = [
        (
            os.path.join(os.getcwd(), f"{category}-{timestamp}.{extension}"),
            content,
        )
    ]
    if state.export_format in ("json", "csv"):
        response_name = f"{category}-{timestamp}-response.{state.export_format}"
        files.append(
            (
                os.path.join(os.getcwd(), response_name),
                format_response_export(state, state.export_format),
            )
        )
    return files
