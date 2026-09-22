"""Strict numeric contracts for public Top-C coupling helpers."""

import pytest

from filter_lib.bandpass.calculations import (
    calculate_coupling_capacitors,
    calculate_coupling_coefficients,
    calculate_end_coupling,
    calculate_external_q,
    calculate_tank_capacitors,
)


@pytest.mark.parametrize("fbw", [True, 0, -0.1, float("nan"), float("inf")])
def test_coupling_coefficients_require_positive_finite_fbw(fbw) -> None:
    with pytest.raises(ValueError, match="fbw must be positive and finite"):
        calculate_coupling_coefficients([1.0, 1.0], fbw)


@pytest.mark.parametrize(
    "g_values, message",
    [
        ([], "at least 2 value"),
        ([1.0], "at least 2 value"),
        ((1.0, 1.0), "must be a list"),
        ([True, 1.0], r"g_values\[0\] must be positive and finite"),
        ([float("nan"), 1.0], r"g_values\[0\] must be positive and finite"),
        ([1.0, float("inf")], r"g_values\[1\] must be positive and finite"),
    ],
)
def test_coupling_coefficients_validate_prototype_values(g_values, message) -> None:
    with pytest.raises(ValueError, match=message):
        calculate_coupling_coefficients(g_values, 0.1)


def test_coupling_coefficients_reject_underflowing_result() -> None:
    with pytest.raises(ValueError, match="derived coupling coefficients"):
        calculate_coupling_coefficients([1e308, 1e308], 5e-324)


@pytest.mark.parametrize(
    "g_values, message",
    [
        ([], "at least 1 value"),
        ([True], r"g_values\[0\] must be positive and finite"),
        ([float("nan")], r"g_values\[0\] must be positive and finite"),
        ([float("inf")], r"g_values\[0\] must be positive and finite"),
    ],
)
def test_external_q_validates_prototype_values(g_values, message) -> None:
    with pytest.raises(ValueError, match=message):
        calculate_external_q(g_values, 0.1)


def test_external_q_rejects_overflowing_result() -> None:
    with pytest.raises(ValueError, match="derived external Q"):
        calculate_external_q([1.0], 5e-324)


@pytest.mark.parametrize("k_values", [[True], [float("nan")], [float("inf")]])
def test_coupling_capacitors_validate_coefficients(k_values) -> None:
    with pytest.raises(ValueError, match=r"k_values\[0\] must be positive and finite"):
        calculate_coupling_capacitors(k_values, 1e-12)


@pytest.mark.parametrize("resonators", [True, 0, 2.5])
def test_tank_capacitors_require_integer_resonator_count(resonators) -> None:
    with pytest.raises(ValueError, match="integer"):
        calculate_tank_capacitors(resonators, 100e-12, [10e-12])


def test_tank_capacitors_require_matching_coupling_count() -> None:
    with pytest.raises(ValueError, match="exactly"):
        calculate_tank_capacitors(3, 100e-12, [10e-12])


def test_tank_capacitors_reject_nonpositive_derived_capacitance() -> None:
    with pytest.raises(ValueError, match="derived tank capacitances"):
        calculate_tank_capacitors(2, 100e-12, [100e-12])


@pytest.mark.parametrize(
    "values",
    [
        (float("nan"), 1.0, 1.0, 1.0),
        (1.0, float("inf"), 1.0, 1.0),
        (1.0, 1.0, True, 1.0),
        (1.0, 1.0, 1.0, 0.0),
    ],
)
def test_end_coupling_validates_inputs(values) -> None:
    with pytest.raises(ValueError, match="positive and finite"):
        calculate_end_coupling(*values)


def test_end_coupling_rejects_nonfinite_derived_values() -> None:
    with pytest.raises(ValueError, match="derived"):
        calculate_end_coupling(1e308, 1e308, 1e308, 1.0)
