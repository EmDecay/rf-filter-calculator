"""Regression tests for public order validation and deep-stopband stability."""

import json
import math
import sys

import pytest

from filter_lib import cli
from filter_lib.bandpass.calculations import (
    calculate_bandpass_filter,
    calculate_min_q,
    compute_bandpass_3db_edges,
    estimate_insertion_loss,
)
from filter_lib.bandpass.g_values import calculate_butterworth_g_values
from filter_lib.bandpass.passband_measurement import measure_netlist_passband
from filter_lib.bandpass.transfer import (
    frequency_from_deviation,
)
from filter_lib.bandpass.transfer import (
    frequency_sweep as bandpass_frequency_sweep,
)
from filter_lib.bandpass.transfer import (
    generate_frequency_points as generate_bandpass_frequency_points,
)
from filter_lib.highpass import calculations as highpass_calculations
from filter_lib.highpass.calculations import calculate_butterworth as calculate_highpass
from filter_lib.highpass.transfer import (
    bessel_response as highpass_bessel,
)
from filter_lib.highpass.transfer import (
    butterworth_response as highpass_butterworth,
)
from filter_lib.highpass.transfer import (
    chebyshev_response as highpass_chebyshev,
)
from filter_lib.lowpass import calculations as lowpass_calculations
from filter_lib.lowpass.calculations import calculate_butterworth as calculate_lowpass
from filter_lib.lowpass.transfer import (
    bessel_response as lowpass_bessel,
)
from filter_lib.lowpass.transfer import (
    butterworth_response as lowpass_butterworth,
)
from filter_lib.lowpass.transfer import (
    chebyshev_response as lowpass_chebyshev,
)
from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.chebyshev_g_calculator import calculate_chebyshev_g_values
from filter_lib.shared.circuit_model import CircuitElement
from filter_lib.shared.cli_aliases import resolve_coupling, resolve_filter_type
from filter_lib.shared.eseries import MatchPolicy, find_closest_single, match_component
from filter_lib.shared.netlist_simulation import (
    find_3db_edges,
    logspace,
    passband_ripple_db,
    solve_s21,
)
from filter_lib.shared.numeric import positive_geometric_mean
from filter_lib.shared.strict_json import dumps_strict
from filter_lib.shared.transfer_functions import (
    chebyshev_polynomial,
    generate_frequency_points,
    magnitude_to_db,
)

HUGE_INTEGER = 10**400


@pytest.mark.parametrize("calculator", [calculate_lowpass, calculate_highpass])
@pytest.mark.parametrize("order", [True, 3.5, "3"])
def test_ladder_calculators_reject_non_integer_order(calculator, order):
    with pytest.raises(ValueError, match="between 2 and 9"):
        calculator(10e6, 50, order, "pi")


@pytest.mark.parametrize(
    "response",
    [
        lowpass_butterworth,
        highpass_butterworth,
    ],
)
@pytest.mark.parametrize("order", [True, 3.5, 0])
def test_public_responses_reject_invalid_order(response, order):
    with pytest.raises(ValueError, match="positive integer"):
        response(10e6, 10e6, order)


@pytest.mark.parametrize("response", [lowpass_bessel, highpass_bessel])
@pytest.mark.parametrize("order", [True, 3.5, 10])
def test_bessel_responses_reject_unsupported_order(response, order):
    with pytest.raises(ValueError, match="positive integer|between 2 and 9"):
        response(10e6, 10e6, order)


@pytest.mark.parametrize("response", [lowpass_chebyshev, highpass_chebyshev])
@pytest.mark.parametrize("ripple", [True, 0.0, float("nan"), float("inf")])
def test_chebyshev_responses_reject_invalid_ripple(response, ripple):
    with pytest.raises(ValueError, match="positive and finite"):
        response(10e6, 10e6, 3, ripple)


@pytest.mark.parametrize(
    ("response", "frequency", "cutoff"),
    [
        (lowpass_chebyshev, 1e300, 1e-300),
        (highpass_chebyshev, 1e-300, 1e300),
        (lowpass_bessel, 1e300, 1e-300),
        (highpass_bessel, 1e-300, 1e300),
    ],
)
def test_deep_stopband_evaluation_saturates_without_overflow(response, frequency, cutoff):
    args = (
        (frequency, cutoff, 9, 0.5) if "chebyshev" in response.__name__ else (frequency, cutoff, 9)
    )
    magnitude = response(*args)
    assert magnitude == 0.0
    assert math.isfinite(magnitude)


@pytest.mark.parametrize(
    ("response", "frequency"),
    [
        (lowpass_chebyshev, 1e54),
        (highpass_chebyshev, 1e-54),
    ],
)
def test_minimum_positive_ripple_remains_numerically_effective(response, frequency):
    magnitude = response(frequency, 1.0, 3, 5e-324)

    assert magnitude == pytest.approx(0.2282055435, rel=1e-9)


def test_chebyshev_polynomial_represents_overflowing_limit_as_infinity():
    assert chebyshev_polynomial(9, 1e300) == math.inf


def test_chebyshev_polynomial_handles_arbitrary_size_integer_order():
    huge_order = 10**400

    assert math.isfinite(chebyshev_polynomial(huge_order, 0.5))
    assert chebyshev_polynomial(huge_order, 2.0) == math.inf
    assert chebyshev_polynomial(3, 10**400) == math.inf


@pytest.mark.parametrize("response", [lowpass_chebyshev, highpass_chebyshev])
def test_chebyshev_response_handles_arbitrary_size_integer_order(response):
    assert 0.0 <= response(0.5, 1.0, 10**400, 0.5) <= 1.0


@pytest.mark.parametrize(
    ("name", "operation"),
    [
        ("shared frequency center", lambda: generate_frequency_points(HUGE_INTEGER, 2)),
        ("magnitude to dB", lambda: magnitude_to_db(HUGE_INTEGER)),
        ("3 dB frequency array", lambda: find_3db_edges([HUGE_INTEGER], [1.0])),
        ("3 dB magnitude array", lambda: find_3db_edges([1.0], [HUGE_INTEGER])),
        ("ripple limit", lambda: passband_ripple_db([1.0], [1.0], HUGE_INTEGER)),
        ("lowpass response frequency", lambda: lowpass_butterworth(HUGE_INTEGER, 1.0, 3)),
        ("lowpass response cutoff", lambda: lowpass_butterworth(1.0, HUGE_INTEGER, 3)),
        ("highpass response frequency", lambda: highpass_butterworth(HUGE_INTEGER, 1.0, 3)),
        ("highpass response cutoff", lambda: highpass_butterworth(1.0, HUGE_INTEGER, 3)),
        ("lowpass synthesis cutoff", lambda: calculate_lowpass(HUGE_INTEGER, 50.0, 3, "pi")),
        ("lowpass synthesis impedance", lambda: calculate_lowpass(1e6, HUGE_INTEGER, 3, "pi")),
        ("highpass synthesis cutoff", lambda: calculate_highpass(HUGE_INTEGER, 50.0, 3, "pi")),
        ("highpass synthesis impedance", lambda: calculate_highpass(1e6, HUGE_INTEGER, 3, "pi")),
        ("bandpass edge center", lambda: compute_bandpass_3db_edges(HUGE_INTEGER, 1.0)),
        ("bandpass edge bandwidth", lambda: compute_bandpass_3db_edges(1.0, HUGE_INTEGER)),
        ("inverse bandpass deviation", lambda: frequency_from_deviation(HUGE_INTEGER, 1.0, 1.0)),
        ("E-series single", lambda: find_closest_single(HUGE_INTEGER)),
        ("E-series match", lambda: match_component(HUGE_INTEGER, parallel_mode="additive")),
        ("strict JSON", lambda: dumps_strict({"value": HUGE_INTEGER})),
    ],
)
def test_binary64_public_apis_reject_arbitrary_size_integers(name, operation):
    del name
    with pytest.raises(ValueError):
        operation()


@pytest.mark.parametrize(
    "changes",
    [
        {"f0": HUGE_INTEGER},
        {"bw": HUGE_INTEGER},
        {"z0": HUGE_INTEGER},
        {"q_safety": HUGE_INTEGER},
        {"qu": HUGE_INTEGER},
        {"ql": HUGE_INTEGER},
        {"qc": HUGE_INTEGER},
    ],
)
def test_bandpass_synthesis_rejects_arbitrary_size_numeric_inputs(changes):
    inputs = {
        "f0": 10e6,
        "bw": 500e3,
        "z0": 50.0,
        "n_resonators": 3,
        "filter_type": "butterworth",
        "coupling": "top",
    }
    inputs.update(changes)

    with pytest.raises(ValueError):
        calculate_bandpass_filter(**inputs)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: BuildConfig(inductor_q=HUGE_INTEGER),
        lambda: BuildConfig(capacitor_tolerance_pct=HUGE_INTEGER),
        lambda: BuildConfig(source_resistance_ohm=HUGE_INTEGER),
        lambda: CircuitElement("C1", 1, 0, "C", HUGE_INTEGER),
        lambda: MatchPolicy(prefer_single_within_pct=HUGE_INTEGER),
        lambda: MatchPolicy(minimum_capacitance_f=HUGE_INTEGER),
    ],
)
def test_configuration_contracts_reject_arbitrary_size_integers(factory):
    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize(
    "operation",
    [
        lambda: solve_s21(1, [], HUGE_INTEGER, 50.0, 1, 1, [1e6]),
        lambda: solve_s21(1, [], 50.0, 50.0, 1, 1, [HUGE_INTEGER]),
        lambda: calculate_chebyshev_g_values(3, HUGE_INTEGER),
    ],
)
def test_solver_and_prototype_contracts_reject_arbitrary_size_integers(operation):
    with pytest.raises(ValueError):
        operation()


@pytest.mark.parametrize(
    "operation",
    [
        lambda: generate_frequency_points(1e6, num_points=HUGE_INTEGER),
        lambda: generate_bandpass_frequency_points(1e6, 100e3, points=HUGE_INTEGER),
        lambda: bandpass_frequency_sweep(1e6, 100e3, 3, "butterworth", points=HUGE_INTEGER),
        lambda: logspace(1.0, 2.0, HUGE_INTEGER),
        lambda: measure_netlist_passband({}, 1e6, 100e3, points=HUGE_INTEGER),
        lambda: calculate_chebyshev_g_values(HUGE_INTEGER, 0.5),
        lambda: calculate_butterworth_g_values(HUGE_INTEGER),
    ],
)
def test_list_producing_apis_reject_impossible_allocations(operation):
    with pytest.raises(ValueError):
        operation()


@pytest.mark.parametrize(
    "operation",
    [
        lambda: resolve_filter_type([]),
        lambda: resolve_coupling([]),
        lambda: solve_s21(1, [(1, 0, [], 1.0)], 50.0, 50.0, 1, 1, [1e6]),
    ],
)
def test_enum_like_public_inputs_reject_unhashable_wrong_types(operation):
    with pytest.raises(ValueError):
        operation()


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (1e300, 1e300, 1e300),
        (1e-300, 1e-300, 1e-300),
        (5e-324, 1e308, math.sqrt(5e-324) * math.sqrt(1e308)),
    ],
)
def test_positive_geometric_mean_avoids_product_overflow_and_underflow(first, second, expected):
    assert positive_geometric_mean(first, second) == pytest.approx(expected)


def test_inverse_bandpass_deviation_avoids_overflowing_shift_product():
    frequency = frequency_from_deviation(-1e308, 1e308, 1e308)

    assert frequency == pytest.approx(1.0, rel=1e-12)


def test_minimum_q_preserves_representable_result_after_compensating_scale():
    assert calculate_min_q(5e-324, 1e308, 1e308) == 5e-324


def test_insertion_loss_preserves_finite_result_across_extreme_scales():
    result = estimate_insertion_loss([1.0], 5e-324, 1e308)

    assert result == pytest.approx(4.343 / (5e-324 * 1e308), rel=1e-12)


def test_insertion_loss_scales_prototype_sum_before_combining_extremes():
    result = estimate_insertion_loss([1e308, 1e308], 1e308, 1e308)

    assert result == pytest.approx(8.686e-308, rel=1e-12)


@pytest.mark.parametrize("frequency", [-1.0, float("nan"), float("inf")])
def test_response_frequency_must_be_non_negative_and_finite(frequency):
    with pytest.raises(ValueError, match="non-negative and finite"):
        lowpass_butterworth(frequency, 10e6, 3)


_LADDER_CALCULATORS = (
    lowpass_calculations.calculate_butterworth,
    lowpass_calculations.calculate_chebyshev,
    lowpass_calculations.calculate_bessel,
    highpass_calculations.calculate_butterworth,
    highpass_calculations.calculate_chebyshev,
    highpass_calculations.calculate_bessel,
)


def _ladder_args(calculator, cutoff: float, impedance: float) -> tuple:
    if calculator.__name__ == "calculate_chebyshev":
        return cutoff, impedance, 0.5, 3, "pi"
    return cutoff, impedance, 3, "pi"


@pytest.mark.parametrize("calculator", _LADDER_CALCULATORS)
@pytest.mark.parametrize(
    ("cutoff", "impedance"),
    [(5e-324, 50.0), (10e6, 5e-324), (1e308, 1e308)],
)
def test_ladder_component_results_must_be_positive_and_finite(calculator, cutoff, impedance):
    with pytest.raises(ValueError, match="finite positive component values"):
        calculator(*_ladder_args(calculator, cutoff, impedance))


def test_ladder_does_not_evaluate_unused_overflowing_component_formula():
    capacitors, inductors, order = calculate_lowpass(1e-300, 1.5e-9, 3, "pi")

    assert order == 3
    assert len(capacitors) == 2
    assert len(inductors) == 1
    assert all(math.isfinite(value) and value > 0 for value in [*capacitors, *inductors])


@pytest.mark.parametrize("calculator", [calculate_lowpass, calculate_highpass])
@pytest.mark.parametrize("cutoff", [1e307, 3e307])
def test_ladder_scaling_avoids_overflowing_intermediate_angular_frequency(calculator, cutoff):
    first, second, order = calculator(cutoff, 10.0, 3, "pi")

    assert order == 3
    assert all(math.isfinite(value) and value > 0 for value in [*first, *second])


@pytest.mark.parametrize(
    "arguments",
    [
        ["lp", "bw", "pi", "5e-324", "--no-toroids", "--no-match"],
        [
            "lp",
            "bw",
            "pi",
            "10MHz",
            "--sim-build",
            "--capacitor-q",
            "5e-324",
            "--no-toroids",
        ],
        [
            "bp",
            "bw",
            "top",
            "-f",
            "10MHz",
            "-b",
            "500kHz",
            "--qu",
            "5e-324",
            "--format",
            "json",
            "--no-toroids",
        ],
    ],
)
def test_unrepresentable_cli_values_fail_cleanly(monkeypatch, capsys, arguments):
    monkeypatch.setattr(sys, "argv", ["filter-calc", *arguments])

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err.startswith("Error:")
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("frequency", ["1e155", "1e-200"])
def test_extreme_ladder_build_json_keeps_center_frequency_finite(monkeypatch, capsys, frequency):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "filter-calc",
            "lp",
            "bw",
            "pi",
            frequency,
            "--sim-build",
            "--no-toroids",
            "--analysis-points",
            "51",
            "--format",
            "json",
        ],
    )

    cli.main()
    payload = json.loads(capsys.readouterr().out)
    measurement = payload["simulated"]["measurement"]
    assert measurement["cutoff_hz"] > 0
    assert math.isfinite(measurement["cutoff_hz"])
    assert measurement["f0_hz"] is None
    assert measurement["bandwidth_hz"] is None


@pytest.mark.parametrize(
    "frequency_args",
    [
        ["-f", "1e155", "-b", "1e153"],
        ["-f", "1e-200", "-b", "1e-202"],
        ["--fl", "9.95e154", "--fh", "1.005e155"],
        ["--fl", "9.95e-201", "--fh", "1.005e-200"],
    ],
)
def test_extreme_bandpass_centers_remain_finite(monkeypatch, capsys, frequency_args):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "filter-calc",
            "bp",
            "bw",
            "top",
            *frequency_args,
            "--no-toroids",
            "--no-match",
            "--format",
            "json",
        ],
    )

    cli.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["center_frequency_hz"] > 0
    assert math.isfinite(payload["center_frequency_hz"])
    assert payload["synthesis_validation"]["measured_center_hz"] > 0
    assert math.isfinite(payload["synthesis_validation"]["measured_center_hz"])
