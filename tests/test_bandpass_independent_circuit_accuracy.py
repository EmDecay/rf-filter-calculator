"""Exported Top-C component values checked against a fully independent circuit model.

Nothing here reuses production builders, nodal solvers, measurement helpers, or ideal
response code. The references are:

- an ABCD cascade of the documented Top-C diagram (series Ce_in, shunt Cp_i || L_i,
  series Cs_i,i+1, series Ce_out) evaluated from the exported component values;
- the lowpass-to-bandpass deviation (f^2 - f0^2)/(BW*f) and its positive quadratic root;
- closed-form Butterworth and equal-ripple Chebyshev magnitudes, and the reverse Bessel
  polynomial normalized to its own -3 dB frequency.
"""

import copy
import math

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.bandpass.passband_measurement import measure_netlist_passband


def _transducer_gain(result: dict, frequency: float, inductor_q: float | None = None) -> float:
    """|S21|^2 between equal Z0 ports; optional inductor Q is series R fixed at f0."""
    omega = 2 * math.pi * frequency
    z0 = result["z0"]
    inductance = result["L_resonant"]
    series_r = 0.0 if inductor_q is None else 2 * math.pi * result["f0"] * inductance / inductor_q
    a, b, c, d = 1 + 0j, 0j, 0j, 1 + 0j

    def series(impedance: complex) -> None:
        nonlocal b, d
        b, d = a * impedance + b, c * impedance + d

    def shunt(admittance: complex) -> None:
        nonlocal a, c
        a, c = a + b * admittance, c + d * admittance

    series(1 / (1j * omega * result["c_end_in"]))
    for index, tank_capacitance in enumerate(result["c_tank"]):
        shunt(1j * omega * tank_capacitance + 1 / (series_r + 1j * omega * inductance))
        if index < len(result["c_coupling"]):
            series(1 / (1j * omega * result["c_coupling"][index]))
    series(1 / (1j * omega * result["c_end_out"]))
    return abs(2 / (a + b / z0 + c * z0 + d)) ** 2


def _gain_db(result: dict, frequency: float, inductor_q: float | None = None) -> float:
    return 10 * math.log10(_transducer_gain(result, frequency, inductor_q))


def _frequency_at_deviation(delta: float, f0: float, bw: float) -> float:
    """Positive root of f^2 - delta*bw*f - f0^2 = 0."""
    half = delta * bw / 2
    return half + math.sqrt(half * half + f0 * f0)


def _independent_edges(result: dict) -> tuple[float, float, float]:
    """Center-connected half-power edges relative to the passband peak, and the peak."""
    f0, bw = result["f0"], result["bw"]
    peak = max(
        _transducer_gain(result, _frequency_at_deviation(i / 400 - 1, f0, bw)) for i in range(801)
    )
    threshold = peak / 2

    def crossing(direction: int) -> float:
        inside, delta = f0, 0.0
        while True:
            delta += direction * 1e-3
            outside = _frequency_at_deviation(delta, f0, bw)
            if _transducer_gain(result, outside) < threshold:
                break
            inside = outside
        for _ in range(100):
            middle = 0.5 * (inside + outside)
            if _transducer_gain(result, middle) >= threshold:
                inside = middle
            else:
                outside = middle
        return 0.5 * (inside + outside)

    return crossing(-1), crossing(1), peak


def _chebyshev_3db_deviation(order: int, ripple_db: float) -> float:
    epsilon = math.sqrt(10 ** (ripple_db / 10) - 1)
    return math.cosh(math.acosh(1 / epsilon) / order)


def _bessel_power(omega: float, order: int) -> float:
    coefficients = [
        math.factorial(2 * order - k)
        / (2 ** (order - k) * math.factorial(k) * math.factorial(order - k))
        for k in range(order + 1)
    ]
    value = sum(coefficient * (1j * omega) ** k for k, coefficient in enumerate(coefficients))
    return (coefficients[0] / abs(value)) ** 2


def _bessel_3db_omega(order: int) -> float:
    low, high = 0.0, 10.0
    for _ in range(100):
        middle = 0.5 * (low + high)
        if _bessel_power(middle, order) > 0.5:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


def _prototype_db(delta: float, family: str, order: int, ripple_db: float | None) -> float:
    """Textbook lowpass prototype with its -3 dB point at |delta| = 1."""
    x = abs(delta)
    if family == "butterworth":
        return -10 * math.log10(1 + x ** (2 * order))
    if family == "chebyshev":
        scaled = x * _chebyshev_3db_deviation(order, ripple_db)
        if scaled <= 1:
            polynomial = math.cos(order * math.acos(scaled))
        else:
            polynomial = math.cosh(order * math.acosh(scaled))
        return -10 * math.log10(1 + (10 ** (ripple_db / 10) - 1) * polynomial**2)
    return 10 * math.log10(_bessel_power(x * _bessel_3db_omega(order), order))


def _design(f0, bw, order, family, ripple_db=None, z0=50.0, **choice):
    kwargs = dict(choice)
    if ripple_db is not None:
        kwargs["ripple_db"] = ripple_db
    return calculate_bandpass_filter(f0, bw, z0, order, family, "top", **kwargs)


_EDGE_CASES = {
    "butterworth-min-order": dict(f0=10e6, bw=0.5e6, order=2, family="butterworth"),
    "butterworth-max-order": dict(f0=10e6, bw=0.2e6, order=9, family="butterworth"),
    "chebyshev-small-ripple": dict(f0=10e6, bw=0.5e6, order=3, family="chebyshev", ripple_db=0.01),
    "chebyshev-max-order": dict(f0=10e6, bw=0.2e6, order=9, family="chebyshev", ripple_db=1.0),
    "chebyshev-max-ripple": dict(f0=10e6, bw=0.5e6, order=3, family="chebyshev", ripple_db=3.0),
    "bessel-asymmetric": dict(f0=10e6, bw=0.5e6, order=4, family="bessel"),
    "bessel-max-order": dict(f0=10e6, bw=0.1e6, order=9, family="bessel"),
    "tank-impedance-200": dict(
        f0=10e6, bw=0.5e6, order=3, family="butterworth", resonator_impedance=200.0
    ),
    "tank-inductance-1u8": dict(
        f0=10e6, bw=0.5e6, order=3, family="butterworth", resonator_inductance=1.8e-6
    ),
    "one-hertz-75-ohm": dict(f0=1.0, bw=0.05, order=3, family="butterworth", z0=75.0),
    "100-ghz": dict(f0=100e9, bw=2e9, order=5, family="chebyshev", ripple_db=0.5),
    "fbw-1e-4": dict(f0=10e6, bw=1e3, order=5, family="butterworth"),
    # Outside the validated envelope, but both requested skirts are still calibrated.
    "fbw-20-percent": dict(f0=10e6, bw=2e6, order=3, family="butterworth"),
}


class TestIndependentHalfPowerEdges:
    """Both requested -3 dB skirts land where the exported circuit actually crosses -3 dB.

    Tolerance 1e-4 is five times the calibration tolerance. It is deliberately tighter
    than the FBW^2/8 error (3.1e-4 at 5% FBW) of the arithmetic f0 +/- BW/2 shortcut.
    """

    @pytest.mark.parametrize("case", list(_EDGE_CASES), ids=list(_EDGE_CASES))
    def test_exported_values_cross_half_power_at_requested_edges(self, case):
        spec = _EDGE_CASES[case]
        result = _design(**spec)
        low, high, peak = _independent_edges(result)
        requested_low = _frequency_at_deviation(-1.0, spec["f0"], spec["bw"])
        requested_high = _frequency_at_deviation(1.0, spec["f0"], spec["bw"])

        # A lossless equal-terminated ladder reaches full transmission in its passband.
        assert 10 * math.log10(peak) == pytest.approx(0.0, abs=1e-3)
        assert low == pytest.approx(requested_low, rel=1e-4, abs=0)
        assert high == pytest.approx(requested_high, rel=1e-4, abs=0)
        assert (result["f_low"], result["f_high"]) == pytest.approx(
            (requested_low, requested_high), rel=1e-12, abs=0
        )

    @pytest.mark.parametrize(
        "f_low, f_high", [(14.0e6, 14.35e6), (7.0e6, 7.3e6)], ids=["20m", "40m"]
    )
    def test_edge_specified_request_realizes_the_supplied_edges(self, f_low, f_high):
        """--fl/--fh requests become f0 = sqrt(fl*fh), BW = fh - fl, so the edges return."""
        result = _design(math.sqrt(f_low * f_high), f_high - f_low, 5, "chebyshev", 0.25)
        low, high, _peak = _independent_edges(result)

        assert (result["f_low"], result["f_high"]) == pytest.approx(
            (f_low, f_high), rel=1e-12, abs=0
        )
        assert (low, high) == pytest.approx((f_low, f_high), rel=1e-4, abs=0)


class TestNarrowbandPrototypeLimit:
    """At 0.01% FBW a coupled-resonator filter must reproduce its lowpass prototype.

    This checks the whole chain (g-values, couplings, external Q, end-coupling and
    tank compensation) against textbook magnitudes, not the library's ideal response.
    """

    @pytest.mark.parametrize(
        "family, order, ripple_db",
        [
            ("butterworth", 2, None),
            ("butterworth", 9, None),
            ("chebyshev", 3, 0.01),
            ("chebyshev", 5, 1.0),
            ("chebyshev", 9, 3.0),
            ("bessel", 2, None),
            ("bessel", 4, None),
            ("bessel", 9, None),
        ],
    )
    def test_circuit_matches_closed_form_prototype(self, family, order, ripple_db):
        f0, bw = 10e6, 1e3
        result = _design(f0, bw, order, family, ripple_db)

        for delta in (-3.0, -2.0, -1.5, -1.0, -0.7, -0.4, 0.0, 0.2, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0):
            actual_db = _gain_db(result, _frequency_at_deviation(delta, f0, bw))
            assert actual_db == pytest.approx(
                _prototype_db(delta, family, order, ripple_db), abs=0.03
            ), delta


def _component_values(result: dict) -> list[float]:
    return [
        *result["c_tank"],
        *result["c_coupling"],
        result["c_end_in"],
        result["c_end_out"],
    ]


class TestFrequencyAndImpedanceScaling:
    """Scaling f0, BW by s and Z0 by r scales every C by 1/(s*r) and L by r/s."""

    @pytest.mark.parametrize("family, order", [("chebyshev", 5), ("bessel", 4)])
    @pytest.mark.parametrize(
        "frequency_scale, impedance_scale",
        [(1e-7, 1.0), (1e4, 1.5), (1e290, 1e-3), (1e-290, 1e3), (1.0, 1e5)],
    )
    def test_components_follow_exact_scaling(self, family, order, frequency_scale, impedance_scale):
        ripple = 0.5 if family == "chebyshev" else None
        base = _design(10e6, 0.5e6, order, family, ripple)
        scaled = _design(
            10e6 * frequency_scale,
            0.5e6 * frequency_scale,
            order,
            family,
            ripple,
            z0=50.0 * impedance_scale,
        )

        assert scaled["L_resonant"] * frequency_scale / impedance_scale == pytest.approx(
            base["L_resonant"], rel=1e-9, abs=0
        )
        assert [
            value * frequency_scale * impedance_scale for value in _component_values(scaled)
        ] == pytest.approx(_component_values(base), rel=1e-9, abs=0)
        assert scaled["f_tank_hz"] / frequency_scale == pytest.approx(
            base["f_tank_hz"], rel=1e-9, abs=0
        )
        assert scaled["fbw_synth"] == pytest.approx(base["fbw_synth"], rel=1e-9, abs=0)
        assert scaled["response_validation_status"] == base["response_validation_status"]


class TestValidationRecordMatchesIndependentMeasurement:
    """Every JSON-visible measured number in synthesis_validation is independently true."""

    @pytest.mark.parametrize(
        "spec",
        [
            dict(f0=10e6, bw=0.5e6, order=3, family="butterworth"),
            dict(f0=10e6, bw=0.2e6, order=5, family="chebyshev", ripple_db=1.0),
            dict(f0=10e6, bw=0.5e6, order=4, family="bessel"),
            dict(f0=10e6, bw=1.5e6, order=3, family="butterworth"),
        ],
        ids=["butterworth", "chebyshev-1db", "bessel", "butterworth-15pct"],
    )
    def test_reported_measurements(self, spec):
        result = _design(**spec)
        validation = result["synthesis_validation"]
        f0, bw, order, family = spec["f0"], spec["bw"], spec["order"], spec["family"]
        ripple_db = spec.get("ripple_db")
        low, high, peak = _independent_edges(result)
        grid_tolerance = 2e-5 * high  # 2001-point linear interpolation of the skirts

        assert validation["measured_f_low_hz"] == pytest.approx(low, abs=grid_tolerance)
        assert validation["measured_f_high_hz"] == pytest.approx(high, abs=grid_tolerance)
        assert validation["measured_center_hz"] == pytest.approx(
            math.sqrt(low * high), abs=grid_tolerance
        )
        assert validation["measured_bandwidth_hz"] == pytest.approx(
            high - low, abs=2 * grid_tolerance
        )
        assert validation["center_error_rel"] == pytest.approx(
            math.sqrt(low * high) / f0 - 1, abs=grid_tolerance / f0
        )
        assert validation["bandwidth_error_rel"] == pytest.approx(
            (high - low) / bw - 1, abs=2 * grid_tolerance / bw
        )
        # The validator's reference is its sampled local peak, which can sit a few
        # micro-dB below the true lossless maximum between grid points.
        assert 10 * math.log10(peak) - 1e-4 <= validation["peak_db"] <= 10 * math.log10(peak)
        peak_db = validation["peak_db"]
        assert validation["connected_region_count"] == 1
        assert validation["internal_hole_count"] == 0

        # Shape and ripple on the same normalized-deviation grid as the validator.
        deltas = [-4.0 + 8.0 * index / 2000 for index in range(2001)]
        normalized = {
            delta: _gain_db(result, _frequency_at_deviation(delta, f0, bw)) - peak_db
            for delta in deltas
            if abs(delta) <= 1.0
        }
        shape_error = max(
            abs(actual - _prototype_db(delta, family, order, ripple_db))
            for delta, actual in normalized.items()
        )
        # The library normalizes Bessel with 5-digit tabulated -3 dB factors (Zverev).
        ideal_tolerance = 1e-3 if family == "bessel" else 1e-6
        assert validation["max_passband_shape_error_db"] == pytest.approx(
            shape_error, abs=ideal_tolerance + 1e-4
        )
        ripple_limit = 1.0 / _chebyshev_3db_deviation(order, ripple_db) if ripple_db else 1.0
        in_ripple_band = [
            value for delta, value in normalized.items() if abs(delta) <= ripple_limit
        ]
        variation = max(in_ripple_band) - min(in_ripple_band)
        assert validation["measured_passband_variation_db"] == pytest.approx(variation, abs=1e-4)

        assert validation["near_stopband_normalized_deviations"] == [-2.0, -1.5, 1.5, 2.0]
        assert set(validation["stopband_samples"]) == {"-2", "-1.5", "+1.5", "+2"}
        errors = []
        for delta in validation["near_stopband_normalized_deviations"]:
            sample = validation["stopband_samples"][f"{delta:+g}"]
            frequency = _frequency_at_deviation(delta, f0, bw)
            ideal = _prototype_db(delta, family, order, ripple_db)
            assert sample["frequency_hz"] == pytest.approx(frequency, rel=1e-12, abs=0)
            assert sample["actual_db"] == pytest.approx(
                _gain_db(result, frequency) - peak_db, abs=1e-6
            )
            assert sample["ideal_db"] == pytest.approx(ideal, abs=ideal_tolerance)
            errors.append(abs(sample["actual_db"] - ideal))
        assert validation["max_stopband_sample_error_db"] == pytest.approx(
            max(errors), abs=ideal_tolerance
        )

        shape_ok = shape_error <= 0.30 and max(errors) <= 8.0
        if family == "chebyshev":
            shape_ok = shape_ok and variation <= ripple_db + 0.20
        in_envelope = bw / f0 <= 0.10
        assert validation["edge_validated"] is True
        assert validation["shape_validated"] is shape_ok
        assert validation["validated"] is (shape_ok and in_envelope)
        assert result["response_validation_status"] == (
            "validated" if shape_ok and in_envelope else "outside_validated_envelope"
        )
        if shape_ok and in_envelope:
            assert result["warnings"] == []


class TestPerturbedCircuitMeasurement:
    """Calibration measures the -3 dB region around the local peak nearest f0.

    An 8% error on the middle tank capacitor of a 1 dB Chebyshev design splits the
    response into three -3 dB regions, and its strongest peak lies well below f0.
    """

    def test_center_connected_region_ignores_a_stronger_off_center_peak(self):
        f0, bw, points = 10e6, 0.5e6, 2001
        result = copy.deepcopy(_design(f0, bw, 5, "chebyshev", 1.0))
        result["c_tank"][2] *= 1.08

        measurement = measure_netlist_passband(result, f0, bw, points=points)

        deltas = [-4.0 + 8.0 * index / (points - 1) for index in range(points)]
        freqs = [_frequency_at_deviation(delta, f0, bw) for delta in deltas]
        gains = [_transducer_gain(result, frequency) for frequency in freqs]
        maxima = [
            index
            for index in range(points)
            if (index == 0 or gains[index] >= gains[index - 1])
            and (index == points - 1 or gains[index] >= gains[index + 1])
        ]
        local = min(maxima, key=lambda index: abs(math.log(freqs[index] / f0)))
        strongest = max(maxima, key=lambda index: gains[index])
        assert freqs[strongest] < freqs[local] and gains[strongest] > 1.5 * gains[local]
        threshold = gains[local] / 2
        above = [gain >= threshold for gain in gains]
        region_starts = [i for i in range(points) if above[i] and (i == 0 or not above[i - 1])]

        def crossing(inside: float, outside: float) -> float:
            for _ in range(100):
                middle = 0.5 * (inside + outside)
                if _transducer_gain(result, middle) >= threshold:
                    inside = middle
                else:
                    outside = middle
            return 0.5 * (inside + outside)

        low_index = local
        while above[low_index - 1]:
            low_index -= 1
        high_index = local
        while above[high_index + 1]:
            high_index += 1
        first = region_starts[0]
        last = max(i for i in range(points) if above[i])

        assert measurement["peak_db"] == pytest.approx(10 * math.log10(gains[local]), abs=1e-9)
        assert measurement["connected_region_count"] == len(region_starts) == 3
        assert measurement["f_low"] == pytest.approx(
            crossing(freqs[low_index], freqs[low_index - 1]), rel=1e-5, abs=0
        )
        assert measurement["f_high"] == pytest.approx(
            crossing(freqs[high_index], freqs[high_index + 1]), rel=1e-5, abs=0
        )
        assert measurement["outer_f_low"] == pytest.approx(
            crossing(freqs[first], freqs[first - 1]), rel=1e-5, abs=0
        )
        assert measurement["outer_f_high"] == pytest.approx(
            crossing(freqs[last], freqs[last + 1]), rel=1e-5, abs=0
        )


class TestLossModelIsMetadataAndMatchesCircuit:
    """Q inputs never change synthesized values; loss comparisons match a lossy circuit."""

    def test_q_inputs_do_not_change_synthesized_components(self):
        lossless = _design(10e6, 0.5e6, 3, "butterworth")
        for choice in ({"qu": 50.0}, {"ql": 200.0, "qc": 400.0}, {"ql": 80.0}, {"qc": 0.01}):
            lossy = _design(10e6, 0.5e6, 3, "butterworth", **choice)
            assert _component_values(lossy) == _component_values(lossless)
            assert lossy["L_resonant"] == lossless["L_resonant"]

    @pytest.mark.parametrize(
        "choice, combination, resonator_qu",
        [
            ({}, "not_supplied", None),
            ({"qu": 150.0}, "direct_resonator_q", 150.0),
            ({"ql": 80.0}, "reciprocal_component_loss_sum", 80.0),
            ({"qc": 400.0}, "reciprocal_component_loss_sum", 400.0),
            ({"ql": 200.0, "qc": 400.0}, "reciprocal_component_loss_sum", 400.0 / 3.0),
        ],
    )
    def test_q_model_records_the_supplied_loss_channels(self, choice, combination, resonator_qu):
        result = _design(10e6, 0.5e6, 3, "butterworth", **choice)
        assert result["q_model"]["combination"] == combination
        if resonator_qu is None:
            assert result["q_model"]["resonator_qu"] is None
        else:
            assert result["q_model"]["resonator_qu"] == pytest.approx(resonator_qu, rel=1e-12)

    def test_cohn_comparison_and_harmonics_match_independent_lossy_circuit(self):
        result = _design(10e6, 0.5e6, 3, "butterworth", qu=30.0)
        f0 = result["f0"]
        validation = result["loss_estimate_validation"]
        assert validation["comparison_tolerance_db"] == 0.5
        assert validation["reference_frequency_hz"] == f0
        assert set(validation["comparisons"]) == {"100", "250", "30"}

        lossless_db = _gain_db(result, f0)
        for key, record in validation["comparisons"].items():
            q = float(key)
            added_loss = lossless_db - _gain_db(result, f0, inductor_q=q)
            estimate = 4.343 * sum(result["g_values"]) / (result["fbw_synth"] * q)
            assert record["cohn_estimate_db"] == pytest.approx(estimate, rel=1e-12)
            assert record["lossless_center_gain_db"] == pytest.approx(lossless_db, abs=1e-9)
            assert record["circuit_added_center_loss_db"] == pytest.approx(added_loss, abs=1e-9)
            assert record["estimate_minus_circuit_db"] == pytest.approx(
                estimate - added_loss, abs=1e-9
            )
            expected_status = (
                "agrees_at_center"
                if abs(estimate - added_loss) <= 0.5
                else "poor_approximation_at_center"
            )
            assert record["status"] == expected_status
        # Low Q is outside the small-loss approximation; the reported status must say so.
        assert validation["comparisons"]["30"]["status"] == "poor_approximation_at_center"
        assert validation["comparisons"]["250"]["status"] == "agrees_at_center"

        samples = result["harmonic_response"]["samples"]
        assert [sample["multiple"] for sample in samples] == [2, 3]
        for sample in samples:
            frequency = f0 * sample["multiple"]
            assert sample["frequency_hz"] == frequency
            assert sample["transducer_gain_db"] == pytest.approx(
                _gain_db(result, frequency), abs=1e-9
            )
