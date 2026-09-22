"""Highpass ladders are the exact lowpass-to-highpass frequency transformation.

Replacing s/wc with wc/s turns every lowpass element into its dual at the same
ladder position: a shunt C becomes a shunt L and a series L becomes a series C,
each resonating with the element it replaces at the cutoff (L_hp * C_lp = 1/wc^2).
Together with the lowpass reference tests this pins every highpass value.
"""

import math

import pytest

from filter_lib.highpass import calculations as hp
from filter_lib.lowpass import calculations as lp

_FAMILIES = {
    "butterworth": (lp.calculate_butterworth, hp.calculate_butterworth, (), range(2, 10)),
    "chebyshev": (lp.calculate_chebyshev, hp.calculate_chebyshev, (0.5,), (3, 5, 7, 9)),
    "bessel": (lp.calculate_bessel, hp.calculate_bessel, (), range(2, 10)),
}


@pytest.mark.parametrize(("cutoff_hz", "impedance"), [(1e3, 50.0), (14.2e6, 75.0), (2.4e9, 600.0)])
@pytest.mark.parametrize("topology", ["pi", "t"])
@pytest.mark.parametrize("family", sorted(_FAMILIES))
def test_each_highpass_element_resonates_with_its_lowpass_counterpart_at_cutoff(
    family, topology, cutoff_hz, impedance
):
    lowpass, highpass, extra, orders = _FAMILIES[family]
    inverse_omega_squared = 1 / (2 * math.pi * cutoff_hz) ** 2

    for order in orders:
        lp_caps, lp_inds, _ = lowpass(cutoff_hz, impedance, *extra, order, topology)
        # Highpass returns inductors first, the reverse of the lowpass tuple.
        hp_inds, hp_caps, hp_order = highpass(cutoff_hz, impedance, *extra, order, topology)

        assert hp_order == order
        assert [l_hp * c_lp for l_hp, c_lp in zip(hp_inds, lp_caps, strict=True)] == (
            pytest.approx([inverse_omega_squared] * len(lp_caps), rel=1e-12, abs=0)
        )
        assert [c_hp * l_lp for c_hp, l_lp in zip(hp_caps, lp_inds, strict=True)] == (
            pytest.approx([inverse_omega_squared] * len(lp_inds), rel=1e-12, abs=0)
        )
