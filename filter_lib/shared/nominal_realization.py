"""Nominal physical realization of calculated filter circuits."""

from collections.abc import Iterable
from dataclasses import replace

from .build_loss_models import LossModel, _design_frequency, loss_model
from .build_response import evaluation_ports
from .build_types import (
    BuildConfig,
    ComponentSubstitution,
    NominalRealization,
    resolve_build_config,
)
from .circuit_builders import build_named_circuit
from .circuit_display_names import display_component_name, format_name_list
from .circuit_model import CircuitElement, NamedCircuit
from .component_realization import _realize_capacitor, _realize_inductor, realize_tank_split
from .formatting import format_frequency
from .resolved_parts import PARTS_FROM_ANOTHER_DESIGN_MESSAGE, ResolvedParts
from .tank_trimmers import tank_nodes, tank_ports
from .tank_tuning import TuningPlan, tune

NOMINAL_PARTS_LIMITATION = (
    "Chosen parts are simulated at their nominal values, without lead or package parasitics."
)


def stray_limitation(stray_f: float, trimmers: bool = False) -> str:
    """The limitation printed when the build adds the assumed stray across each pair.

    ``trimmers``: a tank's fixed part and trimmer count as extra parts too.
    """
    across = (
        "Each parallel pair, and each extra part beside a tank's trimmer, has"
        if trimmers
        else "Each parallel pair has"
    )
    return (
        f"{across} an assumed {stray_f * 1e12:g} pF stray across it, the same "
        "in every tolerance case; it is an assumption, not a measured value."
    )


# Printed when a chip inductor (a part with a checked SRF) is built with its
# self-capacitance.
SELF_CAPACITANCE_LIMITATION = (
    "Each chip inductor is simulated as its inductance with a fixed self-capacitance across "
    "it: the upper bound at its catalog inductance from its guaranteed minimum SRF, measured "
    "in the maker's fixture. Board mounting changes the SRF, and the part's Q and loss are "
    "not modelled unless an inductor Q is given."
)
# Printed when an inductor Q is applied to a chip inductor.
CHIP_Q_LIMITATION = (
    "A chip inductor's Q is applied to its inductance alone; with its self-capacitance "
    "across it, its Q at its terminals is lower, more so near its SRF. The qualified range "
    "comes from the lossless part model, so it does not include that Q."
)


# Printed when a tank is built as a fixed part plus a trimmer.
TRIMMER_LIMITATION = (
    "Each tank with a trimmer is tuned at the tank frequency so that its node susceptance "
    "matches the calculated design's. Each trimmer is simulated as its knob capacitance in "
    "series with the inductance its fit assumes. Its knob stops are the maker's guaranteed "
    "range, measured at the maker's frequency; the range it covers at the tank frequency "
    "rests on that assumed inductance, so it is not guaranteed. The tuned response restores "
    "each tank's resonance, not the coupling between tanks or the external Q, so it is not "
    "the design's response."
)


# Readable text (table and SPICE comments) prints this one only when a toroid winding
# was actually used; JSON keeps every limitation.
TOROID_LIMITATION = (
    "Toroid windings were checked only for frequency range, whole-turn inductance, and wire fit."
)


def uses_toroid(substitutions: Iterable[ComponentSubstitution]) -> bool:
    """Return whether any inductor was realized as a toroid winding."""
    return any(item.inductor_kind == "toroid" for item in substitutions)


def applicable_part_limitations(realization: NominalRealization) -> list[str]:
    """Return the realization's limitations once each, without the unused toroid caveat."""
    skipped = set() if uses_toroid(realization.substitutions) else {TOROID_LIMITATION}
    return [item for item in dict.fromkeys(realization.limitations) if item not in skipped]


def grouped_part_warnings(substitutions: Iterable[ComponentSubstitution]) -> list[str]:
    """Print each warning once, naming every part it applies to (``L1–L3: ...``).

    Names are the component-table names, so a warning reads the same in the table's
    build block and in SPICE comments.
    """
    groups: dict[str, list[str]] = {}
    for substitution in substitutions:
        name = display_component_name(substitution.logical_name)
        for warning in substitution.warnings:
            message = warning.removeprefix(f"{name}: ")
            groups.setdefault(message, []).append(name)
    return [f"{format_name_list(names)}: {message}" for message, names in groups.items()]


def _realize_element(
    element: CircuitElement,
    config: BuildConfig,
    parts: ResolvedParts,
    losses: LossModel,
) -> tuple[list[CircuitElement], ComponentSubstitution, list[str]]:
    if parts.target(element.name) != element.value:
        raise ValueError(PARTS_FROM_ANOTHER_DESIGN_MESSAGE)
    if element.kind == "C":
        return _realize_capacitor(
            element,
            parts.capacitor(element.name),
            parts.match_policy,
            losses.capacitor_q_for(element.name),
            losses.reference_frequency_hz,
        )
    if element.kind == "L":
        return _realize_inductor(
            element,
            parts.inductor(element.name),
            config,
            losses.inductor_q,
            losses.reference_frequency_hz,
        )
    raise ValueError(f"nominal realization supports only C and L elements, got {element.kind!r}")


def realize_nominal_build(
    result: dict,
    category: str,
    config: BuildConfig | None = None,
    *,
    parts: ResolvedParts,
) -> NominalRealization:
    """Realize the chosen parts while preserving topology and traceability.

    Every capacitor and inductor is the part ``design()`` resolved in ``parts`` (which
    must have standard capacitor values); nothing is selected here.
    """
    active_config = resolve_build_config(config)
    if parts.eseries is None:
        raise ValueError("The chosen parts need standard capacitor values (an E-series)")
    exact = build_named_circuit(result, category)
    # The cutoff or center frequency must be physical even when no part depends on it.
    _design_frequency(result, category)
    losses = loss_model(result, category, active_config)
    inductor_q, capacitor_q = losses.inductor_q, losses.capacitor_q
    if (
        active_config.reference_frequency_hz is not None
        and inductor_q is None
        and capacitor_q is None
    ):
        raise ValueError(
            "The frequency at which the Q values apply was given without any Q: give an "
            "inductor, capacitor, or resonator Q"
        )
    loss_reference_frequency = losses.reference_frequency_hz

    physical: list[CircuitElement] = []
    substitutions: list[ComponentSubstitution] = []
    warnings: list[str] = []
    plans = []
    for element in exact.elements:
        tank = parts.tank(element.name) if element.kind == "C" else None
        if tank is not None and tank.split is not None:
            if parts.target(element.name) != element.value:
                raise ValueError(PARTS_FROM_ANOTHER_DESIGN_MESSAGE)
            realized, substitution, plan = realize_tank_split(
                element,
                tank,
                losses.capacitor_q_for(element.name),
                losses.reference_frequency_hz,
            )
            plans.append(plan)
            part_warnings: list[str] = []
        else:
            realized, substitution, part_warnings = _realize_element(
                element, active_config, parts, losses
            )
        physical.extend(realized)
        substitutions.append(substitution)
        warnings.extend(part_warnings)

    limitations = list(losses.limitations)
    if inductor_q is not None or capacitor_q is not None:
        reference = format_frequency(loss_reference_frequency)
        limitations.append(
            f"Each Q is modeled as a fixed series resistance that gives that Q at {reference}; "
            f"away from {reference} the modeled Q changes."
        )
    limitations.append(NOMINAL_PARTS_LIMITATION)
    strays = [item.stray_capacitance_f for item in substitutions if item.stray_capacitance_f]
    if strays:
        limitations.append(stray_limitation(parts.match_policy.stray_capacitance_f, bool(plans)))
    if any(item.self_capacitance_f for item in substitutions):
        limitations.append(SELF_CAPACITANCE_LIMITATION)
        if inductor_q is not None:
            limitations.append(CHIP_Q_LIMITATION)
    limitations.append(TOROID_LIMITATION)
    circuit = NamedCircuit(
        exact.category,
        exact.n_nodes,
        tuple(physical),
        exact.in_node,
        exact.out_node,
    )
    tuning = None
    settings: tuple = ()
    if plans:
        limitations.append(TRIMMER_LIMITATION)
        source, load = evaluation_ports(result, category, active_config)
        tuning = TuningPlan(
            trimmers=tuple(plans),
            tank_nodes=tank_nodes(result),
            ports=tank_ports(circuit, source, load),
        )
        circuit, settings = tune(circuit, tuning)
        by_tank = {setting.tank: setting for setting in settings}
        substitutions = [
            item
            if item.trimmer is None
            else replace(item, trimmer=replace(item.trimmer, setting=by_tank[item.logical_name]))
            for item in substitutions
        ]
    return NominalRealization(
        circuit=circuit,
        substitutions=tuple(substitutions),
        warnings=tuple(warnings),
        limitations=tuple(limitations),
        tuning=tuning,
        trimmer_settings=settings,
    )
