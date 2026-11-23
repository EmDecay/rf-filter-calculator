"""Output formatters for bandpass filter results.

Provides JSON, CSV, and quiet text formatting.
"""

import csv
import io
from typing import Any

from ..shared.display_common import (
    ESERIES_CSV_HEADER,
    csv_match_fields,
    json_component,
)
from ..shared.display_helpers import format_component_value, split_value_unit
from ..shared.formatting import format_capacitance, format_inductance
from ..shared.inductor_display import CSV_INDUCTOR_HEADER, inductor_csv_columns
from ..shared.resolved_parts import ResolvedParts
from ..shared.strict_json import dumps_strict, validate_finite_tree
from .trimmer_display import (
    CSV_TRIMMER_HEADER,
    coupling_advice_payload,
    tank_trimmers_payload,
    trimmer_csv_columns,
)

# Type alias for filter result dict
BandpassResult = dict[str, Any]

# Every resonator has the same inductance, so the first one's resolved part speaks for all.
RESONATOR_INDUCTOR = "LT1"


def format_json(
    result: BandpassResult,
    parts: ResolvedParts,
    build_analysis=None,
    coupling_advice=None,
) -> str:
    """Format results as JSON.

    Args:
        result: Dict from calculate_bandpass_filter()
        parts: The parts ``design()`` resolved: capacitor choices (when the design has
            an E-series) and the inductor suggestions (unless they are off)
        build_analysis: Optional realized-build analysis result
        coupling_advice: The design's tank-inductance advice (``coupling_advice`` key)

    Returns:
        JSON formatted string
    """

    def component(name: str, value: float, circuit_name: str) -> dict[str, Any]:
        return json_component(name, value, parts, circuit_name)

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
        "loss_estimate_validation": result.get("loss_estimate_validation"),
        "harmonic_response": result.get("harmonic_response"),
        "response_validation_status": result.get("response_validation_status"),
        "synthesis_validation": result.get("synthesis_validation"),
        "requested_parameters": result.get("requested_parameters"),
        "internal_synthesis_parameters": result.get("internal_synthesis_parameters"),
        "warnings": list(result.get("warnings", [])),
        "components": {
            "tank_capacitors": [
                component(f"Cp{i + 1}", v, f"CT{i + 1}") for i, v in enumerate(result["c_tank"])
            ],
            "inductors": [
                component(f"L{i + 1}", result["L_resonant"], f"LT{i + 1}")
                for i in range(result["n_resonators"])
            ],
            "coupling_capacitors": [
                component(f"Cs{i + 1}{i + 2}", v, f"CK{i + 1}")
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
            component("Ce_in", result["c_end_in"], "CIN"),
            component("Ce_out", result["c_end_out"], "COUT"),
        ]
    if result.get("ripple_db") is not None:
        output["ripple_db"] = result["ripple_db"]
    output["tank_trimmers"] = tank_trimmers_payload(parts)
    output["coupling_advice"] = coupling_advice_payload(coupling_advice)
    if build_analysis is not None:
        from ..shared.build_output import build_analysis_fields

        output.update(build_analysis_fields(result, build_analysis))
    return dumps_strict(output, indent=2)


def format_csv(result: BandpassResult, parts: ResolvedParts) -> str:
    """Format results as CSV.

    Args:
        result: Dict from calculate_bandpass_filter()
        parts: The parts ``design()`` resolved; the E-series columns appear when the
            design has an E-series, the inductor columns unless suggestions are off

    Returns:
        CSV rows separated by LF, without a final line terminator (the caller
        ends the document, as for LP/HP CSV).
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
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    eseries = parts.eseries
    emit_inductors = parts.shows_suggestions
    emit_trimmers = bool(parts.tanks)
    header = ["Component", "Value", "Unit"]
    if eseries:
        header.extend(ESERIES_CSV_HEADER)
    if emit_inductors:
        header.extend(CSV_INDUCTOR_HEADER)
    if emit_trimmers:
        header.extend(CSV_TRIMMER_HEADER)
    writer.writerow(header)

    # Inductor columns apply only to inductor rows and trimmer columns only to tank rows;
    # every other row gets blank padding (and inductor rows blank E-series columns), to
    # keep the CSV rectangular.
    def write_capacitor(name: str, circuit_name: str, value: float) -> None:
        row = [name, *split_value_unit(format_capacitance(value))]
        match = parts.capacitor(circuit_name) if eseries else None
        row.extend(csv_match_fields(match, format_capacitance, eseries))
        if emit_inductors:
            row.extend(inductor_csv_columns(None))
        if emit_trimmers:
            row.extend(trimmer_csv_columns(parts.tank(circuit_name)))
        writer.writerow(row)

    for i, v in enumerate(result["c_tank"]):
        write_capacitor(f"Cp{i + 1}", f"CT{i + 1}", v)
    for i in range(result["n_resonators"]):
        row = [f"L{i + 1}", *split_value_unit(format_inductance(result["L_resonant"]))]
        row.extend(csv_match_fields(None, format_inductance, eseries))
        if emit_inductors:
            row.extend(inductor_csv_columns(parts.inductor(f"LT{i + 1}")))
        if emit_trimmers:
            row.extend(trimmer_csv_columns(None))
        writer.writerow(row)
    for i, v in enumerate(result["c_coupling"]):
        write_capacitor(f"Cs{i + 1}{i + 2}", f"CK{i + 1}", v)
    for name, circuit_name, value in _end_cap_items(result):
        write_capacitor(name, circuit_name, value)
    return output.getvalue().removesuffix("\n")


def _end_cap_items(result: BandpassResult) -> list[tuple[str, str, float]]:
    """End-coupling capacitors as (name, circuit name, value); empty when absent."""
    if result.get("c_end_in") is None or result.get("c_end_out") is None:
        return []
    return [("Ce_in", "CIN", result["c_end_in"]), ("Ce_out", "COUT", result["c_end_out"])]


def capacitor_parts(result: BandpassResult) -> list[tuple[str, str, float]]:
    """Every capacitor in table order as (table name, circuit name, value).

    Tank capacitors first, then the coupling capacitors; the circuit name keys the part
    in ``ResolvedParts``.
    """
    tank = [(f"Cp{i + 1}", f"CT{i + 1}", v) for i, v in enumerate(result["c_tank"])]
    return tank + _coupling_capacitor_parts(result)


def _coupling_capacitor_parts(result: BandpassResult) -> list[tuple[str, str, float]]:
    """Coupling capacitors in table order as (table name, circuit name, value).

    Ce_in (when present), Cs12…, then Ce_out (when present).
    """
    rows = []
    if result.get("c_end_in") is not None:
        rows.append(("Ce_in", "CIN", result["c_end_in"]))
    rows.extend(
        (f"Cs{i + 1}{i + 2}", f"CK{i + 1}", cs) for i, cs in enumerate(result["c_coupling"])
    )
    if result.get("c_end_out") is not None:
        rows.append(("Ce_out", "COUT", result["c_end_out"]))
    return rows


def coupling_capacitor_rows(result: BandpassResult) -> list[tuple[str, float]]:
    """Coupling capacitors in table order: Ce_in (when present), Cs12…, then Ce_out."""
    return [(label, value) for label, _circuit_name, value in _coupling_capacitor_parts(result)]


def format_quiet(result: BandpassResult, raw: bool = False) -> str:
    """Format results as minimal text (values only), in the table's order.

    Args:
        result: Dict from calculate_bandpass_filter()
        raw: If True, use scientific notation

    Returns:
        Minimal text output
    """
    rows = [(f"Cp{i + 1}", v, format_capacitance) for i, v in enumerate(result["c_tank"])]
    rows += [
        (f"L{i + 1}", result["L_resonant"], format_inductance)
        for i in range(result["n_resonators"])
    ]
    rows += [(name, value, format_capacitance) for name, value in coupling_capacitor_rows(result)]
    return "\n".join(
        format_component_value(name, value, formatter, raw) for name, value, formatter in rows
    )
