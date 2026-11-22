"""Resolve every chosen part of a design once, for every output to read.

``design()`` calls ``resolve_parts`` after synthesis. It is the only caller of the part
selection functions (``match_component`` for capacitors and each inductor kind's
selector); the table, JSON, CSV, both SPICE decks, the build simulation, and the web
and wizard documents read the ``ResolvedParts`` it returns.
"""

from __future__ import annotations

from ..shared.cancellation import (
    CancellationCheck,
    raise_if_cancelled,
    require_cancellation_check,
)
from ..shared.chip_selection import suggest_chips
from ..shared.circuit_builders import build_named_circuit
from ..shared.circuit_model import CircuitElement
from ..shared.eseries import DEFAULT_MATCH_POLICY, E_SERIES, MatchPolicy, match_component
from ..shared.inductor_suggestion import (
    AIR_COIL_EXCLUSION,
    AUTO,
    CALCULATED,
    DEFAULT_BUILD_INDUCTORS,
    DEFAULT_INDUCTOR_DETAIL,
    NO_QUALIFYING_SUGGESTION,
    SUGGESTIONS_NOT_USED,
    InductorSuggestion,
    KindSuggestions,
    require_build_inductors,
    require_build_with_suggestions,
    require_inductor_detail,
)
from ..shared.resolved_parts import InductorParts, ResolvedParts
from ..shared.srf_screen import CheckWindow, check_window
from ..shared.tank_trimmers import size_tanks
from ..shared.toroid_selection import suggest_toroids
from .design_request import DesignRequest
from .render_options import needs_eseries_message

# Why the build uses an inductor's calculated value when suggestions are not used.
SUGGESTIONS_NOT_USED_NOTE = "Inductor suggestions are not used."
NO_SUGGESTION_NOTE = "No inductor suggestion qualifies."

__all__ = [
    "NO_SUGGESTION_NOTE",
    "SUGGESTIONS_NOT_USED_NOTE",
    "resolve_match_policy",
    "resolve_parts",
    "resolve_parts_for",
]


def resolve_match_policy(request: DesignRequest) -> MatchPolicy:
    """The capacitor match policy for ``request``; ``design()`` is its only user."""
    return MatchPolicy(
        allow_sub_pf=request.allow_sub_pf,
        grade=request.capacitor_grade,
        tolerance_override_pct=request.capacitor_tolerance_pct,
        stray_capacitance_f=request.stray_capacitance_f,
    )


def _check_window(result: dict, category: str) -> CheckWindow:
    """The window the suggestions are checked over (``srf_screen.check_window``).

    A band-pass result made without ``f_high`` (a hand-made one) gets its upper -3 dB
    edge from ``f0`` and ``bw``, as synthesis computes it.
    """
    if category == "bandpass" and "f_high" not in result and "bw" in result:
        from ..bandpass.resonator_math import compute_bandpass_3db_edges

        _f_low, f_high = compute_bandpass_3db_edges(result["f0"], result["bw"])
        result = {**result, "f_high": f_high}
    return check_window(result, category)


def _design_frequency(result: dict, category: str) -> float:
    """The frequency the inductor kinds check against: the cutoff or the center."""
    return result["f0"] if category == "bandpass" else result["freq_hz"]


def _kind_suggestions(
    target_h: float, design_freq_hz: float, window: CheckWindow
) -> tuple[KindSuggestions, ...]:
    """Every kind's suggestions for one inductance, in the fixed build order.

    Toroid windings are screened at the design frequency (their rated range); chip
    inductors over the check window (``srf_screen.check_window``).
    """
    return (
        suggest_toroids(target_h, design_freq_hz),
        KindSuggestions("air-coil", reason_none=AIR_COIL_EXCLUSION),
        suggest_chips(target_h, window),
    )


def _build_pick(
    kinds: tuple[KindSuggestions, ...], build_inductors: str
) -> tuple[InductorSuggestion | None, str, str | None]:
    """The suggestion the build uses, its JSON ``status``, and why when there is none."""
    if build_inductors == AUTO:
        candidates = tuple(item for group in kinds for item in group.suggestions)
        reason_none = NO_SUGGESTION_NOTE
    else:
        group = next(group for group in kinds if group.kind == build_inductors)
        candidates = group.suggestions
        reason_none = group.reason_none
    if not candidates:
        return None, NO_QUALIFYING_SUGGESTION, reason_none
    return candidates[0], candidates[0].status, None


def _inductor_parts(
    element: CircuitElement,
    kinds: tuple[KindSuggestions, ...],
    detail: str,
    build_inductors: str,
) -> InductorParts:
    """Choose the part the build uses for one inductor and say why when there is none."""
    if detail == "none" or build_inductors == CALCULATED:
        pick, status, note = None, SUGGESTIONS_NOT_USED, SUGGESTIONS_NOT_USED_NOTE
    else:
        pick, status, note = _build_pick(kinds, build_inductors)
    return InductorParts(
        name=element.name,
        target_h=element.value,
        kinds=() if detail == "none" else kinds,
        build_pick=pick,
        build_status=status,
        build_note=note,
    )


def resolve_parts_for(
    result: dict,
    category: str,
    *,
    eseries: str | None = "E24",
    policy: MatchPolicy | None = None,
    inductor_detail: str = DEFAULT_INDUCTOR_DETAIL,
    build_inductors: str = DEFAULT_BUILD_INDUCTORS,
    should_cancel: CancellationCheck | None = None,
) -> ResolvedParts:
    """Resolve the parts of a synthesis ``result`` under explicit settings.

    ``resolve_parts`` passes the request's settings; a test or a library caller with a
    hand-made result passes its own. Capacitors are chosen only when ``eseries`` is set.
    Each distinct inductance is screened once (band-pass resonators share one), and
    ``should_cancel`` is polled before each part. A band-pass design with standard values
    also sizes each tank as a fixed part plus a trimmer, from the design alone
    (``tank_trimmers.size_tanks``).
    """
    require_inductor_detail(inductor_detail)
    require_build_inductors(build_inductors)
    require_build_with_suggestions(inductor_detail, build_inductors)
    require_cancellation_check(should_cancel)
    if eseries is not None and (not isinstance(eseries, str) or eseries not in E_SERIES):
        raise ValueError("E-series must be E12, E24, or E96")
    if policy is not None and not isinstance(policy, MatchPolicy):
        raise ValueError("policy must be a MatchPolicy or None")
    active_policy = DEFAULT_MATCH_POLICY if policy is None else policy
    if eseries is None and active_policy != DEFAULT_MATCH_POLICY:
        # The request's rule: every capacitor policy choice needs standard values.
        raise ValueError(needs_eseries_message("A capacitor match policy"))
    circuit = build_named_circuit(result, category)
    design_freq_hz = _design_frequency(result, category)
    # Suggestions off: nothing is screened, so no window is needed.
    window = None if inductor_detail == "none" else _check_window(result, category)
    capacitors = {}
    inductors = {}
    screened: dict[float, tuple[KindSuggestions, ...]] = {}
    for element in circuit.elements:
        raise_if_cancelled(should_cancel)
        if element.kind == "C":
            if eseries is not None:
                capacitors[element.name] = match_component(
                    element.value, eseries, parallel_mode="additive", policy=active_policy
                )
            continue
        if element.value not in screened:
            # Suggestions off: nothing is screened, and the build uses calculated values.
            screened[element.value] = (
                ()
                if inductor_detail == "none"
                else _kind_suggestions(element.value, design_freq_hz, window)
            )
        inductors[element.name] = _inductor_parts(
            element, screened[element.value], inductor_detail, build_inductors
        )
    tanks = {}
    if category == "bandpass" and eseries is not None:
        raise_if_cancelled(should_cancel)
        tanks = size_tanks(
            result, circuit, capacitors, inductors, active_policy, eseries, should_cancel
        )
    return ResolvedParts(
        eseries=eseries,
        match_policy=active_policy,
        capacitors=capacitors,
        inductors=inductors,
        inductor_detail=inductor_detail,
        build_inductors=build_inductors,
        check_window=window,
        tanks=tanks,
    )


def resolve_parts(
    request: DesignRequest, result: dict, should_cancel: CancellationCheck | None = None
) -> ResolvedParts:
    """Resolve the parts of ``request``'s synthesized ``result`` (``design()`` only)."""
    return resolve_parts_for(
        result,
        request.category,
        eseries=request.eseries,
        policy=resolve_match_policy(request),
        inductor_detail=request.inductor_suggestions,
        build_inductors=request.build_inductors,
        should_cancel=should_cancel,
    )
