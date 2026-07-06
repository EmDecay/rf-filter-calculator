"""Recommend iron-powder toroid cores for a target inductance at a design freq.

Hard filters (frequency-range gate, wire-fit) exclude candidates; the remaining
pool is ranked by accuracy (|error_pct|), then temperature coefficient, then
outer diameter, then name for deterministic tie-break. Top-N is returned.
"""

import math
from dataclasses import dataclass

from .toroid_core_data import ToroidCore, iter_cores_for_frequency
from .toroid_inductance import WindingSolution, solve_winding
from .toroid_wire import MechanicalFit, fit_wire


@dataclass(frozen=True)
class ToroidRecommendation:
    """One ranked recommendation: core + winding + mechanical fit + DC Q."""

    core: ToroidCore
    winding: WindingSolution
    mechanical: MechanicalFit
    q_dc_upper_bound: float
    design_freq_hz: float


def _q_dc_upper_bound(l_actual_h: float, freq_hz: float, r_dc_ohm: float) -> float:
    """Q = ωL/R using DC resistance only.

    An upper bound, not an estimate: at RF the effective resistance rises
    with skin effect and core loss, so the real Q is always lower. Display
    code labels it accordingly.
    """
    if r_dc_ohm <= 0:
        return float("inf")
    return 2.0 * math.pi * freq_hz * l_actual_h / r_dc_ohm


def _sort_key(rec: ToroidRecommendation) -> tuple[float, float, float, str]:
    """Ranking: accuracy, then temp stability, then size; name breaks ties
    so results are deterministic across runs."""
    return (
        abs(rec.winding.error_pct),
        rec.core.temp_coeff_ppm_per_c,
        rec.core.od_mm,
        rec.core.name,
    )


def recommend_cores(
    l_target_h: float, design_freq_hz: float, *, top_n: int = 3
) -> list[ToroidRecommendation]:
    """Top-N toroid recommendations for an L target at a design frequency.

    Applies frequency-range gating and mechanical wire-fit as hard filters,
    then ranks survivors by |error_pct|, temp coefficient, and core OD.

    Args:
        l_target_h: Target inductance in Henries
        design_freq_hz: Operating frequency in Hz (gates core selection by
            the core's published frequency range)
        top_n: Maximum number of recommendations to return

    Returns:
        Up to top_n recommendations, best first; empty list when no core
        covers the frequency or fits mechanically.

    Raises:
        ValueError: If l_target_h or design_freq_hz is non-positive, or
            top_n < 1.
    """
    if l_target_h <= 0:
        raise ValueError("l_target_h must be positive")
    if design_freq_hz <= 0:
        raise ValueError("design_freq_hz must be positive")
    if top_n < 1:
        raise ValueError("top_n must be >= 1")

    candidates: list[ToroidRecommendation] = []
    for core in iter_cores_for_frequency(design_freq_hz):
        winding = solve_winding(l_target_h, core)
        if winding is None:
            continue
        mechanical = fit_wire(core, winding.n_turns)
        if not mechanical.fits:
            continue
        q = _q_dc_upper_bound(winding.l_actual_h, design_freq_hz, mechanical.dc_resistance_ohm)
        candidates.append(
            ToroidRecommendation(
                core=core,
                winding=winding,
                mechanical=mechanical,
                q_dc_upper_bound=q,
                design_freq_hz=design_freq_hz,
            )
        )

    candidates.sort(key=_sort_key)
    return candidates[:top_n]
