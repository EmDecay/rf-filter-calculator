"""Component and response export formatting for the wizard results screen."""

from __future__ import annotations

import os
from datetime import datetime

from .filter_type_calculators import BANDPASS_WIZARD_RESPONSE_POINTS
from .state import FilterState


def format_response_export(state: FilterState, fmt: str) -> str:
    """Return response data in the shared CLI-compatible export schema."""
    from filter_lib.shared.response_export import (
        export_response_csv,
        export_response_json,
        response_meta,
    )

    if state.category == "bandpass":
        from filter_lib.bandpass.transfer import netlist_frequency_sweep

        sweep = netlist_frequency_sweep(
            state.result,
            points=BANDPASS_WIZARD_RESPONSE_POINTS,
        )
        freqs = [frequency for frequency, _ in sweep]
        response_db = [magnitude for _, magnitude in sweep]
    else:
        if state.category == "lowpass":
            from filter_lib.lowpass.transfer import (
                frequency_response,
                generate_frequency_points,
            )
        else:
            from filter_lib.highpass.transfer import (
                frequency_response,
                generate_frequency_points,
            )

        result = state.result
        freqs = generate_frequency_points(result["freq_hz"])
        response_db = frequency_response(
            result["filter_type"],
            freqs,
            result["freq_hz"],
            result["order"],
            result.get("ripple") or 0.5,
        )

    meta = response_meta(state.category, state.result)
    if fmt == "json":
        return export_response_json(freqs, response_db, meta)
    return export_response_csv(freqs, response_db)


def format_component_json(state: FilterState) -> str:
    """Return category JSON, reusing the analysis stored by the worker."""
    eseries = None if state.eseries == "none" else state.eseries
    if state.category == "lowpass":
        from filter_lib.lowpass.display import format_json
    elif state.category == "highpass":
        from filter_lib.highpass.display import format_json
    else:
        from filter_lib.bandpass.formatters import format_json

    return format_json(
        state.result,
        eseries=eseries,
        build_analysis=state.build_analysis,
    )


def format_component_csv(state: FilterState) -> str:
    """Return category CSV, rejecting the unsupported analysis combination."""
    if state.build_analysis_enabled or state.build_analysis is not None:
        raise ValueError("realized-build analysis is not supported in component CSV")

    eseries = None if state.eseries == "none" else state.eseries
    if state.category == "lowpass":
        from filter_lib.lowpass.display import format_csv
    elif state.category == "highpass":
        from filter_lib.highpass.display import format_csv
    else:
        from filter_lib.bandpass.formatters import format_csv
    return format_csv(state.result, eseries=eseries)


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
