"""Toroid inductance <-> turns math.

Canonical formulas (all A_L in nH/turn^2, all L in Henries):
    L[H]    = A_L * 1e-9 * N^2
    N_ideal = sqrt(L[H] / (A_L * 1e-9)) = sqrt(1000 * L[uH] / A_L)

Beware the alternate `N = 100 * sqrt(L[uH]/A_L)` form seen in Amidon catalogs:
it assumes A_L in "uH per 100 turns^2" and gives ~3x-too-many turns when fed
A_L in nH/turn^2. A regression fixture in tests locks the correct behaviour
(T68-2 @ 2.5 uH -> N=21, not 66).
"""

import math
from dataclasses import dataclass

from .numeric import require_nonnegative_finite, require_positive_finite
from .toroid_core_data import ToroidCore, _require_toroid_core


def compute_ideal_turns(l_henries: float, al_nh_per_turn2: float) -> float:
    """Continuous turn count for a target inductance. Not rounded."""
    require_positive_finite(l_henries, "l_henries")
    require_positive_finite(al_nh_per_turn2, "al_nh_per_turn2")
    log_turns = 0.5 * (math.log(l_henries) - math.log(al_nh_per_turn2) - math.log(1e-9))
    try:
        turns = math.exp(log_turns)
    except OverflowError as error:
        raise ValueError("ideal turn count is outside the finite numeric range") from error
    if not math.isfinite(turns) or turns <= 0:
        raise ValueError("ideal turn count is outside the finite numeric range")
    return turns


def compute_integer_turns(l_henries: float, al_nh_per_turn2: float) -> int:
    """Integer turns minimizing absolute error in realized inductance.

    Inductance follows N², so rounding the continuous turn count does not in
    general minimize inductance error.  Compare the physical floor/ceiling
    options directly; ties use fewer turns.  One turn is the physical floor.
    """
    n_ideal = compute_ideal_turns(l_henries, al_nh_per_turn2)
    candidates = {max(1, math.floor(n_ideal)), max(1, math.ceil(n_ideal))}
    errors = {
        turns: abs(inductance_from_turns(turns, al_nh_per_turn2) - l_henries)
        for turns in candidates
    }
    minimum_error = min(errors.values())
    tied = [
        turns
        for turns, error in errors.items()
        if math.isclose(error, minimum_error, rel_tol=1e-12, abs_tol=0.0)
    ]
    return min(tied)


def inductance_from_turns(n: int, al_nh_per_turn2: float) -> float:
    """L in Henries for integer N turns."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("n must be a non-negative integer")
    require_positive_finite(al_nh_per_turn2, "al_nh_per_turn2")
    if n == 0:
        return 0.0
    try:
        inductance = math.exp(math.log(al_nh_per_turn2) + math.log(1e-9) + 2 * math.log(n))
    except OverflowError as error:
        raise ValueError("inductance is outside the finite numeric range") from error
    if not math.isfinite(inductance) or inductance <= 0:
        raise ValueError("inductance is outside the finite numeric range")
    return inductance


def l_tolerance_range(l_henries: float, tolerance_pct: float) -> tuple[float, float]:
    """(L_min, L_max) bracketing the nominal by +/- tolerance_pct."""
    require_positive_finite(l_henries, "l_henries")
    require_nonnegative_finite(tolerance_pct, "tolerance_pct")
    if tolerance_pct >= 100:
        raise ValueError("tolerance_pct must be finite and in [0, 100)")
    factor = tolerance_pct / 100.0
    limits = (l_henries * (1 - factor), l_henries * (1 + factor))
    if not all(math.isfinite(value) and value > 0 for value in limits):
        raise ValueError("tolerance range is outside the positive finite numeric range")
    return limits


def _error_pct(actual_h: float, target_h: float) -> float:
    error = (actual_h / target_h - 1.0) * 100.0
    if not math.isfinite(error):
        raise ValueError("winding error is outside the finite numeric range")
    return error


@dataclass(frozen=True)
class TurnOption:
    """One physical integer-turn option considered by the solver."""

    n_turns: int
    l_actual_h: float
    error_pct: float


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
    turn_options: tuple[TurnOption, ...] = ()
    selected_reason: str = "minimum absolute inductance error; ties use fewer turns"


def solve_winding(l_target_h: float, core: ToroidCore) -> WindingSolution:
    """Solve the best physical integer-turn winding for a target L and core."""
    require_positive_finite(l_target_h, "l_target_h")
    core = _require_toroid_core(core)
    n_ideal = compute_ideal_turns(l_target_h, core.al_nh_per_turn2)
    n_int = compute_integer_turns(l_target_h, core.al_nh_per_turn2)
    l_actual = inductance_from_turns(n_int, core.al_nh_per_turn2)
    error_pct = _error_pct(l_actual, l_target_h)
    l_min, l_max = l_tolerance_range(l_actual, core.al_tolerance_pct)
    turn_counts = sorted({max(1, math.floor(n_ideal)), max(1, math.ceil(n_ideal))})
    turn_options = tuple(
        TurnOption(
            n_turns=turns,
            l_actual_h=inductance_from_turns(turns, core.al_nh_per_turn2),
            error_pct=_error_pct(inductance_from_turns(turns, core.al_nh_per_turn2), l_target_h),
        )
        for turns in turn_counts
    )
    return WindingSolution(
        n_ideal=n_ideal,
        n_turns=n_int,
        l_target_h=l_target_h,
        l_actual_h=l_actual,
        error_pct=error_pct,
        l_min_h=l_min,
        l_max_h=l_max,
        turn_options=turn_options,
    )
