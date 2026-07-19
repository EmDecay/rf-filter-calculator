"""Tests for transfer function modules (lowpass, highpass, bandpass, shared)."""

import json
import math

import pytest

from filter_lib.bandpass import transfer as bp_transfer
from filter_lib.highpass import transfer as hp_transfer
from filter_lib.lowpass import transfer as lp_transfer
from filter_lib.shared.response_export import (
    export_response_csv,
    export_response_json,
    response_meta,
)
from filter_lib.shared.transfer_functions import (
    chebyshev_polynomial,
    generate_frequency_points,
    magnitude_to_db,
)

# --- Shared transfer_functions ---


class TestSharedTransferFunctions:
    """Tests for shared transfer function utilities."""

    def test_generate_frequency_points_count(self):
        points = generate_frequency_points(10e6, num_points=51)
        assert len(points) == 51

    def test_generate_frequency_points_range(self):
        points = generate_frequency_points(10e6)
        assert points[0] == pytest.approx(1e6, rel=0.01)
        assert points[-1] == pytest.approx(100e6, rel=0.01)

    def test_generate_frequency_points_invalid(self):
        with pytest.raises(ValueError, match="positive"):
            generate_frequency_points(-1)

    @pytest.mark.parametrize("f0", [True, "10MHz", None])
    def test_generate_frequency_points_rejects_non_real_center(self, f0):
        with pytest.raises(ValueError, match="positive and finite"):
            generate_frequency_points(f0, num_points=2)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"num_points": 1},
            {"num_points": 2.5},
            {"decades": 0},
            {"decades": True},
            {"decades": "2"},
            {"decades": float("inf")},
            {"points_per_decade": 0},
            {"points_per_decade": 2.5},
            {"decades": 0.01, "points_per_decade": 25},
        ],
    )
    def test_generate_frequency_points_rejects_invalid_grid_controls(self, kwargs):
        with pytest.raises(ValueError):
            generate_frequency_points(10e6, **kwargs)

    def test_generate_frequency_points_rejects_overflowing_span(self):
        with pytest.raises(ValueError, match="finite"):
            generate_frequency_points(1e308, num_points=3)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"decades": 1e308},
            {"decades": 1e6, "points_per_decade": 2},
            {"decades": 1.0, "points_per_decade": 10**400},
        ],
    )
    def test_generate_frequency_points_rejects_impractical_grid_allocation(self, kwargs):
        with pytest.raises(ValueError, match="too large|must not exceed"):
            generate_frequency_points(1.0, **kwargs)

    def test_chebyshev_polynomial_base_cases(self):
        assert chebyshev_polynomial(0, 0.5) == pytest.approx(1.0)
        assert chebyshev_polynomial(1, 0.5) == pytest.approx(0.5)

    def test_chebyshev_polynomial_recurrence(self):
        # T2(x) = 2x^2 - 1
        assert chebyshev_polynomial(2, 0.5) == pytest.approx(2 * 0.25 - 1)

    def test_chebyshev_polynomial_matches_recurrence_form(self):
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

    def test_magnitude_to_db_unity(self):
        assert magnitude_to_db(1.0) == pytest.approx(0.0)

    def test_magnitude_to_db_zero(self):
        assert magnitude_to_db(0.0) == -120.0

    def test_magnitude_to_db_half(self):
        assert magnitude_to_db(0.5) == pytest.approx(20 * math.log10(0.5))

    @pytest.mark.parametrize("magnitude", [float("nan"), float("inf"), float("-inf")])
    def test_magnitude_to_db_rejects_non_finite_input(self, magnitude):
        with pytest.raises(ValueError, match="finite"):
            magnitude_to_db(magnitude)

    @pytest.mark.parametrize("magnitude", [True, "1", None])
    def test_magnitude_to_db_rejects_non_real_input(self, magnitude):
        with pytest.raises(ValueError, match="finite"):
            magnitude_to_db(magnitude)

    def test_export_response_json_unified_schema_lowpass(self):
        """Golden test: LP/HP exports carry the unified filter block + data."""
        result = {
            "filter_type": "butterworth",
            "freq_hz": 10e6,
            "order": 3,
            "ripple": None,
            "topology": "pi",
        }
        s = export_response_json([1e6, 10e6], [-0.1, -3.0], response_meta("lowpass", result))
        data = json.loads(s)
        assert data["filter"] == {
            "category": "lowpass",
            "response_type": "butterworth",
            "order": 3,
            "cutoff_hz": 10e6,
            "topology": "pi",
        }
        assert data["data"] == [
            {"frequency_hz": 1e6, "magnitude_db": -0.1},
            {"frequency_hz": 10e6, "magnitude_db": -3.0},
        ]

    def test_export_response_json_includes_ripple_for_chebyshev(self):
        result = {
            "filter_type": "chebyshev",
            "freq_hz": 10e6,
            "order": 5,
            "ripple": 0.5,
            "topology": "t",
        }
        s = export_response_json([1e6], [-0.5], response_meta("highpass", result))
        data = json.loads(s)
        assert data["filter"]["category"] == "highpass"
        assert data["filter"]["ripple_db"] == 0.5

    @pytest.mark.parametrize("category", ["not-a-category", "", None, [], {}])
    def test_response_meta_rejects_unknown_category(self, category):
        with pytest.raises(ValueError, match="category"):
            response_meta(category, {})

    @pytest.mark.parametrize("result", [None, [], "result"])
    def test_response_meta_requires_mapping_result(self, result):
        with pytest.raises(ValueError, match="result must be a mapping"):
            response_meta("lowpass", result)

    @pytest.mark.parametrize(
        ("category", "result"),
        [
            ("lowpass", {}),
            ("highpass", {"filter_type": "butterworth", "order": 3}),
            (
                "bandpass",
                {"filter_type": "butterworth", "n_resonators": 3, "f0": 10e6},
            ),
        ],
    )
    def test_response_meta_rejects_missing_required_fields(self, category, result):
        with pytest.raises(ValueError):
            response_meta(category, result)

    @pytest.mark.parametrize(
        "meta",
        [
            [],
            {"category": "not-a-category"},
            {"category": []},
            {
                "category": "lowpass",
                "response_type": [],
                "order": 3,
                "cutoff_hz": 1e6,
            },
            {"category": "lowpass"},
            {
                "category": "lowpass",
                "response_type": "butterworth",
                "order": 3,
                "cutoff_hz": 1e6,
                "f0_hz": 1e6,
            },
            {
                "category": "lowpass",
                "response_type": "chebyshev",
                "order": 3,
                "cutoff_hz": 1e6,
                "ripple_db": 3.1,
            },
        ],
    )
    def test_response_json_rejects_schema_invalid_metadata(self, meta):
        with pytest.raises(ValueError):
            export_response_json([], [], meta)

    def test_export_response_csv(self):
        result = export_response_csv([1e6, 10e6], [-0.1, -3.0])
        lines = result.split("\n")
        assert lines[0] == "frequency_hz,magnitude_db"
        assert len(lines) == 3

    @pytest.mark.parametrize("exporter", [export_response_json, export_response_csv])
    def test_response_export_rejects_mismatched_array_lengths(self, exporter):
        args = ([1e6, 10e6], [-0.1])
        if exporter is export_response_json:
            with pytest.raises(ValueError, match="same length"):
                exporter(*args, {"category": "lowpass"})
        else:
            with pytest.raises(ValueError, match="same length"):
                exporter(*args)

    def test_response_json_rejects_non_finite_values(self):
        with pytest.raises(ValueError, match=r"\$\.data\[0\]\.magnitude_db.*finite"):
            export_response_json(
                [1e6],
                [float("nan")],
                {"category": "lowpass", "cutoff_hz": 1e6},
            )

    def test_response_json_rejects_non_finite_metadata(self):
        with pytest.raises(ValueError, match=r"\$\.filter\.cutoff_hz.*finite"):
            export_response_json(
                [1e6],
                [-3.0],
                {"category": "lowpass", "cutoff_hz": float("inf")},
            )

    @pytest.mark.parametrize(
        "freqs,response_db",
        [
            ([float("inf")], [-3.0]),
            ([1e6], [float("nan")]),
        ],
    )
    def test_response_csv_rejects_non_finite_values(self, freqs, response_db):
        with pytest.raises(ValueError, match="finite"):
            export_response_csv(freqs, response_db)

    @pytest.mark.parametrize("exporter", [export_response_json, export_response_csv])
    @pytest.mark.parametrize(
        "freqs,response_db",
        [
            ([True], [False]),
            (["1MHz"], [0.0]),
            ([0.0], [0.0]),
            ([-1.0], [0.0]),
            ([1e6], [True]),
            ([1e6], ["-3"]),
        ],
    )
    def test_response_export_requires_numeric_frequency_and_db_values(
        self, exporter, freqs, response_db
    ):
        if exporter is export_response_json:
            with pytest.raises(ValueError):
                exporter(freqs, response_db, {"category": "lowpass"})
        else:
            with pytest.raises(ValueError):
                exporter(freqs, response_db)


# --- Lowpass transfer ---


class TestLowpassTransfer:
    """Tests for lowpass transfer functions."""

    def test_butterworth_dc_gain(self):
        assert lp_transfer.butterworth_response(0, 10e6, 5) == pytest.approx(1.0)

    def test_butterworth_at_cutoff(self):
        mag = lp_transfer.butterworth_response(10e6, 10e6, 3)
        db = magnitude_to_db(mag)
        assert db == pytest.approx(-3.0, abs=0.1)

    def test_butterworth_attenuation(self):
        mag = lp_transfer.butterworth_response(100e6, 10e6, 5)
        assert mag < 0.01

    def test_chebyshev_response(self):
        mag = lp_transfer.chebyshev_response(5e6, 10e6, 4, 0.5)
        assert 0 < mag <= 1.0

    def test_bessel_response(self):
        mag = lp_transfer.bessel_response(5e6, 10e6, 3)
        assert 0 < mag <= 1.0

    def test_bessel_invalid_order(self):
        with pytest.raises(ValueError, match="Order must be between 2 and 9"):
            lp_transfer.bessel_response(5e6, 10e6, 1)

    def test_bessel_valid_orders(self):
        for order in range(2, 10):
            mag = lp_transfer.bessel_response(5e6, 10e6, order)
            assert 0 <= mag <= 1.0

    def test_frequency_response_butterworth(self):
        freqs = [1e6, 10e6, 100e6]
        resp = lp_transfer.frequency_response("butterworth", freqs, 10e6, 3)
        assert len(resp) == 3
        assert resp[0] > resp[2]  # LPF: low freq better than high

    def test_frequency_response_chebyshev(self):
        resp = lp_transfer.frequency_response("ch", [1e6, 10e6], 10e6, 4, 1.0)
        assert len(resp) == 2

    def test_frequency_response_bessel(self):
        resp = lp_transfer.frequency_response("bessel", [1e6, 10e6], 10e6, 5)
        assert len(resp) == 2

    def test_frequency_response_invalid_type(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            lp_transfer.frequency_response("invalid", [1e6], 10e6, 3)

    @pytest.mark.parametrize("module", [lp_transfer, hp_transfer])
    def test_frequency_response_validates_definition_on_empty_grid(self, module):
        with pytest.raises(ValueError, match="Unknown filter type"):
            module.frequency_response("invalid", [], 10e6, 3)
        with pytest.raises(ValueError, match="positive and finite"):
            module.frequency_response("bw", [], 0.0, 3)
        with pytest.raises(ValueError, match="positive integer"):
            module.frequency_response("bw", [], 10e6, 0)

    @pytest.mark.parametrize("module", [lp_transfer, hp_transfer])
    def test_frequency_response_rejects_non_string_type(self, module):
        with pytest.raises(ValueError, match="must be a string"):
            module.frequency_response(None, [1e6], 10e6, 3)

    @pytest.mark.parametrize("module", [lp_transfer, hp_transfer])
    @pytest.mark.parametrize("freqs", [None, 1, "1MHz", {"frequency": 1e6}])
    def test_frequency_response_requires_frequency_sequence(self, module, freqs):
        with pytest.raises(ValueError, match="freqs must be a sequence"):
            module.frequency_response("bw", freqs, 10e6, 3)


# --- Highpass transfer ---


class TestHighpassTransfer:
    """Tests for highpass transfer functions."""

    def test_butterworth_dc_blocking(self):
        assert hp_transfer.butterworth_response(0, 10e6, 3) == 0.0

    def test_butterworth_at_cutoff(self):
        mag = hp_transfer.butterworth_response(10e6, 10e6, 3)
        db = magnitude_to_db(mag)
        assert db == pytest.approx(-3.0, abs=0.1)

    def test_butterworth_high_freq_passthrough(self):
        mag = hp_transfer.butterworth_response(1e9, 10e6, 3)
        assert mag > 0.99

    def test_chebyshev_dc_blocking(self):
        assert hp_transfer.chebyshev_response(0, 10e6, 3, 0.5) == 0.0

    def test_chebyshev_passband(self):
        mag = hp_transfer.chebyshev_response(100e6, 10e6, 4, 0.5)
        assert mag > 0.9

    def test_bessel_dc_blocking(self):
        assert hp_transfer.bessel_response(0, 10e6, 3) == 0.0

    def test_bessel_invalid_order(self):
        with pytest.raises(ValueError, match="Order must be between 2 and 9"):
            hp_transfer.bessel_response(10e6, 10e6, 1)

    def test_bessel_valid_orders(self):
        for order in range(2, 10):
            mag = hp_transfer.bessel_response(100e6, 10e6, order)
            assert 0 <= mag <= 1.0

    def test_frequency_response_rising(self):
        freqs = [1e6, 10e6, 100e6]
        resp = hp_transfer.frequency_response("bw", freqs, 10e6, 3)
        assert len(resp) == 3
        assert resp[2] > resp[0]  # HPF: high freq better than low

    def test_frequency_response_invalid_type(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            hp_transfer.frequency_response("unknown", [1e6], 10e6, 3)


# --- Bandpass transfer ---


class TestBandpassTransfer:
    """Tests for bandpass transfer functions."""

    def test_bandpass_deviation_at_center(self):
        assert bp_transfer._bandpass_deviation(14e6, 14e6, 1e6) == pytest.approx(0.0)

    def test_bandpass_deviation_invalid_freq(self):
        with pytest.raises(ValueError, match="must be positive"):
            bp_transfer._bandpass_deviation(-1, 14e6, 1e6)

    def test_bandpass_deviation_invalid_bw(self):
        with pytest.raises(ValueError, match="must be positive"):
            bp_transfer._bandpass_deviation(14e6, 14e6, -1)

    @pytest.mark.parametrize(
        "frequency,f0,bw",
        [
            (float("nan"), 14e6, 1e6),
            (14e6, float("inf"), 1e6),
            (14e6, 14e6, float("nan")),
        ],
    )
    def test_bandpass_deviation_rejects_non_finite_inputs(self, frequency, f0, bw):
        with pytest.raises(ValueError, match="finite"):
            bp_transfer._bandpass_deviation(frequency, f0, bw)

    def test_bandpass_deviation_is_stable_at_large_equal_frequencies(self):
        assert bp_transfer._bandpass_deviation(1e308, 1e308, 1e307) == 0.0

    def test_bandpass_deviation_extreme_ratio_returns_infinity_not_nan(self):
        deviation = bp_transfer._bandpass_deviation(1e308, 1e-308, 1e-308)
        assert math.isinf(deviation)
        assert deviation > 0

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

    def test_magnitude_butterworth_at_center(self):
        assert bp_transfer.magnitude_butterworth(14e6, 14e6, 1e6, 3) == pytest.approx(1.0)

    def test_magnitude_butterworth_off_center(self):
        mag = bp_transfer.magnitude_butterworth(20e6, 14e6, 1e6, 3)
        assert mag < 0.5

    def test_magnitude_chebyshev_at_center(self):
        assert bp_transfer.magnitude_chebyshev(14e6, 14e6, 1e6, 3, 0.5) == pytest.approx(1.0)

    def test_magnitude_bessel_differs_from_butterworth_off_center(self):
        mag_bes = bp_transfer.magnitude_bessel(10e6, 14e6, 1e6, 3)
        mag_bw = bp_transfer.magnitude_butterworth(10e6, 14e6, 1e6, 3)
        assert mag_bes != pytest.approx(mag_bw)

    def test_magnitude_db_at_center(self):
        assert bp_transfer.magnitude_db(14e6, 14e6, 1e6, 3, "butterworth") == pytest.approx(0.0)

    def test_magnitude_db_chebyshev(self):
        assert bp_transfer.magnitude_db(14e6, 14e6, 1e6, 3, "chebyshev", 0.5) == pytest.approx(0.0)

    def test_magnitude_db_bessel(self):
        assert bp_transfer.magnitude_db(14e6, 14e6, 1e6, 3, "bessel") == pytest.approx(0.0)

    def test_magnitude_db_invalid_type(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            bp_transfer.magnitude_db(14e6, 14e6, 1e6, 3, "invalid")

    def test_magnitude_db_floor(self):
        """Deep-stopband response floors at -120 dB, same as LP/HP."""
        db = bp_transfer.magnitude_db(100e6, 14e6, 1e6, 5, "butterworth")
        assert db == -120.0

    @pytest.mark.parametrize("order", [True, 0, -1, 2.5])
    @pytest.mark.parametrize(
        "function_name,extra_args",
        [
            ("magnitude_butterworth", ()),
            ("magnitude_chebyshev", (0.5,)),
            ("magnitude_bessel", ()),
        ],
    )
    def test_public_magnitude_functions_reject_invalid_order(
        self, function_name, extra_args, order
    ):
        function = getattr(bp_transfer, function_name)
        with pytest.raises(ValueError, match="order must be a positive integer"):
            function(14e6, 14e6, 1e6, order, *extra_args)

    @pytest.mark.parametrize("order", [True, 0, -1, 2.5])
    def test_public_db_and_sweep_functions_reject_invalid_order(self, order):
        with pytest.raises(ValueError, match="order must be a positive integer"):
            bp_transfer.magnitude_db(14e6, 14e6, 1e6, order, "butterworth")
        with pytest.raises(ValueError, match="order must be a positive integer"):
            bp_transfer.frequency_sweep(14e6, 1e6, order, "butterworth", points=3)
        result = {
            "f0": 14e6,
            "bw": 1e6,
            "n_resonators": order,
            "filter_type": "butterworth",
            "ripple_db": None,
        }
        with pytest.raises(ValueError, match="order must be a positive integer"):
            bp_transfer.frequency_response(result, [])

    @pytest.mark.parametrize("result", [None, 1, [], "result"])
    def test_bandpass_frequency_response_requires_result_mapping(self, result):
        with pytest.raises(ValueError, match="result must be a mapping"):
            bp_transfer.frequency_response(result, [])

    @pytest.mark.parametrize("freqs", [None, 1, "1MHz", {"frequency": 1e6}])
    def test_bandpass_frequency_response_requires_frequency_sequence(self, freqs):
        result = {
            "f0": 14e6,
            "bw": 1e6,
            "n_resonators": 3,
            "filter_type": "butterworth",
            "ripple_db": None,
        }
        with pytest.raises(ValueError, match="freqs must be a sequence"):
            bp_transfer.frequency_response(result, freqs)

    @pytest.mark.parametrize("result", [None, 1, [], "result"])
    def test_bandpass_netlist_sweep_requires_result_mapping(self, result):
        with pytest.raises(ValueError, match="result must be a mapping"):
            bp_transfer.netlist_frequency_sweep(result, points=3)

    @pytest.mark.parametrize("ripple_db", [True, 0.0, float("nan"), float("inf")])
    def test_chebyshev_magnitude_and_sweep_reject_invalid_ripple(self, ripple_db):
        with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
            bp_transfer.magnitude_chebyshev(14e6, 14e6, 1e6, 3, ripple_db)
        with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
            bp_transfer.magnitude_db(14e6, 14e6, 1e6, 3, "chebyshev", ripple_db)
        with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
            bp_transfer.frequency_sweep(14e6, 1e6, 3, "chebyshev", ripple_db, points=3)

    @pytest.mark.parametrize("filter_type", ["butterworth", "chebyshev", "bessel"])
    def test_extreme_deviation_returns_zero_magnitude_and_finite_db(self, filter_type):
        ripple_db = 0.5
        if filter_type == "butterworth":
            magnitude = bp_transfer.magnitude_butterworth(1e308, 1e-308, 1e-308, 9)
        elif filter_type == "chebyshev":
            magnitude = bp_transfer.magnitude_chebyshev(1e308, 1e-308, 1e-308, 9, ripple_db)
        else:
            magnitude = bp_transfer.magnitude_bessel(1e308, 1e-308, 1e-308, 9)
        assert magnitude == 0.0
        assert bp_transfer.magnitude_db(1e308, 1e-308, 1e-308, 9, filter_type, ripple_db) == -120.0

    @pytest.mark.parametrize("filter_type", ["butterworth", "chebyshev"])
    def test_extreme_positive_order_does_not_overflow(self, filter_type):
        huge_order = 10**400
        assert bp_transfer.magnitude_db(2.0, 1.0, 1.0, huge_order, filter_type, 0.5) == -120.0

    def test_frequency_sweep_defaults(self):
        result = bp_transfer.frequency_sweep(14e6, 1e6, 3, "butterworth")
        assert len(result) == 61
        assert all(isinstance(r, tuple) and len(r) == 2 for r in result)

    def test_frequency_sweep_custom_points(self):
        result = bp_transfer.frequency_sweep(14e6, 1e6, 3, "butterworth", points=31)
        assert len(result) == 31

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"points": 1},
            {"points": 2.5},
            {"decades": 0},
            {"decades": float("nan")},
        ],
    )
    def test_frequency_sweep_rejects_invalid_grid_controls(self, kwargs):
        with pytest.raises(ValueError):
            bp_transfer.frequency_sweep(14e6, 1e6, 3, "butterworth", **kwargs)

    def test_frequency_sweep_rejects_non_finite_or_overflowing_span(self):
        with pytest.raises(ValueError, match="finite"):
            bp_transfer.frequency_sweep(float("inf"), 1e6, 3, "butterworth")
        with pytest.raises(ValueError, match="finite"):
            bp_transfer.frequency_sweep(1e308, 1e307, 3, "butterworth")

    def test_generate_frequency_points_bandpass(self):
        points = bp_transfer.generate_frequency_points(14e6, 1e6, points=101)
        assert len(points) == 101
        assert all(f > 0 for f in points)

    def test_frequency_response_with_result(self):
        result = {
            "f0": 14e6,
            "bw": 1e6,
            "n_resonators": 3,
            "filter_type": "butterworth",
            "ripple_db": 0.5,
        }
        resp = bp_transfer.frequency_response(result, [13e6, 14e6, 15e6])
        assert len(resp) == 3
        assert resp[1] > resp[0]  # Peak at center

    def test_export_response_json_bandpass(self):
        """Golden test: bandpass exports carry the unified filter block + data."""
        result = {
            "filter_type": "butterworth",
            "coupling": "top",
            "f0": 14e6,
            "bw": 1e6,
            "n_resonators": 3,
            "ripple_db": None,
        }
        s = export_response_json([13e6, 14e6], [-3.0, 0.0], response_meta("bandpass", result))
        data = json.loads(s)
        assert data["filter"] == {
            "category": "bandpass",
            "response_type": "butterworth",
            "order": 3,
            "f0_hz": 14e6,
            "bw_hz": 1e6,
            "coupling": "top",
        }
        assert data["data"][0] == {"frequency_hz": 13e6, "magnitude_db": -3.0}

    def test_export_response_csv_bandpass(self):
        csv_str = export_response_csv([13e6, 14e6], [-3.0, 0.0])
        lines = csv_str.split("\n")
        assert lines[0] == "frequency_hz,magnitude_db"
        assert len(lines) == 3


class TestNetlistSweep:
    """Netlist-true bandpass response (simulated from synthesized values)."""

    @staticmethod
    def _result(fbw, n=3, ftype="butterworth"):
        from filter_lib.bandpass.calculations import calculate_bandpass_filter

        f0 = 10e6
        return calculate_bandpass_filter(f0, f0 * fbw, 50, n, ftype, "top")

    def test_peak_near_unity_at_center(self):
        from filter_lib.bandpass.transfer import netlist_frequency_sweep

        result = self._result(0.05)
        sweep = netlist_frequency_sweep(result, points=201)
        peak_db = max(db for _, db in sweep)
        assert peak_db == pytest.approx(0.0, abs=0.1)

    def test_docstring_describes_ideal_component_simulation_limits(self):
        from filter_lib.bandpass.transfer import netlist_frequency_sweep

        docstring = netlist_frequency_sweep.__doc__ or ""
        assert "ideal-component circuit" in docstring
        assert "not a measurement" in docstring
        assert "parasitics" in docstring

    def test_3db_crossings_match_printed_cutoffs(self):
        """The -3 dB points of the simulated response agree with f_low/f_high."""
        from filter_lib.bandpass.transfer import netlist_frequency_sweep

        result = self._result(0.10)
        sweep = netlist_frequency_sweep(result, decades=0.15, points=2001)
        peak = max(db for _, db in sweep)
        above = [f for f, db in sweep if db >= peak - 3.0103]
        f_lo_meas, f_hi_meas = above[0], above[-1]
        assert f_lo_meas == pytest.approx(result["f_low"], rel=0.03)
        assert f_hi_meas == pytest.approx(result["f_high"], rel=0.03)

    def test_netlist_diverges_from_prototype_at_wide_fbw(self):
        """At 20% FBW the real circuit skews away from the symmetric prototype.

        This is why plots are simulated rather than computed from the
        prototype: reverting would silently show users an idealized shape
        their built filter cannot reproduce.
        """
        from filter_lib.bandpass.transfer import frequency_sweep, netlist_frequency_sweep

        result = self._result(0.20)
        netlist = netlist_frequency_sweep(result, points=201)
        prototype = frequency_sweep(
            result["f0"], result["bw"], result["n_resonators"], result["filter_type"], points=201
        )
        deltas = [abs(a - b) for (_, a), (_, b) in zip(netlist, prototype)]
        assert max(deltas) > 1.0

    def test_netlist_response_factory_matches_sweep(self):
        from filter_lib.bandpass.transfer import netlist_frequency_sweep
        from filter_lib.shared.transfer_response_dispatch import make_bp_netlist_response_db

        result = self._result(0.05)
        response_db = make_bp_netlist_response_db(result)
        sweep = netlist_frequency_sweep(result, points=21)
        for f, db in sweep[::5]:
            assert response_db(f) == pytest.approx(db, abs=1e-9)

    def test_netlist_sweep_rejects_too_few_points(self):
        from filter_lib.bandpass.transfer import netlist_frequency_sweep

        with pytest.raises(ValueError, match="points"):
            netlist_frequency_sweep(self._result(0.05), points=1)

    @pytest.mark.parametrize("kwargs", [{"points": 2.5}, {"decades": 0}])
    def test_netlist_sweep_rejects_invalid_grid_controls(self, kwargs):
        from filter_lib.bandpass.transfer import netlist_frequency_sweep

        with pytest.raises(ValueError):
            netlist_frequency_sweep(self._result(0.05), **kwargs)
