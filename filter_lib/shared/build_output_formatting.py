"""Text rendering for the build simulation block (table output on every surface).

The table de-duplicates and filters caveats so each prints only where it applies;
JSON keeps every warning and limitation entry.
"""

import math
import textwrap

from .build_analysis import RANDOM_CASES_LIMITATION
from .build_types import BuildAnalysisResult, CircuitMeasurement, ComponentSubstitution
from .capacitor_choice import assumed_tolerance_pct
from .capacitor_grades import require_grade
from .circuit_display_names import display_component_name
from .component_realization import FIXED_PLUS_TRIMMER_METHOD, inductor_case_tolerance_pct
from .display_helpers import SECTION_RULE, wrap_keeping_units
from .eseries import TOLERANCE_NOT_SOURCED
from .formatting import (
    band_edge_digits,
    format_capacitance,
    format_fixed,
    format_frequency,
    format_inductance,
    format_restated_frequency,
    format_tank_frequency,
)
from .inductor_suggestion import KIND_LABELS, NO_QUALIFYING_SUGGESTION, SUGGESTIONS_NOT_USED
from .nominal_realization import TOROID_LIMITATION, grouped_part_warnings, uses_toroid
from .srf_screen import describe_range, format_range_top

BUILD_SIMULATION_HEADING = "Build Simulation (chosen parts; simulated, not measured)"
EQUAL_PORTS_GAIN_NOTE = (
    "Source and load are equal, so each gain in dB is the negative of the insertion loss."
)
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
    NO_QUALIFYING_SUGGESTION: "no inductor suggestion used",
    SUGGESTIONS_NOT_USED: "inductor suggestions not used",
}

PASSBAND_NOTES = {
    "lowpass": "Passband = up to the requested cutoff, including it.",
    "highpass": "Passband = from the requested cutoff upward, including it.",
    "bandpass": "Passband = between the requested -3 dB edges, including them.",
}

# A chosen-parts result outside the frequencies where every chip inductor is within its
# allowances (BuildAnalysisResult.qualified_range_hz).
PARASITIC_PREDICTION = "predicted with the parasitic model, not qualified"
# Table labels for the figures a measurement reports outside the range (JSON keys of
# CircuitMeasurement.outside_range), in that order.
_OUTSIDE_LABELS = {
    "cutoff_hz": "-3 dB cutoff",
    "f_low_hz": "lower -3 dB edge",
    "f_high_hz": "upper -3 dB edge",
    "f0_hz": "center",
    "bandwidth_hz": "-3 dB bandwidth",
    "reference_peak_frequency_hz": "the peak the -3 dB points are measured from",
    "peak_frequency_hz": "peak gain",
    "open_half_power_region": "the range above -3 dB, open at the end of the sweep",
    "half_power_regions": "a separate range above -3 dB",
}


def highpass_passband_note(top_hz: float | None) -> str:
    """The high-pass passband note when its figures are limited to the qualified range."""
    # The top is printed rounded down, like the qualified range it ends at.
    upper = (
        "upward, including it"
        if top_hz is None
        else f"up to {format_range_top(top_hz)}, including both"
    )
    return (
        f"Passband = from the requested cutoff {upper}; a high-pass build takes its peak and "
        "half-power threshold only where its chip inductors are qualified."
    )


def _outside_labels(keys) -> str:
    """The figures outside the range, in words (``peak gain and -3 dB cutoff``)."""
    names = [label for key, label in _OUTSIDE_LABELS.items() if key in keys]
    if len(names) > 1:
        return ", ".join(names[:-1]) + " and " + names[-1]
    return names[0]


def qualified_range_line(qualified_range: tuple[float, float], lossy: bool = False) -> str:
    """Where every chip inductor in the build is within its allowances.

    ``lossy``: a Q is applied to a chip inductor, which the screen's lossless part model
    does not include, so the line says the range is that model's.
    """
    model = (
        " (in its lossless part model; the Q you gave is not part of this check)" if lossy else ""
    )
    return (
        f"Qualified range: {describe_range(qualified_range)}, where every chip inductor{model} "
        f"stays within its allowances; results outside it are {PARASITIC_PREDICTION}."
    )


def _lossy_chips(analysis: BuildAnalysisResult) -> bool:
    """Whether the build applies a Q to an inductor that carries a self-capacitance."""
    realization = analysis.nominal_realization
    chips = {s.logical_name for s in realization.substitutions if s.self_capacitance_f}
    return any(
        element.kind == "L" and element.quality_factor is not None and element.name in chips
        for element in realization.circuit.elements
    )


def _edge_digits(measurement: CircuitMeasurement) -> int | None:
    """Digits a band-pass measurement's center and edges need to restate its bandwidth
    (as the design header prints its edges); ``None`` without both edges."""
    if measurement.f_high is None or measurement.bw is None or measurement.bw <= 0:
        return None
    return band_edge_digits(measurement.f_high, measurement.bw)


def _band_frequency(value: float, digits: int | None) -> str:
    return format_frequency(value) if digits is None else format_restated_frequency(value, digits)


def _landmark_text(category: str, measurement: CircuitMeasurement) -> str | None:
    """Return the -3 dB landmarks, or ``None`` when the sweep does not contain them."""
    if category == "bandpass":
        if measurement.f0 is None or measurement.bw is None:
            return None
        digits = _edge_digits(measurement)
        return (
            f"center {_band_frequency(measurement.f0, digits)}, "
            f"-3 dB bandwidth {format_frequency(measurement.bw)}, "
            f"edges {_band_frequency(measurement.f_low, digits)} / "
            f"{_band_frequency(measurement.f_high, digits)}"
        )
    cutoff = measurement.ladder_cutoff(category)
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
        digits = _edge_digits(measurement) if category == "bandpass" else None
        lines.append(
            f"-3 dB measured from the {format_fixed(reference, 2)} dB peak at "
            f"{_band_frequency(measurement.reference_peak_frequency_hz, digits)}"
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


def _measurement_row(
    label: str,
    category: str,
    measurement: CircuitMeasurement,
    qualified_range: tuple[float, float] | None = None,
) -> list[str]:
    """One measurement; a chosen-parts landmark outside ``qualified_range`` is labelled."""
    first, *rest = _format_measurement(category, measurement)
    outside = measurement.outside_range(category, qualified_range)
    if outside:
        rest.extend(
            textwrap.wrap(
                f"{_outside_labels(outside)} {PARASITIC_PREDICTION}",
                width=_WRAP_WIDTH - len(_ROW_INDENT),
                break_on_hyphens=False,
            )
        )
    return [f"{label:<15}{first}", *(_ROW_INDENT + line for line in rest)]


def trimmer_part_text(substitution: ComponentSubstitution) -> str:
    """A tank's fixed part plus its trimmer and nominal setting (``Parts used`` row)."""
    trimmer = substitution.trimmer
    assert trimmer is not None
    setting = trimmer.setting
    fixed = " || ".join(format_capacitance(value) for value in substitution.physical_parts)
    text = f"{fixed} + " if fixed else ""
    # The knob setting, then what it gives with the series inductance at the tank frequency.
    text += (
        f"trimmer {trimmer.part_numbers[0]} set to {format_capacitance(setting.setting_f)} "
        f"({format_capacitance(setting.effective_f)} effective at "
        f"{format_tank_frequency(trimmer.tuning_frequency_hz)})"
    )
    if not setting.in_range:
        text += f" (end of its range; {format_capacitance(setting.required_f)} needed)"
    if substitution.stray_capacitance_f:
        text += f", plus {format_capacitance(substitution.stray_capacitance_f)} stray (assumed)"
    return text


def _format_substitution(substitution: ComponentSubstitution, eseries: str | None = None) -> str:
    """Return one ``Parts used`` row (without alignment padding)."""
    formatter = format_capacitance if substitution.kind == "C" else format_inductance
    name = display_component_name(substitution.logical_name)
    if substitution.method == FIXED_PLUS_TRIMMER_METHOD:
        return f"  {name}: {trimmer_part_text(substitution)}"
    if substitution.method == "exact_fallback":
        reason = _FALLBACK_REASONS.get(substitution.status, "no part chosen")
        return (
            f"  {name}: {formatter(substitution.nominal_value)}, calculated value used ({reason})"
        )
    detail = " || ".join(formatter(value) for value in substitution.physical_parts)
    if substitution.self_capacitance_f is not None:
        detail += (
            f", {KIND_LABELS[substitution.inductor_kind].lower()} {substitution.part_name}, "
            f"plus {format_capacitance(substitution.self_capacitance_f)} self-capacitance"
        )
        return f"  {name}: {detail}"
    if substitution.core_name is not None:
        detail += f", {substitution.turns} turns"
        if substitution.wire_awg is not None:
            detail += f" of AWG {substitution.wire_awg}"
        detail += f" on {substitution.core_name}"
        if substitution.wire_length_mm is not None:
            detail += f" ({substitution.wire_length_mm:.0f} mm wire)"
    elif substitution.inductor_kind is not None:
        detail += f", {KIND_LABELS[substitution.inductor_kind].lower()} {substitution.part_name}"
    elif eseries is not None:
        detail += f" ({eseries})"
    if substitution.stray_capacitance_f:
        detail += f", plus {formatter(substitution.stray_capacitance_f)} stray (assumed)"
    return f"  {name}: {detail}"


def _parts_used_lines(analysis: BuildAnalysisResult) -> list[str]:
    substitutions = analysis.nominal_realization.substitutions
    width = max((len(display_component_name(s.logical_name)) for s in substitutions), default=0)
    lines = ["Parts used:"]
    for substitution in substitutions:
        name = display_component_name(substitution.logical_name)
        row = _format_substitution(substitution, analysis.eseries)
        # Align the values after the names; a long row continues under its value.
        aligned = row.replace(f"  {name}: ", f"  {name + ':':<{width + 1}} ", 1)
        lines.extend(wrap_keeping_units(aligned, _WRAP_WIDTH, subsequent_indent=" " * (width + 4)))
    note = _stray_note(analysis)
    if note:
        lines.append(note)
    return lines


def _stray_note(analysis: BuildAnalysisResult) -> str | None:
    """The assumed pair stray, when no row shows it but it shaped the capacitor choice.

    The stray decides whether a pair can beat a single part, so it is stated even when
    every pair lost (or the stray is zero); a row shows it only when a pair carries it.
    """
    substitutions = analysis.nominal_realization.substitutions
    chosen = any(item.kind == "C" and item.method != "exact_fallback" for item in substitutions)
    if not chosen or any(item.stray_capacitance_f for item in substitutions):
        return None
    stray = analysis.match_policy.stray_capacitance_f
    pairs = any(item.kind == "C" and len(item.physical_parts) > 1 for item in substitutions)
    amount = f"{format_capacitance(stray)} (assumed)" if stray else "none"
    suffix = "" if pairs else "; no parallel pair chosen"
    return f"  Stray across a pair's second part: {amount}{suffix}."


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


# Band-pass spread rows of positions in the band, printed with the edges' digits.
_BAND_POSITION_METRICS = frozenset({"f_low_hz", "f_high_hz", "f0_hz"})


def _format_metric_value(metric: str, value: float, digits: int | None = None) -> str:
    if metric in _BAND_POSITION_METRICS:
        return _band_frequency(value, digits)
    if metric.endswith("_hz"):
        return format_frequency(value)
    return f"{format_fixed(value, 3)} dB"


def _metric_values(summary, digits: int | None = None) -> str:
    """Join min / p05 / median / p95 / max, printing a shared unit once."""
    texts = [
        _format_metric_value(summary.metric, value, digits)
        for value in (summary.minimum, summary.p05, summary.p50, summary.p95, summary.maximum)
    ]
    units = {text.rsplit(" ", 1)[-1] for text in texts}
    if len(units) == 1:
        unit = units.pop()
        return " / ".join(text.rsplit(" ", 1)[0] for text in texts) + f" {unit}"
    return " / ".join(texts)


def _format_summary(
    summary, width: int = 0, outside: bool = False, digits: int | None = None
) -> list[str]:
    """Return one metric row, plus a case-count line when any case was left out.

    ``outside``: some case's value rests on frequencies outside the qualified range, so
    the row says it is predicted with the parasitic model, not qualified.
    """
    label = METRIC_LABELS.get(summary.metric, summary.metric) + ":"
    lines = [f"  {label:<{width + 1}} {_metric_values(summary, digits)}"]
    if outside:
        lines.extend(
            textwrap.wrap(
                f"some cases outside the qualified range: {PARASITIC_PREDICTION}",
                width=_WRAP_WIDTH,
                initial_indent=" " * (width + 4),
                subsequent_indent=" " * (width + 4),
                break_on_hyphens=False,
            )
        )
    if summary.omitted_cases or summary.grid_censored_cases or summary.unresolved_cases:
        total = summary.included_cases + summary.omitted_cases
        counts = f"{summary.included_cases} of {total} cases"
        if summary.grid_censored_cases:
            counts += f"; {summary.grid_censored_cases} outside the simulated frequency range"
        if summary.unresolved_cases:
            counts += f"; {summary.unresolved_cases} did not converge"
        lines.append(" " * (width + 4) + counts)
    return lines


def inductor_tolerance_text(analysis: BuildAnalysisResult) -> str:
    """How the inductors' tolerances were set: entered, or each chip inductor's own."""
    default = f"±{inductor_case_tolerance_pct(analysis.config):g}%"
    inductors = [item for item in analysis.nominal_realization.substitutions if item.kind == "L"]
    own = sorted({item.tolerance_pct for item in inductors if item.own_tolerance})
    if not own:
        return f"L {default}"
    own_text = f"±{own[0]:g}%" if len(own) == 1 else f"±{own[0]:g}% to ±{own[-1]:g}%"
    text = f"each chip inductor at its own tolerance ({own_text})"
    if not all(item.own_tolerance for item in inductors):
        text += f", other inductors {default}"
    return text


def _tolerance_lines(analysis: BuildAnalysisResult) -> list[str]:
    config = analysis.config
    first, *rest = _wrapped(
        f"Tolerance cases: {capacitor_tolerance_text(analysis)}, "
        f"{inductor_tolerance_text(analysis)}."
    )
    cases = f"  {len(analysis.cases)} cases: nominal, all low, all high,"
    samples = config.sample_count
    if samples:
        noun = "case" if samples == 1 else "cases"
        second = (
            f"  each part low and high alone, and {samples} extra random tolerance {noun} "
            f"(seed {config.seed})."
        )
    else:
        second = "  and each part low and high alone."
    lines = [first, *rest, cases, second]
    if analysis.has_trimmers:
        out_of_range = analysis.out_of_range_cases()
        reach = (
            "every trimmer reached its setting in every case"
            if not out_of_range
            else f"in {out_of_range} {'case' if out_of_range == 1 else 'cases'} a trimmer could "
            "not reach its setting and stays at the end of its range (JSON lists each case)"
        )
        lines.extend(
            _wrapped(
                "Each case is simulated with every trimmer at its nominal setting, then again "
                f"with every trimmer retuned for that case; {reach}."
            )
        )
    return lines


def capacitor_tolerance_text(analysis: BuildAnalysisResult) -> str:
    """How the capacitors' tolerances were set: the grade, any override, any assumption."""
    policy = analysis.match_policy
    grade = require_grade(policy.grade).label.lower()
    if policy.tolerance_override_pct is None:
        text = f"each capacitor at its {grade}-grade tolerance"
    else:
        text = (
            f"each capacitor at the larger of ±{policy.tolerance_override_pct:g}% and its "
            f"{grade}-grade tolerance"
        )
    assumed = any(
        item.kind == "C" and item.status in (TOLERANCE_NOT_SOURCED, "expert_override_required")
        for item in analysis.nominal_realization.substitutions
    )
    if assumed:
        text += f" (±{assumed_tolerance_pct(policy):g}% where not sourced)"
    return text


def _wrapped(text: str) -> list[str]:
    """A note at the block's width (most notes fit on one line)."""
    return textwrap.wrap(text, width=_WRAP_WIDTH, subsequent_indent="  ", break_on_hyphens=False)


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
    ]
    # Only with equal ports is the source's available power what the load would get without
    # the filter, so only then is Gt the familiar insertion loss with its sign flipped.
    if analysis.source_resistance_ohm == analysis.load_resistance_ohm:
        lines.append(EQUAL_PORTS_GAIN_NOTE)
    qualified = analysis.qualified_range_hz
    passband_note = (
        PASSBAND_NOTES[category]
        if analysis.passband_top_hz is None and analysis.peak_range_hz is None
        else highpass_passband_note(analysis.passband_top_hz)
    )
    lines += [
        _loss_line(analysis),
        *_wrapped(passband_note),
        *(
            []
            if qualified is None
            else _wrapped(qualified_range_line(qualified, _lossy_chips(analysis)))
        ),
        *_measurement_row("Ideal values:", category, analysis.calculated),
        *_measurement_row("Chosen parts:", category, analysis.nominal_build, qualified),
    ]
    fallback_note = _fallback_note(analysis)
    if fallback_note is not None:
        lines.append(fallback_note)
    lines.extend(_parts_used_lines(analysis))
    lines.extend(_tolerance_lines(analysis))
    columns = "(min / 5th percentile / median / 95th percentile / max)"
    lines.extend(
        _wrapped(f"Spread across these cases, trimmers at their nominal settings {columns}:")
        if analysis.has_trimmers
        else [f"Spread across these cases {columns}:"]
    )
    summaries = (*analysis.metric_summaries, *analysis.tuned_metric_summaries)
    width = max((len(METRIC_LABELS.get(item.metric, item.metric)) for item in summaries), default=0)
    # The design's own band sets how finely band-pass positions print.
    digits = _edge_digits(analysis.calculated) if category == "bandpass" else None
    outside = analysis.metrics_outside_qualified_range()
    for summary in analysis.metric_summaries:
        lines.extend(_format_summary(summary, width, summary.metric in outside, digits))
    if analysis.has_trimmers:
        lines.append("Spread after retuning the trimmers in each case:")
        outside = analysis.metrics_outside_qualified_range(tuned=True)
        for summary in analysis.tuned_metric_summaries:
            lines.extend(_format_summary(summary, width, summary.metric in outside, digits))
    warnings = grouped_part_warnings(analysis.nominal_realization.substitutions)
    if warnings:
        lines.append("Build warnings:")
        lines.extend(_bullets(warnings))
    lines.append("Model limits:")
    lines.extend(_bullets(_applicable_limitations(analysis)))
    return lines
