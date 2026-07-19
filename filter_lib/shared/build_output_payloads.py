"""Machine-readable payloads for realized-build analysis."""

from typing import Any

from .build_output_model import build_model_payload, realization_summary
from .build_types import (
    BuildAnalysisResult,
    CircuitMeasurement,
    ComponentSubstitution,
)
from .circuit_model import CircuitElement
from .strict_json import validate_finite_tree


def _measurement_payload(
    measurement: CircuitMeasurement, category: str | None = None
) -> dict[str, Any]:
    """Return one response measurement without inventing missing skirt values."""
    payload = {
        "f_low_hz": measurement.f_low,
        "f_high_hz": measurement.f_high,
        "f0_hz": measurement.f0,
        "bandwidth_hz": measurement.bw,
        "worst_design_passband_gain_db": measurement.worst_passband_db,
        "peak_transducer_gain_db": measurement.peak_transducer_gain_db,
        "edge_at_simulation_grid_boundary": measurement.at_grid_edge,
    }
    if category == "lowpass":
        payload["cutoff_hz"] = measurement.f_high
    elif category == "highpass":
        payload["cutoff_hz"] = measurement.f_low
    return payload


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
        "core_name": substitution.core_name,
        "turns": substitution.turns,
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


def _summary_payload(summary) -> dict[str, Any]:
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
    }


def build_analysis_fields(result: dict, analysis: BuildAnalysisResult) -> dict[str, Any]:
    """Build category-parity JSON fields attached by ``--sim-build``."""
    config = analysis.config
    fields: dict[str, Any] = {
        "target": _target_payload(result, analysis.category),
        "simulated": {
            "realization": "calculated_exact_values",
            "measurement": _measurement_payload(analysis.calculated, analysis.category),
        },
        "nominal_build": {
            **realization_summary(analysis.nominal_realization),
            "measurement": _measurement_payload(analysis.nominal_build, analysis.category),
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
            "capacitor_tolerance_pct": config.capacitor_tolerance_pct,
            "inductor_tolerance_pct": config.inductor_tolerance_pct,
            "sample_count": config.sample_count,
            "seed": config.seed,
            "grid_points": config.grid_points,
            "cases": [
                {
                    "case_id": case.case_id,
                    "component_factors": [
                        {"physical_element_name": name, "factor": factor}
                        for name, factor in case.component_factors
                    ],
                    "measurement": _measurement_payload(case.measurement, analysis.category),
                }
                for case in analysis.cases
            ],
            "metric_summaries": [
                _summary_payload(summary) for summary in analysis.metric_summaries
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
