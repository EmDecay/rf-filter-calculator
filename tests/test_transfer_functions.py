"""Idealized lowpass/highpass transfer functions and the shared response helpers.

Magnitudes are pinned to references computed independently of the implementation:
the Butterworth closed form, the Chebyshev Type I equal-ripple form built from the
three-term Tn recurrence (cutoff = ripple-band edge), the reverse Bessel polynomial
evaluated with complex arithmetic at the published delay-normalized -3 dB
frequencies, and the lowpass-to-highpass substitution f -> fc^2 / f.
"""

import math

import pytest

from filter_lib.highpass import transfer as hp_transfer
from filter_lib.lowpass import transfer as lp_transfer
from filter_lib.shared.transfer_functions import (
    chebyshev_polynomial,
    generate_frequency_points,
    magnitude_to_db,
)

FC = 10e6
HALF_POWER_DB = 10 * math.log10(0.5)  # -3.0103 dB

# -3 dB frequencies of the delay-normalized Bessel lowpass (Zverev, Handbook of
# Filter Synthesis). The response functions place the user's cutoff at these.
PUBLISHED_BESSEL_3DB_W = {
    2: 1.3617,
    3: 1.7557,
    4: 2.1139,
    5: 2.4274,
    6: 2.7034,
    7: 2.9517,
    8: 3.1796,
    9: 3.3917,
}


def _butterworth_reference(ratio: float, order: int) -> float:
    return 1.0 / math.sqrt(1.0 + ratio ** (2 * order))


def _chebyshev_reference(ratio: float, order: int, ripple_db: float) -> float:
    t_previous, t_current = 1.0, ratio
    for _ in range(order - 1):
        t_previous, t_current = t_current, 2.0 * ratio * t_current - t_previous
    epsilon_squared = 10 ** (ripple_db / 10) - 1
    return 1.0 / math.sqrt(1.0 + epsilon_squared * t_current**2)


def _bessel_reference(ratio: float, order: int) -> float:
    coefficients = [
        math.factorial(2 * order - k)
        // (2 ** (order - k) * math.factorial(k) * math.factorial(order - k))
        for k in range(order + 1)
    ]
    w = ratio * PUBLISHED_BESSEL_3DB_W[order]
    theta = sum(c * (1j * w) ** k for k, c in enumerate(coefficients))
    return coefficients[0] / abs(theta)


_LP_RESPONSES = {
    "butterworth": lambda f, order: lp_transfer.butterworth_response(f, FC, order),
    "chebyshev": lambda f, order: lp_transfer.chebyshev_response(f, FC, order, 0.5),
    "bessel": lambda f, order: lp_transfer.bessel_response(f, FC, order),
}
_HP_RESPONSES = {
    "butterworth": lambda f, order: hp_transfer.butterworth_response(f, FC, order),
    "chebyshev": lambda f, order: hp_transfer.chebyshev_response(f, FC, order, 0.5),
    "bessel": lambda f, order: hp_transfer.bessel_response(f, FC, order),
}
_REFERENCES = {
    "butterworth": lambda ratio, order: _butterworth_reference(ratio, order),
    "chebyshev": lambda ratio, order: _chebyshev_reference(ratio, order, 0.5),
    "bessel": lambda ratio, order: _bessel_reference(ratio, order),
}


class TestFrequencyGrid:
    def test_fixed_count_grid_spans_two_decades_log_uniformly(self):
        points = generate_frequency_points(FC, num_points=5)

        assert points == pytest.approx([1e6, 1e6 * 10**0.5, 1e7, 1e7 * 10**0.5, 1e8], rel=1e-12)

    def test_default_grid_is_two_decades_at_25_points_per_decade(self):
        points = generate_frequency_points(FC)

        assert len(points) == 51
        assert points[0] == pytest.approx(1e6, rel=1e-12)
        assert points[25] == pytest.approx(FC, rel=1e-12)
        assert points[-1] == pytest.approx(1e8, rel=1e-12)

    def test_two_points_is_the_smallest_grid(self):
        assert generate_frequency_points(FC, num_points=2) == pytest.approx([1e6, 1e8], rel=1e-12)

    def test_flexible_grid_is_centered_on_the_cutoff(self):
        points = generate_frequency_points(1e6, decades=1.0, points_per_decade=10)

        steps = [math.log10(b / a) for a, b in zip(points, points[1:])]
        assert len(points) == 11
        assert points[0] == pytest.approx(1e6 / math.sqrt(10), rel=1e-12)
        assert points[5] == pytest.approx(1e6, rel=1e-12)
        assert points[-1] == pytest.approx(1e6 * math.sqrt(10), rel=1e-12)
        assert steps == pytest.approx([0.1] * 10, rel=1e-9)

    @pytest.mark.parametrize("f0", [-1.0, 0.0, True, "10MHz", None, float("nan"), float("inf")])
    def test_rejects_center_that_is_not_positive_and_finite(self, f0):
        with pytest.raises(ValueError, match="Cutoff frequency must be positive and finite"):
            generate_frequency_points(f0, num_points=2)

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"num_points": 1}, "num_points must be an integer >= 2"),
            ({"num_points": 2.5}, "num_points must be an integer >= 2"),
            ({"num_points": True}, "num_points must be an integer >= 2"),
            ({"decades": 0}, "decades must be positive and finite"),
            ({"decades": True}, "decades must be positive and finite"),
            ({"decades": "2"}, "decades must be positive and finite"),
            ({"decades": float("inf")}, "decades must be positive and finite"),
            ({"points_per_decade": 0}, "points_per_decade must be a positive integer"),
            ({"points_per_decade": 2.5}, "points_per_decade must be a positive integer"),
            ({"decades": 0.01, "points_per_decade": 25}, "at least one interval"),
        ],
    )
    def test_rejects_invalid_grid_controls(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            generate_frequency_points(FC, **kwargs)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"decades": 1e308},
            {"decades": 1e6, "points_per_decade": 2},
            {"decades": 1.0, "points_per_decade": 10**400},
        ],
    )
    def test_rejects_impractical_grid_allocation(self, kwargs):
        with pytest.raises(ValueError, match="too large|must not exceed"):
            generate_frequency_points(1.0, **kwargs)

    @pytest.mark.parametrize(
        ("f0", "kwargs"),
        [(1e308, {"num_points": 3}), (1e308, {}), (5e-324, {})],
        ids=["fixed-count-overflow", "flexible-overflow", "flexible-underflow"],
    )
    def test_rejects_span_that_leaves_the_positive_finite_range(self, f0, kwargs):
        with pytest.raises(ValueError, match="must remain positive and finite"):
            generate_frequency_points(f0, **kwargs)


class TestChebyshevPolynomial:
    def test_low_orders_match_textbook_polynomials(self):
        assert chebyshev_polynomial(0, 0.37) == 1.0
        assert chebyshev_polynomial(1, 0.5) == pytest.approx(0.5)
        assert chebyshev_polynomial(2, 0.5) == pytest.approx(2 * 0.25 - 1)
        assert chebyshev_polynomial(3, 2.0) == pytest.approx(4 * 8 - 3 * 2)

    def test_matches_recurrence_form(self):
        """cos/cosh magnitude form equals the classic Tn recurrence on x >= 0."""

        def recurrence_tn(n: int, x: float) -> float:
            if n == 0:
                return 1.0
            if n == 1:
                return x
            t_prev2, t_prev1 = 1.0, x
            for _ in range(2, n + 1):
                t_prev2, t_prev1 = t_prev1, 2 * x * t_prev1 - t_prev2
            return t_prev1

        for n in range(2, 10):
            for i in range(0, 31):
                x = i / 10  # 0.0 .. 3.0
                assert chebyshev_polynomial(n, x) == pytest.approx(
                    recurrence_tn(n, x), rel=1e-9, abs=1e-9
                ), f"mismatch at n={n}, x={x}"
            # exact signed agreement inside [-1, 0]
            for i in range(0, 11):
                x = -i / 10
                assert chebyshev_polynomial(n, x) == pytest.approx(
                    recurrence_tn(n, x), rel=1e-9, abs=1e-9
                ), f"mismatch at n={n}, x={x}"
            # below -1 the magnitude form drops the sign; squares must agree
            # (response functions only ever use Cn squared)
            for i in range(11, 31):
                x = -i / 10
                assert chebyshev_polynomial(n, x) ** 2 == pytest.approx(
                    recurrence_tn(n, x) ** 2, rel=1e-9
                ), f"square mismatch at n={n}, x={x}"

    @pytest.mark.parametrize(
        ("n", "x", "message"),
        [
            (True, 0.5, "n must be a non-negative integer"),
            (2.5, 0.5, "n must be a non-negative integer"),
            (-1, 0.5, "n must be a non-negative integer"),
            (2, True, "x must be a real number"),
            (2, "0.5", "x must be a real number"),
            (2, float("nan"), "x must be a real number"),
        ],
    )
    def test_rejects_invalid_arguments(self, n, x, message):
        with pytest.raises(ValueError, match=message):
            chebyshev_polynomial(n, x)


class TestMagnitudeToDb:
    @pytest.mark.parametrize(
        ("magnitude", "expected_db"),
        [
            (1.0, 0.0),
            (1 / math.sqrt(2), HALF_POWER_DB),
            (0.5, 20 * math.log10(0.5)),
            (1e-5, -100.0),
            (1e-7, -120.0),
            (0.0, -120.0),
        ],
        ids=["unity", "half-power", "half-amplitude", "minus-100", "below-floor", "zero"],
    )
    def test_converts_amplitude_ratio_with_minus_120_db_floor(self, magnitude, expected_db):
        assert magnitude_to_db(magnitude) == pytest.approx(expected_db, abs=1e-12)

    @pytest.mark.parametrize(
        "magnitude", [float("nan"), float("inf"), float("-inf"), True, "1", None]
    )
    def test_rejects_values_that_are_not_finite_reals(self, magnitude):
        with pytest.raises(ValueError, match="Magnitude must be finite"):
            magnitude_to_db(magnitude)


class TestLowpassHighpassMagnitudes:
    @pytest.mark.parametrize("order", [1, 3, 5, 9])
    @pytest.mark.parametrize("ratio", [0.0, 0.5, 1.0, 2.0, 10.0])
    def test_butterworth_matches_closed_form(self, order, ratio):
        magnitude = lp_transfer.butterworth_response(ratio * FC, FC, order)

        assert magnitude == pytest.approx(_butterworth_reference(ratio, order), rel=1e-12, abs=0)

    @pytest.mark.parametrize(("order", "ripple_db"), [(3, 0.5), (5, 0.1), (4, 1.0), (9, 3.0)])
    @pytest.mark.parametrize("ratio", [0.0, 0.3, 0.8, 1.0, 1.5, 3.0])
    def test_chebyshev_matches_equal_ripple_form(self, order, ripple_db, ratio):
        magnitude = lp_transfer.chebyshev_response(ratio * FC, FC, order, ripple_db)

        expected = _chebyshev_reference(ratio, order, ripple_db)
        assert magnitude == pytest.approx(expected, rel=1e-9, abs=0)

    @pytest.mark.parametrize("module", [lp_transfer, hp_transfer], ids=["lowpass", "highpass"])
    @pytest.mark.parametrize("ripple_db", [0.01, 0.5, 1.0, 3.0])
    def test_chebyshev_cutoff_is_the_ripple_edge_not_minus_3db(self, module, ripple_db):
        magnitude = module.chebyshev_response(FC, FC, 5, ripple_db)

        assert magnitude_to_db(magnitude) == pytest.approx(-ripple_db, abs=1e-9)

    @pytest.mark.parametrize(("order", "ripple_db"), [(3, 0.5), (5, 0.1), (9, 1.0)])
    def test_chebyshev_minus_3db_point_lies_beyond_the_ripple_edge(self, order, ripple_db):
        epsilon = math.sqrt(10 ** (ripple_db / 10) - 1)
        ratio_3db = math.cosh(math.acosh(1 / epsilon) / order)

        lowpass = lp_transfer.chebyshev_response(ratio_3db * FC, FC, order, ripple_db)
        highpass = hp_transfer.chebyshev_response(FC / ratio_3db, FC, order, ripple_db)

        assert ratio_3db > 1.0
        assert magnitude_to_db(lowpass) == pytest.approx(HALF_POWER_DB, abs=1e-9)
        assert magnitude_to_db(highpass) == pytest.approx(HALF_POWER_DB, abs=1e-9)

    @pytest.mark.parametrize(("order", "ripple_db"), [(3, 0.5), (5, 1.0)])
    def test_chebyshev_passband_stays_inside_the_ripple_band(self, order, ripple_db):
        passband_db = [
            magnitude_to_db(lp_transfer.chebyshev_response(i / 400 * FC, FC, order, ripple_db))
            for i in range(401)
        ]

        assert max(passband_db) == pytest.approx(0.0, abs=1e-4)
        assert min(passband_db) == pytest.approx(-ripple_db, abs=1e-4)
        assert all(-ripple_db - 1e-9 <= db <= 1e-12 for db in passband_db)

    @pytest.mark.parametrize("order", range(2, 10))
    def test_bessel_cutoff_is_minus_3db_for_every_supported_order(self, order):
        magnitude = lp_transfer.bessel_response(FC, FC, order)

        assert magnitude_to_db(magnitude) == pytest.approx(HALF_POWER_DB, abs=1e-3)

    @pytest.mark.parametrize("order", [2, 3, 5, 9])
    @pytest.mark.parametrize("ratio", [0.25, 0.5, 2.0, 4.0])
    def test_bessel_matches_reverse_bessel_polynomial(self, order, ratio):
        magnitude = lp_transfer.bessel_response(ratio * FC, FC, order)

        assert magnitude == pytest.approx(_bessel_reference(ratio, order), rel=1e-9, abs=0)

    @pytest.mark.parametrize("module", [lp_transfer, hp_transfer], ids=["lowpass", "highpass"])
    @pytest.mark.parametrize("order", [1, 10])
    def test_bessel_rejects_orders_outside_the_coefficient_table(self, module, order):
        with pytest.raises(ValueError, match="Order must be between 2 and 9"):
            module.bessel_response(FC, FC, order)

    @pytest.mark.parametrize("family", ["butterworth", "chebyshev", "bessel"])
    @pytest.mark.parametrize("ratio", [0.1, 0.7, 1.3, 10.0])
    def test_highpass_is_lowpass_at_inverted_frequency(self, family, ratio):
        highpass = _HP_RESPONSES[family](ratio * FC, 5)
        lowpass = _LP_RESPONSES[family](FC / ratio, 5)

        assert highpass == pytest.approx(lowpass, rel=1e-12, abs=0)

    @pytest.mark.parametrize("family", ["butterworth", "chebyshev", "bessel"])
    def test_lowpass_passes_and_highpass_blocks_dc(self, family):
        assert _LP_RESPONSES[family](0.0, 3) == pytest.approx(1.0, abs=1e-15)
        assert _HP_RESPONSES[family](0.0, 3) == 0.0

    @pytest.mark.parametrize(
        ("response", "args"),
        [
            (lp_transfer.butterworth_response, (1e30, 1.0, 9)),
            (hp_transfer.butterworth_response, (1e-30, 1.0, 9)),
            (lp_transfer.butterworth_response, (1e300, 1.0, 2)),
            (hp_transfer.butterworth_response, (1e-300, 1.0, 2)),
            (lp_transfer.bessel_response, (1e306, 1.0, 9)),
            (hp_transfer.bessel_response, (1e-306, 1.0, 9)),
        ],
        ids=[
            "lp-butterworth-power-beyond-sqrt-max",
            "hp-butterworth-power-beyond-sqrt-max",
            "lp-butterworth-power-overflow",
            "hp-butterworth-power-overflow",
            "lp-bessel-term-overflow",
            "hp-bessel-term-overflow",
        ],
    )
    def test_deep_stopband_saturates_to_exactly_zero(self, response, args):
        assert response(*args) == 0.0


class TestFrequencyResponseWrappers:
    @pytest.mark.parametrize("module", [lp_transfer, hp_transfer], ids=["lowpass", "highpass"])
    @pytest.mark.parametrize(
        ("spelling", "family"),
        [
            ("butterworth", "butterworth"),
            ("BW", "butterworth"),
            ("bw", "butterworth"),
            ("Chebyshev", "chebyshev"),
            ("ch", "chebyshev"),
            ("bessel", "bessel"),
            ("bs", "bessel"),
        ],
    )
    def test_returns_reference_db_for_every_accepted_spelling(self, module, spelling, family):
        ratios = [0.5, 1.0, 2.0]
        response_db = module.frequency_response(spelling, [r * FC for r in ratios], FC, 5, 0.5)

        prototype_ratios = ratios if module is lp_transfer else [1 / r for r in ratios]
        expected = [20 * math.log10(_REFERENCES[family](r, 5)) for r in prototype_ratios]
        assert response_db == pytest.approx(expected, abs=1e-9)

    def test_deep_stopband_is_floored_at_minus_120_db(self):
        assert lp_transfer.frequency_response("bw", [1000 * FC], FC, 9) == [-120.0]
        assert hp_transfer.frequency_response("bw", [0.0, FC / 1000], FC, 9) == [-120.0, -120.0]

    @pytest.mark.parametrize("module", [lp_transfer, hp_transfer], ids=["lowpass", "highpass"])
    def test_validates_definition_even_for_an_empty_grid(self, module):
        with pytest.raises(ValueError, match="Unknown filter type"):
            module.frequency_response("elliptic", [], FC, 3)
        with pytest.raises(ValueError, match="positive and finite"):
            module.frequency_response("bw", [], 0.0, 3)
        with pytest.raises(ValueError, match="positive integer"):
            module.frequency_response("bw", [], FC, 0)

    @pytest.mark.parametrize("module", [lp_transfer, hp_transfer], ids=["lowpass", "highpass"])
    def test_rejects_non_string_type(self, module):
        with pytest.raises(ValueError, match="must be a string"):
            module.frequency_response(None, [1e6], FC, 3)

    @pytest.mark.parametrize("module", [lp_transfer, hp_transfer], ids=["lowpass", "highpass"])
    @pytest.mark.parametrize("freqs", [None, 1, "1MHz", {"frequency": 1e6}])
    def test_requires_frequency_sequence(self, module, freqs):
        with pytest.raises(ValueError, match="freqs must be a sequence"):
            module.frequency_response("bw", freqs, FC, 3)
