"""Output formatters for bandpass filter results.

Provides JSON, CSV, and quiet text formatting.
"""

import csv
import io
from collections.abc import Callable
from typing import Any

from ..shared.display_common import (
    ESERIES_CSV_HEADER,
    build_standard_match,
    csv_match_fields,
)
from ..shared.display_helpers import format_eseries_match as _shared_format_eseries
from ..shared.formatting import format_capacitance, format_inductance
from ..shared.strict_json import dumps_strict, validate_finite_tree
from ..shared.toroid_display import (
    CSV_TOROID_HEADER,
    build_json_recommendations,
    csv_columns_for_best,
)
from ..shared.toroid_selection import recommend_cores

# Type alias for filter result dict
BandpassResult = dict[str, Any]


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


def format_json(
    result: BandpassResult,
    eseries: str | None = None,
    include_toroids: bool = True,
    matched_sim: dict[str, Any] | None = None,
    build_analysis=None,
) -> str:
    """Format results as JSON.

    Args:
        result: Dict from calculate_bandpass_filter()
        eseries: E-series name (None disables matching)
        include_toroids: Attach resonator_toroid_recommendations top-level field
        matched_sim: Optional matched-value simulation summary (additive
            top-level ``matched_sim`` key when present)
        build_analysis: Optional realized-build analysis result

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
        # Retained as an explicitly labeled compatibility heuristic. The Q
        # model below is the authoritative interpretation for loss estimates.
        "q_min": result["q_min"],
        "q_min_is_heuristic": result.get("q_min_is_heuristic", True),
        "q_safety_compatibility_only": result.get("q_safety_compatibility_only", True),
        "q_model": result.get("q_model"),
        "il_estimates": result.get("il_estimates", {}),
        "response_validation_status": result.get("response_validation_status"),
        "synthesis_validation": result.get("synthesis_validation"),
        "requested_parameters": result.get("requested_parameters"),
        "internal_synthesis_parameters": result.get("internal_synthesis_parameters"),
        "warnings": list(result.get("warnings", [])),
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
        candidates = build_json_recommendations(recs)
        output["resonator_toroid_candidates"] = candidates
        # Additive compatibility alias for consumers of the pre-2.1 schema.
        # Candidate records themselves explicitly deny RF suitability claims.
        output["resonator_toroid_recommendations"] = candidates
    if matched_sim is not None:
        output["matched_sim"] = matched_sim
    if build_analysis is not None:
        from ..shared.build_output import build_analysis_fields

        output.update(build_analysis_fields(result, build_analysis))
    return dumps_strict(output, indent=2)


def _bandpass_json_component(
    name: str, value: float, unit_key: str, eseries: str | None, parallel_mode: str
) -> dict[str, Any]:
    """Build one JSON component entry for bandpass export.

    Only capacitor entries (unit_key == "value_farads") receive a
    standard_match block — inductors are wound to value, never E-series
    matched — so parallel_mode is meaningful only for capacitors.
    """
    component: dict[str, Any] = {"name": name, unit_key: value}
    if eseries and unit_key == "value_farads":
        component["standard_match"] = build_standard_match(value, eseries, unit_key, parallel_mode)
    return component


def format_csv(
    result: BandpassResult,
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
    validate_finite_tree(
        {
            "center_frequency_hz": result["f0"],
            "tank_capacitors": result["c_tank"],
            "inductance_henries": result["L_resonant"],
            "coupling_capacitors": result["c_coupling"],
            "end_capacitor_input": result.get("c_end_in"),
            "end_capacitor_output": result.get("c_end_out"),
        }
    )
    output = io.StringIO()
    writer = csv.writer(output)
    header = ["Component", "Value", "Unit"]
    if eseries:
        header.extend(ESERIES_CSV_HEADER)
    if include_toroids:
        header.extend(CSV_TOROID_HEADER)
    writer.writerow(header)
    n_toroid_cols = len(CSV_TOROID_HEADER)

    # Toroid columns apply only to inductor rows (inductors are wound on
    # cores; capacitors are purchased parts). All resonators share L_resonant,
    # so one recommendation is computed and repeated per L row; capacitor
    # rows get blank padding to keep the CSV rectangular.
    toroid_cols: list[str] = []
    if include_toroids:
        recs = recommend_cores(result["L_resonant"], result["f0"])
        toroid_cols = csv_columns_for_best(recs)

    for i, v in enumerate(result["c_tank"]):
        formatted = format_capacitance(v)
        val, unit = formatted.rsplit(" ", 1)
        row = [f"Cp{i + 1}", val, unit]
        row.extend(csv_match_fields(v, format_capacitance, eseries, "additive"))
        if include_toroids:
            row.extend([""] * n_toroid_cols)
        writer.writerow(row)
    for i in range(result["n_resonators"]):
        formatted = format_inductance(result["L_resonant"])
        val, unit = formatted.rsplit(" ", 1)
        row = [f"L{i + 1}", val, unit]
        if eseries:
            row.extend([""] * len(ESERIES_CSV_HEADER))
        if include_toroids:
            row.extend(toroid_cols)
        writer.writerow(row)
    for i, v in enumerate(result["c_coupling"]):
        formatted = format_capacitance(v)
        val, unit = formatted.rsplit(" ", 1)
        row = [f"Cs{i + 1}{i + 2}", val, unit]
        row.extend(csv_match_fields(v, format_capacitance, eseries, "additive"))
        if include_toroids:
            row.extend([""] * n_toroid_cols)
        writer.writerow(row)
    for name, value in _end_cap_items(result):
        formatted = format_capacitance(value)
        val, unit = formatted.rsplit(" ", 1)
        row = [name, val, unit]
        row.extend(csv_match_fields(value, format_capacitance, eseries, "additive"))
        if include_toroids:
            row.extend([""] * n_toroid_cols)
        writer.writerow(row)
    return output.getvalue()


def _end_cap_items(result: BandpassResult) -> list[tuple[str, float]]:
    """End-coupling capacitors as (name, value) pairs; empty when absent."""
    if result.get("c_end_in") is None or result.get("c_end_out") is None:
        return []
    return [("Ce_in", result["c_end_in"]), ("Ce_out", result["c_end_out"])]


def format_quiet(result: BandpassResult, raw: bool = False) -> str:
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
