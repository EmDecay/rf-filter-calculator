"""Build-realization analysis: physical parts, losses, and tolerance screening."""

import math
import statistics
import time
from dataclasses import replace

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.lowpass.calculations import calculate_butterworth as lp_butterworth
from filter_lib.shared import build_analysis, tolerance_screening
from filter_lib.shared.build_analysis import _analysis_limitations, measure_calculated_and_nominal
from filter_lib.shared.build_response import (
    build_frequency_grid,
    evaluation_ports,
    measure_circuit,
)
from filter_lib.shared.build_simulation import (
    BuildConfig,
    CircuitMeasurement,
    ScreeningCase,
    analyze_build,
    build_named_circuit,
    derive_series_resistance,
    realize_nominal_build,
)
from filter_lib.shared.build_types import BuildAnalysisCancelled
from filter_lib.shared.parsing import parse_impedance
from filter_lib.shared.tolerance_screening import summarize_cases


def test_build_simulation_facade_preserves_public_contract():
    from filter_lib.shared import build_simulation
    from filter_lib.shared.build_analysis import analyze_build as extracted_analyze_build
    from filter_lib.shared.build_types import BuildConfig as ExtractedBuildConfig
    from filter_lib.shared.nominal_realization import (
        realize_nominal_build as extracted_realize_nominal_build,
    )

    expected = {
        "BuildConfig",
        "ComponentSubstitution",
        "NominalRealization",
        "CircuitMeasurement",
        "ScreeningCase",
        "MetricSummary",
        "BuildAnalysisResult",
        "derive_series_resistance",
        "realize_nominal_build",
        "analyze_build",
    }
    assert expected <= set(build_simulation.__all__)
    assert build_simulation.BuildConfig is ExtractedBuildConfig
    assert build_simulation.analyze_build is extracted_analyze_build
    assert build_simulation.realize_nominal_build is extracted_realize_nominal_build
    assert BuildConfig().grid_points == 601


def _lp_result(order: int = 3, frequency_hz: float = 10e6) -> dict:
    capacitors, inductors, actual_order = lp_butterworth(frequency_hz, 50.0, order, "pi")
    return {
        "filter_type": "butterworth",
        "freq_hz": frequency_hz,
        "impedance": 50.0,
        "capacitors": capacitors,
        "inductors": inductors,
        "order": actual_order,
        "ripple": None,
        "topology": "pi",
    }


def _one_cap_result(value: float) -> dict:
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": [value],
        "inductors": [],
        "order": 1,
        "ripple": None,
        "topology": "pi",
    }


class TestBuildConfig:
    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"capacitor_tolerance_pct": -1}, "^Capacitor tolerance must be at least 0%"),
            ({"capacitor_tolerance_pct": True}, "^Capacitor tolerance must be at least 0%"),
            ({"inductor_tolerance_pct": 100}, "^Inductor tolerance must be .* less than 100%$"),
            ({"inductor_q": 0}, "^Inductor Q must be between"),
            ({"inductor_q": "100"}, "^Inductor Q must be between"),
            ({"capacitor_q": float("inf")}, "^Capacitor Q must be between"),
            (
                {"resonator_q": 100, "inductor_q": 200},
                "^Use either resonator Q or inductor/capacitor Q, not both$",
            ),
            (
                {"source_resistance_ohm": 0},
                "^Simulation source resistance must be positive and finite$",
            ),
            (
                {"load_resistance_ohm": float("nan")},
                "^Simulation load resistance must be positive and finite$",
            ),
            ({"sample_count": -1}, "random tolerance cases must be a whole number from 0 to 10000"),
            ({"sample_count": 10_001}, "random tolerance cases must be a whole number"),
            ({"seed": True}, "^Random seed must be a whole number$"),
            ({"grid_points": 20}, "^Frequency points must be a whole number from 51 to 5001$"),
            ({"reference_frequency_hz": 0}, "^The frequency at which the Q values apply must be"),
            ({"eseries": "E7"}, "^E-series must be E12, E24, or E96$"),
            ({"eseries": 24}, "^E-series must be E12, E24, or E96$"),
            ({"use_toroid_candidates": 1}, "use_toroid_candidates must be boolean"),
            ({"match_policy": {}}, "match_policy must be a MatchPolicy"),
        ],
    )
    def test_invalid_config_rejected(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            BuildConfig(**kwargs)

    @pytest.mark.parametrize(
        "settings",
        [
            {"inductor_q": 0.01},
            {"inductor_q": 1e9},
            {"capacitor_q": 0.01},
            {"capacitor_q": 1e9},
            {"resonator_q": 0.01},
            {"resonator_q": 1e9},
            {"sample_count": 10_000},
            {"grid_points": 51},
            {"grid_points": 5001},
        ],
        ids=lambda settings: "-".join(f"{key}={value:g}" for key, value in settings.items()),
    )
    def test_every_documented_bound_is_inclusive(self, settings):
        config = BuildConfig(**settings)

        assert {key: getattr(config, key) for key in settings} == settings

    @pytest.mark.parametrize("config", [False, 0, {}, [], "config", object()])
    @pytest.mark.parametrize("operation", [realize_nominal_build, analyze_build])
    def test_public_build_operations_reject_wrong_config_type(self, operation, config):
        with pytest.raises(ValueError, match="config must be a BuildConfig or None"):
            operation(_lp_result(), "lowpass", config)


class TestDesignResultValidation:
    @pytest.mark.parametrize(
        "category, key, value, message",
        [
            ("lowpass", "freq_hz", float("nan"), "freq_hz must be positive and finite"),
            ("lowpass", "impedance", 0.0, "impedance must be positive and finite"),
            ("bandpass", "f0", -1.0, "f0 must be positive and finite"),
            ("bandpass", "z0", float("inf"), "z0 must be positive and finite"),
        ],
    )
    def test_analysis_rejects_nonphysical_design_frequency_or_impedance(
        self, category, key, value, message
    ):
        result = (
            _lp_result()
            if category == "lowpass"
            else calculate_bandpass_filter(10e6, 1e6, 50, 2, "butterworth", "top")
        )
        result[key] = value

        with pytest.raises(ValueError, match=message):
            analyze_build(
                result, category, BuildConfig(grid_points=51, use_toroid_candidates=False)
            )

    @pytest.mark.parametrize("reference", [float("nan"), 0.0])
    def test_nonphysical_synthesis_loss_reference_is_rejected(self, reference):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 2, "butterworth", "top", qu=150)
        result["q_model"]["reference_frequency_hz"] = reference

        with pytest.raises(
            ValueError, match="q_model reference_frequency_hz must be positive and finite"
        ):
            realize_nominal_build(result, "bandpass", BuildConfig(use_toroid_candidates=False))

    @pytest.mark.parametrize("category, key", [("lowpass", "freq_hz"), ("bandpass", "f0")])
    def test_nominal_realization_rejects_a_zero_design_frequency(self, category, key):
        result = (
            _lp_result()
            if category == "lowpass"
            else calculate_bandpass_filter(10e6, 1e6, 50, 2, "butterworth", "top")
        )
        result[key] = 0.0

        with pytest.raises(ValueError, match=f"^{key} must be positive and finite$"):
            realize_nominal_build(result, category, BuildConfig(use_toroid_candidates=False))

    def test_frequency_grid_rejects_a_span_that_overflows_near_the_float_maximum(self):
        # The span's stop is finite here, but its last log-spaced point rounds past it.
        with pytest.raises(ValueError, match="^frequency span must be positive and finite$"):
            build_frequency_grid(
                {"freq_hz": 1.7976931348623157e307}, "lowpass", BuildConfig().grid_points
            )

    @pytest.mark.parametrize("points", [0, 1, True, 2.5, "601", None, 10**300])
    def test_frequency_grid_requires_an_integer_point_count(self, points):
        """1 and True divided by zero, 0 returned [], a float leaked TypeError, and
        10**300 attempted an unbounded allocation."""
        with pytest.raises(ValueError, match="^points must be an integer between 2 and "):
            build_frequency_grid({"freq_hz": 10e6}, "lowpass", points)

    @pytest.mark.parametrize("category", ["bandstop", "Lowpass", None, 1])
    def test_frequency_grid_rejects_an_unknown_category(self, category):
        """An unknown category was silently swept as a ladder around freq_hz."""
        with pytest.raises(ValueError, match="^category must be "):
            build_frequency_grid({"freq_hz": 10e6}, category, 51)

    def test_frequency_grid_requires_a_result_mapping(self):
        with pytest.raises(ValueError, match="^result must be a mapping$"):
            build_frequency_grid(None, "lowpass", 51)

    def test_two_point_grid_spans_one_decade_each_side(self):
        assert build_frequency_grid({"freq_hz": 10e6}, "highpass", 2) == pytest.approx(
            [1e6, 100e6], rel=1e-12, abs=0
        )


class TestNominalRealization:
    def test_loss_reference_requires_an_effective_q_model(self):
        config = BuildConfig(
            reference_frequency_hz=12_345,
            use_toroid_candidates=False,
            grid_points=51,
        )

        with pytest.raises(ValueError, match="Q values apply was given without any Q"):
            realize_nominal_build(_lp_result(), "lowpass", config)
        with pytest.raises(ValueError, match="Q values apply was given without any Q"):
            analyze_build(_lp_result(), "lowpass", config)

    def test_loss_reference_can_use_bandpass_synthesis_q_model(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", qu=150)
        realization = realize_nominal_build(
            result,
            "bandpass",
            BuildConfig(
                reference_frequency_hz=12e6,
                use_toroid_candidates=False,
            ),
        )

        lossy = [element for element in realization.circuit.elements if element.quality_factor]
        assert lossy
        assert all(element.loss_reference_frequency_hz == 12e6 for element in lossy)

    def test_selected_parallel_capacitor_parts_remain_physical_branches(self):
        realization = realize_nominal_build(
            _one_cap_result(318.31e-12),
            "lowpass",
            BuildConfig(use_toroid_candidates=False),
        )

        assert [element.name for element in realization.circuit.elements] == ["C1A", "C1B"]
        # abs=0: pytest.approx's default 1e-12 absolute tolerance would accept +/-1 pF.
        assert [element.value for element in realization.circuit.elements] == pytest.approx(
            [47e-12, 270e-12], rel=1e-9, abs=0
        )
        substitution = realization.substitutions[0]
        assert substitution.method == "e_series_parallel"
        assert substitution.physical_parts == pytest.approx((47e-12, 270e-12), rel=1e-9, abs=0)
        assert substitution.nominal_value == pytest.approx(317e-12, rel=1e-9, abs=0)

    def test_sub_pf_policy_refusal_is_an_explicit_exact_fallback(self):
        target = 0.5e-12
        realization = realize_nominal_build(
            _one_cap_result(target),
            "lowpass",
            BuildConfig(use_toroid_candidates=False),
        )

        substitution = realization.substitutions[0]
        assert substitution.method == "exact_fallback"
        assert substitution.status == "expert_override_required"
        assert substitution.nominal_value == target
        assert any(
            "Below 1 pF no part is chosen automatically" in warning
            for warning in substitution.warnings
        )
        assert any(
            "No standard part chosen; the simulation uses the calculated value." in warning
            for warning in realization.warnings
        )

    def test_verified_integer_turn_candidate_replaces_inductor(self):
        realization = realize_nominal_build(_lp_result(), "lowpass", BuildConfig())
        inductor_substitutions = [
            substitution for substitution in realization.substitutions if substitution.kind == "L"
        ]

        simulated = {
            element.logical_name: element.value
            for element in realization.circuit.elements
            if element.kind == "L"
        }
        assert inductor_substitutions
        for substitution in inductor_substitutions:
            assert substitution.method == "verified_toroid_integer_turns"
            assert substitution.status == "screened_candidate"
            assert isinstance(substitution.turns, int) and substitution.turns >= 1
            assert substitution.core_name is not None
            # Qualified cores accept an integer-turn error within their 5% AL tolerance.
            assert substitution.nominal_value != substitution.calculated_value
            assert substitution.nominal_value == pytest.approx(
                substitution.calculated_value, rel=0.05, abs=0
            )
            # The simulated nominal circuit uses the wound value, not the calculated one.
            assert simulated[substitution.logical_name] == substitution.nominal_value

    def test_no_verified_candidate_is_recorded_as_fallback(self):
        realization = realize_nominal_build(_lp_result(frequency_hz=1e12), "lowpass", BuildConfig())
        inductor_substitutions = [
            substitution for substitution in realization.substitutions if substitution.kind == "L"
        ]

        assert inductor_substitutions
        assert all(item.method == "exact_fallback" for item in inductor_substitutions)
        assert all(item.status == "no_verified_candidate" for item in inductor_substitutions)
        assert any(
            "No suitable toroid; the simulation uses the calculated value." in warning
            for warning in realization.warnings
        )

    def test_poor_integer_turn_match_is_an_exact_fallback(self):
        result = _lp_result()
        result["inductors"] = [10e-9]
        realization = realize_nominal_build(result, "lowpass", BuildConfig())

        substitution = next(item for item in realization.substitutions if item.kind == "L")
        assert substitution.method == "exact_fallback"
        assert substitution.status == "no_verified_candidate"
        assert substitution.nominal_value == 10e-9

    def test_loss_reference_override_does_not_change_toroid_screen_frequency(self):
        result = _lp_result(frequency_hz=30e6)
        design_reference = realize_nominal_build(
            result,
            "lowpass",
            BuildConfig(inductor_q=100),
        )
        overridden_loss_reference = realize_nominal_build(
            result,
            "lowpass",
            BuildConfig(inductor_q=100, reference_frequency_hz=3e6),
        )

        default_sub = next(item for item in design_reference.substitutions if item.kind == "L")
        override_sub = next(
            item for item in overridden_loss_reference.substitutions if item.kind == "L"
        )
        assert (override_sub.core_name, override_sub.turns, override_sub.nominal_value) == (
            default_sub.core_name,
            default_sub.turns,
            default_sub.nominal_value,
        )
        default_inductor = next(
            item for item in design_reference.circuit.elements if item.kind == "L"
        )
        override_inductor = next(
            item for item in overridden_loss_reference.circuit.elements if item.kind == "L"
        )
        assert override_inductor.series_resistance_ohm == pytest.approx(
            default_inductor.series_resistance_ohm / 10
        )

    def test_q_is_converted_to_constant_series_loss_at_reference_frequency(self):
        config = BuildConfig(
            inductor_q=80,
            capacitor_q=200,
            use_toroid_candidates=False,
        )
        realization = realize_nominal_build(_lp_result(), "lowpass", config)

        omega = 2 * math.pi * 10e6  # the design frequency is the default loss reference
        for element in realization.circuit.elements:
            assert element.loss_reference_frequency_hz == 10e6
            if element.kind == "L":
                # Series loss of an inductor with Q at the reference: R = omega * L / Q.
                assert element.quality_factor == 80
                expected = omega * element.value / 80
            else:
                # Series loss of a capacitor with Q at the reference: R = 1 / (omega * C * Q).
                assert element.quality_factor == 200
                expected = 1 / (omega * element.value * 200)
            assert element.series_resistance_ohm == pytest.approx(expected, rel=1e-12, abs=0)

    @pytest.mark.parametrize(
        "synthesis_q, config_q, limitation",
        [
            ({"qu": 150}, {}, "The resonator Qu from the design"),
            ({}, {"resonator_q": 150}, "The resonator Q you gave"),
        ],
        ids=["synthesis-qu", "build-config-resonator-q"],
    )
    def test_bandpass_complete_resonator_q_uses_one_equivalent_loss_channel(
        self, synthesis_q, config_q, limitation
    ):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", **synthesis_q)
        realization = realize_nominal_build(
            result,
            "bandpass",
            BuildConfig(use_toroid_candidates=False, **config_q),
        )

        inductors = [element for element in realization.circuit.elements if element.kind == "L"]
        capacitors = [element for element in realization.circuit.elements if element.kind == "C"]
        assert len(inductors) == 3
        for inductor in inductors:
            assert inductor.quality_factor == 150
            # Series loss of an inductor with Q at f0: R = 2*pi*f0*L / Q.
            assert inductor.series_resistance_ohm == pytest.approx(
                2 * math.pi * 10e6 * result["L_resonant"] / 150
            )
        assert all(element.quality_factor is None for element in capacitors)
        assert all(element.series_resistance_ohm == 0 for element in capacitors)
        assert any(limitation in item for item in realization.limitations)

    def test_complete_resonator_q_is_rejected_for_non_resonator_ladders(self):
        with pytest.raises(ValueError, match="only for bandpass"):
            realize_nominal_build(
                _lp_result(),
                "lowpass",
                BuildConfig(resonator_q=150, use_toroid_candidates=False),
            )

    def test_bandpass_separate_ql_qc_remain_separate_loss_channels(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", ql=200, qc=400)
        realization = realize_nominal_build(
            result,
            "bandpass",
            BuildConfig(use_toroid_candidates=False),
        )

        assert all(
            element.quality_factor == 200
            for element in realization.circuit.elements
            if element.kind == "L"
        )
        assert all(
            element.quality_factor == 400
            for element in realization.circuit.elements
            if (element.logical_name or "").startswith("CT")
        )
        assert all(
            element.quality_factor is None
            for element in realization.circuit.elements
            if element.kind == "C" and not (element.logical_name or "").startswith("CT")
        )
        assert (
            "The capacitor Q applies only to the resonator capacitors (Cp1\u2013Cp3); "
            "the coupling and end capacitors are modeled as lossless."
        ) in realization.limitations

    @pytest.mark.parametrize(
        "synthesis_q, lossy_prefix",
        [({"ql": 200}, "LT"), ({"qc": 400}, "CT")],
        ids=["inductor-ql-only", "tank-qc-only"],
    )
    def test_single_synthesis_component_q_loads_only_its_own_channel(
        self, synthesis_q, lossy_prefix
    ):
        """An omitted QL or QC is ideal: the supplied Q is not moved to the other part."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", **synthesis_q)
        realization = realize_nominal_build(
            result, "bandpass", BuildConfig(use_toroid_candidates=False)
        )

        (quality_factor,) = synthesis_q.values()
        for element in realization.circuit.elements:
            if element.logical_name.startswith(lossy_prefix):
                assert element.quality_factor == quality_factor, element.name
                assert element.series_resistance_ohm > 0, element.name
            else:
                assert element.quality_factor is None, element.name
                assert element.series_resistance_ohm == 0, element.name
        assert not any(
            "inductor and capacitor losses together" in item for item in realization.limitations
        )

    def test_explicit_build_capacitor_q_applies_to_every_bandpass_capacitor(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")
        realization = realize_nominal_build(
            result,
            "bandpass",
            BuildConfig(capacitor_q=400, use_toroid_candidates=False),
        )

        assert all(
            element.quality_factor == 400
            for element in realization.circuit.elements
            if element.kind == "C"
        )


class TestBuildAnalysis:
    def test_finite_q_lowers_nominal_peak_transducer_gain(self):
        result = _lp_result()
        lossless = analyze_build(
            result,
            "lowpass",
            BuildConfig(
                capacitor_tolerance_pct=0,
                inductor_tolerance_pct=0,
                grid_points=101,
                use_toroid_candidates=False,
            ),
        )
        lossy = analyze_build(
            result,
            "lowpass",
            BuildConfig(
                capacitor_tolerance_pct=0,
                inductor_tolerance_pct=0,
                inductor_q=40,
                capacitor_q=80,
                grid_points=101,
                use_toroid_candidates=False,
            ),
        )

        assert lossy.nominal_build.peak_transducer_gain_db < (
            lossless.nominal_build.peak_transducer_gain_db
        )

    def test_unequal_evaluation_ports_are_preserved_in_result(self):
        analysis = analyze_build(
            _lp_result(),
            "lowpass",
            BuildConfig(
                source_resistance_ohm=25,
                load_resistance_ohm=100,
                grid_points=101,
                use_toroid_candidates=False,
            ),
        )
        assert analysis.source_resistance_ohm == 25
        assert analysis.load_resistance_ohm == 100
        assert analysis.gain_metric == "transducer_power_gain_db"
        assert any(
            "the different source and load resistances apply only to this simulation" in item
            for item in analysis.limitations
        )

    def test_screening_case_order_and_seeded_samples_are_reproducible(self):
        config = BuildConfig(
            capacitor_tolerance_pct=5,
            inductor_tolerance_pct=10,
            sample_count=3,
            seed=73,
            grid_points=101,
            use_toroid_candidates=False,
        )
        first = analyze_build(_lp_result(order=3), "lowpass", config)
        second = analyze_build(_lp_result(order=3), "lowpass", config)

        expected_prefix = [
            "nominal",
            "coherent:low",
            "coherent:high",
            "one:C1A:low",
            "one:C1A:high",
            "one:C1B:low",
            "one:C1B:high",
            "one:L1:low",
            "one:L1:high",
            "one:C2A:low",
            "one:C2A:high",
            "one:C2B:low",
            "one:C2B:high",
        ]
        assert [case.case_id for case in first.cases] == expected_prefix + [
            "sample:0001",
            "sample:0002",
            "sample:0003",
        ]
        assert first.cases == second.cases
        assert first.metric_summaries == second.metric_summaries

        for case in first.cases:
            for element_name, factor in case.component_factors:
                tolerance = 0.05 if element_name.startswith("C") else 0.10
                assert 1.0 - tolerance <= factor <= 1.0 + tolerance

        # Deterministic cases apply exactly the stated bound in the stated direction.
        factors = {case.case_id: dict(case.component_factors) for case in first.cases}
        parts = ("C1A", "C1B", "L1", "C2A", "C2B")
        bound = {name: 0.10 if name == "L1" else 0.05 for name in parts}
        assert factors["nominal"] == dict.fromkeys(parts, 1.0)
        assert factors["coherent:low"] == pytest.approx({n: 1 - bound[n] for n in parts})
        assert factors["coherent:high"] == pytest.approx({n: 1 + bound[n] for n in parts})
        for name in parts:
            for direction, sign in (("low", -1), ("high", 1)):
                expected = {other: 1.0 for other in parts}
                expected[name] = 1 + sign * bound[name]
                assert factors[f"one:{name}:{direction}"] == pytest.approx(expected)

    def test_different_seed_changes_only_uniform_sample_cases(self):
        common = {
            "sample_count": 2,
            "grid_points": 101,
            "use_toroid_candidates": False,
        }
        first = analyze_build(_lp_result(), "lowpass", BuildConfig(seed=1, **common))
        second = analyze_build(_lp_result(), "lowpass", BuildConfig(seed=2, **common))

        deterministic_count = len(first.cases) - 2
        assert first.cases[:deterministic_count] == second.cases[:deterministic_count]
        assert [case.component_factors for case in first.cases[-2:]] != [
            case.component_factors for case in second.cases[-2:]
        ]

    def test_summary_and_limitations_do_not_claim_probability_or_worst_case(self):
        analysis = analyze_build(
            _lp_result(),
            "lowpass",
            BuildConfig(sample_count=2, seed=7, grid_points=101),
        )

        assert analysis.metric_summaries
        assert all(
            summary.minimum <= summary.p05 <= summary.p50 for summary in analysis.metric_summaries
        )
        assert all(
            summary.p50 <= summary.p95 <= summary.maximum for summary in analysis.metric_summaries
        )
        limitations = " ".join(analysis.limitations).lower()
        for phrase in (
            "do not guarantee the true worst case",
            "not a production-yield estimate",
            "layout",
            "srf",
            "temperature",
            "power",
        ):
            assert phrase in limitations

    def test_metric_envelopes_are_inclusive_order_statistics_of_finite_values(self):
        """Percentiles match the standard library's inclusive (linear) quantiles.

        The lost case has no half-power edges (censored) and the default -inf peak gain;
        neither may leak into a summary, but its finite worst-passband gain is included.
        """
        worst = [-3.0, -1.0, -2.5, -0.5, -4.0, -2.0, -1.5]
        peaks = [0.0, -0.1, -0.2, -0.3, -0.4, -0.5, -0.6]
        lows = [9.0, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6]
        cases = tuple(
            ScreeningCase(f"case:{i}", (), CircuitMeasurement(low, 11.0, db, False, peak))
            for i, (low, db, peak) in enumerate(zip(lows, worst, peaks))
        ) + (ScreeningCase("lost", (), CircuitMeasurement(None, None, -80.0, True)),)

        summaries = {item.metric: item for item in summarize_cases(cases, "bandpass")}

        expected_values = {
            "peak_transducer_gain_db": peaks,
            "worst_passband_db": worst + [-80.0],
            "f_low_hz": lows,
            "f_high_hz": [11.0] * 7,
            "f0_hz": [math.sqrt(low * 11.0) for low in lows],
            "bw_hz": [11.0 - low for low in lows],
        }
        assert summaries.keys() == expected_values.keys()
        for metric, values in expected_values.items():
            summary = summaries[metric]
            quantiles = statistics.quantiles(values, n=20, method="inclusive")
            assert (
                summary.minimum,
                summary.p05,
                summary.p50,
                summary.p95,
                summary.maximum,
            ) == pytest.approx(
                (min(values), quantiles[0], quantiles[9], quantiles[18], max(values)),
                rel=1e-12,
            ), metric
            assert (summary.included_cases, summary.omitted_cases) == (len(values), 8 - len(values))
            assert summary.grid_censored_cases == (0 if metric.endswith("_db") else 1)

    def test_limitations_disclose_every_omitted_or_ambiguous_case_count(self):
        """Censored, unresolved, and disconnected cases each get their own counted notice."""
        limitations = _analysis_limitations(("realization note",), "bandpass", 50.0, 50.0, 3, 2, 4)

        assert limitations[0] == "realization note"
        assert (
            "3 tolerance cases are left out of the edge, center, and bandwidth figures because "
            "a -3 dB edge fell outside the simulated frequency range; JSON output lists each case."
        ) in limitations
        assert (
            "2 tolerance cases are left out of the figures because the measurement did not "
            "converge."
        ) in limitations
        assert (
            "In 4 tolerance cases the response is above -3 dB in separate frequency ranges; "
            "their edges and bandwidth come from the range around the peak nearest the center."
        ) in limitations
        assert not any(
            "the different source and load resistances apply only to this simulation" in item
            for item in limitations
        )
        # No advice to extend the sweep: no option does that.
        assert not any("extend" in item for item in limitations)

        clean = _analysis_limitations((), "bandpass", 25.0, 100.0, 0, 0, 0)
        assert not any("tolerance cases are left out" in item for item in clean)
        assert any(
            "the different source and load resistances apply only to this simulation" in item
            for item in clean
        )

    def test_ladder_limitations_name_the_cutoff_not_a_bandwidth(self):
        """Low-pass and high-pass report a cutoff, so their notices never say bandwidth."""
        limitations = _analysis_limitations((), "highpass", 50.0, 50.0, 1, 0, 2)

        assert (
            "1 tolerance case is left out of the cutoff figures because the -3 dB point fell "
            "outside the simulated frequency range; JSON output lists each case."
        ) in limitations
        assert (
            "In 2 tolerance cases the response is above -3 dB in separate frequency ranges; "
            "their cutoff comes from the range that holds the peak."
        ) in limitations
        assert not any("bandwidth" in item for item in limitations)

    def test_lowpass_summaries_report_cutoff_without_bandpass_only_metrics(self):
        analysis = analyze_build(
            _lp_result(),
            "lowpass",
            BuildConfig(sample_count=1, grid_points=101, use_toroid_candidates=False),
        )

        metrics = {summary.metric for summary in analysis.metric_summaries}
        assert "cutoff_hz" in metrics
        assert metrics.isdisjoint({"f_low_hz", "f_high_hz", "f0_hz", "bw_hz"})

    def test_cutoff_summary_counts_and_discloses_grid_censored_cases(self):
        analysis = analyze_build(
            _lp_result(),
            "lowpass",
            BuildConfig(
                capacitor_tolerance_pct=99,
                inductor_tolerance_pct=99,
                grid_points=101,
                use_toroid_candidates=False,
            ),
        )

        cutoff = next(item for item in analysis.metric_summaries if item.metric == "cutoff_hz")
        assert cutoff.grid_censored_cases > 0
        assert cutoff.included_cases + cutoff.omitted_cases == len(analysis.cases)
        assert cutoff.maximum < 100e6
        assert any(
            "left out of the cutoff figures because the -3 dB point fell outside" in item
            for item in analysis.limitations
        )

    def test_one_sided_censored_bandpass_edge_is_excluded_from_its_summary(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 2, "butterworth", "top")
        analysis = analyze_build(
            result,
            "bandpass",
            BuildConfig(
                eseries="E96",
                capacitor_tolerance_pct=50,
                inductor_tolerance_pct=50,
                grid_points=51,
                use_toroid_candidates=False,
            ),
        )
        # All parts 50% low double the center, pushing the upper skirt past the window.
        censored = next(case for case in analysis.cases if case.case_id == "coherent:low")
        assert censored.measurement.at_grid_edge is True
        assert censored.measurement.f_low is not None and censored.measurement.f_high is None

        uncensored = [
            case.measurement.f_low for case in analysis.cases if not case.measurement.at_grid_edge
        ]
        f_low = next(item for item in analysis.metric_summaries if item.metric == "f_low_hz")
        assert f_low.included_cases == len(uncensored)
        assert f_low.grid_censored_cases == len(analysis.cases) - len(uncensored)
        assert (f_low.minimum, f_low.maximum) == (min(uncensored), max(uncensored))
        assert censored.measurement.f_low > f_low.maximum

    def test_edge_metrics_are_omitted_when_every_case_loses_the_passband(self):
        """Integer-turn toroids detune a 0.01% fractional-bandwidth design far beyond its
        passband, so no screened case has two half-power edges to summarize."""
        result = calculate_bandpass_filter(10e6, 1e3, 50, 2, "butterworth", "top")
        analysis = analyze_build(result, "bandpass", BuildConfig(eseries="E96", grid_points=51))

        assert analysis.calculated.bw == pytest.approx(1e3, rel=0.03)
        assert analysis.nominal_build.at_grid_edge is True
        assert (analysis.nominal_build.f0, analysis.nominal_build.bw) == (None, None)
        assert all(case.measurement.at_grid_edge for case in analysis.cases)
        assert [summary.metric for summary in analysis.metric_summaries] == [
            "peak_transducer_gain_db",
            "worst_passband_db",
        ]
        assert (
            f"{len(analysis.cases)} tolerance cases are left out of the edge, center, and "
            "bandwidth figures because a -3 dB edge fell outside the simulated frequency range; "
            "JSON output lists each case."
        ) in analysis.limitations

    @pytest.mark.parametrize(
        "category, result",
        [
            ("lowpass", _lp_result(order=5)),
            ("bandpass", calculate_bandpass_filter(10e6, 1e6, 50, 2, "butterworth", "top")),
        ],
    )
    def test_calculated_and_nominal_helper_matches_full_analysis(self, category, result):
        config = BuildConfig(inductor_q=60, capacitor_q=400, grid_points=201)
        analysis = analyze_build(result, category, config)

        measured = measure_calculated_and_nominal(result, category, config)

        assert measured.config == analysis.config
        assert measured.source_resistance_ohm == analysis.source_resistance_ohm
        assert measured.load_resistance_ohm == analysis.load_resistance_ohm
        assert measured.calculated == analysis.calculated
        assert measured.nominal_realization == analysis.nominal_realization
        assert measured.nominal_build == analysis.nominal_build == analysis.cases[0].measurement

    @pytest.mark.runtime_budget
    def test_default_analysis_runtime_is_bounded(self):
        started = time.perf_counter()
        analysis = analyze_build(_lp_result(order=5), "lowpass", BuildConfig())
        elapsed = time.perf_counter() - started
        assert analysis.cases
        assert elapsed < 2.0


class TestBuildAnalysisCancellation:
    """``should_cancel`` lets an interactive caller stop a long analysis between cases."""

    CONFIG = BuildConfig(sample_count=20, grid_points=51, use_toroid_candidates=False)

    def test_analysis_stops_before_the_next_case_once_the_check_flips(self, monkeypatch):
        measured_cases: list[object] = []
        real_measure = tolerance_screening.measure_circuit

        def counting_measure(*args, **kwargs):
            measured_cases.append(args[0])
            return real_measure(*args, **kwargs)

        monkeypatch.setattr(tolerance_screening, "measure_circuit", counting_measure)
        checks = 0

        def cancel_on_fourth_check() -> bool:
            nonlocal checks
            checks += 1
            return checks >= 4

        with pytest.raises(BuildAnalysisCancelled, match="^Build simulation was cancelled$"):
            analyze_build(
                _lp_result(), "lowpass", self.CONFIG, should_cancel=cancel_on_fourth_check
            )

        # Check 1 precedes the calculated measurement and checks 2-3 precede the nominal
        # case and the first corner; the fourth check fires before any further case.
        assert checks == 4
        assert len(measured_cases) == 2

    def test_an_already_cancelled_check_measures_nothing(self, monkeypatch):
        measured: list[object] = []

        def record(*args, **_kwargs):
            measured.append(args[0])

        monkeypatch.setattr(build_analysis, "measure_circuit", record)
        monkeypatch.setattr(tolerance_screening, "measure_circuit", record)

        with pytest.raises(BuildAnalysisCancelled):
            analyze_build(_lp_result(), "lowpass", self.CONFIG, should_cancel=lambda: True)

        assert measured == []

    def test_a_check_that_never_fires_changes_nothing(self):
        checks: list[int] = []

        def never_cancel() -> bool:
            checks.append(1)
            return False

        expected = analyze_build(_lp_result(), "lowpass", self.CONFIG)
        actual = analyze_build(_lp_result(), "lowpass", self.CONFIG, should_cancel=never_cancel)

        assert actual == expected
        # One check before the calculated measurement and one before every case.
        assert len(checks) == 1 + len(expected.cases)

    def test_cancellation_is_not_reported_as_an_input_error(self):
        assert not issubclass(BuildAnalysisCancelled, ValueError)

    @pytest.mark.parametrize("should_cancel", [True, "stop", 0])
    def test_a_non_callable_check_is_rejected(self, should_cancel):
        with pytest.raises(ValueError, match="should_cancel must be a zero-argument callable"):
            analyze_build(_lp_result(), "lowpass", self.CONFIG, should_cancel=should_cancel)


class TestPhysicalInputLimits:
    """Accepted Q and port values keep analysis fast; anything beyond is rejected up front.

    Before the limits, a 1e-300 source or Q took 12-35 s and a 9-resonator bandpass with a
    1e12 ohm load over a minute, although no lumped filter has such values.
    """

    @pytest.mark.runtime_budget
    @pytest.mark.parametrize(
        "settings",
        [
            {"source_resistance_ohm": 50e-6},
            {"source_resistance_ohm": 50e6},
            {"load_resistance_ohm": 50e-6},
            {"load_resistance_ohm": 50e6},
            {"inductor_q": 0.01},
            {"capacitor_q": 0.01},
            {"inductor_q": 1e9},
            {"capacitor_q": 1e9},
        ],
        ids=lambda settings: "-".join(f"{key}={value:g}" for key, value in settings.items()),
    )
    def test_lowpass_analysis_at_each_accepted_limit_is_bounded(self, settings):
        started = time.perf_counter()
        analysis = analyze_build(_lp_result(), "lowpass", BuildConfig(**settings))
        elapsed = time.perf_counter() - started

        assert analysis.cases
        assert elapsed < 5.0

    @pytest.mark.runtime_budget
    @pytest.mark.parametrize("port", ["source_resistance_ohm", "load_resistance_ohm"])
    def test_bandpass_measurement_at_the_high_impedance_limit_is_bounded(self, port):
        """1e6 times the design impedance is the last decade that avoids the slow exact path."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")
        config = BuildConfig(**{port: 50e6}, use_toroid_candidates=False)

        started = time.perf_counter()
        measured = measure_calculated_and_nominal(result, "bandpass", config)
        elapsed = time.perf_counter() - started

        assert math.isfinite(measured.calculated.peak_transducer_gain_db)
        assert elapsed < 5.0

    @pytest.mark.parametrize(
        ("category", "port", "value", "message"),
        [
            (
                "lowpass",
                "load_resistance_ohm",
                50e6 * (1 + 1e-9),
                "^Simulation load resistance 5e\\+07 ohm is outside the supported range 5e-05 to 5e\\+07 ohm "
                "\\(1e-06 to 1e\\+06 times the 50 ohm design impedance\\)$",
            ),
            (
                "lowpass",
                "source_resistance_ohm",
                50e-6 * (1 - 1e-9),
                "^Simulation source resistance 5e-05 ohm is outside the supported range",
            ),
            (
                "lowpass",
                "load_resistance_ohm",
                1e300,
                "^Simulation load resistance 1e\\+300 ohm is outside",
            ),
            # The range follows the design impedance: 1 ohm is inside for 50 ohm, not for 1 Mohm.
            (
                "bandpass",
                "source_resistance_ohm",
                0.5,
                "^Simulation source resistance 0.5 ohm is outside the supported range 1 to 1e\\+12 ohm "
                "\\(1e-06 to 1e\\+06 times the 1e\\+06 ohm design impedance\\)$",
            ),
        ],
        ids=["load-above", "source-below", "load-1e300", "relative-to-bandpass-z0"],
    )
    def test_ports_beyond_the_ratio_limit_are_rejected(self, category, port, value, message):
        result = (
            _lp_result()
            if category == "lowpass"
            else calculate_bandpass_filter(10e6, 0.5e6, 1e6, 3, "butterworth", "top")
        )

        with pytest.raises(ValueError, match=message):
            evaluation_ports(result, category, BuildConfig(**{port: value}))

    @pytest.mark.parametrize(
        ("design", "typed"),
        [(50.0, "50M"), (3.3, "3.3M"), (75.0, "0.000075"), (0.1, "100k")],
    )
    def test_ratio_limit_is_inclusive_for_typed_boundary_values(self, design, typed):
        """A limit value typed as a decimal passes although binary64 rounds the ratio."""
        port = parse_impedance(typed)
        result = {**_lp_result(), "impedance": design}

        assert evaluation_ports(result, "lowpass", BuildConfig(load_resistance_ohm=port)) == (
            design,
            port,
        )

    @pytest.mark.parametrize(
        ("name", "label"),
        [
            ("inductor_q", "Inductor Q"),
            ("capacitor_q", "Capacitor Q"),
            ("resonator_q", "Resonator Q"),
        ],
    )
    @pytest.mark.parametrize(
        "value", [math.nextafter(0.01, 0.0), math.nextafter(1e9, math.inf), 1e-300, True]
    )
    def test_quality_factors_outside_the_range_are_rejected(self, name, label, value):
        with pytest.raises(ValueError, match=f"^{label} must be between 0.01 and 1e9$"):
            BuildConfig(**{name: value})

    def test_gain_below_binary64_range_names_the_evaluation_inputs(self):
        """The Q range keeps BuildConfig away from underflow; a circuit built directly can
        still reach it, and the message names the inputs instead of the old
        "response refinement requires finite dB values"."""
        result = _lp_result()
        circuit = build_named_circuit(result, "lowpass")
        lossy = replace(
            circuit,
            elements=tuple(
                replace(element, series_resistance_ohm=1e301, quality_factor=1e-300)
                if element.kind == "L"
                else element
                for element in circuit.elements
            ),
        )

        with pytest.raises(ValueError) as raised:
            measure_circuit(
                lossy, result, "lowpass", build_frequency_grid(result, "lowpass", 51), 50.0, 50.0
            )

        message = str(raised.value)
        assert message.startswith("The simulated transducer gain at ")
        assert "underflows binary64 (below about 4.9e-324, or -3233 dB)" in message
        assert message.endswith(
            "Simulation inputs: source resistance 50 \u03a9, load resistance 50 \u03a9, lowest "
            "inductor Q 1e-300; use less extreme component Q or port resistances"
        )


class TestBandpassMeasurement:
    """Calculated-circuit measurements that every build analysis starts from."""

    @staticmethod
    def _measure_calculated(result: dict):
        grid = build_frequency_grid(result, "bandpass", BuildConfig().grid_points)
        circuit = build_named_circuit(result, "bandpass")
        return measure_circuit(circuit, result, "bandpass", grid, result["z0"], result["z0"])

    def test_default_grid_resolves_very_narrow_bandpass_bandwidth(self):
        result = calculate_bandpass_filter(10e6, 1e3, 50, 3, "butterworth", "top")

        measurement = self._measure_calculated(result)

        assert measurement.bw == pytest.approx(1e3, rel=0.03)
        assert measurement.at_grid_edge is False

    def test_measurement_anchors_the_region_containing_the_requested_center(self):
        """A 3 dB-ripple Chebyshev response also crosses half power below the passband;
        the reported edges must come from the region around the requested center."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "chebyshev", "top", ripple_db=3.0)

        measurement = self._measure_calculated(result)

        assert len(measurement.threshold_regions) > 1  # precondition for this regression
        assert measurement.center_in_selected_region is True
        assert measurement.f_low < result["f0"] < measurement.f_high
        assert measurement.f0 == pytest.approx(result["f0"], rel=0.03)


class TestSeriesLossConversion:
    @pytest.mark.parametrize(
        "kind, value, quality_factor, frequency, message",
        [
            ("R", 1e-6, 100, 10e6, "kind must be 'C' or 'L'"),
            (None, 1e-6, 100, 10e6, "kind must be 'C' or 'L'"),
            ("L", 0.0, 100, 10e6, "value must be positive and finite"),
            ("L", float("nan"), 100, 10e6, "value must be positive and finite"),
            ("C", 1e-9, True, 10e6, "quality_factor must be positive and finite"),
            ("C", 1e-9, -5, 10e6, "quality_factor must be positive and finite"),
            ("L", 1e-6, 100, float("inf"), "reference_frequency_hz must be positive and finite"),
            # exp() overflow and underflow of the derived resistance.
            ("L", 1e300, 1e-300, 1e300, "outside the finite numeric range"),
            ("C", 1e300, 1e300, 1e300, "outside the finite numeric range"),
        ],
    )
    def test_invalid_inputs_and_unrepresentable_results_are_rejected(
        self, kind, value, quality_factor, frequency, message
    ):
        with pytest.raises(ValueError, match=message):
            derive_series_resistance(kind, value, quality_factor, frequency)


def test_loss_formula_reference_values():
    frequency = 10e6
    assert derive_series_resistance("L", 1e-6, 100, frequency) == pytest.approx(
        2 * math.pi * frequency * 1e-6 / 100
    )
    assert derive_series_resistance("C", 100e-12, 200, frequency) == pytest.approx(
        1 / (2 * math.pi * frequency * 100e-12 * 200)
    )
