"""Output formatters for bandpass filter results.

Provides JSON, CSV, and quiet text formatting.
"""

import csv
import io
import json
from collections.abc import Callable
from typing import Any

from ..shared.display_helpers import format_eseries_match as _shared_format_eseries
from ..shared.eseries import match_component
from ..shared.formatting import format_capacitance, format_inductance
from ..shared.toroid_display import (
    CSV_TOROID_HEADER,
    build_json_recommendations,
    csv_columns_for_best,
)
from ..shared.toroid_selection import recommend_cores

# Type alias for filter result dict
FilterResult = dict[str, Any]


def format_eseries_match(
    value: float, series: str, unit_formatter: Callable[[float], str]
) -> list[str]:
    """Format E-series match for a component value.

    Uses additive parallel mode for consistency with lowpass/highpass.

    Args:
        value: Component value
        series: E-series name (E12, E24, E96)
        unit_formatter: Function to format value with units

    Returns:
        List of formatted match strings
    """
    return _shared_format_eseries(value, series, unit_formatter, parallel_mode="additive")


def _build_standard_match(
    value: float, eseries: str, unit_key: str, parallel_mode: str
) -> dict[str, Any]:
    """Build JSON-serializable E-series match data."""
    match = match_component(value, eseries, parallel_mode=parallel_mode)

    standard: dict[str, Any] = {
        "series": eseries,
        "nearest": {
            unit_key: match.single_value,
            "error_pct": match.single_error_pct,
        },
    }

    if match.parallel and match.parallel_value is not None and match.parallel_error_pct is not None:
        standard["parallel"] = {
            "components": [{unit_key: match.parallel[0]}, {unit_key: match.parallel[1]}],
            unit_key: match.parallel_value,
            "error_pct": match.parallel_error_pct,
        }

    return standard


def format_json(
    result: FilterResult,
    eseries: str | None = None,
    include_toroids: bool = True,
) -> str:
    """Format results as JSON.

    Args:
        result: Dict from calculate_bandpass_filter()
        eseries: E-series name (None disables matching)
        include_toroids: Attach resonator_toroid_recommendations top-level field

    Returns:
        JSON formatted string
    """
    output = {
        "filter_type": result["filter_type"],
        "coupling": result["coupling"],
        "center_frequency_hz": result["f0"],
        "bandwidth_hz": result["bw"],
        "f_low_hz": result["f_low"],
        "f_high_hz": result["f_high"],
        "fractional_bw": result["fbw"],
        "impedance_ohms": result["z0"],
        "n_resonators": result["n_resonators"],
        "q_min": result["q_min"],
        "components": {
            "tank_capacitors": [
                _bandpass_json_component(f"Cp{i + 1}", v, "value_farads", eseries, "additive")
                for i, v in enumerate(result["c_tank"])
            ],
            "inductors": [
                _bandpass_json_component(
                    f"L{i + 1}", result["L_resonant"], "value_henries", eseries, "harmonic"
                )
                for i in range(result["n_resonators"])
            ],
            "coupling_capacitors": [
                _bandpass_json_component(
                    f"Cs{i + 1}{i + 2}", v, "value_farads", eseries, "additive"
                )
                for i, v in enumerate(result["c_coupling"])
            ],
        },
        "external_q": {"input": result["qe_in"], "output": result["qe_out"]},
    }
    # Top-C results carry series end-coupling capacitors that realize the
    # external Q. JSON schema: components.end_coupling_capacitors is a list of
    # {"name": "Ce_in"|"Ce_out", "value_farads": float, "standard_match": {...}}
    # present whenever the synthesis emits end caps.
    if result.get("c_end_in") is not None and result.get("c_end_out") is not None:
        output["components"]["end_coupling_capacitors"] = [
            _bandpass_json_component(
                "Ce_in", result["c_end_in"], "value_farads", eseries, "additive"
            ),
            _bandpass_json_component(
                "Ce_out", result["c_end_out"], "value_farads", eseries, "additive"
            ),
        ]
    if result.get("ripple_db") is not None:
        output["ripple_db"] = result["ripple_db"]
    if include_toroids:
        recs = recommend_cores(result["L_resonant"], result["f0"])
        output["resonator_toroid_recommendations"] = build_json_recommendations(recs)
    return json.dumps(output, indent=2)


def _bandpass_json_component(
    name: str, value: float, unit_key: str, eseries: str | None, parallel_mode: str
) -> dict[str, Any]:
    """Build one JSON component entry for bandpass export."""
    component: dict[str, Any] = {"name": name, unit_key: value}
    if eseries:
        component["standard_match"] = _build_standard_match(value, eseries, unit_key, parallel_mode)
    return component


def _csv_match_fields(
    value: float, formatter, eseries: str | None, parallel_mode: str
) -> list[str]:
    """Build optional E-series columns for CSV."""
    if not eseries:
        return []

    match = match_component(value, eseries, parallel_mode=parallel_mode)
    nearest_fmt = formatter(match.single_value)
    nearest_val, nearest_unit = nearest_fmt.rsplit(" ", 1)

    parallel_vals = ""
    parallel_err = ""
    if match.parallel and match.parallel_error_pct is not None:
        p1_fmt = formatter(match.parallel[0])
        p2_fmt = formatter(match.parallel[1])
        parallel_vals = f"{p1_fmt} || {p2_fmt}"
        parallel_err = f"{match.parallel_error_pct:.1f}"

    return [
        nearest_val,
        nearest_unit,
        f"{match.single_error_pct:.1f}",
        parallel_vals,
        parallel_err,
        eseries,
    ]


def format_csv(
    result: FilterResult,
    eseries: str | None = None,
    include_toroids: bool = True,
) -> str:
    """Format results as CSV.

    Args:
        result: Dict from calculate_bandpass_filter()
        eseries: E-series name (None disables matching)
        include_toroids: Append toroid best-match columns and populate inductor rows

    Returns:
        CSV formatted string
    """
    output = io.StringIO()
    writer = csv.writer(output)
    header = ["Component", "Value", "Unit"]
    if eseries:
        header.extend(
            [
                "NearestStdValue",
                "NearestStdUnit",
                "NearestStdErrorPct",
                "ParallelStdValues",
                "ParallelStdErrorPct",
                "Eseries",
            ]
        )
    if include_toroids:
        header.extend(CSV_TOROID_HEADER)
    writer.writerow(header)
    n_toroid_cols = len(CSV_TOROID_HEADER)

    toroid_cols: list[str] = []
    if include_toroids:
        recs = recommend_cores(result["L_resonant"], result["f0"])
        toroid_cols = csv_columns_for_best(recs)

    for i, v in enumerate(result["c_tank"]):
        formatted = format_capacitance(v)
        val, unit = formatted.rsplit(" ", 1)
        row = [f"Cp{i + 1}", val, unit]
        row.extend(_csv_match_fields(v, format_capacitance, eseries, "additive"))
        if include_toroids:
            row.extend([""] * n_toroid_cols)
        writer.writerow(row)
    for i in range(result["n_resonators"]):
        formatted = format_inductance(result["L_resonant"])
        val, unit = formatted.rsplit(" ", 1)
        row = [f"L{i + 1}", val, unit]
        row.extend(_csv_match_fields(result["L_resonant"], format_inductance, eseries, "harmonic"))
        if include_toroids:
            row.extend(toroid_cols)
        writer.writerow(row)
    for i, v in enumerate(result["c_coupling"]):
        formatted = format_capacitance(v)
        val, unit = formatted.rsplit(" ", 1)
        row = [f"Cs{i + 1}{i + 2}", val, unit]
        row.extend(_csv_match_fields(v, format_capacitance, eseries, "additive"))
        if include_toroids:
            row.extend([""] * n_toroid_cols)
        writer.writerow(row)
    for name, value in _end_cap_items(result):
        formatted = format_capacitance(value)
        val, unit = formatted.rsplit(" ", 1)
        row = [name, val, unit]
        row.extend(_csv_match_fields(value, format_capacitance, eseries, "additive"))
        if include_toroids:
            row.extend([""] * n_toroid_cols)
        writer.writerow(row)
    return output.getvalue()


def _end_cap_items(result: FilterResult) -> list[tuple[str, float]]:
    """End-coupling capacitors as (name, value) pairs; empty when absent."""
    if result.get("c_end_in") is None or result.get("c_end_out") is None:
        return []
    return [("Ce_in", result["c_end_in"]), ("Ce_out", result["c_end_out"])]


def format_quiet(result: FilterResult, raw: bool = False) -> str:
    """Format results as minimal text (values only).

    Args:
        result: Dict from calculate_bandpass_filter()
        raw: If True, use scientific notation

    Returns:
        Minimal text output
    """
    lines: list[str] = []
    for i, v in enumerate(result["c_tank"]):
        if raw:
            lines.append(f"Cp{i + 1}: {v:.6e} F")
        else:
            lines.append(f"Cp{i + 1}: {format_capacitance(v)}")
    for i in range(result["n_resonators"]):
        if raw:
            lines.append(f"L{i + 1}: {result['L_resonant']:.6e} H")
        else:
            lines.append(f"L{i + 1}: {format_inductance(result['L_resonant'])}")
    for i, v in enumerate(result["c_coupling"]):
        if raw:
            lines.append(f"Cs{i + 1}{i + 2}: {v:.6e} F")
        else:
            lines.append(f"Cs{i + 1}{i + 2}: {format_capacitance(v)}")
    for name, value in _end_cap_items(result):
        if raw:
            lines.append(f"{name}: {value:.6e} F")
        else:
            lines.append(f"{name}: {format_capacitance(value)}")
    return "\n".join(lines)
