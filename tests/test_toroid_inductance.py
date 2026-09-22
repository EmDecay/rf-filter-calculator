"""Toroid turns/inductance math: L = A_L·N² with A_L stored in nH/turn²."""

import math

import pytest

from filter_lib.shared.toroid_core_data import get_core
from filter_lib.shared.toroid_inductance import (
    compute_ideal_turns,
    compute_integer_turns,
    inductance_from_turns,
    l_tolerance_range,
    solve_winding,
)


def test_exact_square_round_trips_between_turns_and_inductance():
    """T50-2 (A_L 4.9 nH/turn²) at 0.49 µH -> N = sqrt(490 / 4.9) = 10 exactly."""
    assert compute_ideal_turns(0.49e-6, 4.9) == pytest.approx(10.0, abs=1e-12)
    assert compute_integer_turns(0.49e-6, 4.9) == 10
    assert inductance_from_turns(10, 4.9) == pytest.approx(0.49e-6, rel=1e-12)
    assert inductance_from_turns(0, 4.9) == 0.0


@pytest.mark.parametrize("l_uh", [0.5, 2.5, 10.0])
@pytest.mark.parametrize(
    ("core_name", "amidon_al_uh_per_100_turns"),
    [("T25-6", 27), ("T50-2", 49), ("T68-2", 57)],
)
def test_ideal_turns_match_amidon_catalog_formula(core_name, amidon_al_uh_per_100_turns, l_uh):
    """Amidon: N = 100·sqrt(L[µH] / A_L[µH per 100 turns]) with catalog A_L values."""
    expected = 100 * math.sqrt(l_uh / amidon_al_uh_per_100_turns)

    turns = compute_ideal_turns(l_uh * 1e-6, get_core(core_name).al_nh_per_turn2)

    assert turns == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize(
    ("core_name", "l_target_h", "expected_n"),
    [
        ("T50-2", 0.49e-6, 10),
        # 100·sqrt(2.5 / 57) = 20.9.  Feeding the nH/turn² value (5.7) into the
        # Amidon µH-per-100-turns formula would give the wrong answer, 66.
        ("T68-2", 2.5e-6, 21),
        ("T37-2", 1.0e-6, 16),  # sqrt(1000 / 4.0) = 15.8
        ("T106-2", 10e-6, 27),  # sqrt(10000 / 13.5) = 27.2
        ("T200-2", 100e-6, 91),  # sqrt(100000 / 12.0) = 91.3
    ],
)
def test_hand_calculated_turn_counts(core_name, l_target_h, expected_n):
    assert solve_winding(l_target_h, get_core(core_name)).n_turns == expected_n


def test_integer_turns_minimize_inductance_error_not_turn_rounding():
    """At N_ideal = 11.5, 11 turns miss by 11.25·A_L and 12 turns by 11.75·A_L.

    Python's round(11.5) would choose 12.
    """
    al = 4.9
    target = al * 1e-9 * 11.5**2

    assert compute_integer_turns(target, al) == 11


def test_integer_turns_exact_inductance_error_tie_prefers_fewer_turns():
    al = 4.9
    target = al * 1e-9 * ((10**2 + 11**2) / 2)

    assert compute_integer_turns(target, al) == 10


@pytest.mark.parametrize(
    ("core_name", "options", "chosen", "error_pct"),
    [
        # T37-2 (A_L 4.0): 15 turns -> 0.900 µH, 16 turns -> 1.024 µH.
        ("T37-2", [(15, -10.0), (16, 2.4)], 16, 2.4),
        # T50-2 (A_L 4.9): 14 turns -> 0.9604 µH, 15 turns -> 1.1025 µH.
        ("T50-2", [(14, -3.96), (15, 10.25)], 14, -3.96),
    ],
)
def test_winding_reports_neighbouring_turn_options_with_signed_error(
    core_name, options, chosen, error_pct
):
    winding = solve_winding(1e-6, get_core(core_name))

    assert [(option.n_turns, option.error_pct) for option in winding.turn_options] == [
        (turns, pytest.approx(error)) for turns, error in options
    ]
    assert winding.n_turns == chosen
    assert winding.error_pct == pytest.approx(error_pct)
    assert winding.l_actual_h == pytest.approx(1e-6 * (1 + error_pct / 100))
    assert winding.selected_reason == "minimum absolute inductance error; ties use fewer turns"


def test_target_below_one_turn_realizes_one_turn_and_reports_the_error():
    core = get_core("T106-2")  # A_L 13.5 nH/turn²; 1 fH needs ~2.7e-4 turns

    winding = solve_winding(1e-15, core)

    assert winding.n_turns == 1
    assert [option.n_turns for option in winding.turn_options] == [1]
    assert winding.l_actual_h == pytest.approx(13.5e-9, rel=1e-12, abs=0)
    assert winding.error_pct == pytest.approx((13.5e-9 / 1e-15 - 1) * 100)
    assert compute_integer_turns(1e-12, 4.9) == 1


def test_winding_range_brackets_actual_inductance_by_core_al_tolerance():
    winding = solve_winding(0.49e-6, get_core("T50-2"))  # T50-2 A_L is ±5%

    assert (winding.l_min_h, winding.l_max_h) == pytest.approx((0.4655e-6, 0.5145e-6))


def test_tolerance_range_accepts_zero_and_rejects_full_or_unrepresentable_ranges():
    assert l_tolerance_range(1e-6, 5.0) == pytest.approx((0.95e-6, 1.05e-6))
    assert l_tolerance_range(1e-6, 0.0) == (1e-6, 1e-6)
    with pytest.raises(ValueError, match=r"tolerance_pct must be finite and in \[0, 100\)"):
        l_tolerance_range(1e-6, 100.0)
    with pytest.raises(ValueError, match="tolerance range is outside"):
        l_tolerance_range(1.79e308, 5.0)


@pytest.mark.parametrize(
    ("function", "args", "message"),
    [
        (compute_ideal_turns, (1e308, 5e-324), "ideal turn count is outside"),
        (inductance_from_turns, (10**200, 4.9), "inductance is outside"),
        (inductance_from_turns, (1, 5e-324), "inductance is outside"),
        (solve_winding, (5e-324, get_core("T50-2")), "winding error is outside"),
    ],
    ids=["turns-overflow", "inductance-overflow", "inductance-underflow", "error-overflow"],
)
def test_unrepresentable_results_raise_value_error_not_arithmetic_errors(function, args, message):
    with pytest.raises(ValueError, match=message):
        function(*args)


@pytest.mark.parametrize(
    "value", [0, -1.0, float("nan"), float("inf"), True, "1e-6", None, 10**400]
)
@pytest.mark.parametrize(
    ("function", "build_args", "label"),
    [
        (compute_ideal_turns, lambda value: (value, 4.9), "l_henries"),
        (compute_ideal_turns, lambda value: (1e-6, value), "al_nh_per_turn2"),
        (inductance_from_turns, lambda value: (10, value), "al_nh_per_turn2"),
        (l_tolerance_range, lambda value: (value, 5.0), "l_henries"),
        (solve_winding, lambda value: (value, get_core("T50-2")), "l_target_h"),
    ],
)
def test_turn_math_rejects_non_positive_or_non_real_inputs(function, build_args, label, value):
    with pytest.raises(ValueError, match=f"{label} must be positive and finite"):
        function(*build_args(value))


@pytest.mark.parametrize("tolerance", [-1.0, float("nan"), True, "5", None, 10**400])
def test_tolerance_percentage_must_be_non_negative_finite_real(tolerance):
    with pytest.raises(ValueError, match="tolerance_pct must be non-negative and finite"):
        l_tolerance_range(1e-6, tolerance)


@pytest.mark.parametrize("turns", [-1, True, 1.5, "2"])
def test_inductance_requires_non_negative_integer_turns(turns):
    with pytest.raises(ValueError, match="n must be a non-negative integer"):
        inductance_from_turns(turns, 4.9)


def test_solve_winding_requires_a_catalog_core():
    with pytest.raises(ValueError, match="core must be a ToroidCore"):
        solve_winding(1e-6, "T50-2")
