"""Normalized LC prototypes must realize their textbook magnitude responses.

Every prototype is evaluated here as a 1-ohm doubly terminated ladder with ABCD
matrices, independently of the synthesis code, and compared with the closed-form
Butterworth, Chebyshev, and Bessel responses. At a cutoff of 1/(2*pi) Hz and a
1-ohm impedance the lowpass calculators return the prototype g-values themselves.
"""

import math

import pytest

from filter_lib.lowpass import calculations as lp
from filter_lib.shared.chebyshev_g_calculator import calculate_chebyshev_g_values

NORMALIZED_CUTOFF_HZ = 1 / (2 * math.pi)


def _power_gain(elements: list[float], omega: float, *, first_shunt: bool = True) -> float:
    """Return |S21|^2 of a 1-ohm doubly terminated lowpass ladder (shunt C, series L)."""
    s = 1j * omega
    a, b, c, d = 1, 0, 0, 1
    for position, value in enumerate(elements):
        if (position % 2 == 0) == first_shunt:
            admittance = s * value
            a, c = a + b * admittance, c + d * admittance
        else:
            impedance = s * value
            b, d = a * impedance + b, c * impedance + d
    return abs(2 / (a + b + c + d)) ** 2


def _ladder_order(capacitors: list[float], inductors: list[float], topology: str) -> list[float]:
    """Interleave lowpass elements from the source end: Pi starts shunt-C, T starts series-L."""
    remaining_caps, remaining_inds = iter(capacitors), iter(inductors)
    starts_with_cap = topology == "pi"
    return [
        next(remaining_caps) if (position % 2 == 0) == starts_with_cap else next(remaining_inds)
        for position in range(len(capacitors) + len(inductors))
    ]


def _log_epsilon_squared(ripple_db: float) -> float:
    """Return log(10**(ripple_db/10) - 1), accurate down to the smallest positive ripple."""
    log_x = math.log(ripple_db) + math.log(math.log(10) / 10)
    if log_x < -40:  # expm1(x) equals x to double precision here
        return log_x
    return math.log(math.expm1(math.exp(log_x)))


@pytest.mark.parametrize("topology", ["pi", "t"])
@pytest.mark.parametrize("order", range(2, 10))
def test_butterworth_prototype_is_maximally_flat_with_3db_at_cutoff(order, topology):
    capacitors, inductors, _ = lp.calculate_butterworth(NORMALIZED_CUTOFF_HZ, 1.0, order, topology)
    ladder = _ladder_order(capacitors, inductors, topology)

    for omega in (0.0, 0.5, 1.0, 2.0):
        expected = 1 / (1 + omega ** (2 * order))
        assert _power_gain(ladder, omega, first_shunt=topology == "pi") == pytest.approx(
            expected, rel=1e-12
        )


@pytest.mark.parametrize("ripple_db", [5e-324, 1e-20, 0.01, 0.1, 0.5, 1.0, 3.0, 5.0, 20.0])
@pytest.mark.parametrize("order", [1, 3, 5, 7, 9])
def test_chebyshev_prototype_is_equiripple_with_ripple_at_band_edge(order, ripple_db):
    """|S21|^2 = 1/(1 + eps^2 T_n(w)^2), eps^2 = 10^(ripple/10) - 1, for odd equal-terminated n.

    The passband points are the reflection zeros (T_n = 0, full transmission) and the
    ripple troughs (|T_n| = 1, attenuation equal to ripple_db, including w = 1). The
    stopband points are placed where eps * T_n(w) equals a chosen value y.
    """
    ladder = calculate_chebyshev_g_values(order, ripple_db)[1:]
    ripple_trough = math.exp(-ripple_db * math.log(10) / 10)
    points = [
        (0.0, 1.0),
        (math.cos(math.pi / (2 * order)), 1.0),
        (math.cos(math.pi / order), ripple_trough),
        (1.0, ripple_trough),
    ]
    log_epsilon = 0.5 * _log_epsilon_squared(ripple_db)
    for y in (0.5, 2.0, 30.0):
        chebyshev_value = math.exp(math.log(y) - log_epsilon)
        if chebyshev_value >= 1:
            omega = math.cosh(math.acosh(chebyshev_value) / order)
            points.append((omega, 1 / (1 + y * y)))

    for omega, expected in points:
        assert _power_gain(ladder, omega) == pytest.approx(expected, rel=1e-10), omega


@pytest.mark.parametrize("topology", ["pi", "t"])
@pytest.mark.parametrize("ripple_db", [5e-324, 0.01, 1.5, 3.0])
@pytest.mark.parametrize("order", [3, 9])
def test_public_chebyshev_ladder_realizes_requested_ripple(order, ripple_db, topology):
    """The public calculator honours ripple across the accepted (0, 3] dB range.

    The published-table tests stop at 1 dB, so this pins the calculator itself (not only
    the g-value helper) at both range endpoints: full transmission at DC and at the first
    reflection zero, and exactly ripple_db of loss at the band edge w = 1.
    """
    capacitors, inductors, _ = lp.calculate_chebyshev(
        NORMALIZED_CUTOFF_HZ, 1.0, ripple_db, order, topology
    )
    ladder = _ladder_order(capacitors, inductors, topology)
    first_shunt = topology == "pi"
    band_edge_gain = math.exp(-ripple_db * math.log(10) / 10)

    for omega, expected in [
        (0.0, 1.0),
        (math.cos(math.pi / (2 * order)), 1.0),
        (1.0, band_edge_gain),
    ]:
        assert _power_gain(ladder, omega, first_shunt=first_shunt) == pytest.approx(
            expected, rel=1e-10
        ), omega


def _bessel_polynomial(order: int) -> list[float]:
    """Reverse Bessel polynomial coefficients, lowest power first (delay-normalized)."""
    return [
        math.factorial(2 * order - k)
        / (2 ** (order - k) * math.factorial(k) * math.factorial(order - k))
        for k in range(order + 1)
    ]


def _ideal_bessel_gain(order: int, omega: float, delay_to_3db_scale: float) -> float:
    coefficients = _bessel_polynomial(order)
    s = 1j * omega * delay_to_3db_scale
    denominator = sum(coefficient * s**power for power, coefficient in enumerate(coefficients))
    return abs(coefficients[0] / denominator) ** 2


def _bessel_3db_scale(order: int) -> float:
    """Bisect the delay-normalized Bessel response for its -3 dB frequency."""
    low, high = 0.1, 10.0
    for _ in range(100):
        middle = 0.5 * (low + high)
        if _ideal_bessel_gain(order, 1.0, middle) > 0.5:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


@pytest.mark.parametrize("order", range(2, 10))
def test_bessel_table_realizes_bessel_response_with_3db_at_cutoff(order):
    """The 4-decimal table rows stay within 6e-5 of the ideal Bessel power gain.

    Rounding alone leaves at most about 3.3e-5; a change of 5 in the fourth decimal of
    any single element moves the response by more than 1.1e-4.
    """
    capacitors, inductors, _ = lp.calculate_bessel(NORMALIZED_CUTOFF_HZ, 1.0, order, "pi")
    ladder = _ladder_order(capacitors, inductors, "pi")
    scale = _bessel_3db_scale(order)

    for omega in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0):
        assert _power_gain(ladder, omega) == pytest.approx(
            _ideal_bessel_gain(order, omega, scale), abs=6e-5
        ), omega
