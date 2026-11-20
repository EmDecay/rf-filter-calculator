"""Common display formatting functions for lowpass and highpass filters.

Extracts shared logic to reduce code duplication between filter display modules.
Each filter module can import these and customize as needed.
"""

import csv
from io import StringIO

from .display_helpers import format_component_value, split_value_unit
from .eseries import ESeriesMatch
from .formatting import (
    format_capacitance,
    format_fixed,
    format_inductance,
    format_restated_frequency,
    format_restated_value,
)
from .inductor_display import (
    CSV_INDUCTOR_HEADER,
    inductor_csv_columns,
    inductor_note_line,
    inductor_suggestions_payload,
)
from .resolved_parts import ResolvedParts
from .strict_json import dumps_strict, validate_finite_tree

ESERIES_CSV_HEADER = [
    "NearestStdValue",
    "NearestStdUnit",
    "NearestStdErrorPct",
    "ParallelStdValues",
    "ParallelStdErrorPct",
    "Eseries",
    "RecommendedStdKind",
    "RecommendedStdValues",
    "RecommendedStdErrorPct",
    "RecommendationStatus",
    "RecommendationReason",
    "RecommendationWarnings",
    "RecommendationPolicy",
]


def build_standard_match(match: ESeriesMatch, eseries: str, unit_key: str) -> dict:
    """Build JSON-serializable E-series match data for one component's resolved choice.

    Args:
        match: The choice ``design()`` resolved for the component
        eseries: E-series name ('E12', 'E24', 'E96')
        unit_key: JSON key naming the unit ('value_farads')

    Returns:
        Dict with 'series' and 'nearest' keys; 'parallel' only when a
        two-component pair beats the single nearest value.
    """
    standard: dict = {
        "series": eseries,
        "nearest": {
            unit_key: match.nearest_value,
            "error_pct": match.nearest_error_pct,
        },
        "policy": match.policy.as_dict(),
        "status": match.status,
        "tolerance_basis": _tolerance_basis(match),
        "selected": None,
        "reason": match.recommendation_reason,
        "warnings": list(match.warnings),
    }

    if match.recommended_kind == "single":
        standard["selected"] = {
            "kind": "single",
            "components": [{unit_key: match.single_value}],
            unit_key: match.single_value,
            "error_pct": match.single_error_pct,
        }
    elif (
        match.prefers_parallel
        and match.parallel
        and match.parallel_value is not None
        and match.parallel_error_pct is not None
    ):
        standard["parallel"] = {
            "components": [{unit_key: match.parallel[0]}, {unit_key: match.parallel[1]}],
            unit_key: match.parallel_value,
            "error_pct": match.parallel_error_pct,
        }
        standard["selected"] = {"kind": "parallel", **standard["parallel"]}

    return standard


def _tolerance_basis(match) -> str | None:
    """``sourced`` (grade table), ``assumed`` (tolerance not sourced), or None (no part)."""
    if match.tolerance_sourced is None:
        return None
    return "sourced" if match.tolerance_sourced else "assumed"


def json_component(
    name: str, value: float, parts: ResolvedParts, circuit_name: str | None = None
) -> dict:
    """Build one component object for JSON export from the design's resolved parts.

    ``circuit_name`` is the part's named-circuit element name (``CT1`` for band-pass
    ``Cp1``; the table name for ladders when omitted). A capacitor gets its standard
    choice when the design has an E-series; an inductor gets its suggestions unless
    they are off. Inductors have no standard-value choice: they are made or chosen for
    the calculated value (see the suggestions).
    """
    key = circuit_name or name
    if key.startswith("L"):
        component: dict = {"name": name, "value_henries": value}
        if parts.shows_suggestions:
            component["inductor_suggestions"] = inductor_suggestions_payload(parts.inductor(key))
        return component
    component = {"name": name, "value_farads": value}
    if parts.eseries:
        component["standard_match"] = build_standard_match(
            parts.capacitor(key), parts.eseries, "value_farads"
        )
    return component


def csv_match_fields(match: ESeriesMatch | None, formatter, eseries: str | None) -> list[str]:
    """Build the E-series recommendation-policy CSV columns for one resolved choice.

    Length and order must stay in sync with the eseries header block in
    format_csv_result — every row in the file needs the same column count. A row
    without a choice (an inductor) gets blanks; no E-series gives no columns.
    """
    if not eseries:
        return []
    if match is None:
        return [""] * len(ESERIES_CSV_HEADER)

    nearest_fmt = formatter(match.nearest_value)
    nearest_val, nearest_unit = split_value_unit(nearest_fmt)

    parallel_vals = ""
    parallel_err = ""
    if match.prefers_parallel and match.parallel and match.parallel_error_pct is not None:
        p1_fmt = formatter(match.parallel[0])
        p2_fmt = formatter(match.parallel[1])
        parallel_vals = f"{p1_fmt} || {p2_fmt}"
        parallel_err = format_fixed(match.parallel_error_pct, 1)

    selected_values = ""
    selected_error = ""
    if match.recommended_kind == "single":
        selected_values = formatter(match.single_value)
        selected_error = format_fixed(match.single_error_pct, 1)
    elif match.prefers_parallel:
        selected_values = parallel_vals
        selected_error = parallel_err

    return [
        nearest_val,
        nearest_unit,
        format_fixed(match.nearest_error_pct, 1),
        parallel_vals,
        parallel_err,
        eseries,
        match.recommended_kind,
        selected_values,
        selected_error,
        match.status,
        match.recommendation_reason,
        "; ".join(match.warnings),
        match.policy.summary(),
    ]


def format_json_result(
    result: dict,
    parts: ResolvedParts,
    primary_component: str = "capacitors",
    build_analysis=None,
) -> str:
    """Format filter results as JSON.

    Args:
        result: Filter result dictionary with capacitors, inductors, etc.
        parts: The parts ``design()`` resolved: capacitor choices (when the design has
            an E-series) and inductor suggestions (unless they are off)
        primary_component: Which component type to list first ('capacitors' or 'inductors')
        build_analysis: Optional realized-build analysis result

    Returns:
        JSON string with filter data.
    """
    cap_list = [json_component(f"C{i + 1}", v, parts) for i, v in enumerate(result["capacitors"])]
    ind_list = [json_component(f"L{i + 1}", v, parts) for i, v in enumerate(result["inductors"])]
    if primary_component == "capacitors":
        components = {"capacitors": cap_list, "inductors": ind_list}
    else:
        components = {"inductors": ind_list, "capacitors": cap_list}

    output = {
        "filter_type": result["filter_type"],
        "cutoff_frequency_hz": result["freq_hz"],
        "impedance_ohms": result["impedance"],
        "order": result["order"],
        "components": components,
    }

    if result.get("topology"):
        output["topology"] = result["topology"]

    if result.get("ripple"):
        output["ripple_db"] = result["ripple"]

    if build_analysis is not None:
        from .build_output import build_analysis_fields

        output.update(build_analysis_fields(result, build_analysis))

    return dumps_strict(output, indent=2)


def format_csv_result(
    result: dict,
    parts: ResolvedParts,
    primary_component: str = "capacitors",
) -> str:
    """Format filter results as CSV.

    Args:
        result: Filter result dictionary with capacitors, inductors, etc.
        parts: The parts ``design()`` resolved; the E-series columns appear when the
            design has an E-series, the inductor columns (each inductor's best
            suggestion) unless suggestions are off
        primary_component: Which component type to list first ('capacitors' or 'inductors')

    Returns:
        CSV rows separated by LF, without a final line terminator; the CLI's
        print and the wizard's saved file each end the document with one.
    """
    validate_finite_tree({"capacitors": result["capacitors"], "inductors": result["inductors"]})
    eseries = parts.eseries
    emit_inductors = parts.shows_suggestions

    header = ["Component", "Value", "Unit"]
    if eseries:
        header.extend(ESERIES_CSV_HEADER)
    if emit_inductors:
        header.extend(CSV_INDUCTOR_HEADER)
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)

    capacitors = ("C", result["capacitors"], format_capacitance)
    inductors = ("L", result["inductors"], format_inductance)
    groups = (
        [capacitors, inductors] if primary_component == "capacitors" else [inductors, capacitors]
    )

    for prefix, values, formatter in groups:
        for i, v in enumerate(values):
            name = f"{prefix}{i + 1}"
            val, unit = split_value_unit(formatter(v))
            row = [name, val, unit]
            # E-series columns are capacitor-only and inductor columns are
            # inductor-only; the other component type gets empty cells so
            # every row keeps the header's column count.
            match = parts.capacitor(name) if prefix == "C" and eseries else None
            row.extend(csv_match_fields(match, formatter, eseries))
            if emit_inductors:
                row.extend(inductor_csv_columns(parts.inductor(name) if prefix == "L" else None))
            writer.writerow(row)

    return output.getvalue().removesuffix("\n")


def format_quiet_result(
    result: dict, raw: bool = False, primary_component: str = "capacitors"
) -> str:
    """Format minimal output with just component values.

    Args:
        result: Filter result dictionary with capacitors, inductors, etc.
        raw: If True, show raw SI values; if False, use engineering notation
        primary_component: Which component type to list first ('capacitors' or 'inductors')

    Returns:
        Minimal string output with component values.
    """
    lines = []

    if primary_component == "capacitors":
        for i, v in enumerate(result["capacitors"]):
            lines.append(format_component_value(f"C{i + 1}", v, format_capacitance, raw))
        for i, v in enumerate(result["inductors"]):
            lines.append(format_component_value(f"L{i + 1}", v, format_inductance, raw))
    else:
        for i, v in enumerate(result["inductors"]):
            lines.append(format_component_value(f"L{i + 1}", v, format_inductance, raw))
        for i, v in enumerate(result["capacitors"]):
            lines.append(format_component_value(f"C{i + 1}", v, format_capacitance, raw))

    return "\n".join(lines)


def format_header(result: dict, topology: str, filter_category: str) -> str:
    """Format common filter header information.

    Args:
        result: Filter result dictionary
        topology: Topology description (e.g., 'Pi', 'T')
        filter_category: Filter category (e.g., 'Low-Pass', 'High-Pass')

    Returns:
        Multi-line header string (title, cutoff, impedance, order). The cutoff and
        impedance restate the typed design values exactly.
    """
    lines = []
    title = f"{result['filter_type'].title()} {topology} {filter_category} Filter"
    lines.append(f"\n{title}")
    lines.append("=" * 50)
    lines.append(f"Cutoff Frequency:    {format_restated_frequency(result['freq_hz'])}")
    lines.append(f"Impedance Z₀:        {format_restated_value(result['impedance'])} Ω")
    if result.get("ripple") is not None:
        lines.append(f"Ripple:              {result['ripple']} dB")
    lines.append(f"Order:               {result['order']}")
    lines.append("=" * 50)
    return "\n".join(lines)


def print_header(result: dict, topology: str, filter_category: str) -> None:
    """Print common filter header information."""
    print(format_header(result, topology, filter_category))


def format_component_table(
    result: dict,
    raw: bool = False,
    primary_component: str = "capacitors",
    mention_suggestions: bool = True,
) -> str:
    """Format component values in a two-column table.

    Args:
        result: Filter result dictionary
        raw: If True, show raw SI values in scientific notation
        primary_component: Which component type in left column ('capacitors' or 'inductors')
        mention_suggestions: If True, the inductor footnote points at the inductor
            suggestions (pass False when that section is off or empty)

    Returns:
        Multi-line table string.
    """
    col_width = 24

    if primary_component == "capacitors":
        left_label, right_label = "Capacitors", "Inductors"
        left_vals, right_vals = result["capacitors"], result["inductors"]
        left_fmt, right_fmt = format_capacitance, format_inductance
        left_prefix, right_prefix = "C", "L"
        left_unit, right_unit = "F", "H"
    else:
        left_label, right_label = "Inductors", "Capacitors"
        left_vals, right_vals = result["inductors"], result["capacitors"]
        left_fmt, right_fmt = format_inductance, format_capacitance
        left_prefix, right_prefix = "L", "C"
        left_unit, right_unit = "H", "F"

    max_rows = max(len(left_vals), len(right_vals))

    horiz = "\u2500" * col_width
    lines = [
        f"\n{'Component Values':^50}",
        f"\u250c{horiz}\u252c{horiz}\u2510",
        f"\u2502{left_label:^{col_width}}\u2502{right_label:^{col_width}}\u2502",
        f"\u251c{horiz}\u253c{horiz}\u2524",
    ]

    for i in range(max_rows):
        if i < len(left_vals):
            val = left_vals[i]
            left_str = (
                f"{left_prefix}{i + 1}: {val:.6e} {left_unit}"
                if raw
                else f"{left_prefix}{i + 1}: {left_fmt(val)}"
            )
        else:
            left_str = ""
        if i < len(right_vals):
            val = right_vals[i]
            right_str = (
                f"{right_prefix}{i + 1}: {val:.6e} {right_unit}"
                if raw
                else f"{right_prefix}{i + 1}: {right_fmt(val)}"
            )
        else:
            right_str = ""
        lines.append(
            f"\u2502 {left_str:<{col_width - 2}} \u2502 {right_str:<{col_width - 2}} \u2502"
        )

    lines.append(f"\u2514{horiz}\u2534{horiz}\u2518")
    if result["inductors"]:
        lines.append(inductor_note_line(mention_suggestions))
    return "\n".join(lines)


def print_component_table(
    result: dict, raw: bool = False, primary_component: str = "capacitors"
) -> None:
    """Print component values in a formatted table."""
    print(format_component_table(result, raw, primary_component))
