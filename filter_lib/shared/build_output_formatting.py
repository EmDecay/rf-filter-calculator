"""Concise text rendering for realized-build analysis."""

from .build_types import BuildAnalysisResult, CircuitMeasurement, ComponentSubstitution
from .formatting import format_capacitance, format_frequency, format_inductance


def _format_measurement(category: str, measurement: CircuitMeasurement) -> str:
    """Format category-specific response landmarks on one line."""
    if category == "bandpass":
        if measurement.f0 is None or measurement.bw is None:
            landmarks = "no complete -3 dB passband on the simulation grid"
        else:
            landmarks = (
                f"f0 {format_frequency(measurement.f0)}, "
                f"BW {format_frequency(measurement.bw)}, "
                f"edges {format_frequency(measurement.f_low)} / "
                f"{format_frequency(measurement.f_high)}"
            )
    else:
        cutoff = measurement.f_high if category == "lowpass" else measurement.f_low
        landmarks = (
            f"-3 dB cutoff {format_frequency(cutoff)}"
            if cutoff is not None
            else "no -3 dB cutoff on the simulation grid"
        )
    return (
        f"{landmarks}; peak Gt {measurement.peak_transducer_gain_db:.2f} dB; "
        f"worst requested-passband Gt {measurement.worst_passband_db:.2f} dB"
    )


def _format_substitution(substitution: ComponentSubstitution) -> str:
    formatter = format_capacitance if substitution.kind == "C" else format_inductance
    parts = " + ".join(formatter(value) for value in substitution.physical_parts)
    detail = f"{substitution.method}: {parts}"
    if substitution.core_name is not None:
        detail += f" on {substitution.core_name}, {substitution.turns} turns"
    return f"  {substitution.logical_name}: {detail} [{substitution.status}]"


def _format_metric_value(metric: str, value: float) -> str:
    if metric.endswith("_hz"):
        return format_frequency(value)
    return f"{value:.3f} dB"


def _format_summary(summary) -> str:
    case_counts = f"; cases included {summary.included_cases}, omitted {summary.omitted_cases}"
    if summary.grid_censored_cases:
        case_counts += f" ({summary.grid_censored_cases} grid-boundary-censored)"
    return (
        f"  {summary.metric}: "
        f"min {_format_metric_value(summary.metric, summary.minimum)}, "
        f"p05 {_format_metric_value(summary.metric, summary.p05)}, "
        f"median {_format_metric_value(summary.metric, summary.p50)}, "
        f"p95 {_format_metric_value(summary.metric, summary.p95)}, "
        f"max {_format_metric_value(summary.metric, summary.maximum)}"
        f"{case_counts}"
    )


def format_build_analysis_block(analysis: BuildAnalysisResult) -> list[str]:
    """Render a concise, plainly limited realized-build simulation block."""
    config = analysis.config
    lines = [
        "",
        "Realized-Build Analysis (simulation, not a measurement)",
        "-" * 62,
        (
            f"Evaluation: Rs={analysis.source_resistance_ohm:g} ohm, "
            f"Rl={analysis.load_resistance_ohm:g} ohm; transducer power gain"
        ),
        "Calculated exact values: " + _format_measurement(analysis.category, analysis.calculated),
        "Selected nominal build:  "
        + _format_measurement(analysis.category, analysis.nominal_build),
        "Nominal substitutions:",
    ]
    lines.extend(
        _format_substitution(substitution)
        for substitution in analysis.nominal_realization.substitutions
    )
    lines.extend(
        (
            "Tolerance screening: "
            f"C +/-{config.capacitor_tolerance_pct:g}%, "
            f"L +/-{config.inductor_tolerance_pct:g}%; "
            f"{len(analysis.cases)} cases "
            f"({config.sample_count} seeded uniform samples, seed {config.seed})",
            "Screened metric envelopes (not guaranteed worst case or probability):",
        )
    )
    lines.extend(_format_summary(summary) for summary in analysis.metric_summaries)
    warnings = tuple(dict.fromkeys(analysis.nominal_realization.warnings))
    if warnings:
        lines.append("Build warnings:")
        lines.extend(f"  - {warning}" for warning in warnings)
    lines.append("Model limits:")
    lines.extend(f"  - {item}" for item in dict.fromkeys(analysis.limitations))
    return lines
