"""Nominal physical realization of calculated filter circuits."""

from collections.abc import Iterable

from .build_loss_models import (
    _design_frequency,
    _loss_quality_factors,
    _loss_reference_frequency,
)
from .build_types import (
    BuildConfig,
    ComponentSubstitution,
    NominalRealization,
    resolve_build_config,
)
from .circuit_builders import build_named_circuit
from .circuit_display_names import display_component_name, format_name_list
from .circuit_model import CircuitElement, NamedCircuit
from .component_realization import _realize_capacitor, _realize_inductor
from .formatting import format_frequency

NOMINAL_PARTS_LIMITATION = (
    "Chosen parts are simulated at their nominal values, without lead or package parasitics."
)
# Readable text (table and SPICE comments) prints this one only when a toroid winding
# was actually used; JSON keeps every limitation.
TOROID_LIMITATION = (
    "Toroid windings were checked only for frequency range, whole-turn inductance, and wire fit."
)


def uses_toroid(substitutions: Iterable[ComponentSubstitution]) -> bool:
    """Return whether any inductor was realized as a toroid winding."""
    return any(item.core_name is not None for item in substitutions)


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
    inductor_q: float | None,
    capacitor_q: float | None,
    capacitor_q_tank_only: bool,
    design_frequency: float,
    loss_reference_frequency: float,
) -> tuple[list[CircuitElement], ComponentSubstitution, list[str]]:
    if element.kind == "C":
        element_capacitor_q = (
            capacitor_q if not capacitor_q_tank_only or element.name.startswith("CT") else None
        )
        return _realize_capacitor(
            element,
            config,
            element_capacitor_q,
            loss_reference_frequency,
        )
    if element.kind == "L":
        part, substitution, warnings = _realize_inductor(
            element,
            config,
            inductor_q,
            design_frequency,
            loss_reference_frequency,
        )
        return [part], substitution, warnings
    raise ValueError(f"nominal realization supports only C and L elements, got {element.kind!r}")


def realize_nominal_build(
    result: dict, category: str, config: BuildConfig | None = None
) -> NominalRealization:
    """Realize selected physical parts while preserving topology and traceability."""
    active_config = resolve_build_config(config)
    exact = build_named_circuit(result, category)
    design_frequency = _design_frequency(result, category)
    inductor_q, capacitor_q, tank_only, q_limitations = _loss_quality_factors(
        result, category, active_config
    )
    if (
        active_config.reference_frequency_hz is not None
        and inductor_q is None
        and capacitor_q is None
    ):
        raise ValueError(
            "The frequency at which the Q values apply was given without any Q: give an "
            "inductor, capacitor, or resonator Q"
        )
    loss_reference_frequency = _loss_reference_frequency(result, category, active_config)

    physical: list[CircuitElement] = []
    substitutions: list[ComponentSubstitution] = []
    warnings: list[str] = []
    for element in exact.elements:
        parts, substitution, part_warnings = _realize_element(
            element,
            active_config,
            inductor_q,
            capacitor_q,
            tank_only,
            design_frequency,
            loss_reference_frequency,
        )
        physical.extend(parts)
        substitutions.append(substitution)
        warnings.extend(part_warnings)

    limitations = list(q_limitations)
    if inductor_q is not None or capacitor_q is not None:
        reference = format_frequency(loss_reference_frequency)
        limitations.append(
            f"Each Q is modeled as a fixed series resistance that gives that Q at {reference}; "
            f"away from {reference} the modeled Q changes."
        )
    limitations.extend((NOMINAL_PARTS_LIMITATION, TOROID_LIMITATION))
    circuit = NamedCircuit(
        exact.category,
        exact.n_nodes,
        tuple(physical),
        exact.in_node,
        exact.out_node,
    )
    return NominalRealization(
        circuit=circuit,
        substitutions=tuple(substitutions),
        warnings=tuple(warnings),
        limitations=tuple(limitations),
    )
