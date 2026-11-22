"""Machine-readable payloads for realized-build analysis."""

from typing import Any

from .build_output_model import build_model_payload, realization_summary
from .build_types import (
    DEFAULT_INDUCTOR_TOLERANCE_PCT,
    BuildAnalysisResult,
    CaseTuning,
    CircuitMeasurement,
    ComponentSubstitution,
    TrimmerSetting,
    TrimmerUse,
)
from .circuit_model import CircuitElement
from .response_refinement import (
    FREQUENCY_TOLERANCE_FRACTION,
    GAIN_TOLERANCE_DB,
    MAX_REFINEMENT_PASSES,
)
from .strict_json import validate_finite_tree


def _measurement_payload(
    measurement: CircuitMeasurement,
    category: str | None = None,
    qualified_range: tuple[float, float] | None = None,
    *,
    chosen_parts: bool = False,
) -> dict[str, Any]:
    """Return one response measurement without inventing missing skirt values.

    ``model`` says whether it is of the ideal circuit or the chosen parts; a chosen-parts
    measurement lists the landmarks outside the build's qualified range, which are
    predicted with the parasitic model, not qualified.
    """
    payload: dict[str, Any] = {
        "model": "chosen_parts" if chosen_parts else "ideal",
        "f_low_hz": measurement.f_low,
        "f_high_hz": measurement.f_high,
        "f0_hz": measurement.f0,
        "bandwidth_hz": measurement.bw,
        "worst_design_passband_gain_db": measurement.worst_passband_db,
        "peak_transducer_gain_db": measurement.peak_transducer_gain_db,
        "edge_at_simulation_grid_boundary": measurement.at_grid_edge,
        "measurement_converged": measurement.measurement_converged,
        "response_evaluations": measurement.response_evaluations,
        "peak_frequency_hz": measurement.peak_frequency_hz,
        "reference_peak_frequency_hz": measurement.reference_peak_frequency_hz,
        "reference_peak_gain_db": measurement.reference_peak_gain_db,
        "half_power_threshold_db": measurement.threshold_db,
        "connected_region_count": len(measurement.threshold_regions),
        "half_power_regions": [
            {"f_low_hz": low, "f_high_hz": high} for low, high in measurement.threshold_regions
        ],
        "selected_region_index": measurement.selected_region_index,
        "center_in_selected_region": measurement.center_in_selected_region,
    }
    if category in ("lowpass", "highpass"):
        payload["cutoff_hz"] = measurement.ladder_cutoff(category)
    if chosen_parts and category is not None:
        payload["outside_qualified_range"] = list(
            measurement.outside_range(category, qualified_range)
        )
    return payload


def trimmer_setting_payload(setting: TrimmerSetting) -> dict[str, Any]:
    """One tank's trimmer setting (capacitances at the tank frequency, in farads)."""
    return {
        "tank": setting.tank,
        "required_capacitance_f": setting.required_f,
        "setting_f": setting.setting_f,
        "effective_capacitance_f": setting.effective_f,
        "in_range": setting.in_range,
    }


def _trimmer_payload(trimmer: TrimmerUse | None) -> dict[str, Any] | None:
    if trimmer is None:
        return None
    return {
        "maker": trimmer.maker,
        "family": trimmer.family,
        "part_numbers": list(trimmer.part_numbers),
        "series_inductance_h": trimmer.series_inductance_h,
        "series_inductance_basis": (
            "assumed" if trimmer.series_inductance_assumed else "bound_from_minimum_srf"
        ),
        "range_at_tuning_frequency_f": list(trimmer.range_f),
        "tuning_frequency_hz": trimmer.tuning_frequency_hz,
        "nominal_setting": trimmer_setting_payload(trimmer.setting),
    }


def _case_tuning_payload(
    tuning: CaseTuning | None, category: str, qualified_range: tuple[float, float] | None
) -> dict[str, Any] | None:
    if tuning is None:
        return None
    return {
        "settings": [trimmer_setting_payload(setting) for setting in tuning.settings],
        "all_trimmers_in_range": tuning.all_in_range,
        "measurement": _measurement_payload(
            tuning.measurement, category, qualified_range, chosen_parts=True
        ),
    }


def _substitution_payload(substitution: ComponentSubstitution) -> dict[str, Any]:
    """Return an auditable calculated-to-physical substitution record."""
    return {
        "logical_name": substitution.logical_name,
        "kind": substitution.kind,
        "calculated_value_si": substitution.calculated_value,
        "nominal_value_si": substitution.nominal_value,
        "physical_parts_si": list(substitution.physical_parts),
        "method": substitution.method,
        "status": substitution.status,
        "inductor_kind": substitution.inductor_kind,
        "part_name": substitution.part_name,
        "core_name": substitution.core_name,
        "turns": substitution.turns,
        "wire_awg": substitution.wire_awg,
        "wire_length_mm": substitution.wire_length_mm,
        "stray_capacitance_f": substitution.stray_capacitance_f,
        "self_capacitance_f": substitution.self_capacitance_f,
        "tolerance_pct": substitution.tolerance_pct,
        "own_tolerance": substitution.own_tolerance,
        "trimmer": _trimmer_payload(substitution.trimmer),
        "warnings": list(substitution.warnings),
    }


def _element_payload(element: CircuitElement) -> dict[str, Any]:
    """Return the exact physical branch consumed by simulation and SPICE."""
    return {
        "name": element.name,
        "logical_name": element.logical_name,
        "kind": element.kind,
        "node_1": element.node1,
        "node_2": element.node2,
        "value_si": element.value,
        "series_resistance_ohm": element.series_resistance_ohm,
        "quality_factor_at_reference": element.quality_factor,
        "loss_reference_frequency_hz": element.loss_reference_frequency_hz,
        "tolerance_fraction": element.tolerance,
        "fixed": element.fixed,
        "series_inductance_h": element.series_inductance_h,
    }


def _target_payload(result: dict, category: str) -> dict[str, Any]:
    """Describe requested synthesis targets separately from simulated results."""
    if category == "bandpass":
        requested = result.get("requested_parameters", {})
        frequency_specification = requested.get("frequency_specification", "center_and_bandwidth")
        return {
            "category": category,
            "response_type": result["filter_type"],
            "order": result["n_resonators"],
            "frequency_specification": frequency_specification,
            "center_frequency_hz": result["f0"],
            "bandwidth_hz": result["bw"],
            "f_low_hz": requested.get("f_low_hz", result["f_low"]),
            "f_high_hz": requested.get("f_high_hz", result["f_high"]),
            "design_impedance_ohm": result["z0"],
            "equal_termination_synthesis": True,
            "response_validation_status": result.get("response_validation_status"),
        }
    return {
        "category": category,
        "response_type": result["filter_type"],
        "order": result["order"],
        "cutoff_frequency_hz": result["freq_hz"],
        "design_impedance_ohm": result["impedance"],
        "equal_termination_synthesis": True,
    }


def _summary_payload(summary, outside: frozenset[str] = frozenset()) -> dict[str, Any]:
    return {
        "metric": summary.metric,
        "minimum": summary.minimum,
        "p05": summary.p05,
        "p50": summary.p50,
        "p95": summary.p95,
        "maximum": summary.maximum,
        "included_cases": summary.included_cases,
        "omitted_cases": summary.omitted_cases,
        "grid_censored_cases": summary.grid_censored_cases,
        "unresolved_cases": summary.unresolved_cases,
        # An included case rests on a frequency outside the qualified range.
        "outside_qualified_range": summary.metric in outside,
    }


def build_analysis_fields(result: dict, analysis: BuildAnalysisResult) -> dict[str, Any]:
    """Build category-parity JSON fields attached by ``--sim-build``."""
    config = analysis.config
    category = analysis.category
    qualified = analysis.qualified_range_hz
    fields: dict[str, Any] = {
        "target": _target_payload(result, category),
        "simulated": {
            "realization": "calculated_exact_values",
            "measurement": _measurement_payload(analysis.calculated, category),
        },
        "nominal_build": {
            **realization_summary(analysis.nominal_realization),
            "qualified_range_hz": None if qualified is None else list(qualified),
            "passband_top_hz": analysis.passband_top_hz,
            "peak_range_hz": None
            if analysis.peak_range_hz is None
            else list(analysis.peak_range_hz),
            "measurement": _measurement_payload(
                analysis.nominal_build, category, qualified, chosen_parts=True
            ),
            "substitutions": [
                _substitution_payload(item) for item in analysis.nominal_realization.substitutions
            ],
            "circuit_elements": [
                _element_payload(element)
                for element in analysis.nominal_realization.circuit.elements
            ],
            "warnings": list(analysis.nominal_realization.warnings),
            "limitations": list(analysis.nominal_realization.limitations),
        },
        "tolerance_analysis": {
            "method": "deterministic_corners_plus_seeded_uniform_screening",
            # Each part varies by its own tolerance (circuit_elements[].tolerance_fraction).
            "tolerance_source": "each_part",
            "capacitor_grade": analysis.match_policy.grade,
            "capacitor_tolerance_override_pct": analysis.match_policy.tolerance_override_pct,
            # The entered tolerance, used for every inductor; null when none was entered,
            # and then each chip inductor uses its own (substitutions[].tolerance_pct) and
            # toroid windings and calculated values the fallback.
            "inductor_tolerance_pct": config.inductor_tolerance_pct,
            "inductor_fallback_tolerance_pct": DEFAULT_INDUCTOR_TOLERANCE_PCT,
            "sample_count": config.sample_count,
            "seed": config.seed,
            "grid_points": config.grid_points,
            "unresolved_cases": sum(
                not case.measurement.measurement_converged for case in analysis.cases
            ),
            "disconnected_region_cases": sum(
                len(case.measurement.threshold_regions) > 1 for case in analysis.cases
            ),
            "measurement_policy": {
                "method": "mesh_doubling_with_evaluated_extrema_and_crossings",
                "grid_points_are_initial": True,
                "gain_tolerance_db": GAIN_TOLERANCE_DB,
                "frequency_tolerance_fraction": FREQUENCY_TOLERANCE_FRACTION,
                "frequency_tolerance_reference": "bandwidth"
                if category == "bandpass"
                else "cutoff",
                "max_refinement_passes": MAX_REFINEMENT_PASSES,
                "convergence_is_not_a_mathematical_bound": True,
            },
            "cases": [
                {
                    "case_id": case.case_id,
                    "component_factors": [
                        {"physical_element_name": name, "factor": factor}
                        for name, factor in case.component_factors
                    ],
                    # With trimmers: every trimmer at its nominal setting (untuned).
                    "measurement": _measurement_payload(
                        case.measurement, category, qualified, chosen_parts=True
                    ),
                    "tuning": _case_tuning_payload(case.tuning, category, qualified),
                }
                for case in analysis.cases
            ],
            "metric_summaries": [
                _summary_payload(summary, analysis.metrics_outside_qualified_range())
                for summary in analysis.metric_summaries
            ],
            # Each trimmer is retuned in every case; the spread after retuning follows.
            "trimmers_retuned_in_each_case": analysis.has_trimmers,
            "trimmer_out_of_range_cases": analysis.out_of_range_cases(),
            "tuned_metric_summaries": [
                _summary_payload(summary, analysis.metrics_outside_qualified_range(tuned=True))
                for summary in analysis.tuned_metric_summaries
            ],
            "limitations": list(analysis.limitations),
        },
        "evaluation": {
            "source_resistance_ohm": analysis.source_resistance_ohm,
            "load_resistance_ohm": analysis.load_resistance_ohm,
            "gain_metric": analysis.gain_metric,
            "unequal_loads_change_evaluation_not_synthesis": True,
        },
        "build_model": build_model_payload(result, analysis),
    }
    validate_finite_tree(fields)
    return fields
