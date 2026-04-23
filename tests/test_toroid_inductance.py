"""Tests for toroid inductance math (Phase 2).

Includes hand-calculated fixtures AND the T68-2 regression test that locks out
the unit-mismatched formula from the research doc (plan Accuracy Contract).
"""

import pytest

from filter_lib.shared.toroid_core_data import get_core
from filter_lib.shared.toroid_inductance import (
    WindingSolution,
    compute_ideal_turns,
    compute_integer_turns,
    inductance_from_turns,
    l_tolerance_range,
    solve_winding,
)


def test_compute_ideal_turns_t50_2():
    """T50-2 (A_L=4.9) at L=0.49uH -> N_ideal = sqrt(100) = 10.0 exactly."""
    n = compute_ideal_turns(0.49e-6, 4.9)
    assert n == pytest.approx(10.0, abs=1e-12)


def test_compute_ideal_turns_raises_on_zero_l():
    with pytest.raises(ValueError):
        compute_ideal_turns(0, 4.9)


def test_compute_ideal_turns_raises_on_neg_al():
    with pytest.raises(ValueError):
        compute_ideal_turns(1e-6, -1)


def test_compute_integer_turns_t50_2():
    assert compute_integer_turns(0.49e-6, 4.9) == 10


def test_compute_integer_turns_sub_half_turn_none():
    """Target L smaller than N=0.5 turn produces None."""
    assert compute_integer_turns(1e-12, 4.9) is None


def test_compute_integer_turns_neg_l_raises():
    with pytest.raises(ValueError):
        compute_integer_turns(-1, 4.9)


def test_inductance_from_turns_roundtrip():
    """N=10 on A_L=4.9 returns exactly 0.49 uH."""
    assert inductance_from_turns(10, 4.9) == pytest.approx(0.49e-6, rel=1e-12)


def test_inductance_from_turns_zero_is_zero():
    assert inductance_from_turns(0, 4.9) == 0.0


def test_inductance_from_turns_neg_raises():
    with pytest.raises(ValueError):
        inductance_from_turns(-1, 4.9)


def test_l_tolerance_range_plus_minus_5():
    lo, hi = l_tolerance_range(1e-6, 5.0)
    assert lo == pytest.approx(0.95e-6)
    assert hi == pytest.approx(1.05e-6)


@pytest.mark.parametrize(
    "core_name,l_target_h,expected_n",
    [
        ("T50-2", 0.49e-6, 10),
        ("T68-2", 2.5e-6, 21),  # Regression: research doc says 66 (wrong units); correct is 21
        ("T37-2", 1.0e-6, 16),
        ("T106-2", 10e-6, 27),
        ("T200-2", 100e-6, 91),
    ],
)
def test_hand_calculated_fixtures(core_name, l_target_h, expected_n):
    """Five hand-calculated N targets, each locked as a regression."""
    w = solve_winding(l_target_h, get_core(core_name))
    assert w is not None
    assert w.n_turns == expected_n


def test_t68_2_regression_not_66():
    """Regression: research example '2.5 uH -> N=66' is wrong.

    N = 100 * sqrt(L[uH]/A_L) only works if A_L is in Amidon 'uH per 100 turns^2'.
    Our database uses nH/turn^2 (T68-2 = 5.7), so the correct answer is N=21.
    See plan.md "Accuracy Contract" section.
    """
    w = solve_winding(2.5e-6, get_core("T68-2"))
    assert w is not None
    assert w.n_turns == 21
    assert w.n_turns != 66


def test_solve_winding_returns_none_below_half_turn():
    """Extremely low target L on a big core returns None."""
    w = solve_winding(1e-15, get_core("T200-2"))
    assert w is None


def test_solve_winding_error_pct_signed():
    """error_pct is signed (+ over, - under)."""
    # T37-2 (A_L=4.0) at 1 uH -> N=16, L_actual=1.024 uH, err=+2.4%
    w = solve_winding(1e-6, get_core("T37-2"))
    assert w is not None
    assert w.error_pct > 0
    assert w.error_pct == pytest.approx(2.4, abs=0.01)


def test_solve_winding_includes_tolerance_range():
    """WindingSolution carries A_L-tolerance-derived L range around L_actual."""
    w = solve_winding(0.49e-6, get_core("T50-2"))
    assert w is not None
    assert isinstance(w, WindingSolution)
    assert w.l_min_h == pytest.approx(w.l_actual_h * 0.95)
    assert w.l_max_h == pytest.approx(w.l_actual_h * 1.05)


def test_solve_winding_raises_on_neg_l():
    with pytest.raises(ValueError):
        solve_winding(-1, get_core("T50-2"))
