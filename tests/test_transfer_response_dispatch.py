"""Single-frequency response factories: every filter-type spelling routes correctly.

Each factory is evaluated where the three families differ by many dB, and the
result is compared with an independently computed reference for the expected
family, so a mis-routed alias cannot pass.
"""

import math

import pytest

from filter_lib.shared.transfer_response_dispatch import (
    make_bp_netlist_response_db,
    make_bp_response_db,
    make_hp_response_db,
    make_lp_response_db,
)

FC = 10e6
F0 = 1e6
BW = 100e3


def _chebyshev_db(x: float, order: int, ripple_db: float) -> float:
    t_previous, t_current = 1.0, x
    for _ in range(order - 1):
        t_previous, t_current = t_current, 2.0 * x * t_current - t_previous
    return -10 * math.log10(1 + (10 ** (ripple_db / 10) - 1) * t_current**2)


def _chebyshev_3db_deviation(order: int, ripple_db: float) -> float:
    epsilon = math.sqrt(10 ** (ripple_db / 10) - 1)
    return math.cosh(math.acosh(1 / epsilon) / order)


def _frequency_at_deviation(delta: float) -> float:
    """Positive root of f^2 - delta*BW*f - F0^2 = 0."""
    half = delta * BW / 2
    return half + math.sqrt(half * half + F0 * F0)


# Order-5 prototypes at twice the cutoff (ratio 2). The Bessel value is the
# delay-normalized reverse Bessel polynomial evaluated at 2 * 2.4274 rad/s.
LP_ORDER5_RATIO2_DB = {
    "butterworth": -10 * math.log10(1 + 2**10),
    "chebyshev": _chebyshev_db(2.0, 5, 0.5),
    "bessel": -14.0626,
}
# Order-3 bandpass at a normalized deviation of 2 (reverse Bessel polynomial
# 15 + 15s + 6s^2 + s^3 at 2 * 1.7557 rad/s for the Bessel entry).
BP_ORDER3_DEVIATION2_DB = {
    "butterworth": -10 * math.log10(1 + 2**6),
    "chebyshev": _chebyshev_db(2.0 * _chebyshev_3db_deviation(3, 0.5), 3, 0.5),
    "bessel": -12.0006,
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

    @pytest.mark.parametrize(("spelling", "family"), SPELLINGS)
    def test_bandpass_factory_routes_every_spelling(self, spelling, family):
        response_db = make_bp_response_db(F0, BW, 3, spelling, 0.5)

        assert response_db(_frequency_at_deviation(2.0)) == pytest.approx(
            BP_ORDER3_DEVIATION2_DB[family], abs=1e-3
        )

    @pytest.mark.parametrize(
        "factory",
        [make_lp_response_db, make_hp_response_db],
        ids=["lowpass", "highpass"],
    )
    @pytest.mark.parametrize("ripple_db", [0.1, 1.0, 3.0])
    def test_lp_hp_factories_forward_chebyshev_ripple(self, factory, ripple_db):
        assert factory("chebyshev", FC, 5, ripple_db)(FC) == pytest.approx(-ripple_db, abs=1e-9)

    @pytest.mark.parametrize("ripple_db", [0.1, 1.0])
    def test_bandpass_factory_forwards_chebyshev_ripple(self, ripple_db):
        expected = _chebyshev_db(2.0 * _chebyshev_3db_deviation(3, ripple_db), 3, ripple_db)

        response_db = make_bp_response_db(F0, BW, 3, "chebyshev", ripple_db)

        assert response_db(_frequency_at_deviation(2.0)) == pytest.approx(expected, abs=1e-9)

    def test_ripple_defaults_to_half_db(self):
        assert make_lp_response_db("ch", FC, 5)(FC) == pytest.approx(-0.5, abs=1e-9)
        assert make_hp_response_db("ch", FC, 5)(FC) == pytest.approx(-0.5, abs=1e-9)
        assert make_bp_response_db(F0, BW, 3, "ch")(_frequency_at_deviation(2.0)) == pytest.approx(
            BP_ORDER3_DEVIATION2_DB["chebyshev"], abs=1e-9
        )

    def test_factories_report_db_with_the_minus_120_db_floor(self):
        assert make_lp_response_db("bw", FC, 9)(1000 * FC) == -120.0
        assert make_hp_response_db("bw", FC, 9)(0.0) == -120.0
        assert make_bp_response_db(F0, BW, 9, "bw")(100 * F0) == -120.0


_FACTORIES = [
    lambda filter_type: make_lp_response_db(filter_type, FC, 5),
    lambda filter_type: make_hp_response_db(filter_type, FC, 5),
    lambda filter_type: make_bp_response_db(F0, BW, 3, filter_type),
]


class TestFilterTypeValidation:
    @pytest.mark.parametrize("factory", _FACTORIES, ids=["lowpass", "highpass", "bandpass"])
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
