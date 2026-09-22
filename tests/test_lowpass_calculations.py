"""Lowpass ladder values against published prototype tables and exact scaling laws.

Component values are normalized back to prototype g-values with the textbook
denormalization (shunt C = g / (Z * omega), series L = g * Z / omega) and compared
with published tables at a non-trivial design point.
"""

import math

import pytest

from filter_lib.lowpass import calculations as lp
from tests.test_chebyshev_calculator import PUBLISHED_G_VALUES

# Matthaei, Young & Jones, Table 4.05-1(a): maximally flat, equal 1-ohm terminations.
BUTTERWORTH_PUBLISHED: dict[int, list[float]] = {
    2: [1.4142, 1.4142],
    3: [1.0000, 2.0000, 1.0000],
    4: [0.7654, 1.8478, 1.8478, 0.7654],
    5: [0.6180, 1.6180, 2.0000, 1.6180, 0.6180],
    6: [0.5176, 1.4142, 1.9318, 1.9318, 1.4142, 0.5176],
    7: [0.4450, 1.2470, 1.8019, 2.0000, 1.8019, 1.2470, 0.4450],
    8: [0.3902, 1.1111, 1.6629, 1.9616, 1.9616, 1.6629, 1.1111, 0.3902],
    9: [0.3473, 1.0000, 1.5321, 1.8794, 2.0000, 1.8794, 1.5321, 1.0000, 0.3473],
}

# Zverev (1967) Bessel prototype, normalized to -3 dB at omega = 1, listed from the
# source end. The rows are asymmetric, so this also pins element orientation.
BESSEL_PUBLISHED: dict[int, list[float]] = {
    2: [0.5755, 2.1478],
    3: [0.3374, 0.9705, 2.2034],
    4: [0.2334, 0.6725, 1.0815, 2.2404],
    5: [0.1743, 0.5072, 0.8040, 1.1110, 2.2582],
    6: [0.1365, 0.4002, 0.6392, 0.8538, 1.1126, 2.2645],
    7: [0.1106, 0.3259, 0.5249, 0.7020, 0.8690, 1.1052, 2.2659],
    8: [0.0919, 0.2719, 0.4409, 0.5936, 0.7303, 0.8695, 1.0956, 2.2656],
    9: [0.0780, 0.2313, 0.3770, 0.5108, 0.6306, 0.7407, 0.8639, 1.0863, 2.2649],
}

CUTOFF_HZ = 7.1e6
IMPEDANCE = 75.0
OMEGA = 2 * math.pi * CUTOFF_HZ


def _normalized_ladder(capacitors, inductors, topology: str) -> list[float]:
    """Return g-values in ladder order; Pi starts with a shunt C, T with a series L."""
    remaining_caps, remaining_inds = iter(capacitors), iter(inductors)
    ladder = []
    for position in range(len(capacitors) + len(inductors)):
        if (position % 2 == 0) == (topology == "pi"):
            ladder.append(next(remaining_caps) * IMPEDANCE * OMEGA)
        else:
            ladder.append(next(remaining_inds) * OMEGA / IMPEDANCE)
    return ladder


@pytest.mark.parametrize("topology", ["pi", "t"])
@pytest.mark.parametrize("order", sorted(BUTTERWORTH_PUBLISHED))
def test_butterworth_matches_published_prototype(order, topology):
    capacitors, inductors, returned_order = lp.calculate_butterworth(
        CUTOFF_HZ, IMPEDANCE, order, topology
    )

    assert returned_order == order
    assert _normalized_ladder(capacitors, inductors, topology) == pytest.approx(
        BUTTERWORTH_PUBLISHED[order], abs=6e-5
    )


@pytest.mark.parametrize("ripple_db", sorted(PUBLISHED_G_VALUES))
@pytest.mark.parametrize("order", [3, 5, 7, 9])
def test_chebyshev_matches_published_prototype(order, ripple_db):
    capacitors, inductors, returned_order = lp.calculate_chebyshev(
        CUTOFF_HZ, IMPEDANCE, ripple_db, order, "pi"
    )

    assert returned_order == order
    assert _normalized_ladder(capacitors, inductors, "pi") == pytest.approx(
        PUBLISHED_G_VALUES[ripple_db][order], abs=1e-4
    )


@pytest.mark.parametrize("order", sorted(BESSEL_PUBLISHED))
def test_bessel_matches_published_prototype_from_source_end(order):
    capacitors, inductors, returned_order = lp.calculate_bessel(CUTOFF_HZ, IMPEDANCE, order, "pi")

    assert returned_order == order
    assert _normalized_ladder(capacitors, inductors, "pi") == pytest.approx(
        BESSEL_PUBLISHED[order], abs=6e-5
    )


_FAMILIES = {
    "butterworth": lambda f, z, topology: lp.calculate_butterworth(f, z, 5, topology),
    "chebyshev": lambda f, z, topology: lp.calculate_chebyshev(f, z, 0.5, 7, topology),
    "bessel": lambda f, z, topology: lp.calculate_bessel(f, z, 6, topology),
}


@pytest.mark.parametrize("topology", ["pi", "t"])
@pytest.mark.parametrize("family", sorted(_FAMILIES))
def test_impedance_scaling_is_exact(family, topology):
    """L scales with Z and C with 1/Z over a thousandfold impedance change."""
    calculate = _FAMILIES[family]
    caps_low, inds_low, _ = calculate(CUTOFF_HZ, 5.0, topology)
    caps_high, inds_high, _ = calculate(CUTOFF_HZ, 5000.0, topology)

    assert inds_high == pytest.approx([1000 * value for value in inds_low], rel=1e-12)
    assert caps_high == pytest.approx([value / 1000 for value in caps_low], rel=1e-12, abs=0)


@pytest.mark.parametrize("topology", ["pi", "t"])
@pytest.mark.parametrize("family", sorted(_FAMILIES))
def test_frequency_scaling_is_exact(family, topology):
    """Both L and C scale with 1/f from 1 kHz to 1 GHz."""
    calculate = _FAMILIES[family]
    caps_low, inds_low, _ = calculate(1e3, IMPEDANCE, topology)
    caps_high, inds_high, _ = calculate(1e9, IMPEDANCE, topology)

    assert inds_high == pytest.approx([value / 1e6 for value in inds_low], rel=1e-12, abs=0)
    assert caps_high == pytest.approx([value / 1e6 for value in caps_low], rel=1e-12, abs=0)
