"""Generic finite SPICE decks from the authoritative named circuits."""

from __future__ import annotations

from .build_response import build_frequency_grid, evaluation_ports
from .build_types import BuildConfig, NominalRealization, resolve_build_config
from .circuit_builders import build_named_circuit
from .circuit_model import CircuitElement
from .nominal_realization import realize_nominal_build
from .numeric import is_finite_real


def _number(value: float) -> str:
    if not is_finite_real(value) or value <= 0:
        raise ValueError("SPICE values must be positive and finite")
    return f"{value:.12g}"


def _comment(text: str) -> str:
    return " ".join(text.splitlines())


def _element_lines(element: CircuitElement) -> list[str]:
    value = _number(element.value)
    if not element.series_resistance_ohm:
        return [f"{element.name} {element.node1} {element.node2} {value}"]
    internal_node = f"NLOSS{element.name}"
    return [
        f"{element.name} {element.node1} {internal_node} {value}",
        f"RLOSS{element.name} {internal_node} {element.node2} "
        f"{_number(element.series_resistance_ohm)}",
    ]


def _nominal_comments(realization: NominalRealization) -> list[str]:
    comments: list[str] = []
    for substitution in realization.substitutions:
        details = [
            substitution.logical_name,
            substitution.method,
            substitution.status,
            f"calculated={_number(substitution.calculated_value)}",
            f"nominal={_number(substitution.nominal_value)}",
        ]
        if substitution.core_name is not None:
            details.append(f"core={substitution.core_name}")
        if substitution.turns is not None:
            details.append(f"turns={substitution.turns}")
        comments.append("* substitution: " + " ".join(details))
    comments.extend(f"* warning: {_comment(warning)}" for warning in realization.warnings)
    comments.extend(
        f"* limitation: {_comment(limitation)}" for limitation in realization.limitations
    )
    return comments


def export_spice_deck(
    result: dict,
    category: str,
    *,
    realization: str = "exact",
    config: BuildConfig | None = None,
) -> str:
    """Export an exact or nominal-build passive network as generic SPICE.

    The deck includes a 1 V AC Thevenin source, separate finite source/load
    resistances, a logarithmic AC sweep, and explicit series-loss resistors.
    """
    active_config = resolve_build_config(config)
    nominal: NominalRealization | None = None
    if realization == "exact":
        circuit = build_named_circuit(result, category)
        realization_label = "calculated_exact"
    elif realization == "nominal_build":
        nominal = realize_nominal_build(result, category, active_config)
        circuit = nominal.circuit
        realization_label = "nominal_build"
    else:
        raise ValueError("realization must be 'exact' or 'nominal_build'")

    source, load = evaluation_ports(result, category, active_config)
    frequency_grid = build_frequency_grid(result, category, active_config.grid_points)
    start, stop = frequency_grid[0], frequency_grid[-1]
    # Validate the complete numeric envelope before rendering any text.
    for value in (source, load, start, stop):
        _number(value)

    lines = [
        "* RF Filter Calculator generic AC deck",
        f"* category: {category}",
        f"* realization: {realization_label}",
        f"* printed trace: vm({circuit.out_node}) is load-node voltage, not gain in dB",
        f"* transducer gain: Gt=4*Rs/Rl*|V({circuit.out_node})/V(NSOURCE)|^2",
        (
            "* limitations: ideal values omit layout, parasitics, SRF, temperature, "
            "and power behavior"
            if nominal is None
            else "* limitations: nominal values and constant-series-loss models omit "
            "layout, parasitics, SRF, temperature, and power behavior"
        ),
        f"* ports: input={circuit.in_node} output={circuit.out_node} ground=0 source=NSOURCE",
    ]
    if nominal is not None:
        lines.extend(_nominal_comments(nominal))
    lines.extend(
        (
            "VINPUT NSOURCE 0 AC 1",
            f"RSOURCE NSOURCE {circuit.in_node} {_number(source)}",
        )
    )
    for element in circuit.elements:
        lines.extend(_element_lines(element))
    lines.extend(
        (
            f"RLOAD {circuit.out_node} 0 {_number(load)}",
            f".ac dec 200 {_number(start)} {_number(stop)}",
            f".print ac vm({circuit.out_node})",
            ".end",
        )
    )
    deck = "\n".join(lines) + "\n"
    lowered = deck.lower()
    if any(token in lowered.split() for token in ("nan", "inf", "+inf", "-inf")):
        raise ValueError("SPICE deck must contain only finite numeric values")
    return deck
