"""Build-realization analysis: physical parts, losses, and tolerance screening."""

import math
import time

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.lowpass.calculations import calculate_butterworth as lp_butterworth
from filter_lib.shared.build_simulation import (
    BuildConfig,
    analyze_build,
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
        assert [element.value for element in realization.circuit.elements] == pytest.approx(
            [47e-12, 270e-12]
        )
        substitution = realization.substitutions[0]
        assert substitution.method == "e_series_parallel"
        assert substitution.physical_parts == pytest.approx((47e-12, 270e-12))
        assert substitution.nominal_value == pytest.approx(317e-12)

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

        assert inductor_substitutions
        for substitution in inductor_substitutions:
            assert substitution.method == "verified_toroid_integer_turns"
            assert isinstance(substitution.turns, int) and substitution.turns >= 1
            assert substitution.core_name is not None
            assert substitution.nominal_value > 0

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

    def test_bandpass_complete_resonator_q_uses_one_equivalent_loss_channel(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", qu=150)
        realization = realize_nominal_build(
            result,
            "bandpass",
            BuildConfig(use_toroid_candidates=False),
        )

        inductors = [element for element in realization.circuit.elements if element.kind == "L"]
        capacitors = [element for element in realization.circuit.elements if element.kind == "C"]
        assert all(element.quality_factor == 150 for element in inductors)
        assert all(element.quality_factor is None for element in capacitors)
        assert any("complete resonator Q" in limitation for limitation in realization.limitations)

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

    def test_default_grid_resolves_very_narrow_bandpass_bandwidth(self):
        result = calculate_bandpass_filter(
            10e6,
            1e3,
            50,
            3,
            "butterworth",
            "top",
        )
        analysis = analyze_build(
            result,
            "bandpass",
            BuildConfig(
                capacitor_tolerance_pct=0,
                inductor_tolerance_pct=0,
                use_toroid_candidates=False,
            ),
        )

        assert analysis.calculated.bw == pytest.approx(1e3, rel=0.03)
        assert analysis.calculated.at_grid_edge is False

    def test_cutoff_summary_excludes_and_counts_grid_censored_cases(self):
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

    def test_default_analysis_runtime_is_bounded(self):
        started = time.perf_counter()
        analysis = analyze_build(_lp_result(order=5), "lowpass", BuildConfig())
        elapsed = time.perf_counter() - started
        assert analysis.cases
        assert elapsed < 2.0


def test_loss_formula_reference_values():
    frequency = 10e6
    assert derive_series_resistance("L", 1e-6, 100, frequency) == pytest.approx(
        2 * math.pi * frequency * 1e-6 / 100
    )
    assert derive_series_resistance("C", 100e-12, 200, frequency) == pytest.approx(
        1 / (2 * math.pi * frequency * 100e-12 * 200)
    )
