"""Compatibility facade for the legacy ``--sim-matched`` workflow.

``run_matched_simulation`` now delegates to build-realization analysis, which
preserves selected physical capacitor branches, uses a verified integer-turn
toroid candidate when available, records explicit fallbacks, and applies any
declared loss model.  Older helper functions remain for callers that need the
former capacitor-only dictionary transformation.
"""

import copy
import math
from dataclasses import dataclass

from .build_simulation import BuildConfig, CircuitMeasurement, analyze_build
from .eseries import match_component
from .netlist_builders import (
    build_bandpass_top_c_netlist,
    build_hp_netlist,
    build_lp_netlist,
)
from .netlist_simulation import find_3db_edges, solve_s21

# Dense grid so interpolated -3 dB edge shifts resolve well below the
# E-series rounding error being measured (~0.04% spacing near f0).
GRID_POINTS = 1201

_BUILDERS = {
    "lowpass": build_lp_netlist,
    "highpass": build_hp_netlist,
    "bandpass": build_bandpass_top_c_netlist,
}


@dataclass(frozen=True)
class MatchedSimSummary:
    """Deprecated calculated-vs-nominal comparison for one filter design."""

    category: str  # 'lowpass', 'highpass', or 'bandpass'
    series: str  # E-series used for the matched realization
    exact: CircuitMeasurement
    matched: CircuitMeasurement
    deprecated: bool = True
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


def _simulation_grid(result: dict, category: str) -> list[float]:
    """Log-spaced frequency grid centered on the design passband.

    Bandpass reuses the plot sweep's adaptive span (10×BW clamped to
    0.1–1.0 decades each side); LP/HP span one decade each side of the
    cutoff, which always brackets the -3 dB point.
    """
    if category == "bandpass":
        f0, bw = result["f0"], result["bw"]
        decades = math.log10((f0 + 10 * bw) / f0)
        decades = max(0.1, min(1.0, decades))
        center = f0
    else:
        center = result["freq_hz"]
        decades = 1.0
    log_start = math.log10(center) - decades
    log_end = math.log10(center) + decades
    step = (log_end - log_start) / (GRID_POINTS - 1)
    return [10 ** (log_start + i * step) for i in range(GRID_POINTS)]


def _measure(
    result: dict, category: str, freqs: list[float], passband: tuple[float, float]
) -> CircuitMeasurement:
    """Solve |S21| for one circuit and extract its -3 dB summary."""
    n_nodes, branches, in_node, out_node = _BUILDERS[category](result)
    z0 = result["z0"] if category == "bandpass" else result["impedance"]
    mags = solve_s21(n_nodes, branches, z0, z0, in_node, out_node, freqs)

    reference = result["f0"] if category == "bandpass" else None
    measured_low, measured_high = find_3db_edges(freqs, mags, reference_frequency=reference)
    at_grid_edge = measured_low == freqs[0] or measured_high == freqs[-1]
    if category == "lowpass":
        # The passband extends to DC, so the low "edge" is just the grid start.
        at_grid_edge = measured_high == freqs[-1]
        f_low, f_high = None, measured_high
    elif category == "highpass":
        # The passband extends upward, so the high "edge" is the grid end.
        at_grid_edge = measured_low == freqs[0]
        f_low, f_high = measured_low, None
    else:
        f_low, f_high = measured_low, measured_high

    lo, hi = passband
    in_band = [m for f, m in zip(freqs, mags) if lo <= f <= hi]
    worst = min(20 * math.log10(m) if m > 0 else -math.inf for m in in_band)
    return CircuitMeasurement(
        f_low=f_low, f_high=f_high, worst_passband_db=worst, at_grid_edge=at_grid_edge
    )


def simulate_pair(result: dict, matched: dict, category: str, series: str) -> MatchedSimSummary:
    """Simulate the exact and matched circuits on a shared grid.

    The worst-passband-deviation metric is evaluated over the *design*
    passband (design -3 dB edges for bandpass, DC..fc for lowpass, fc..grid
    top for highpass) for both circuits, so the matched value shows how much
    the standard-value rounding degrades the band the user asked for.
    """
    freqs = _simulation_grid(result, category)
    if category == "bandpass":
        passband = (result["f_low"], result["f_high"])
    elif category == "lowpass":
        passband = (freqs[0], result["freq_hz"])
    else:
        passband = (result["freq_hz"], freqs[-1])
    return MatchedSimSummary(
        category=category,
        series=series,
        exact=_measure(result, category, freqs, passband),
        matched=_measure(matched, category, freqs, passband),
    )


def run_matched_simulation(
    result: dict,
    category: str,
    series: str,
    *,
    use_toroid_candidates: bool = True,
) -> MatchedSimSummary:
    """Deprecated wrapper over calculated/nominal build-realization analysis."""
    analysis = analyze_build(
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
    return f"{(matched - exact) / exact * 100:+.2f}%"


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
    lines.append(
        row(
            "Worst passband dev:",
            exact.worst_passband_db,
            matched.worst_passband_db,
            lambda v: f"{v:.2f} dB",
            f"{matched.worst_passband_db - exact.worst_passband_db:+.2f} dB",
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
