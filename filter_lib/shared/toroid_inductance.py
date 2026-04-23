"""Toroid inductance <-> turns math.

Canonical formulas (all A_L in nH/turn^2, all L in Henries):
    L[H]    = A_L * 1e-9 * N^2
    N_ideal = sqrt(L[H] / (A_L * 1e-9)) = sqrt(1000 * L[uH] / A_L)

Research doc's `N = 100 * sqrt(L/A_L)` form is wrong for A_L in nH/turn^2 — it
assumes the Amidon "uH per 100 turns^2" convention (10x larger A_L). Regression
fixture in tests locks the correct behaviour (T68-2 @ 2.5 uH -> N=21, not 66).
"""

import math
from dataclasses import dataclass

from .toroid_core_data import ToroidCore


def compute_ideal_turns(l_henries: float, al_nh_per_turn2: float) -> float:
    """Continuous turn count for a target inductance. Not rounded."""
    if l_henries <= 0:
        raise ValueError("l_henries must be positive")
    if al_nh_per_turn2 <= 0:
        raise ValueError("al_nh_per_turn2 must be positive")
    al_h = al_nh_per_turn2 * 1e-9
    return math.sqrt(l_henries / al_h)


def compute_integer_turns(l_henries: float, al_nh_per_turn2: float) -> int | None:
    """Nearest integer turns; None if target < half a turn (core too large)."""
    n_ideal = compute_ideal_turns(l_henries, al_nh_per_turn2)
    if n_ideal < 0.5:
        return None
    return max(1, round(n_ideal))


def inductance_from_turns(n: int, al_nh_per_turn2: float) -> float:
    """L in Henries for integer N turns."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if al_nh_per_turn2 <= 0:
        raise ValueError("al_nh_per_turn2 must be positive")
    return al_nh_per_turn2 * 1e-9 * (n**2)


def l_tolerance_range(l_henries: float, tolerance_pct: float) -> tuple[float, float]:
    """(L_min, L_max) bracketing the nominal by +/- tolerance_pct."""
    factor = tolerance_pct / 100.0
    return (l_henries * (1 - factor), l_henries * (1 + factor))


@dataclass(frozen=True)
class WindingSolution:
    """Result of solving N turns for a target L on a specific core."""

    n_ideal: float
    n_turns: int
    l_target_h: float
    l_actual_h: float
    error_pct: float  # (l_actual - l_target) / l_target * 100, signed
    l_min_h: float  # A_L-tolerance lower bound on L_actual
    l_max_h: float  # A_L-tolerance upper bound on L_actual


def solve_winding(l_target_h: float, core: ToroidCore) -> WindingSolution | None:
    """Solve integer-turn winding for a target L and core.

    Returns None if target is unachievable (less than half a turn).
    """
    n_ideal = compute_ideal_turns(l_target_h, core.al_nh_per_turn2)
    n_int = compute_integer_turns(l_target_h, core.al_nh_per_turn2)
    if n_int is None:
        return None
    l_actual = inductance_from_turns(n_int, core.al_nh_per_turn2)
    error_pct = (l_actual / l_target_h - 1) * 100.0
    l_min, l_max = l_tolerance_range(l_actual, core.al_tolerance_pct)
    return WindingSolution(
        n_ideal=n_ideal,
        n_turns=n_int,
        l_target_h=l_target_h,
        l_actual_h=l_actual,
        error_pct=error_pct,
        l_min_h=l_min,
        l_max_h=l_max,
    )
