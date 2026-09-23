"""Single-frequency response factories: every filter-type spelling routes correctly.

Each factory is evaluated where the three families differ by many dB, and the
result is compared with an independently computed reference for the expected
family, so a mis-routed alias cannot pass.
"""

import math

import pytest

from filter_lib.shared.transfer_response_dispatch import (
    make_bp_netlist_response_db,
    make_hp_response_db,
    make_lp_response_db,
)

FC = 10e6


def _chebyshev_db(x: float, order: int, ripple_db: float) -> float:
    t_previous, t_current = 1.0, x
    for _ in range(order - 1):
        t_previous, t_current = t_current, 2.0 * x * t_current - t_previous
    return -10 * math.log10(1 + (10 ** (ripple_db / 10) - 1) * t_current**2)


# Order-5 prototypes at twice the cutoff (ratio 2). The Bessel value is the
# delay-normalized reverse Bessel polynomial evaluated at 2 * 2.4274 rad/s.
LP_ORDER5_RATIO2_DB = {
    "butterworth": -10 * math.log10(1 + 2**10),
    "chebyshev": _chebyshev_db(2.0, 5, 0.5),
    "bessel": -14.0626,
}
SPELLINGS = [
    ("butterworth", "butterworth"),
    ("BUTTERWORTH", "butterworth"),
    ("bw", "butterworth"),
    ("b", "butterworth"),
    ("chebyshev", "chebyshev"),
    ("Chebyshev", "chebyshev"),
    ("ch", "chebyshev"),
    ("c", "chebyshev"),
    ("bessel", "bessel"),
    ("BESSEL", "bessel"),
    ("bs", "bessel"),
]


class TestFilterTypeRouting:
    @pytest.mark.parametrize(("spelling", "family"), SPELLINGS)
    def test_lowpass_factory_routes_every_spelling(self, spelling, family):
        response_db = make_lp_response_db(spelling, FC, 5, 0.5)

        assert response_db(2 * FC) == pytest.approx(LP_ORDER5_RATIO2_DB[family], abs=1e-3)

    @pytest.mark.parametrize(("spelling", "family"), SPELLINGS)
    def test_highpass_factory_routes_every_spelling(self, spelling, family):
        response_db = make_hp_response_db(spelling, FC, 5, 0.5)

        assert response_db(FC / 2) == pytest.approx(LP_ORDER5_RATIO2_DB[family], abs=1e-3)

    @pytest.mark.parametrize(
        "factory",
        [make_lp_response_db, make_hp_response_db],
        ids=["lowpass", "highpass"],
    )
    @pytest.mark.parametrize("ripple_db", [0.1, 1.0, 3.0])
    def test_lp_hp_factories_forward_chebyshev_ripple(self, factory, ripple_db):
        assert factory("chebyshev", FC, 5, ripple_db)(FC) == pytest.approx(-ripple_db, abs=1e-9)

    def test_ripple_defaults_to_half_db(self):
        assert make_lp_response_db("ch", FC, 5)(FC) == pytest.approx(-0.5, abs=1e-9)
        assert make_hp_response_db("ch", FC, 5)(FC) == pytest.approx(-0.5, abs=1e-9)

    def test_factories_report_db_with_the_minus_120_db_floor(self):
        assert make_lp_response_db("bw", FC, 9)(1000 * FC) == -120.0
        assert make_hp_response_db("bw", FC, 9)(0.0) == -120.0


_FACTORIES = [
    lambda filter_type: make_lp_response_db(filter_type, FC, 5),
    lambda filter_type: make_hp_response_db(filter_type, FC, 5),
]


class TestFilterTypeValidation:
    @pytest.mark.parametrize("factory", _FACTORIES, ids=["lowpass", "highpass"])
    @pytest.mark.parametrize(
        ("filter_type", "message"),
        [
            (None, "Filter type must be provided, got None"),
            (1, "filter_type must be a string"),
            ([], "filter_type must be a string"),
            ({}, "filter_type must be a string"),
            (
                "elliptic",
                "Unknown filter type 'elliptic'; expected one of butterworth, chebyshev, bessel",
            ),
        ],
    )
    def test_factory_rejects_invalid_type_before_evaluation(self, factory, filter_type, message):
        with pytest.raises(ValueError, match=message):
            factory(filter_type)


def test_netlist_factory_matches_netlist_sweep():
    from filter_lib.bandpass.calculations import calculate_bandpass_filter
    from filter_lib.bandpass.transfer import netlist_frequency_sweep

    result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")
    response_db = make_bp_netlist_response_db(result)
    sweep = netlist_frequency_sweep(result, points=21)

    for frequency, db in sweep[::5]:
        assert response_db(frequency) == pytest.approx(db, abs=1e-9)
