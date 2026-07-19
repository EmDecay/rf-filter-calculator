"""Common display formatting functions for lowpass and highpass filters.

Extracts shared logic to reduce code duplication between filter display modules.
Each filter module can import these and customize as needed.
"""

import csv
from io import StringIO
from typing import Any

from .display_helpers import format_component_value, split_value_unit
from .eseries import match_component
from .formatting import format_capacitance, format_inductance
from .strict_json import dumps_strict, validate_finite_tree
from .toroid_display import CSV_TOROID_HEADER, build_json_recommendations, csv_columns_for_best
from .toroid_selection import recommend_cores

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


def build_standard_match(value: float, eseries: str, unit_key: str, parallel_mode: str) -> dict:
    """Build JSON-serializable E-series match data for one component.

    Args:
        value: Component value in base SI units (F or H)
        eseries: E-series name ('E12', 'E24', 'E96')
        unit_key: JSON key naming the unit ('value_farads' or 'value_henries')
        parallel_mode: How parallel pairs combine — 'additive' for
            capacitors (C1 + C2), 'harmonic' for inductors (reciprocal sum).
            Must match the component physics or the pair value is wrong.

    Returns:
        Dict with 'series' and 'nearest' keys; 'parallel' only when a
        two-component pair beats the single nearest value.
    """
    match = match_component(value, eseries, parallel_mode=parallel_mode)

    standard: dict = {
        "series": eseries,
        "nearest": {
            unit_key: match.single_value,
            "error_pct": match.single_error_pct,
        },
        "policy": match.policy.as_dict(),
        "status": match.status,
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


def _json_component(
    name: str,
    value: float,
    unit_key: str,
    eseries: str | None,
    parallel_mode: str,
    toroid_freq_hz: float | None = None,
) -> dict:
    """Build one component object for JSON export.

    If toroid_freq_hz is provided AND this is an inductor row (unit_key=value_henries),
    attach `toroid_recommendations` sourced via recommend_cores.
    """
    component = {"name": name, unit_key: value}
    # E-series matching applies to capacitors only: inductors are hand-wound
    # to the exact value (see toroid recommendations), not bought off a
    # standard-value chart.
    if eseries and unit_key == "value_farads":
        component["standard_match"] = build_standard_match(value, eseries, unit_key, parallel_mode)
    if toroid_freq_hz is not None and unit_key == "value_henries":
        recs = recommend_cores(value, toroid_freq_hz)
        component["toroid_recommendations"] = build_json_recommendations(recs)
    return component


def csv_match_fields(value: float, formatter, eseries: str | None, parallel_mode: str) -> list[str]:
    """Build the E-series recommendation-policy CSV columns for one component.

    Length and order must stay in sync with the eseries header block in
    format_csv_result — every row in the file needs the same column count.
    """
    if not eseries:
        return []

    match = match_component(value, eseries, parallel_mode=parallel_mode)
    nearest_fmt = formatter(match.single_value)
    nearest_val, nearest_unit = split_value_unit(nearest_fmt)

    parallel_vals = ""
    parallel_err = ""
    if match.prefers_parallel and match.parallel and match.parallel_error_pct is not None:
        p1_fmt = formatter(match.parallel[0])
        p2_fmt = formatter(match.parallel[1])
        parallel_vals = f"{p1_fmt} || {p2_fmt}"
        parallel_err = f"{match.parallel_error_pct:.1f}"

    selected_values = ""
    selected_error = ""
    if match.recommended_kind == "single":
        selected_values = nearest_fmt
        selected_error = f"{match.single_error_pct:.1f}"
    elif match.prefers_parallel:
        selected_values = parallel_vals
        selected_error = parallel_err

    return [
        nearest_val,
        nearest_unit,
        f"{match.single_error_pct:.1f}",
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
    primary_component: str = "capacitors",
    eseries: str | None = None,
    toroid_freq_hz: float | None = None,
    include_toroids: bool = True,
    matched_sim: dict[str, Any] | None = None,
    build_analysis=None,
) -> str:
    """Format filter results as JSON.

    Args:
        result: Filter result dictionary with capacitors, inductors, etc.
        primary_component: Which component type to list first ('capacitors' or 'inductors')
        eseries: E-series for standard matching (None to disable)
        toroid_freq_hz: Design frequency in Hz for toroid recommendations (None disables)
        include_toroids: If False, skip toroid recommendations entirely
        matched_sim: Optional deprecated matched-value compatibility payload
        build_analysis: Optional realized-build analysis result

    Returns:
        JSON string with filter data.
    """
    freq_for_toroids = toroid_freq_hz if include_toroids else None

    cap_list = [
        _json_component(f"C{i + 1}", v, "value_farads", eseries, "additive")
        for i, v in enumerate(result["capacitors"])
    ]
    ind_list = [
        _json_component(f"L{i + 1}", v, "value_henries", eseries, "harmonic", freq_for_toroids)
        for i, v in enumerate(result["inductors"])
    ]
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

    if matched_sim is not None:
        output["matched_sim"] = matched_sim
    if build_analysis is not None:
        from .build_output import build_analysis_fields

        output.update(build_analysis_fields(result, build_analysis))

    return dumps_strict(output, indent=2)


def format_csv_result(
    result: dict,
    primary_component: str = "capacitors",
    eseries: str | None = None,
    toroid_freq_hz: float | None = None,
    include_toroids: bool = True,
) -> str:
    """Format filter results as CSV.

    Args:
        result: Filter result dictionary with capacitors, inductors, etc.
        primary_component: Which component type to list first ('capacitors' or 'inductors')
        eseries: E-series for standard matching (None to disable)
        toroid_freq_hz: Design frequency in Hz for toroid best-match columns (None disables)
        include_toroids: If False, skip toroid columns entirely (backward-compat CSV)

    Returns:
        CSV string with component data.
    """
    validate_finite_tree(
        {
            "capacitors": result["capacitors"],
            "inductors": result["inductors"],
            "toroid_frequency_hz": toroid_freq_hz,
        }
    )
    emit_toroids = include_toroids and toroid_freq_hz is not None
    n_toroid_cols = len(CSV_TOROID_HEADER)

    header = ["Component", "Value", "Unit"]
    if eseries:
        header.extend(ESERIES_CSV_HEADER)
    if emit_toroids:
        header.extend(CSV_TOROID_HEADER)
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)

    if primary_component == "capacitors":
        left = [("C", result["capacitors"], format_capacitance, "additive")]
        right = [("L", result["inductors"], format_inductance, "harmonic")]
    else:
        left = [("L", result["inductors"], format_inductance, "harmonic")]
        right = [("C", result["capacitors"], format_capacitance, "additive")]

    for prefix, values, formatter, parallel_mode in left + right:
        for i, v in enumerate(values):
            formatted = formatter(v)
            val, unit = split_value_unit(formatted)
            row = [f"{prefix}{i + 1}", val, unit]
            # E-series columns are capacitor-only and toroid columns are
            # inductor-only; the other component type gets empty cells so
            # every row keeps the header's column count.
            if prefix == "C":
                row.extend(csv_match_fields(v, formatter, eseries, parallel_mode))
            elif eseries:
                row.extend([""] * len(ESERIES_CSV_HEADER))
            if emit_toroids:
                if prefix == "L":
                    recs = recommend_cores(v, toroid_freq_hz)
                    row.extend(csv_columns_for_best(recs))
                else:
                    row.extend([""] * n_toroid_cols)
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
        filter_category: Filter category (e.g., 'Low Pass', 'High Pass')

    Returns:
        Multi-line header string (title, cutoff, impedance, order).
    """
    from .formatting import format_frequency

    lines = []
    title = f"{result['filter_type'].title()} {topology} {filter_category} Filter"
    lines.append(f"\n{title}")
    lines.append("=" * 50)
    lines.append(f"Cutoff Frequency:    {format_frequency(result['freq_hz'])}")
    lines.append(f"Impedance Z0:        {result['impedance']:.4g} Ohm")
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
    mention_toroids: bool = True,
) -> str:
    """Format component values in a two-column table.

    Args:
        result: Filter result dictionary
        raw: If True, show raw SI values in scientific notation
        primary_component: Which component type in left column ('capacitors' or 'inductors')
        mention_toroids: If True, the inductor footnote points at the toroid
            recommendations section (suppressed under --no-toroids)

    Returns:
        Multi-line table string.
    """
    from .formatting import format_capacitance, format_inductance

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
        note = " (see toroid recommendations)" if mention_toroids else ""
        lines.append(f"Inductors: wind to value{note}")
    return "\n".join(lines)


def print_component_table(
    result: dict, raw: bool = False, primary_component: str = "capacitors"
) -> None:
    """Print component values in a formatted table."""
    print(format_component_table(result, raw, primary_component))
