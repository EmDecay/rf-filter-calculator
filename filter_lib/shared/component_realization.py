"""Calculated-to-physical capacitor and inductor substitution helpers."""

from dataclasses import replace

from .build_loss_models import _with_loss
from .build_types import BuildConfig, ComponentSubstitution
from .circuit_model import CircuitElement
from .eseries import match_component
from .toroid_selection import find_core_candidates


def _realize_capacitor(
    element: CircuitElement,
    config: BuildConfig,
    quality_factor: float | None,
    reference_frequency_hz: float,
) -> tuple[list[CircuitElement], ComponentSubstitution, list[str]]:
    match = match_component(
        element.value,
        config.eseries,
        parallel_mode="additive",
        policy=config.match_policy,
    )
    selected = match.selected_components
    if selected is None:
        warnings = list(match.warnings)
        warnings.append(
            f"{element.name}: exact calculated value retained and is not a selected physical part."
        )
        physical = [_with_loss(element, quality_factor, reference_frequency_hz)]
        substitution = ComponentSubstitution(
            logical_name=element.name,
            kind="C",
            calculated_value=element.value,
            nominal_value=element.value,
            physical_parts=(element.value,),
            method="exact_fallback",
            status=match.status,
            warnings=tuple(warnings),
        )
        return physical, substitution, warnings

    suffixes = (
        ("",) if len(selected) == 1 else tuple(chr(ord("A") + i) for i in range(len(selected)))
    )
    physical = [
        _with_loss(
            replace(
                element,
                name=f"{element.name}{suffix}",
                value=value,
                logical_name=element.name,
                series_resistance_ohm=0.0,
                quality_factor=None,
                loss_reference_frequency_hz=None,
            ),
            quality_factor,
            reference_frequency_hz,
        )
        for suffix, value in zip(suffixes, selected)
    ]
    method = "e_series_parallel" if len(selected) > 1 else "e_series_single"
    substitution = ComponentSubstitution(
        logical_name=element.name,
        kind="C",
        calculated_value=element.value,
        nominal_value=sum(selected),
        physical_parts=tuple(selected),
        method=method,
        status=match.status,
        warnings=match.warnings,
    )
    return physical, substitution, list(match.warnings)


def _realize_inductor(
    element: CircuitElement,
    config: BuildConfig,
    quality_factor: float | None,
    design_frequency_hz: float,
    loss_reference_frequency_hz: float,
) -> tuple[CircuitElement, ComponentSubstitution, list[str]]:
    candidates = (
        find_core_candidates(element.value, design_frequency_hz, top_n=1)
        if config.use_toroid_candidates
        else []
    )
    if candidates:
        candidate = candidates[0]
        value = candidate.winding.l_actual_h
        realized = replace(
            element,
            value=value,
            logical_name=element.name,
            series_resistance_ohm=0.0,
            quality_factor=None,
            loss_reference_frequency_hz=None,
        )
        realized = _with_loss(realized, quality_factor, loss_reference_frequency_hz)
        substitution = ComponentSubstitution(
            logical_name=element.name,
            kind="L",
            calculated_value=element.value,
            nominal_value=value,
            physical_parts=(value,),
            method="verified_toroid_integer_turns",
            status=candidate.candidate_status,
            warnings=candidate.warnings,
            core_name=candidate.core.name,
            turns=candidate.winding.n_turns,
        )
        warnings = [f"{element.name}: {warning}" for warning in candidate.warnings]
        return realized, substitution, warnings

    if config.use_toroid_candidates:
        status = "no_verified_candidate"
        warning = (
            f"{element.name}: No verified integer-turn toroid candidate was available; "
            "the exact calculated inductance is an explicit fallback."
        )
    else:
        status = "candidate_screen_disabled"
        warning = (
            f"{element.name}: toroid candidate screening was disabled; the exact "
            "calculated inductance is an explicit fallback."
        )
    realized = _with_loss(element, quality_factor, loss_reference_frequency_hz)
    substitution = ComponentSubstitution(
        logical_name=element.name,
        kind="L",
        calculated_value=element.value,
        nominal_value=element.value,
        physical_parts=(element.value,),
        method="exact_fallback",
        status=status,
        warnings=(warning,),
    )
    return realized, substitution, [warning]
