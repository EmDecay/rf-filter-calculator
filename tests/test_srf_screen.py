"""The SRF screen: part model, check window, drift, the henry-based budget and its range.

Hand computations follow ``docs/component-data-sources.md`` (Coverage of the acceptance
designs): ``L0 = L_m (1 - (f_m/SRF)^2)``, ``C_self = 1/((2 pi SRF)^2 L0)``, and
``L(f) = L0 / (1 - (f/SRF)^2)``.
"""

from __future__ import annotations

import math
import sys

import pytest

from filter_lib.design import DesignRequest, design
from filter_lib.shared.chip_inductor_data import chip_parts
from filter_lib.shared.srf_screen import (
    DESIGN_ALLOWANCE_PCT,
    DRIFT_ALLOWANCE_PCT,
    HIGHPASS_CHECK_MULTIPLE,
    LIMIT_ALLOWANCE,
    LIMIT_DRIFT,
    CheckWindow,
    PartModel,
    allowance_range,
    check_window,
    common_range,
    describe_range,
    screen_part,
)


def _part(number: str):
    return next(part for part in chip_parts() if part.part_number == number)


def _model(number: str) -> PartModel:
    part = _part(number)
    return PartModel(part.inductance_h, part.test_frequency_hz, part.srf_min_hz)


def test_the_allowances_are_the_named_defaults():
    assert (DRIFT_ALLOWANCE_PCT, DESIGN_ALLOWANCE_PCT, HIGHPASS_CHECK_MULTIPLE) == (5.0, 10.0, 2.0)


def test_the_part_model_reproduces_the_catalog_value_at_its_test_frequency():
    # 0603CS-24N: 24 nH at 250 MHz, SRF min 2.65 GHz.
    model = PartModel(24e-9, 250e6, 2.65e9)

    assert model.l0_h == pytest.approx(23.7864e-9, rel=2e-6)
    assert model.self_capacitance_f == pytest.approx(0.15164e-12, rel=5e-5)
    assert model.inductance_at(250e6) == pytest.approx(24e-9, rel=1e-13)
    # L0 with C_self resonates exactly at the minimum SRF.
    resonance = 1 / (2 * math.pi * math.sqrt(model.l0_h * model.self_capacitance_f))
    assert resonance == pytest.approx(2.65e9, rel=1e-13)


def test_drift_is_negative_below_the_test_frequency_and_positive_above():
    model = PartModel(24e-9, 250e6, 2.65e9)

    assert model.drift(0) == pytest.approx(-((250 / 2650) ** 2), rel=1e-13)
    assert model.drift(100e6) < 0
    assert model.drift(250e6) == 0
    assert model.drift(500e6) > 0
    with pytest.raises(ValueError, match="unbounded"):
        model.drift(2.65e9)
    for frequency in (-250e6, float("nan"), True, 1e308):
        with pytest.raises(ValueError):
            model.drift(frequency)
    with pytest.raises(ValueError):
        model.inductance_at(float("nan"))
    # So close to the SRF that the squared ratio rounds to 1.
    with pytest.raises(ValueError, match="unbounded"):
        PartModel(25e-9, 100e6, 10**18).drift(10**18 - 1)


@pytest.mark.parametrize(
    "values",
    [(0.0, 100e6, 1e9), (1e-9, float("nan"), 1e9), (1e-9, 1e9, 1e9), (1e-9, 2e9, 1e9)],
    ids=["zero", "nan", "test-at-srf", "test-above-srf"],
)
def test_a_part_model_refuses_impossible_values(values):
    with pytest.raises(ValueError):
        PartModel(*values)


def test_check_windows_follow_the_category():
    lowpass = design(DesignRequest("lowpass", "chebyshev", "pi", 146e6, 50.0, 5, ripple_db=0.1))
    highpass = design(DesignRequest("highpass", "butterworth", "pi", 125e6, 50.0, 3))
    bandpass = design(
        DesignRequest(
            "bandpass", "chebyshev", "top", 146e6, 50.0, 3, ripple_db=0.5, bandwidth_hz=4e6
        )
    )

    assert check_window(lowpass.result, "lowpass") == CheckWindow(0.0, 146e6)
    assert check_window(highpass.result, "highpass") == CheckWindow(125e6, 250e6)
    # The band-pass window ends at the true upper -3 dB edge, not f0 + bw/2.
    assert check_window(bandpass.result, "bandpass").high_hz == pytest.approx(
        148.01369798755184e6, rel=1e-12
    )
    assert CheckWindow(0.0, 146e6).describe() == "DC to 146 MHz"
    assert CheckWindow(125e6, 250e6).describe() == "125 MHz to 250 MHz"
    with pytest.raises(ValueError, match="category"):
        check_window(lowpass.result, "notch")


@pytest.mark.parametrize("window", [(-1.0, 1e6), (2e6, 1e6), (0.0, 0.0), (0.0, float("inf"))])
def test_a_check_window_must_be_ordered_and_finite(window):
    with pytest.raises(ValueError):
        CheckWindow(*window)


def test_extreme_designs_fail_the_screen_instead_of_aborting():
    # A cutoff near the largest float: twice it is not finite, so the window stops there
    # and every part fails on drift (the window is far above every SRF).
    top = sys.float_info.max
    assert check_window({"freq_hz": top}, "highpass") == CheckWindow(top, top)
    screen = screen_part(25e-9, CheckWindow(top, top), _model("LQW15AN25NG80D"), 2.0)
    assert screen.failed_limits == {LIMIT_DRIFT}
    # A subnormal target: the part's error in percent passes the largest float.
    screen = screen_part(5e-324, CheckWindow(0.0, 10e6), _model("LQW15AN25NG80D"), 2.0)
    assert LIMIT_ALLOWANCE in screen.failed_limits
    assert screen.worst_case_pct is None and screen.budget_pct is None


@pytest.mark.parametrize(
    "result, category, message",
    [
        ({"f0": 14e6}, "bandpass", "upper -3 dB edge \\(f_high\\)"),
        ({"freq_hz": float("nan")}, "lowpass", "cutoff \\(freq_hz\\)"),
        ({"freq_hz": True}, "highpass", "cutoff"),
    ],
    ids=["no-edge", "nan-cutoff", "bool-cutoff"],
)
def test_a_window_needs_the_design_s_frequencies(result, category, message):
    with pytest.raises(ValueError, match=message):
        check_window(result, category)


def test_a_part_exactly_at_five_percent_drift_and_tolerance_fails_at_ten_point_two_five():
    # A +5% part whose drift reaches +5% at the top of the window: 1.05 × 1.05 = 1.1025,
    # beyond the 10% allowance, although each term alone is within its limit.
    model = PartModel(50e-9, 100e6, 2e9)
    ratio = ((100e6 / 2e9) ** 2 + 0.05) / 1.05
    top = 2e9 * math.sqrt(ratio)

    screen = screen_part(50e-9, CheckWindow(0.0, top), model, 5.0)

    assert screen.drift_range[1] == pytest.approx(0.05, rel=1e-9)
    assert LIMIT_ALLOWANCE in screen.failed_limits
    assert screen.worst_case_pct[1] == pytest.approx(10.25, rel=1e-8)


def test_a_part_exactly_at_the_allowance_is_within_it():
    # 22 nH +5% is exactly 21 nH +10%, and below its 250 MHz test frequency it has no
    # positive drift: a boundary the comparison must decide exactly, not by rounding.
    screen = screen_part(21e-9, CheckWindow(0.0, 148.0137e6), _model("0603CS-22NXJRW"), 5.0)

    assert screen.passed
    assert screen.worst_case_pct[1] == 10.0


def test_the_budget_checks_both_srf_limits_when_the_window_is_below_the_test_frequency():
    # 0603CS-56NXGRW (56 nH at 200 MHz) for the 146 MHz band-pass tank: at the minimum
    # SRF its +2% end is +4.25% of the target, but with no drift it is +4.78%.
    target = 54.5148e-9
    model = _model("0603CS-56NXGRW")
    window = CheckWindow(0.0, 148.01369798755184e6)

    screen = screen_part(target, window, model, 2.0)

    at_minimum_srf = model.inductance_at(window.high_hz) * 1.02 / target - 1
    assert at_minimum_srf * 100 == pytest.approx(4.25, abs=0.005)
    assert screen.worst_case_pct[1] == pytest.approx((56e-9 * 1.02 / target - 1) * 100, rel=1e-12)
    assert screen.worst_case_pct[1] == pytest.approx(4.78, abs=0.005)
    assert screen.drift_range == (pytest.approx(-((200 / 1900) ** 2), rel=1e-12), 0.0)


def test_the_budget_terms_add_up_to_the_worst_case_in_henries():
    target = 24.7995e-9
    model = _model("LQW15AN25NG80D")
    window = CheckWindow(0.0, 440e6)

    screen = screen_part(target, window, model, 2.0)

    mismatch, tolerance, (drift_low, drift_high) = screen.budget_pct
    high = 25e-9 * 1.02 * (1 + model.drift(440e6)) / target - 1
    low = 25e-9 * 0.98 * (1 + model.drift(0)) / target - 1
    assert mismatch + tolerance + drift_high == pytest.approx(high * 100, rel=1e-12)
    assert mismatch - tolerance + drift_low == pytest.approx(low * 100, rel=1e-12)
    assert screen.worst_case_pct == (
        pytest.approx(low * 100, rel=1e-12),
        pytest.approx(high * 100, rel=1e-12),
    )
    assert screen.achieved_h == pytest.approx(model.inductance_at(440e6), rel=1e-15)


def test_a_window_that_reaches_the_srf_fails_on_drift_with_no_figures():
    screen = screen_part(25e-9, CheckWindow(0.0, 5e9), _model("LQW15AN25NG80D"), 2.0)

    assert screen.failed_limits == {LIMIT_DRIFT}
    assert screen.worst_case_pct is None and screen.allowance_range_hz is None
    assert screen.worst_abs_pct == math.inf


def test_the_high_pass_low_edge_is_checked_where_the_drift_is_negative():
    # hp bw pi 125MHz -n 3 -z 19.792...: 25.2 nH shunt inductors, window 125-250 MHz. The
    # 0603CS-24N is measured at 250 MHz (2 x cutoff), so at the top of the window it has no
    # drift and its -5% end is -9.52%; at the 125 MHz low edge its drift is negative and
    # the same end is -10.13%, so it fails.
    outcome = design(DesignRequest("highpass", "butterworth", "pi", 125e6, 19.792033717615695, 3))
    target = outcome.result["inductors"][0]
    window = check_window(outcome.result, "highpass")
    part = _part("0603CS-24NXJRW")
    model = _model("0603CS-24NXJRW")

    screen = screen_part(target, window, model, part.tolerance_pct)

    assert target == pytest.approx(25.2e-9, rel=1e-12)
    assert part.test_frequency_hz == HIGHPASS_CHECK_MULTIPLE * outcome.result["freq_hz"]
    assert (24e-9 * 0.95 / target - 1) * 100 == pytest.approx(-9.524, abs=5e-4)
    assert screen.failed_limits == {LIMIT_ALLOWANCE}
    assert screen.worst_case_pct[0] == pytest.approx(-10.129, abs=5e-4)
    chips = outcome.parts.inductor("L1").kind("chip").suggestions
    assert chips and all(chip.part_name != "0603CS-24NXJRW" for chip in chips)


def test_the_allowance_range_holds_the_window_and_ends_at_a_limit():
    target = 74.7381e-9
    model = _model("LQW15AN75NG80D")

    low, high = allowance_range(target, model, 2.0)

    # The tolerance leaves room for more than 5% drift, so the drift limit ends the range.
    assert low == 0.0
    assert model.drift(high) == pytest.approx(0.05, rel=1e-9)
    assert high > 146e6
    assert describe_range((low, high)) == "DC to 532.7 MHz"


def test_the_allowance_range_ends_where_the_budget_does_when_the_tolerance_is_wide():
    # LQW15AN26NJ80D for 24.80 nH: 26 nH +5% is already +10.08% with no drift.
    assert allowance_range(24.7995e-9, _model("LQW15AN26NJ80D"), 5.0) is None
    # 25 nH +5% for 24.7995 nH leaves 4.77% for drift before the 10% allowance.
    model = _model("LQW15AN25NJ80D")
    _low, high = allowance_range(24.7995e-9, model, 5.0)
    assert 25e-9 * 1.05 * (1 + model.drift(high)) == pytest.approx(24.7995e-9 * 1.1, rel=1e-9)


@pytest.mark.parametrize(
    ("number", "target_h", "shown"),
    [
        ("LQW18AN20NG00D", 20e-9, "DC to 1.073 GHz"),
        ("LQW15AN75NG80D", 74.7381e-9, "DC to 532.7 MHz"),
        ("0603CS-24NXJRW", 25.2e-9, "160.3 MHz to 627.6 MHz"),
    ],
)
def test_the_allowance_range_ends_pass_the_exact_screen_and_print_inward(number, target_h, shown):
    part = _part(number)
    model = _model(number)

    low, high = allowance_range(target_h, model, part.tolerance_pct)

    assert screen_part(target_h, CheckWindow(low, high), model, part.tolerance_pct).passed
    assert describe_range((low, high)) == shown


@pytest.mark.parametrize(
    ("target_h", "tolerance_pct"),
    [(25e-9, -3.0), (25e-9, 100.0), (25e-9, float("nan")), (0.0, 2.0), (-1e-9, 2.0)],
    ids=["negative", "hundred", "nan", "zero-target", "negative-target"],
)
def test_the_screen_refuses_impossible_targets_and_tolerances(target_h, tolerance_pct):
    model = _model("LQW15AN25NG80D")

    with pytest.raises(ValueError):
        screen_part(target_h, CheckWindow(0.0, 440e6), model, tolerance_pct)
    with pytest.raises(ValueError):
        allowance_range(target_h, model, tolerance_pct)


def test_the_common_range_is_where_every_range_holds():
    assert common_range([]) is None
    assert common_range([(0.0, 5e8), (1e8, 9e8)]) == (1e8, 5e8)
    assert describe_range((1e8, 5e8)) == "100 MHz to 500 MHz"


def test_frequencies_that_round_to_the_srf_count_as_reaching_it():
    # An integer just below 1e18 passes an exact comparison but is 1e18 as a float.
    screen = screen_part(1e-8, CheckWindow(0, 10**18 - 1), PartModel(1e-8, 1e8, 10**18), 2.0)

    assert screen.failed_limits == {LIMIT_DRIFT}
    with pytest.raises(ValueError, match="below its SRF"):
        PartModel(1e-8, 10**18 - 1, 10**18)
