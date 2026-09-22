"""Build-realization analysis: physical parts, losses, and tolerance screening."""

import math
import time

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.lowpass.calculations import calculate_butterworth as lp_butterworth
from filter_lib.shared.build_analysis import measure_calculated_and_nominal
from filter_lib.shared.build_response import build_frequency_grid, measure_circuit
from filter_lib.shared.build_simulation import (
    BuildConfig,
    analyze_build,
    build_named_circuit,
    derive_series_resistance,
    realize_nominal_build,
)


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
            ({"capacitor_tolerance_pct": -1}, "capacitor_tolerance_pct"),
            ({"capacitor_tolerance_pct": True}, "capacitor_tolerance_pct"),
            ({"inductor_tolerance_pct": 100}, "inductor_tolerance_pct"),
            ({"inductor_q": 0}, "inductor_q"),
            ({"inductor_q": "100"}, "inductor_q"),
            ({"capacitor_q": float("inf")}, "capacitor_q"),
            ({"resonator_q": 100, "inductor_q": 200}, "mutually exclusive"),
            ({"source_resistance_ohm": 0}, "source_resistance_ohm"),
            ({"load_resistance_ohm": float("nan")}, "load_resistance_ohm"),
            ({"sample_count": -1}, "sample_count"),
            ({"sample_count": 10_001}, "sample_count"),
            ({"seed": True}, "seed"),
            ({"grid_points": 20}, "grid_points"),
            ({"reference_frequency_hz": 0}, "reference_frequency_hz"),
            ({"eseries": "E7"}, "eseries"),
            ({"eseries": 24}, "eseries"),
            ({"use_toroid_candidates": 1}, "use_toroid_candidates must be boolean"),
            ({"match_policy": {}}, "match_policy must be a MatchPolicy"),
        ],
    )
    def test_invalid_config_rejected(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            BuildConfig(**kwargs)

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

    def test_nonphysical_synthesis_loss_reference_is_rejected(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 2, "butterworth", "top", qu=150)
        result["q_model"]["reference_frequency_hz"] = float("nan")

        with pytest.raises(
            ValueError, match="q_model reference_frequency_hz must be positive and finite"
        ):
            realize_nominal_build(result, "bandpass", BuildConfig(use_toroid_candidates=False))


class TestNominalRealization:
    def test_loss_reference_requires_an_effective_q_model(self):
        config = BuildConfig(
            reference_frequency_hz=12_345,
            use_toroid_candidates=False,
            grid_points=51,
        )

        with pytest.raises(ValueError, match="reference_frequency_hz requires.*Q"):
            realize_nominal_build(_lp_result(), "lowpass", config)
        with pytest.raises(ValueError, match="reference_frequency_hz requires.*Q"):
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
        assert any("automatic-selection floor" in warning for warning in substitution.warnings)
        assert any("not a selected physical part" in warning for warning in realization.warnings)

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
            "No verified integer-turn toroid candidate" in warning
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

        for element in realization.circuit.elements:
            expected = derive_series_resistance(
                element.kind,
                element.value,
                element.quality_factor,
                element.loss_reference_frequency_hz,
            )
            assert element.series_resistance_ohm == pytest.approx(expected)
            assert element.series_resistance_ohm > 0

    @pytest.mark.parametrize(
        "synthesis_q, config_q, limitation",
        [
            ({"qu": 150}, {}, "complete resonator Q from synthesis"),
            ({}, {"resonator_q": 150}, "supplied complete resonator Q"),
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
        assert any("only to CT elements" in item for item in realization.limitations)

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
            "does not imply unequal-termination synthesis" in item for item in analysis.limitations
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
            "not a guaranteed worst case",
            "not a probability",
            "layout",
            "srf",
            "temperature",
            "power",
        ):
            assert phrase in limitations

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
        assert any("grid-boundary-censored" in item for item in analysis.limitations)

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
            f"Edge/cutoff summaries omit {len(analysis.cases)} grid-boundary-censored "
            "screening cases; inspect their case records before extending the sweep."
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
