"""Idealized bandpass responses, sweep grids, and the netlist-simulated sweep.

References are independent of the implementation: the lowpass-to-bandpass
deviation (f^2 - f0^2) / (BW * f) and its positive quadratic root, the
Butterworth and Chebyshev closed forms, and the requirement that ``bw`` is the
true -3 dB bandwidth for every family.
"""

import math

import pytest

from filter_lib.bandpass import transfer as bp_transfer
from filter_lib.bandpass.calculations import calculate_bandpass_filter

F0 = 14e6
BW = 1e6
HALF_POWER_DB = 10 * math.log10(0.5)  # -3.0103 dB


def _deviation(f: float, f0: float = F0, bw: float = BW) -> float:
    return (f * f - f0 * f0) / (bw * f)


def _frequency_at_deviation(delta: float, f0: float = F0, bw: float = BW) -> float:
    """Positive root of f^2 - delta*bw*f - f0^2 = 0."""
    half = delta * bw / 2
    return half + math.sqrt(half * half + f0 * f0)


def _chebyshev_db(x: float, order: int, ripple_db: float) -> float:
    t_previous, t_current = 1.0, x
    for _ in range(order - 1):
        t_previous, t_current = t_current, 2.0 * x * t_current - t_previous
    return -10 * math.log10(1 + (10 ** (ripple_db / 10) - 1) * t_current**2)


def _chebyshev_3db_deviation(order: int, ripple_db: float) -> float:
    epsilon = math.sqrt(10 ** (ripple_db / 10) - 1)
    return math.cosh(math.acosh(1 / epsilon) / order)


def _result(**overrides) -> dict:
    result = {
        "f0": F0,
        "bw": BW,
        "n_resonators": 3,
        "filter_type": "butterworth",
        "ripple_db": None,
    }
    result.update(overrides)
    return result


class TestBandpassFrequencyTransform:
    @pytest.mark.parametrize("ratio", [0.5, 0.97, 1.0, 1.03, 2.0])
    def test_deviation_matches_quadratic_transform(self, ratio):
        f = ratio * F0

        assert bp_transfer._bandpass_deviation(f, F0, BW) == pytest.approx(
            _deviation(f), rel=1e-12, abs=1e-15
        )

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            ((-1.0, F0, BW), "Frequency must be positive and finite"),
            ((float("nan"), F0, BW), "Frequency must be positive and finite"),
            ((F0, float("inf"), BW), "Center frequency must be positive and finite"),
            ((F0, F0, -1.0), "Bandwidth must be positive and finite"),
            ((F0, F0, float("nan")), "Bandwidth must be positive and finite"),
        ],
    )
    def test_deviation_rejects_invalid_inputs(self, args, message):
        with pytest.raises(ValueError, match=message):
            bp_transfer._bandpass_deviation(*args)

    def test_deviation_is_exact_at_huge_equal_frequencies(self):
        assert bp_transfer._bandpass_deviation(1e308, 1e308, 1e307) == 0.0

    def test_deviation_overflow_is_signed_infinity_not_nan(self):
        assert bp_transfer._bandpass_deviation(1e308, 1e-308, 1e-308) == math.inf
        assert bp_transfer._bandpass_deviation(1e-308, 1e308, 1e-308) == -math.inf

    @pytest.mark.parametrize(("f0", "bw"), [(F0, BW), (1e6, 2e6)], ids=["narrow", "wide"])
    @pytest.mark.parametrize("delta", [-5.0, -1.0, -0.1, 0.0, 0.1, 1.0, 5.0])
    def test_frequency_from_deviation_inverts_the_transform(self, f0, bw, delta):
        frequency = bp_transfer.frequency_from_deviation(delta, f0, bw)

        assert frequency == pytest.approx(_frequency_at_deviation(delta, f0, bw), rel=1e-12)
        assert _deviation(frequency, f0, bw) == pytest.approx(delta, abs=1e-9)

    def test_frequency_from_deviation_uses_asymptotes_beyond_float_range(self):
        # f ~= delta*bw far above the band and f ~= f0^2 / (|delta|*bw) far below it.
        assert bp_transfer.frequency_from_deviation(1e300, 1e-300, 1e5) == pytest.approx(
            1e305, rel=1e-12
        )
        assert bp_transfer.frequency_from_deviation(-1e308, 1e300, 1e308) == pytest.approx(
            1e-16, rel=1e-12, abs=0
        )

    @pytest.mark.parametrize(
        ("args", "message"),
        [
            ((float("nan"), F0, BW), "delta must be finite"),
            ((1.0, 0.0, BW), "f0 must be positive and finite"),
            ((1.0, F0, float("inf")), "bw must be positive and finite"),
            ((1e308, 1.0, 1e308), "must produce a positive finite frequency"),
        ],
    )
    def test_frequency_from_deviation_rejects_invalid_inputs(self, args, message):
        with pytest.raises(ValueError, match=message):
            bp_transfer.frequency_from_deviation(*args)


class TestIdealBandpassMagnitudes:
    @pytest.mark.parametrize("order", [1, 3, 5])
    @pytest.mark.parametrize("delta", [-2.0, -0.5, 0.0, 0.5, 1.0, 2.0])
    def test_butterworth_matches_closed_form(self, order, delta):
        magnitude = bp_transfer.magnitude_butterworth(_frequency_at_deviation(delta), F0, BW, order)

        assert magnitude == pytest.approx(1 / math.sqrt(1 + delta ** (2 * order)), rel=1e-9, abs=0)

    @pytest.mark.parametrize(
        ("filter_type", "order"),
        [
            ("butterworth", 3),
            ("butterworth", 5),
            ("chebyshev", 3),
            ("chebyshev", 5),
            ("bessel", 3),
            ("bessel", 5),
        ],
    )
    def test_unity_at_center_and_minus_3db_at_the_true_band_edges(self, filter_type, order):
        """``bw`` is the -3 dB bandwidth between the geometric edges, not f0 +/- bw/2."""
        low, high = _frequency_at_deviation(-1.0), _frequency_at_deviation(1.0)

        center_db = bp_transfer.magnitude_db(F0, F0, BW, order, filter_type, 0.5)
        low_db = bp_transfer.magnitude_db(low, F0, BW, order, filter_type, 0.5)
        high_db = bp_transfer.magnitude_db(high, F0, BW, order, filter_type, 0.5)

        tolerance = 1e-3 if filter_type == "bessel" else 1e-9
        assert center_db == pytest.approx(0.0, abs=1e-12)
        assert low_db == pytest.approx(HALF_POWER_DB, abs=tolerance)
        assert high_db == pytest.approx(HALF_POWER_DB, abs=tolerance)
        assert high - low == pytest.approx(BW, rel=1e-12)

    @pytest.mark.parametrize(("order", "ripple_db"), [(3, 0.5), (5, 0.1), (9, 3.0), (3, 1.0)])
    def test_chebyshev_3db_deviation_matches_closed_form(self, order, ripple_db):
        assert bp_transfer.chebyshev_3db_deviation(order, ripple_db) == pytest.approx(
            _chebyshev_3db_deviation(order, ripple_db), rel=1e-12
        )

    @pytest.mark.parametrize(("order", "ripple_db"), [(3, 0.5), (5, 1.0)])
    def test_chebyshev_ripple_edge_lies_inside_the_3db_band(self, order, ripple_db):
        ripple_edge = 1 / _chebyshev_3db_deviation(order, ripple_db)

        magnitude = bp_transfer.magnitude_chebyshev(
            _frequency_at_deviation(ripple_edge), F0, BW, order, ripple_db
        )

        assert ripple_edge < 1.0
        assert 20 * math.log10(magnitude) == pytest.approx(-ripple_db, abs=1e-9)

    @pytest.mark.parametrize("ripple_db", [0.5, 1.0])
    def test_chebyshev_stopband_matches_equal_ripple_form(self, ripple_db):
        delta = 2.0
        expected = _chebyshev_db(delta * _chebyshev_3db_deviation(3, ripple_db), 3, ripple_db)

        assert bp_transfer.magnitude_db(
            _frequency_at_deviation(delta), F0, BW, 3, "chebyshev", ripple_db
        ) == pytest.approx(expected, abs=1e-9)

    def test_bessel_uses_the_lowpass_prototype_at_the_same_deviation(self):
        # Order-3 delay-normalized Bessel lowpass is -12.0006 dB at twice its
        # -3 dB frequency (reverse Bessel polynomial 15 + 15s + 6s^2 + s^3).
        magnitude_db = bp_transfer.magnitude_db(_frequency_at_deviation(2.0), F0, BW, 3, "bessel")

        assert magnitude_db == pytest.approx(-12.0006, abs=1e-3)

    @pytest.mark.parametrize("order", [1, 10])
    def test_bessel_rejects_orders_outside_the_coefficient_table(self, order):
        with pytest.raises(ValueError, match="Order must be between 2 and 9"):
            bp_transfer.magnitude_bessel(F0, F0, BW, order)

    def test_magnitude_db_rejects_unknown_filter_type(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            bp_transfer.magnitude_db(F0, F0, BW, 3, "elliptic")

    def test_deep_stopband_is_floored_at_minus_120_db(self):
        assert bp_transfer.magnitude_db(100e6, F0, BW, 5, "butterworth") == -120.0

    @pytest.mark.parametrize("order", [True, 0, -1, 2.5])
    @pytest.mark.parametrize(
        ("function_name", "extra_args"),
        [
            ("magnitude_butterworth", ()),
            ("magnitude_chebyshev", (0.5,)),
            ("magnitude_bessel", ()),
        ],
    )
    def test_magnitude_functions_reject_invalid_order(self, function_name, extra_args, order):
        function = getattr(bp_transfer, function_name)
        with pytest.raises(ValueError, match="order must be a positive integer"):
            function(F0, F0, BW, order, *extra_args)

    @pytest.mark.parametrize("order", [True, 0, -1, 2.5, "3"])
    def test_chebyshev_3db_deviation_rejects_invalid_order(self, order):
        with pytest.raises(ValueError, match="order must be a positive integer"):
            bp_transfer.chebyshev_3db_deviation(order, 0.5)

    @pytest.mark.parametrize(
        "ripple_db", [True, 0.0, -0.5, float("nan"), float("inf"), float("-inf")]
    )
    def test_chebyshev_3db_deviation_rejects_invalid_ripple(self, ripple_db):
        with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
            bp_transfer.chebyshev_3db_deviation(3, ripple_db)

    @pytest.mark.parametrize("ripple_db", [True, 0.0, float("nan"), float("inf")])
    def test_chebyshev_magnitude_and_sweep_reject_invalid_ripple(self, ripple_db):
        with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
            bp_transfer.magnitude_chebyshev(F0, F0, BW, 3, ripple_db)
        with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
            bp_transfer.magnitude_db(F0, F0, BW, 3, "chebyshev", ripple_db)
        with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
            bp_transfer.frequency_sweep(F0, BW, 3, "chebyshev", ripple_db, points=3)

    @pytest.mark.parametrize("filter_type", ["butterworth", "chebyshev", "bessel"])
    def test_extreme_deviation_returns_zero_magnitude_and_floored_db(self, filter_type):
        args = (1e308, 1e-308, 1e-308, 9)
        if filter_type == "butterworth":
            magnitude = bp_transfer.magnitude_butterworth(*args)
        elif filter_type == "chebyshev":
            magnitude = bp_transfer.magnitude_chebyshev(*args, 0.5)
        else:
            magnitude = bp_transfer.magnitude_bessel(*args)
        assert magnitude == 0.0
        assert bp_transfer.magnitude_db(*args, filter_type, 0.5) == -120.0

    @pytest.mark.parametrize("filter_type", ["butterworth", "chebyshev"])
    def test_arbitrary_size_order_does_not_overflow(self, filter_type):
        assert bp_transfer.magnitude_db(2.0, 1.0, 1.0, 10**400, filter_type, 0.5) == -120.0

    def test_arbitrary_size_chebyshev_order_stays_inside_the_ripple_band(self):
        magnitude_db = bp_transfer.magnitude_db(F0 * 1.001, F0, BW, 10**400, "chebyshev", 0.5)

        assert -0.5 - 1e-9 <= magnitude_db <= 0.0


class TestIdealBandpassSweeps:
    def test_default_sweep_samples_center_and_true_edges_exactly(self):
        sweep = bp_transfer.frequency_sweep(F0, BW, 3, "butterworth")
        freqs = [f for f, _ in sweep]
        by_frequency = dict(sweep)
        low, high = _frequency_at_deviation(-1.0), _frequency_at_deviation(1.0)
        decades = math.log10(1 + 10 * BW / F0)  # adaptive span: +/- log10(1 + 10*FBW)

        assert len(sweep) == 61
        assert all(b > a for a, b in zip(freqs, freqs[1:]))
        assert freqs[0] == pytest.approx(F0 * 10**-decades, rel=1e-12)
        assert freqs[-1] == pytest.approx(F0 * 10**decades, rel=1e-12)
        assert by_frequency[F0] == 0.0
        low_sample = min(freqs, key=lambda f: abs(f - low))
        high_sample = min(freqs, key=lambda f: abs(f - high))
        assert low_sample == pytest.approx(low, rel=1e-12)
        assert high_sample == pytest.approx(high, rel=1e-12)
        assert by_frequency[low_sample] == pytest.approx(HALF_POWER_DB, abs=1e-9)
        assert by_frequency[high_sample] == pytest.approx(HALF_POWER_DB, abs=1e-9)

    def test_explicit_decades_and_points_set_the_span(self):
        sweep = bp_transfer.frequency_sweep(F0, BW, 3, "butterworth", decades=0.5, points=31)

        assert len(sweep) == 31
        assert sweep[0][0] == pytest.approx(F0 / math.sqrt(10), rel=1e-12)
        assert sweep[-1][0] == pytest.approx(F0 * math.sqrt(10), rel=1e-12)

    def test_two_points_is_the_smallest_sweep(self):
        sweep = bp_transfer.frequency_sweep(F0, BW, 3, "butterworth", decades=1.0, points=2)

        assert [f for f, _ in sweep] == pytest.approx([F0 / 10, F0 * 10], rel=1e-12)

    def test_plot_frequency_points_share_the_sweep_grid(self):
        points = bp_transfer.generate_frequency_points(F0, BW)
        sweep = bp_transfer.frequency_sweep(F0, BW, 3, "butterworth", points=101)

        assert len(points) == 101
        assert points == [f for f, _ in sweep]

    @pytest.mark.parametrize(
        ("args", "kwargs", "message"),
        [
            ((F0, BW), {"points": 1}, "points must be an integer >= 2"),
            ((F0, BW), {"points": 2.5}, "points must be an integer >= 2"),
            ((F0, BW), {"decades": 0}, "decades must be positive and finite"),
            ((F0, BW), {"decades": float("nan")}, "decades must be positive and finite"),
            ((float("inf"), BW), {}, "f0 must be positive and finite"),
            ((F0, 0.0), {}, "bw must be positive and finite"),
            ((1e308, 1e307), {}, "must remain positive and finite"),
            ((5e-324, 5e-324), {}, "must remain positive and finite"),
            ((1.0, 1.0), {"decades": 1e-17, "points": 5}, "must be distinct"),
        ],
        ids=[
            "one-point",
            "fractional-points",
            "zero-decades",
            "nan-decades",
            "infinite-center",
            "zero-bandwidth",
            "overflowing-span",
            "underflowing-span",
            "collapsed-grid",
        ],
    )
    def test_sweep_rejects_invalid_grid_controls(self, args, kwargs, message):
        with pytest.raises(ValueError, match=message):
            bp_transfer.frequency_sweep(*args, 3, "butterworth", **kwargs)

    def test_frequency_response_evaluates_the_result_definition(self):
        low, high = _frequency_at_deviation(-1.0), _frequency_at_deviation(1.0)

        response_db = bp_transfer.frequency_response(_result(), [low, F0, high])

        assert response_db == pytest.approx([HALF_POWER_DB, 0.0, HALF_POWER_DB], abs=1e-9)

    def test_frequency_response_defaults_missing_ripple_to_half_db(self):
        result = _result(filter_type="chebyshev")
        del result["ripple_db"]
        delta = 2.0
        expected = _chebyshev_db(delta * _chebyshev_3db_deviation(3, 0.5), 3, 0.5)

        (response_db,) = bp_transfer.frequency_response(result, [_frequency_at_deviation(delta)])

        assert response_db == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize("order", [True, 0, -1, 2.5])
    def test_db_sweep_and_response_reject_invalid_order(self, order):
        with pytest.raises(ValueError, match="order must be a positive integer"):
            bp_transfer.magnitude_db(F0, F0, BW, order, "butterworth")
        with pytest.raises(ValueError, match="order must be a positive integer"):
            bp_transfer.frequency_sweep(F0, BW, order, "butterworth", points=3)
        with pytest.raises(ValueError, match="order must be a positive integer"):
            bp_transfer.frequency_response(_result(n_resonators=order), [])

    @pytest.mark.parametrize("result", [None, 1, [], "result"])
    def test_frequency_response_requires_result_mapping(self, result):
        with pytest.raises(ValueError, match="result must be a mapping"):
            bp_transfer.frequency_response(result, [])

    @pytest.mark.parametrize("freqs", [None, 1, "1MHz", {"frequency": 1e6}])
    def test_frequency_response_requires_frequency_sequence(self, freqs):
        with pytest.raises(ValueError, match="freqs must be a sequence"):
            bp_transfer.frequency_response(_result(), freqs)


@pytest.fixture(scope="module")
def synthesized_results():
    """Top-C Butterworth order-3 designs at 10 MHz, keyed by fractional bandwidth."""
    return {
        fbw: calculate_bandpass_filter(10e6, 10e6 * fbw, 50, 3, "butterworth", "top")
        for fbw in (0.05, 0.10, 0.20)
    }


class TestNetlistSweep:
    """Netlist-true bandpass response (simulated from synthesized values)."""

    def test_peak_is_unity_near_center(self, synthesized_results):
        sweep = bp_transfer.netlist_frequency_sweep(synthesized_results[0.05], points=201)

        assert max(db for _, db in sweep) == pytest.approx(0.0, abs=0.01)

    def test_docstring_describes_ideal_component_simulation_limits(self):
        docstring = bp_transfer.netlist_frequency_sweep.__doc__ or ""
        assert "ideal-component circuit" in docstring
        assert "not a measurement" in docstring
        assert "parasitics" in docstring

    def test_minus_3db_crossings_match_printed_cutoffs(self, synthesized_results):
        """The plotted circuit response crosses -3 dB at the printed f_low/f_high."""
        from filter_lib.shared.plot_threshold_analysis import find_db_thresholds

        result = synthesized_results[0.10]
        sweep = bp_transfer.netlist_frequency_sweep(result, points=201)

        thresholds = find_db_thresholds(
            [f for f, _ in sweep],
            [db for _, db in sweep],
            levels=[HALF_POWER_DB],
            filter_type="bandpass",
            reference_frequency=result["f0"],
            relative_to_peak=True,
        )

        f_low, f_high = thresholds[HALF_POWER_DB]
        assert f_low == pytest.approx(result["f_low"], rel=1e-4)
        assert f_high == pytest.approx(result["f_high"], rel=1e-4)

    def test_netlist_diverges_from_prototype_at_wide_fbw(self, synthesized_results):
        """At 20% FBW the real circuit skews away from the symmetric prototype.

        This is why plots are simulated rather than computed from the
        prototype: reverting would silently show users an idealized shape
        their built filter cannot reproduce.
        """
        result = synthesized_results[0.20]
        netlist = bp_transfer.netlist_frequency_sweep(result, points=201)
        prototype = bp_transfer.frequency_sweep(
            result["f0"], result["bw"], result["n_resonators"], result["filter_type"], points=201
        )

        assert [f for f, _ in netlist] == [f for f, _ in prototype]
        assert max(abs(a - b) for (_, a), (_, b) in zip(netlist, prototype)) > 1.0

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"points": 1}, "points must be an integer >= 2"),
            ({"points": 2.5}, "points must be an integer >= 2"),
            ({"decades": 0}, "decades must be positive and finite"),
        ],
    )
    def test_rejects_invalid_grid_controls(self, synthesized_results, kwargs, message):
        with pytest.raises(ValueError, match=message):
            bp_transfer.netlist_frequency_sweep(synthesized_results[0.05], **kwargs)

    @pytest.mark.parametrize("result", [None, 1, [], "result"])
    def test_requires_result_mapping(self, result):
        with pytest.raises(ValueError, match="result must be a mapping"):
            bp_transfer.netlist_frequency_sweep(result, points=3)
