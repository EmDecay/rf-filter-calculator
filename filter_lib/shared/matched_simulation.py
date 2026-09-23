"""Compatibility facade for the legacy ``--sim-matched`` workflow.

``run_matched_simulation`` now delegates to build-realization analysis, which
preserves selected physical capacitor branches, uses a verified integer-turn
toroid candidate when available, records explicit fallbacks, and applies any
declared loss model.  The older ``matched_result`` helper remains for callers
that need the former capacitor-only dictionary transformation.
"""

import copy
from dataclasses import dataclass

from .build_analysis import measure_calculated_and_nominal
from .build_simulation import BuildConfig, CircuitMeasurement
from .eseries import match_component
from .formatting import format_fixed

# Dense grid so interpolated -3 dB edge shifts resolve well below the
# E-series rounding error being measured.
GRID_POINTS = 1201


@dataclass(frozen=True)
class MatchedSimSummary:
    """Deprecated calculated-vs-nominal comparison for one filter design."""

    category: str  # 'lowpass', 'highpass', or 'bandpass'
    series: str  # E-series used for the matched realization
    exact: CircuitMeasurement
    matched: CircuitMeasurement
    uses_toroid_candidates: bool = True

    @property
    def calculated(self) -> CircuitMeasurement:
        """Preferred name for the legacy ``exact`` field."""
        return self.exact

    @property
    def nominal_build(self) -> CircuitMeasurement:
        """Preferred name for the legacy ``matched`` field."""
        return self.matched


def _best_cap(value: float, series: str) -> float:
    """Realized capacitance of the recommended E-series match."""
    return match_component(value, series, parallel_mode="additive").best_value


def matched_result(result: dict, category: str, series: str) -> dict:
    """Copy of ``result`` with capacitors replaced by their E-series matches.

    LP/HP results carry a flat ``capacitors`` list; bandpass results carry
    ``c_tank``, ``c_coupling``, and scalar ``c_end_in``/``c_end_out``.
    Inductors are left untouched in both shapes.
    """
    matched = copy.deepcopy(result)
    if category == "bandpass":
        matched["c_tank"] = [_best_cap(v, series) for v in result["c_tank"]]
        matched["c_coupling"] = [_best_cap(v, series) for v in result["c_coupling"]]
        for key in ("c_end_in", "c_end_out"):
            if result.get(key) is not None:
                matched[key] = _best_cap(result[key], series)
    elif category in ("lowpass", "highpass"):
        matched["capacitors"] = [_best_cap(v, series) for v in result["capacitors"]]
    else:
        raise ValueError(f"Unknown category {category!r}")
    return matched


def run_matched_simulation(
    result: dict,
    category: str,
    series: str,
    *,
    use_toroid_candidates: bool = True,
) -> MatchedSimSummary:
    """Deprecated wrapper over calculated/nominal build-realization analysis.

    Only the calculated and nominal-build circuits are measured; the tolerance
    screening that ``--sim-build`` reports is not part of this legacy output.
    """
    analysis = measure_calculated_and_nominal(
        result,
        category,
        BuildConfig(
            eseries=series,
            grid_points=GRID_POINTS,
            use_toroid_candidates=use_toroid_candidates,
        ),
    )
    return MatchedSimSummary(
        category=category,
        series=series,
        exact=analysis.calculated,
        matched=analysis.nominal_build,
        uses_toroid_candidates=use_toroid_candidates,
    )


def _fmt_delta_pct(exact: float | None, matched: float | None) -> str:
    if exact is None or matched is None or exact == 0:
        return ""
    return f"{format_fixed((matched - exact) / exact * 100, 2, explicit_sign=True)}%"


def format_matched_sim_block(summary: MatchedSimSummary) -> list[str]:
    """Render the exact-vs-matched comparison as table-output lines."""
    from .formatting import format_frequency

    lines = [
        "",
        f"Nominal Build Simulation (legacy --sim-matched; {summary.series})",
        "-" * 55,
        "(Calculated ideal circuit versus selected nominal physical realization)",
    ]
    exact, matched = summary.exact, summary.matched
    for name, item in (("Calculated", exact), ("Nominal", matched)):
        if not item.measurement_converged:
            lines.append(f"{name}: UNRESOLVED response measurement (refinement budget exhausted)")
        if item.reference_peak_gain_db is not None:
            lines.append(
                f"{name} half-power reference: "
                f"{format_fixed(item.reference_peak_gain_db, 3)} dB at "
                f"{item.reference_peak_frequency_hz:.9g} Hz; "
                f"{len(item.threshold_regions)} connected region(s)"
            )

    has_required_edges = (
        matched.f_low is not None and matched.f_high is not None
        if summary.category == "bandpass"
        else matched.f_high is not None
        if summary.category == "lowpass"
        else matched.f_low is not None
    )
    if not has_required_edges or matched.at_grid_edge:
        lines.append(
            "Nominal build does not exhibit a clear passband on the simulated "
            "grid; try a finer E-series (e.g. E96)."
        )
        return lines

    def row(label: str, e: float | None, m: float | None, fmt, delta: str) -> str:
        e_str = fmt(e) if e is not None else "n/a"
        m_str = fmt(m) if m is not None else "n/a"
        return f"{label:<22}{e_str:>14}{m_str:>14}  {delta}"

    lines.append(f"{'':<22}{'Calculated':>14}{'Nominal':>14}  {'Delta':<8}")
    if summary.category == "bandpass":
        lines.append(
            row(
                "Center f0:",
                exact.f0,
                matched.f0,
                format_frequency,
                _fmt_delta_pct(exact.f0, matched.f0),
            )
        )
        lines.append(
            row(
                "-3 dB BW:",
                exact.bw,
                matched.bw,
                format_frequency,
                _fmt_delta_pct(exact.bw, matched.bw),
            )
        )
        lines.append(
            row(
                "Lower edge:",
                exact.f_low,
                matched.f_low,
                format_frequency,
                _fmt_delta_pct(exact.f_low, matched.f_low),
            )
        )
        lines.append(
            row(
                "Upper edge:",
                exact.f_high,
                matched.f_high,
                format_frequency,
                _fmt_delta_pct(exact.f_high, matched.f_high),
            )
        )
    else:
        # LP cutoff is the upper -3 dB crossing; HP cutoff is the lower one.
        e_cut = exact.f_high if summary.category == "lowpass" else exact.f_low
        m_cut = matched.f_high if summary.category == "lowpass" else matched.f_low
        lines.append(
            row("-3 dB cutoff:", e_cut, m_cut, format_frequency, _fmt_delta_pct(e_cut, m_cut))
        )
    worst_delta_db = matched.worst_passband_db - exact.worst_passband_db
    lines.append(
        row(
            "Worst passband dev:",
            exact.worst_passband_db,
            matched.worst_passband_db,
            lambda v: f"{format_fixed(v, 2)} dB",
            f"{format_fixed(worst_delta_db, 2, explicit_sign=True)} dB",
        )
    )
    return lines


def matched_sim_json_payload(summary: MatchedSimSummary) -> dict:
    """JSON-friendly exact/matched summary (additive ``matched_sim`` block)."""

    def measurement(m: CircuitMeasurement) -> dict:
        payload = {
            "f_low_hz": m.f_low,
            "f_high_hz": m.f_high,
            "f0_hz": m.f0,
            "bw_hz": m.bw,
            "worst_passband_db": m.worst_passband_db,
            "at_grid_edge": m.at_grid_edge,
            "measurement_converged": m.measurement_converged,
            "reference_peak_frequency_hz": m.reference_peak_frequency_hz,
            "reference_peak_gain_db": m.reference_peak_gain_db,
            "half_power_threshold_db": m.threshold_db,
            "connected_region_count": len(m.threshold_regions),
            "half_power_regions": [
                {"f_low_hz": low, "f_high_hz": high} for low, high in m.threshold_regions
            ],
            "selected_region_index": m.selected_region_index,
        }
        if summary.category == "lowpass":
            payload["cutoff_hz"] = m.f_high
        elif summary.category == "highpass":
            payload["cutoff_hz"] = m.f_low
        return payload

    calculated = measurement(summary.calculated)
    nominal_build = measurement(summary.nominal_build)
    return {
        "eseries": summary.series,
        "deprecated": True,
        "replacement": "build_analysis",
        "inductors": (
            "verified_integer_turn_candidate_or_explicit_fallback"
            if summary.uses_toroid_candidates
            else "calculated_exact_value_toroid_selection_disabled"
        ),
        "exact": calculated,
        "matched": nominal_build,
        "calculated": calculated,
        "nominal_build": nominal_build,
    }
