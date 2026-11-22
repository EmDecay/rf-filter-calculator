"""Tank-inductance advice for a band-pass design whose coupling capacitors are too small.

A Top-C coupling capacitor scales about as ``1/L`` with the tank inductance and an end
capacitor about as ``1/sqrt(L)``, so a lower inductance raises them all. When some coupling
capacitor (``Cs12`` ..., ``Ce_in``, ``Ce_out``) has no standard part of 1 pF or more, the
advice looks for the tank inductance closest to the design's that gives every one of them
such a part.

It tries only inductances that a built-in inductor suggestion supplies: the chip-inductor
catalog values and the whole-turn windings of the verified toroid cores, below the design's
inductance. It starts at the inverse-``L`` estimate and walks up while a value works, or
down until one does, recalculating at most ``MAX_COUPLING_ADVICE_TRIALS`` designs. Each
trial is the rerun a user makes: the value is written as the text the advice prints
(``21nH``), read back with the CLI's parser, and recalculated through ``synthesize`` and
``resolve_parts`` with every other setting of the request (no advice, so no recursion).
A trial works when every coupling capacitor gets a part of 1 pF or more and a qualifying
suggestion supplies the value; the advice keeps that rerun's parts.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field, replace

from ..shared.cancellation import CancellationCheck, raise_if_cancelled
from ..shared.chip_inductor_data import chip_parts
from ..shared.circuit_display_names import display_component_name, format_name_list
from ..shared.eseries import ESeriesMatch
from ..shared.formatting import format_capacitance, format_inductance
from ..shared.inductor_suggestion import DEFAULT_INDUCTOR_DETAIL, KIND_LABELS, InductorSuggestion
from ..shared.parsing import parse_inductance
from ..shared.resolved_parts import ResolvedParts
from ..shared.toroid_core_data import iter_auto_selectable_cores_for_frequency
from ..shared.toroid_inductance import inductance_from_turns
from .design_request import DesignRequest

# The most designs one advice recalculates (each is a full calibration).
MAX_COUPLING_ADVICE_TRIALS = 8
# Whole turns of a verified toroid core tried as candidate windings.
_MAX_TOROID_TURNS = 200
# A suggestion supplies a value when its own value matches it this closely (relative).
_SUPPLY_TOLERANCE = 1e-9
# The coupling capacitors of a band-pass design: the inter-resonator ones and the ends.
_END_COUPLERS = ("CIN", "COUT")

CLI_FLAG = "--tank-inductance"
FIELD_LABEL = "Resonator inductance"
IMPEDANCE_FIELD_LABEL = "Resonator impedance"


@dataclass(frozen=True)
class AdviceTrial:
    """One recalculated design: the value tried and whether it works.

    ``couplers_ok``: every coupling capacitor got a part of 1 pF or more;
    ``supplied``: a qualifying inductor suggestion supplies the value. ``reason`` says why
    the recalculation failed when it did.
    """

    inductance_h: float
    setting: str
    couplers_ok: bool
    supplied: bool
    reason: str | None = None

    @property
    def works(self) -> bool:
        return self.couplers_ok and self.supplied


@dataclass(frozen=True)
class CouplingAdvice:
    """The advice for one design (``None`` on ``DesignResult`` when it does not apply).

    ``short_couplers`` are the coupling capacitors (circuit names) with no part of 1 pF
    or more. ``setting`` is the advised value as written for a rerun, ``inductance_h``
    the value it reads as, ``part`` the suggestion that supplies it, and ``couplers``
    the rerun's coupling-capacitor choices; all ``None`` (and ``couplers`` empty) when no
    value works, with ``reason_none`` saying why.
    """

    short_couplers: tuple[str, ...]
    floor_f: float
    original_inductance_h: float
    estimate_h: float
    trials: tuple[AdviceTrial, ...]
    max_trials: int
    clears_impedance: bool
    inductance_h: float | None = None
    setting: str | None = None
    part: InductorSuggestion | None = None
    couplers: dict[str, ESeriesMatch] = field(default_factory=dict)
    response_validation_status: str | None = None
    reason_none: str | None = None

    @property
    def advised(self) -> bool:
        return self.setting is not None


def inductance_setting(value_h: float, separator: str = "") -> str:
    """``value_h`` as the text a rerun types (``21nH``, ``1.2544uH``).

    ``separator`` goes between the number and the unit (a space for prose).
    """
    if value_h < 1e-6:
        return f"{value_h * 1e9:.12g}{separator}nH"
    return f"{value_h * 1e6:.12g}{separator}µH" if separator else f"{value_h * 1e6:.12g}uH"


def _floor_text(floor_f: float) -> str:
    return f"{floor_f * 1e12:g} pF"


def _coupler_names(parts: ResolvedParts) -> list[str]:
    """The coupling capacitors in table order: Ce_in, Cs12 ..., Ce_out."""
    inner = sorted(
        (name for name in parts.capacitors if name.startswith("CK")), key=lambda n: int(n[2:])
    )
    first, last = _END_COUPLERS
    return [
        *([first] if first in parts.capacitors else []),
        *inner,
        *([last] if last in parts.capacitors else []),
    ]


def _has_part_at_floor(match: ESeriesMatch, floor_f: float) -> bool:
    selected = match.selected_components
    return selected is not None and min(selected) >= floor_f


def short_couplers(parts: ResolvedParts) -> tuple[str, ...]:
    """The coupling capacitors with no standard part of 1 pF or more."""
    floor = parts.match_policy.minimum_capacitance_f
    return tuple(
        name
        for name in _coupler_names(parts)
        if not _has_part_at_floor(parts.capacitor(name), floor)
    )


def _estimate(result: dict, parts: ResolvedParts, names: tuple[str, ...]) -> float:
    """The inverse-``L`` estimate: Cs scales as 1/L and an end capacitor as 1/sqrt(L)."""
    floor = parts.match_policy.minimum_capacitance_f
    inductance = result["L_resonant"]
    estimates = []
    for name in names:
        ratio = parts.target(name) / floor
        estimates.append(inductance * (ratio**2 if name in _END_COUPLERS else ratio))
    return min(estimates)


def _candidates(result: dict, below_h: float) -> list[float]:
    """Inductances a built-in suggestion can supply, below ``below_h``, ascending."""
    values = {part.inductance_h for part in chip_parts()}
    for core in iter_auto_selectable_cores_for_frequency(result["f0"]):
        for turns in range(1, _MAX_TOROID_TURNS + 1):
            values.add(inductance_from_turns(turns, core.al_nh_per_turn2))
    return sorted(value for value in values if value < below_h)


def _supplied_value(suggestion: InductorSuggestion) -> float:
    """The value a suggestion supplies: a chip's catalog value, a winding's inductance."""
    if suggestion.part_model is not None:
        return suggestion.part_model.catalog_inductance_h
    return suggestion.achieved_h


def _supplier(parts: ResolvedParts, value_h: float) -> InductorSuggestion | None:
    """The first qualifying suggestion (build order) whose own value is ``value_h``."""
    resonator = parts.inductor("LT1")
    for suggestion in resonator.suggestions:
        if math.isclose(_supplied_value(suggestion), value_h, rel_tol=_SUPPLY_TOLERANCE):
            return suggestion
    return None


@dataclass
class _Search:
    request: DesignRequest
    should_cancel: CancellationCheck | None
    trials: list[AdviceTrial] = field(default_factory=list)
    # Each working value's trial and rerun, by its index in the candidate list.
    reruns: dict[int, tuple[AdviceTrial, dict, ResolvedParts, InductorSuggestion]] = field(
        default_factory=dict
    )

    def run(self, index: int, value_h: float) -> AdviceTrial:
        from .design_service import synthesize
        from .part_resolution import resolve_parts

        raise_if_cancelled(self.should_cancel)
        setting = inductance_setting(value_h)
        read = parse_inductance(setting, label=FIELD_LABEL)
        # Which parts qualify does not depend on how much of them a run shows, so a run
        # with suggestions off still checks that one supplies the value.
        detail = self.request.inductor_suggestions
        trial_request = replace(
            self.request,
            resonator_inductance=read,
            resonator_impedance=None,
            inductor_suggestions=DEFAULT_INDUCTOR_DETAIL if detail == "none" else detail,
        )
        try:
            result = synthesize(trial_request, self.should_cancel)
            parts = resolve_parts(trial_request, result, self.should_cancel)
        except ValueError as error:
            trial = AdviceTrial(read, setting, False, False, str(error))
            self.trials.append(trial)
            return trial
        couplers_ok = not short_couplers(parts)
        supplier = _supplier(parts, read)
        trial = AdviceTrial(read, setting, couplers_ok, supplier is not None)
        self.trials.append(trial)
        if trial.works and supplier is not None:
            self.reruns[index] = (trial, result, parts, supplier)
        return trial


def _walk(search: _Search, values: list[float], start: int) -> int | None:
    """The largest working index near ``start`` within the trial budget, or ``None``."""
    first = search.run(start, values[start])
    best = start if first.works else None
    if first.couplers_ok:
        # Couplers grow as the value falls, so a larger value may still work.
        index = start + 1
        while index < len(values) and len(search.trials) < MAX_COUPLING_ADVICE_TRIALS:
            trial = search.run(index, values[index])
            if not trial.couplers_ok:
                break
            if trial.works:
                best = index
            index += 1
        if best is not None:
            return best
    index = start - 1
    while index >= 0 and len(search.trials) < MAX_COUPLING_ADVICE_TRIALS:
        trial = search.run(index, values[index])
        if trial.works:
            return index
        if trial.reason is not None:
            # A recalculation that fails outright (the tank too low to couple the ports)
            # fails for every lower value too.
            return None
        index -= 1
    return None


def advise_coupling(
    request: DesignRequest,
    result: dict,
    parts: ResolvedParts,
    should_cancel: CancellationCheck | None = None,
) -> CouplingAdvice | None:
    """The coupling advice for a band-pass design, or ``None`` when it does not apply.

    It applies to a band-pass design with standard capacitor values in which some
    coupling capacitor has no part of 1 pF or more. ``should_cancel`` is polled before
    each recalculated design (and by it).
    """
    if request.category != "bandpass" or parts.eseries is None:
        return None
    names = short_couplers(parts)
    if not names:
        return None
    original = result["L_resonant"]
    estimate = _estimate(result, parts, names)
    common = {
        "short_couplers": names,
        "floor_f": parts.match_policy.minimum_capacitance_f,
        "original_inductance_h": original,
        "estimate_h": estimate,
        "max_trials": MAX_COUPLING_ADVICE_TRIALS,
        "clears_impedance": request.resonator_impedance is not None,
    }
    values = _candidates(result, original)
    if not values:
        return CouplingAdvice(trials=(), reason_none=no_candidate_reason(original), **common)
    start = max(bisect_right(values, estimate) - 1, 0)
    search = _Search(request, should_cancel)
    best = _walk(search, values, start)
    trials = tuple(search.trials)
    if best is None:
        return CouplingAdvice(trials=trials, reason_none=no_value_works_reason(trials), **common)
    chosen, rerun_result, rerun_parts, supplier = search.reruns[best]
    return CouplingAdvice(
        trials=trials,
        inductance_h=chosen.inductance_h,
        setting=chosen.setting,
        part=supplier,
        couplers={name: rerun_parts.capacitor(name) for name in _coupler_names(rerun_parts)},
        response_validation_status=rerun_result.get("response_validation_status"),
        **common,
    )


def no_candidate_reason(inductance_h: float) -> str:
    """No built-in suggestion supplies any lower tank inductance."""
    return (
        "No built-in inductor suggestion supplies a tank inductance below "
        f"{format_inductance(inductance_h)}, so no tank inductance is advised."
    )


def no_value_works_reason(trials: tuple[AdviceTrial, ...]) -> str:
    """None of the tried values works within the search budget."""
    tried = ", ".join(format_inductance(trial.inductance_h) for trial in trials)
    return (
        f"None of the {len(trials)} tank inductances tried ({tried}) gives every coupling "
        "capacitor a part of 1 pF or more with a built-in inductor suggestion, so no tank "
        "inductance is advised."
    )


def advice_lines_text(advice: CouplingAdvice) -> list[str]:
    """The advice as paragraphs (the table wraps them)."""
    short = format_name_list(display_component_name(name) for name in advice.short_couplers)
    verb = "gets" if len(advice.short_couplers) == 1 else "get"
    opening = (
        f"{short} {verb} no standard part of {_floor_text(advice.floor_f)} or more with "
        f"{format_inductance(advice.original_inductance_h)} tanks. A lower tank inductance "
        "raises every coupling capacitor."
    )
    if not advice.advised:
        return [opening, advice.reason_none or ""]
    clear = f' and clear "{IMPEDANCE_FIELD_LABEL}"' if advice.clears_impedance else ""
    groups: dict[str, list[str]] = {}
    for name, match in advice.couplers.items():
        text = " || ".join(format_capacitance(value) for value in match.selected_components or ())
        groups.setdefault(text, []).append(display_component_name(name))
    values = "; ".join(f"{format_name_list(names)}: {text}" for text, names in groups.items())
    part, inductance = advice.part, advice.inductance_h
    assert part is not None and inductance is not None
    supplier = f"{KIND_LABELS[part.kind].lower()} {part.part_name}"
    status = (
        ""
        if advice.response_validation_status == "validated"
        else " Its response check is not confirmed; see that run's warnings."
    )
    return [
        opening,
        f'Rerun with "{FIELD_LABEL}" set to {inductance_setting(inductance, " ")}{clear} '
        f"({CLI_FLAG} {advice.setting}). Recalculated with that value, every coupling "
        f"capacitor gets a part of {_floor_text(advice.floor_f)} or more ({values}), "
        f"and {supplier} supplies the inductance.{status} Every capacitor of the design "
        "changes; use the rerun's own output.",
    ]
