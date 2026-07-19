"""Nominal physical realization of calculated filter circuits."""

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
from .circuit_model import CircuitElement, NamedCircuit
from .component_realization import _realize_capacitor, _realize_inductor


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
    substitution = ComponentSubstitution(
        logical_name=element.name,
        kind=element.kind,
        calculated_value=element.value,
        nominal_value=element.value,
        physical_parts=(element.value,),
        method="exact",
        status="not_substituted",
    )
    return [element], substitution, []


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
            "reference_frequency_hz requires an effective inductor, capacitor, or resonator Q"
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
        limitations.append(
            f"Q is converted to constant series resistance at "
            f"{loss_reference_frequency:.12g} Hz; "
            "the resulting model is not constant-Q away from that reference."
        )
    limitations.extend(
        (
            "E-series parts are nominal values and omit package and connection parasitics.",
            "Toroid candidates are an integer-turn/frequency/mechanical screen, not an RF-Q, "
            "SRF, saturation, thermal, or power suitability determination.",
        )
    )
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
