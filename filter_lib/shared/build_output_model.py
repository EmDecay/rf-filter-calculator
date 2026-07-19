"""Truthful realization and loss-model summaries for build-analysis output."""

from typing import Any

from .build_types import BuildAnalysisResult, NominalRealization


def realization_summary(realization: NominalRealization) -> dict[str, Any]:
    """Describe whether nominal selection required calculated-value fallbacks."""
    fallback_elements = [
        item.logical_name for item in realization.substitutions if item.method == "exact_fallback"
    ]
    realization_name = (
        "selected_nominal_parts_and_calculated_exact_fallbacks"
        if fallback_elements
        else "selected_nominal_physical_parts"
    )
    return {
        "realization": realization_name,
        "has_calculated_exact_fallbacks": bool(fallback_elements),
        "calculated_exact_fallback_elements": fallback_elements,
    }


def _effective_loss_model(result: dict, analysis: BuildAnalysisResult) -> dict[str, Any]:
    config = analysis.config
    physical_losses = [
        {
            "physical_element_name": element.name,
            "logical_name": element.logical_name,
            "kind": element.kind,
            "quality_factor_at_reference": element.quality_factor,
            "series_resistance_ohm": element.series_resistance_ohm,
            "reference_frequency_hz": element.loss_reference_frequency_hz,
        }
        for element in analysis.nominal_realization.circuit.elements
        if element.series_resistance_ohm > 0
    ]
    has_config_q = any(
        value is not None for value in (config.inductor_q, config.capacitor_q, config.resonator_q)
    )
    synthesis_q_model = result.get("q_model") if analysis.category == "bandpass" else None
    has_synthesis_q = isinstance(synthesis_q_model, dict) and any(
        synthesis_q_model.get(name) is not None
        for name in ("inductor_ql", "capacitor_qc", "resonator_qu")
    )
    source = (
        "explicit_build_config_q"
        if has_config_q
        else "bandpass_synthesis_q_model"
        if has_synthesis_q
        else "none"
    )
    return {
        "is_lossless": not physical_losses,
        "source": source,
        "synthesis_q_model": synthesis_q_model,
        "synthesis_q_model_applied": source == "bandpass_synthesis_q_model",
        "physical_elements_with_series_loss": physical_losses,
    }


def build_model_payload(result: dict, analysis: BuildAnalysisResult) -> dict[str, Any]:
    """Report configured controls separately from what realization actually used."""
    config = analysis.config
    toroid_elements = [
        item.logical_name
        for item in analysis.nominal_realization.substitutions
        if item.method == "verified_toroid_integer_turns"
    ]
    return {
        "eseries": config.eseries,
        "inductor_q": config.inductor_q,
        "capacitor_q": config.capacitor_q,
        "resonator_q": config.resonator_q,
        "q_fields_semantics": "explicit_build_config_overrides",
        "effective_loss_model": _effective_loss_model(result, analysis),
        "reference_frequency_hz": config.reference_frequency_hz,
        "toroid_candidate_screen_enabled": config.use_toroid_candidates,
        "verified_toroid_candidate_used": bool(toroid_elements),
        "verified_toroid_elements": toroid_elements,
        "uses_verified_toroid_candidates": bool(toroid_elements),
        "match_policy": config.match_policy.as_dict(),
    }
