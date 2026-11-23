"""Calculated-to-physical capacitor and inductor substitution helpers."""

from dataclasses import replace

from .build_loss_models import _with_loss
from .build_types import DEFAULT_INDUCTOR_TOLERANCE_PCT, BuildConfig, ComponentSubstitution
from .capacitor_choice import assumed_tolerance_pct
from .circuit_display_names import STRAY_PREFIX, display_component_name
from .circuit_model import CircuitElement
from .eseries import MatchPolicy, match_component
from .toroid_selection import find_core_candidates


def inductor_case_tolerance_pct(config: BuildConfig) -> float:
    """The ± percent the tolerance cases give an inductor."""
    entered = config.inductor_tolerance_pct
    return entered if entered is not None else DEFAULT_INDUCTOR_TOLERANCE_PCT


def _inductor_tolerance(config: BuildConfig) -> float:
    return inductor_case_tolerance_pct(config) / 100.0


def _realize_capacitor(
    element: CircuitElement,
    eseries: str,
    policy: MatchPolicy,
    quality_factor: float | None,
    reference_frequency_hz: float,
) -> tuple[list[CircuitElement], ComponentSubstitution, list[str]]:
    match = match_component(element.value, eseries, parallel_mode="additive", policy=policy)
    selected = match.selected_components
    if selected is None:
        warnings = list(match.warnings)
        warnings.append(
            f"{display_component_name(element.name)}: No standard part chosen; "
            "the simulation uses the calculated value."
        )
        physical = [
            _with_loss(
                # No part is chosen; the calculated value varies by the assumed tolerance.
                replace(element, tolerance=assumed_tolerance_pct(policy) / 100.0),
                quality_factor,
                reference_frequency_hz,
            )
        ]
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
                tolerance=fraction,
            ),
            quality_factor,
            reference_frequency_hz,
        )
        for suffix, value, fraction in zip(suffixes, selected, match.part_tolerance_fractions)
    ]
    method = "e_series_parallel" if len(selected) > 1 else "e_series_single"
    stray = policy.stray_capacitance_f if len(selected) > 1 and policy.stray_capacitance_f else None
    if stray is not None:
        physical.append(stray_element(element, stray))
    substitution = ComponentSubstitution(
        logical_name=element.name,
        kind="C",
        calculated_value=element.value,
        nominal_value=sum(selected),
        physical_parts=tuple(selected),
        method=method,
        status=match.status,
        warnings=match.warnings,
        stray_capacitance_f=stray,
    )
    return physical, substitution, list(match.warnings)


def stray_element(element: CircuitElement, value: float) -> CircuitElement:
    """The assumed stray across a pair: a lossless capacitor across the pair's terminals.

    It keeps its value in every tolerance case (``fixed``) and is named with a ``C``
    prefix so a SPICE reader sees a capacitor (``CSTRAY_C1``, shown as "C1 stray").
    """
    name = f"{STRAY_PREFIX}{element.name}"
    return CircuitElement(
        name=name,
        node1=element.node1,
        node2=element.node2,
        kind="C",
        value=value,
        logical_name=name,
        fixed=True,
    )


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
            tolerance=_inductor_tolerance(config),
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
            wire_awg=candidate.mechanical.awg,
            wire_length_mm=candidate.mechanical.wire_length_mm,
        )
        name = display_component_name(element.name)
        warnings = [f"{name}: {warning}" for warning in candidate.warnings]
        return realized, substitution, warnings

    if config.use_toroid_candidates:
        status = "no_verified_candidate"
        warning = (
            f"{display_component_name(element.name)}: No suitable toroid; "
            "the simulation uses the calculated value."
        )
    else:
        status = "candidate_screen_disabled"
        warning = (
            f"{display_component_name(element.name)}: Toroid windings are off; "
            "the simulation uses the calculated value."
        )
    realized = _with_loss(
        replace(element, tolerance=_inductor_tolerance(config)),
        quality_factor,
        loss_reference_frequency_hz,
    )
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
