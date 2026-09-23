"""Ladder values stay accurate at extreme but representable frequency and impedance scales.

The calculators work in the log domain so that intermediate products such as 2*pi*f*Z
cannot overflow. Published-table tests already pin the denormalization formulas at
ordinary scales; here the same textbook formulas are evaluated with 50-digit decimal
arithmetic, so a clamp, a lost scale factor, or a precision-losing shortcut at the
extremes cannot pass as merely "finite and positive".
"""

from decimal import Decimal, localcontext

import pytest

from filter_lib.highpass import calculations as hp
from filter_lib.lowpass import calculations as lp

# Third-order Butterworth prototype: g1 = g3 = 1, g2 = 2 (Matthaei Table 4.05-1(a)).
_G1, _G2, _G3 = Decimal(1), Decimal(2), Decimal(1)
_PI = Decimal("3.14159265358979323846264338327950288419716939937510")

# Each case keeps every component inside the binary64 range; several results are
# near the largest normal float or in the subnormal range, where the log-domain
# evaluation matters most.
_EXTREME_SCALES = [
    (1e-300, 1.5e-9),
    (3e307, 10.0),
    (1e-150, 1e150),
    (1e150, 1e-150),
    (1e150, 1e150),
]


def _reference_pi_ladder(category: str, cutoff_hz: float, impedance: float):
    """Return (capacitors, inductors) of the 3-element Pi ladder in the public tuple order."""
    with localcontext() as context:
        context.prec = 50
        omega = 2 * _PI * Decimal(cutoff_hz)
        z = Decimal(impedance)
        if category == "lowpass":  # shunt C (g1, g3), series L (g2)
            capacitors = [_G1 / (z * omega), _G3 / (z * omega)]
            inductors = [_G2 * z / omega]
        else:  # highpass Pi: shunt L (g1, g3), series C (g2)
            inductors = [z / (omega * _G1), z / (omega * _G3)]
            capacitors = [1 / (_G2 * omega * z)]
    return [float(c) for c in capacitors], [float(ind) for ind in inductors]


@pytest.mark.parametrize(("cutoff_hz", "impedance"), _EXTREME_SCALES)
@pytest.mark.parametrize("category", ["lowpass", "highpass"])
def test_extreme_scale_components_match_high_precision_reference(category, cutoff_hz, impedance):
    if category == "lowpass":
        capacitors, inductors, _ = lp.calculate_butterworth(cutoff_hz, impedance, 3, "pi")
    else:
        inductors, capacitors, _ = hp.calculate_butterworth(cutoff_hz, impedance, 3, "pi")

    expected_capacitors, expected_inductors = _reference_pi_ladder(category, cutoff_hz, impedance)
    assert capacitors == pytest.approx(expected_capacitors, rel=1e-12, abs=0)
    assert inductors == pytest.approx(expected_inductors, rel=1e-12, abs=0)
