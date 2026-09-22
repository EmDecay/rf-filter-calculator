"""Pi/T element placement for lowpass and highpass ladders.

Pi places a shunt element at the source end and T a series element. Lowpass
shunt elements are capacitors and series elements inductors; highpass swaps them.
"""

import json

import pytest

from filter_lib.highpass import calculations as hp
from filter_lib.lowpass import calculations as lp
from filter_lib.shared.display_common import format_json_result

_CALCULATORS = {
    ("lowpass", "butterworth"): (lp.calculate_butterworth, (), range(2, 10)),
    ("lowpass", "chebyshev"): (lp.calculate_chebyshev, (0.5,), (3, 5, 7, 9)),
    ("lowpass", "bessel"): (lp.calculate_bessel, (), range(2, 10)),
    ("highpass", "butterworth"): (hp.calculate_butterworth, (), range(2, 10)),
    ("highpass", "chebyshev"): (hp.calculate_chebyshev, (0.5,), (3, 5, 7, 9)),
    ("highpass", "bessel"): (hp.calculate_bessel, (), range(2, 10)),
}


def _capacitors_and_inductors(category, family, order, topology, impedance=50.0):
    calculate, extra, _ = _CALCULATORS[(category, family)]
    first, second, returned_order = calculate(10e6, impedance, *extra, order, topology)
    assert returned_order == order
    # Lowpass returns (capacitors, inductors); highpass returns (inductors, capacitors).
    return (first, second) if category == "lowpass" else (second, first)


@pytest.mark.parametrize("topology", ["pi", "t"])
@pytest.mark.parametrize(("category", "family"), sorted(_CALCULATORS))
def test_element_counts_follow_source_end_placement(category, family, topology):
    """The source-end kind fills the odd positions, so it gets ceil(n/2) elements."""
    source_end_is_capacitor = (topology == "pi") == (category == "lowpass")

    for order in _CALCULATORS[(category, family)][2]:
        capacitors, inductors = _capacitors_and_inductors(category, family, order, topology)
        odd_positions, even_positions = (order + 1) // 2, order // 2
        if source_end_is_capacitor:
            assert (len(capacitors), len(inductors)) == (odd_positions, even_positions)
        else:
            assert (len(capacitors), len(inductors)) == (even_positions, odd_positions)


@pytest.mark.parametrize(("category", "family"), sorted(_CALCULATORS))
def test_t_ladder_is_the_impedance_dual_of_the_pi_ladder(category, family):
    """Each T element is the Z0-dual of the Pi element at the same position.

    A shunt C of the Pi ladder becomes a series L = Z0^2 * C in the T ladder, and a
    series L becomes a shunt C = L / Z0^2 (and likewise with the highpass kinds).
    """
    impedance = 75.0
    for order in _CALCULATORS[(category, family)][2]:
        pi_caps, pi_inds = _capacitors_and_inductors(category, family, order, "pi", impedance)
        t_caps, t_inds = _capacitors_and_inductors(category, family, order, "t", impedance)

        assert t_inds == pytest.approx([impedance**2 * c for c in pi_caps], rel=1e-12, abs=0)
        assert t_caps == pytest.approx([ind / impedance**2 for ind in pi_inds], rel=1e-12, abs=0)


def test_json_output_omits_topology_when_result_has_none():
    result = {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50,
        "order": 3,
        "capacitors": [1e-10],
        "inductors": [1e-6],
        "ripple": None,
    }
    data = json.loads(format_json_result(result, primary_component="capacitors"))
    assert "topology" not in data
