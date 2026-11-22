"""Calculated-to-physical capacitor and inductor substitution helpers."""

from dataclasses import replace

from .build_loss_models import _with_loss
from .build_types import DEFAULT_INDUCTOR_TOLERANCE_PCT, BuildConfig, ComponentSubstitution
from .capacitor_choice import assumed_tolerance_pct
from .circuit_display_names import SELF_CAPACITANCE_PREFIX, STRAY_PREFIX, display_component_name
from .circuit_model import CircuitElement
from .eseries import ESeriesMatch, MatchPolicy
from .inductor_suggestion import SUGGESTED_INDUCTOR_METHOD, InductorSuggestion
from .resolved_parts import InductorParts


def inductor_case_tolerance_pct(config: BuildConfig) -> float:
    """The ± percent the tolerance cases give a toroid winding or a calculated value.

    An entered inductor tolerance applies to every inductor; without one, a part with a
    checked SRF (a chip inductor) uses its own guaranteed tolerance instead
    (``inductor_tolerance``).
    """
    entered = config.inductor_tolerance_pct
    return entered if entered is not None else DEFAULT_INDUCTOR_TOLERANCE_PCT


def inductor_tolerance(config: BuildConfig, pick: InductorSuggestion | None) -> tuple[float, bool]:
    """The ± percent one inductor's tolerance cases use, and whether it is the part's own."""
    if config.inductor_tolerance_pct is None and pick is not None and pick.part_model is not None:
        return pick.tolerance_pct, True
    return inductor_case_tolerance_pct(config), False


def _realize_capacitor(
    element: CircuitElement,
    match: ESeriesMatch,
    policy: MatchPolicy,
    quality_factor: float | None,
    reference_frequency_hz: float,
) -> tuple[list[CircuitElement], ComponentSubstitution, list[str]]:
    """Realize one capacitor as the parts ``design()`` chose for it (``match``)."""
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


def self_capacitance_element(element: CircuitElement, value: float) -> CircuitElement:
    """An inductor's self-capacitance: a lossless capacitor across the inductor.

    It keeps its value in every tolerance case (``fixed``) and is named with a ``C``
    prefix (``CSELF_L1``, shown as "L1 self-capacitance").
    """
    name = f"{SELF_CAPACITANCE_PREFIX}{element.name}"
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
    parts: InductorParts,
    config: BuildConfig,
    quality_factor: float | None,
    loss_reference_frequency_hz: float,
) -> tuple[list[CircuitElement], ComponentSubstitution, list[str]]:
    """Realize one inductor as its build pick, or at its calculated value with the reason.

    A pick with a part model (a chip inductor) is its ``L0`` with the self-capacitance
    from its minimum SRF across it, which together give the catalog value at the test
    frequency; the self-capacitance stays fixed in every tolerance case.
    """
    name = display_component_name(element.name)
    pick = parts.build_pick
    tolerance_pct, own_tolerance = inductor_tolerance(config, pick)
    if pick is not None:
        model = pick.part_model
        nominal = model.catalog_inductance_h if model is not None else pick.achieved_h
        realized = replace(
            element,
            value=model.l0_h if model is not None else pick.achieved_h,
            logical_name=element.name,
            series_resistance_ohm=0.0,
            quality_factor=None,
            loss_reference_frequency_hz=None,
            tolerance=tolerance_pct / 100.0,
        )
        physical = [_with_loss(realized, quality_factor, loss_reference_frequency_hz)]
        self_capacitance = model.self_capacitance_f if model is not None else None
        if self_capacitance is not None:
            physical.append(self_capacitance_element(element, self_capacitance))
        # A toroid winding also records its core, turns, and wire.
        toroid = pick.build if pick.kind == "toroid" else None
        substitution = ComponentSubstitution(
            logical_name=element.name,
            kind="L",
            calculated_value=element.value,
            nominal_value=nominal,
            physical_parts=(nominal,),
            method=SUGGESTED_INDUCTOR_METHOD,
            status=pick.status,
            warnings=pick.warnings,
            inductor_kind=pick.kind,
            part_name=pick.part_name,
            core_name=toroid.core.name if toroid is not None else None,
            turns=toroid.winding.n_turns if toroid is not None else None,
            wire_awg=toroid.mechanical.awg if toroid is not None else None,
            wire_length_mm=toroid.mechanical.wire_length_mm if toroid is not None else None,
            self_capacitance_f=self_capacitance,
            tolerance_pct=tolerance_pct,
            own_tolerance=own_tolerance,
        )
        return physical, substitution, [f"{name}: {warning}" for warning in pick.warnings]

    warning = f"{name}: {parts.build_note} The simulation uses the calculated value."
    realized = _with_loss(
        replace(element, tolerance=tolerance_pct / 100.0),
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
        status=parts.build_status,
        warnings=(warning,),
        tolerance_pct=tolerance_pct,
    )
    return [realized], substitution, [warning]
