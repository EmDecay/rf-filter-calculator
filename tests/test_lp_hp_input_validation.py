"""Public input validation shared by the six lowpass/highpass ladder calculators.

All six public calculators route through one shared validator, so each calculator is
checked once per field and the full catalogue of invalid values is exercised once.
"""

import math

import pytest

from filter_lib.highpass import calculations as hp
from filter_lib.lowpass import calculations as lp

_CALCULATORS = {
    "lowpass-butterworth": lp.calculate_butterworth,
    "lowpass-chebyshev": lp.calculate_chebyshev,
    "lowpass-bessel": lp.calculate_bessel,
    "highpass-butterworth": hp.calculate_butterworth,
    "highpass-chebyshev": hp.calculate_chebyshev,
    "highpass-bessel": hp.calculate_bessel,
}
_CHEBYSHEV = ["lowpass-chebyshev", "highpass-chebyshev"]

_CUTOFF_ERROR = "Cutoff frequency must be positive and finite"
_IMPEDANCE_ERROR = "Impedance must be positive and finite"
_ORDER_ERROR = "between 2 and 9"
_TOPOLOGY_ERROR = "Topology must be 'pi' or 't'"


def _calculate(name, *, cutoff=10e6, impedance=50.0, order=3, topology="pi", ripple=0.5):
    calculator = _CALCULATORS[name]
    if name in _CHEBYSHEV:
        return calculator(cutoff, impedance, ripple, order, topology)
    return calculator(cutoff, impedance, order, topology)


@pytest.mark.parametrize("name", sorted(_CALCULATORS))
def test_every_calculator_validates_each_input(name):
    with pytest.raises(ValueError, match=_CUTOFF_ERROR):
        _calculate(name, cutoff=float("nan"))
    with pytest.raises(ValueError, match=_IMPEDANCE_ERROR):
        _calculate(name, impedance=0.0)
    with pytest.raises(ValueError, match=_ORDER_ERROR):
        _calculate(name, order=10)
    with pytest.raises(ValueError, match=_TOPOLOGY_ERROR):
        _calculate(name, topology="x")


_NOT_POSITIVE_FINITE_REAL = [0, -1e6, float("nan"), float("inf"), True, "10e6", None]


@pytest.mark.parametrize("value", _NOT_POSITIVE_FINITE_REAL)
def test_cutoff_must_be_a_positive_finite_real(value):
    with pytest.raises(ValueError, match=_CUTOFF_ERROR):
        _calculate("lowpass-butterworth", cutoff=value)


@pytest.mark.parametrize("value", _NOT_POSITIVE_FINITE_REAL)
def test_impedance_must_be_a_positive_finite_real(value):
    with pytest.raises(ValueError, match=_IMPEDANCE_ERROR):
        _calculate("highpass-bessel", impedance=value)


@pytest.mark.parametrize("order", [1, 10, True, 3.0, 3.5, "3", None])
def test_order_must_be_an_integer_from_two_to_nine(order):
    with pytest.raises(ValueError, match=_ORDER_ERROR):
        _calculate("lowpass-chebyshev", order=order)


@pytest.mark.parametrize("topology", ["x", "PI", "", None])
def test_topology_must_be_pi_or_t(topology):
    with pytest.raises(ValueError, match=_TOPOLOGY_ERROR):
        _calculate("highpass-butterworth", topology=topology)


@pytest.mark.parametrize("order", [2, 4, 6, 8])
@pytest.mark.parametrize("name", _CHEBYSHEV)
def test_chebyshev_even_order_is_rejected_for_equal_terminations(name, order):
    with pytest.raises(ValueError, match="requires odd order"):
        _calculate(name, order=order)


@pytest.mark.parametrize(
    "ripple",
    [0.0, -0.1, float("nan"), float("inf"), True, "0.5", None, math.nextafter(3.0, 4.0)],
)
@pytest.mark.parametrize("name", _CHEBYSHEV)
def test_chebyshev_ripple_outside_zero_to_three_db_is_rejected(name, ripple):
    with pytest.raises(ValueError, match=r"positive, finite, and at most 3\.0 dB"):
        _calculate(name, ripple=ripple)


@pytest.mark.parametrize("ripple", [3.0, 5e-324])
@pytest.mark.parametrize("name", _CHEBYSHEV)
def test_chebyshev_ripple_range_endpoints_are_accepted(name, ripple):
    first, second, order = _calculate(name, ripple=ripple)

    assert order == 3
    assert all(math.isfinite(value) and value > 0 for value in [*first, *second])
