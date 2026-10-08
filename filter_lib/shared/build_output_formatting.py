"""Text rendering for the build simulation block (table output on every surface).

The table de-duplicates and filters caveats so each prints only where it applies;
JSON keeps every warning and limitation entry.
"""

import math
import textwrap

from .build_analysis import RANDOM_CASES_LIMITATION
from .build_types import BuildAnalysisResult, CircuitMeasurement, ComponentSubstitution
from .circuit_display_names import display_component_name
from .display_helpers import SECTION_RULE
from .formatting import format_capacitance, format_fixed, format_frequency, format_inductance
from .nominal_realization import TOROID_LIMITATION, grouped_part_warnings, uses_toroid

BUILD_SIMULATION_HEADING = "Build Simulation (chosen parts; simulated, not measured)"
_ROW_INDENT = " " * 15
_WRAP_WIDTH = 96

# Table labels for MetricSummary keys; the JSON keys stay as they are.
METRIC_LABELS = {
    "peak_transducer_gain_db": "Peak gain",
    "worst_passband_db": "Lowest gain in passband",
    "cutoff_hz": "-3 dB cutoff",
    "f_low_hz": "Lower -3 dB edge",
    "f_high_hz": "Upper -3 dB edge",
    "f0_hz": "Center",
    "bw_hz": "-3 dB bandwidth",
}

# Why a calculated value was used instead of a chosen part, by substitution status.
_FALLBACK_REASONS = {
    "expert_override_required": "below 1 pF; no part chosen",
    "no_verified_candidate": "no suitable toroid",
    "candidate_screen_disabled": "toroid windings off",
}

PASSBAND_NOTES = {
    "lowpass": "Passband = up to the requested cutoff, including it.",
    "highpass": "Passband = from the requested cutoff upward, including it.",
    "bandpass": "Passband = between the requested -3 dB edges, including them.",
}


def _landmark_text(category: str, measurement: CircuitMeasurement) -> str | None:
    """Return the -3 dB landmarks, or ``None`` when the sweep does not contain them."""
    if category == "bandpass":
        if measurement.f0 is None or measurement.bw is None:
            return None
        return (
            f"center {format_frequency(measurement.f0)}, "
            f"-3 dB bandwidth {format_frequency(measurement.bw)}, "
            f"edges {format_frequency(measurement.f_low)} / "
            f"{format_frequency(measurement.f_high)}"
        )
    cutoff = measurement.f_high if category == "lowpass" else measurement.f_low
    return None if cutoff is None else f"-3 dB cutoff {format_frequency(cutoff)}"


def _format_measurement(category: str, measurement: CircuitMeasurement) -> list[str]:
    """Return one measurement as lines: landmarks, gains, then any qualifying notes."""
    landmarks = _landmark_text(category, measurement)
    lines = [
        landmarks
        if landmarks is not None
        else (
            "no complete -3 dB passband within the simulated frequency range"
            if category == "bandpass"
            else "no -3 dB cutoff within the simulated frequency range"
        ),
        f"peak gain {format_fixed(measurement.peak_transducer_gain_db, 2)} dB, "
        f"lowest gain in passband {format_fixed(measurement.worst_passband_db, 2)} dB",
    ]
    reference = measurement.reference_peak_gain_db
    if reference is not None and not math.isclose(
        reference, measurement.peak_transducer_gain_db, abs_tol=5e-4
    ):
        lines.append(
            f"-3 dB measured from the {format_fixed(reference, 2)} dB peak at "
            f"{format_frequency(measurement.reference_peak_frequency_hz)}"
        )
    if len(measurement.threshold_regions) > 1:
        taken = (
            "edges taken from the range around the peak nearest the center"
            if category == "bandpass"
            else "cutoff taken from the range that holds the peak"
        )
        lines.append(
            f"above -3 dB in {len(measurement.threshold_regions)} separate ranges; {taken}"
        )
    if not measurement.measurement_converged:
        lines.append("did not converge; values approximate")
    if measurement.at_grid_edge and landmarks is not None:
        point = "a -3 dB edge is" if category == "bandpass" else "the -3 dB point is"
        lines.append(f"{point} outside the simulated frequency range")
    return lines


def _measurement_row(label: str, category: str, measurement: CircuitMeasurement) -> list[str]:
    first, *rest = _format_measurement(category, measurement)
    return [f"{label:<15}{first}", *(_ROW_INDENT + line for line in rest)]


def _format_substitution(substitution: ComponentSubstitution, eseries: str | None = None) -> str:
    """Return one ``Parts used`` row (without alignment padding)."""
    formatter = format_capacitance if substitution.kind == "C" else format_inductance
    name = display_component_name(substitution.logical_name)
    if substitution.method == "exact_fallback":
        reason = _FALLBACK_REASONS.get(substitution.status, "no part chosen")
        return (
            f"  {name}: {formatter(substitution.nominal_value)}, calculated value used ({reason})"
        )
    detail = " || ".join(formatter(value) for value in substitution.physical_parts)
    if substitution.core_name is not None:
        detail += f", {substitution.turns} turns"
        if substitution.wire_awg is not None:
            detail += f" of AWG {substitution.wire_awg}"
        detail += f" on {substitution.core_name}"
        if substitution.wire_length_mm is not None:
            detail += f" ({substitution.wire_length_mm:.0f} mm wire)"
    elif eseries is not None:
        detail += f" ({eseries})"
    return f"  {name}: {detail}"


def _parts_used_lines(analysis: BuildAnalysisResult) -> list[str]:
    substitutions = analysis.nominal_realization.substitutions
    width = max((len(display_component_name(s.logical_name)) for s in substitutions), default=0)
    lines = ["Parts used:"]
    for substitution in substitutions:
        name = display_component_name(substitution.logical_name)
        row = _format_substitution(substitution, analysis.config.eseries)
        # Align the values after the names.
        lines.append(row.replace(f"  {name}: ", f"  {name + ':':<{width + 1}} ", 1))
    return lines


def _fallback_note(analysis: BuildAnalysisResult) -> str | None:
    substitutions = analysis.nominal_realization.substitutions
    fallbacks = sum(item.method == "exact_fallback" for item in substitutions)
    if not fallbacks:
        return None
    return (
        f"{_ROW_INDENT}calculated value used for {fallbacks} of {len(substitutions)} parts "
        "(see Parts used)"
    )


def _loss_line(analysis: BuildAnalysisResult) -> str:
    """State which part losses (Q) the simulation applied."""
    elements = [
        element
        for element in analysis.nominal_realization.circuit.elements
        if element.quality_factor is not None
    ]
    if not elements:
        return "Part losses (Q): none; all parts are lossless."
    reference = format_frequency(elements[0].loss_reference_frequency_hz)
    parts = []
    for kind, label in (("L", "inductors"), ("C", "capacitors")):
        values = dict.fromkeys(
            f"{element.quality_factor:g}" for element in elements if element.kind == kind
        )
        if values:
            parts.append(f"{label} {', '.join(values)}")
    return f"Part losses (Q at {reference}): {', '.join(parts)}."


def _format_metric_value(metric: str, value: float) -> str:
    if metric.endswith("_hz"):
        return format_frequency(value)
    return f"{format_fixed(value, 3)} dB"


def _metric_values(summary) -> str:
    """Join min / p05 / median / p95 / max, printing a shared unit once."""
    texts = [
        _format_metric_value(summary.metric, value)
        for value in (summary.minimum, summary.p05, summary.p50, summary.p95, summary.maximum)
    ]
    units = {text.rsplit(" ", 1)[-1] for text in texts}
    if len(units) == 1:
        unit = units.pop()
        return " / ".join(text.rsplit(" ", 1)[0] for text in texts) + f" {unit}"
    return " / ".join(texts)


def _format_summary(summary, width: int = 0) -> list[str]:
    """Return one metric row, plus a case-count line when any case was left out."""
    label = METRIC_LABELS.get(summary.metric, summary.metric) + ":"
    lines = [f"  {label:<{width + 1}} {_metric_values(summary)}"]
    if summary.omitted_cases or summary.grid_censored_cases or summary.unresolved_cases:
        total = summary.included_cases + summary.omitted_cases
        counts = f"{summary.included_cases} of {total} cases"
        if summary.grid_censored_cases:
            counts += f"; {summary.grid_censored_cases} outside the simulated frequency range"
        if summary.unresolved_cases:
            counts += f"; {summary.unresolved_cases} did not converge"
        lines.append(" " * (width + 4) + counts)
    return lines


def _tolerance_lines(analysis: BuildAnalysisResult) -> list[str]:
    config = analysis.config
    first = (
        f"Tolerance cases: C ±{config.capacitor_tolerance_pct:g}%, "
        f"L ±{config.inductor_tolerance_pct:g}%. "
        f"{len(analysis.cases)} cases: nominal, all low, all high,"
    )
    samples = config.sample_count
    if samples:
        noun = "case" if samples == 1 else "cases"
        second = (
            f"  each part low and high alone, and {samples} extra random tolerance {noun} "
            f"(seed {config.seed})."
        )
    else:
        second = "  and each part low and high alone."
    return [first, second]


def _bullets(items) -> list[str]:
    lines: list[str] = []
    for item in items:
        lines.extend(
            textwrap.wrap(
                item,
                width=_WRAP_WIDTH,
                initial_indent="  - ",
                subsequent_indent="    ",
                break_on_hyphens=False,
            )
        )
    return lines


def _applicable_limitations(analysis: BuildAnalysisResult) -> list[str]:
    """Drop caveats about features this run did not use."""
    skipped = set()
    if not uses_toroid(analysis.nominal_realization.substitutions):
        skipped.add(TOROID_LIMITATION)
    if not analysis.config.sample_count:
        skipped.add(RANDOM_CASES_LIMITATION)
    return [item for item in dict.fromkeys(analysis.limitations) if item not in skipped]


def format_build_analysis_block(analysis: BuildAnalysisResult) -> list[str]:
    """Render the build simulation block with its caveats."""
    category = analysis.category
    lines = [
        "",
        BUILD_SIMULATION_HEADING,
        SECTION_RULE,
        (
            f"Simulated with a {analysis.source_resistance_ohm:g} Ω source and a "
            f"{analysis.load_resistance_ohm:g} Ω load; gains are transducer gain (Gt)."
        ),
        _loss_line(analysis),
        PASSBAND_NOTES[category],
        *_measurement_row("Ideal values:", category, analysis.calculated),
        *_measurement_row("Chosen parts:", category, analysis.nominal_build),
    ]
    fallback_note = _fallback_note(analysis)
    if fallback_note is not None:
        lines.append(fallback_note)
    lines.extend(_parts_used_lines(analysis))
    lines.extend(_tolerance_lines(analysis))
    lines.append(
        "Spread across these cases (min / 5th percentile / median / 95th percentile / max):"
    )
    width = max(
        (len(METRIC_LABELS.get(item.metric, item.metric)) for item in analysis.metric_summaries),
        default=0,
    )
    for summary in analysis.metric_summaries:
        lines.extend(_format_summary(summary, width))
    warnings = grouped_part_warnings(analysis.nominal_realization.substitutions)
    if warnings:
        lines.append("Build warnings:")
        lines.extend(_bullets(warnings))
    lines.append("Model limits:")
    lines.extend(_bullets(_applicable_limitations(analysis)))
    return lines
