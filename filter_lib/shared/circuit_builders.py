"""Authoritative named-circuit builders for supported filter topologies."""

from collections.abc import Mapping, Sequence

from .circuit_model import Branch, CircuitElement, NamedCircuit

# Topology determines placement; category determines component kind.
_ODD_SLOT_RULES: dict[tuple[str, str], tuple[str, bool]] = {
    ("lowpass", "pi"): ("C", True),
    ("lowpass", "t"): ("L", False),
    ("highpass", "t"): ("C", False),
    ("highpass", "pi"): ("L", True),
}


def _required(result: Mapping, key: str) -> object:
    if key not in result:
        raise ValueError(f"result is missing required field {key!r}")
    return result[key]


def _component_list(result: Mapping, key: str) -> list:
    values = _required(result, key)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise ValueError(f"result field {key!r} must be a component sequence")
    return list(values)


def _build_named_ladder(result: Mapping, category: str) -> NamedCircuit:
    topology = _required(result, "topology")
    if not isinstance(topology, str):
        raise ValueError("topology must be 'pi' or 't'")
    try:
        odd_kind, odd_is_shunt = _ODD_SLOT_RULES[(category, topology)]
    except KeyError:
        raise ValueError(f"Unknown topology {topology!r}: use 'pi' or 't'") from None

    capacitors = _component_list(result, "capacitors")
    inductors = _component_list(result, "inductors")
    counters = {"C": 0, "L": 0}
    elements: list[CircuitElement] = []
    node = 1
    order = _required(result, "order")
    if not isinstance(order, int) or isinstance(order, bool) or order < 1:
        raise ValueError("order must be a positive integer")

    for position in range(1, order + 1):
        is_odd = position % 2 == 1
        kind = odd_kind if is_odd else ("L" if odd_kind == "C" else "C")
        is_shunt = odd_is_shunt if is_odd else not odd_is_shunt
        values = capacitors if kind == "C" else inductors
        if not values:
            raise ValueError(
                f"Component lists are shorter than ladder order at position {position}"
            )
        value = values.pop(0)
        counters[kind] += 1
        name = f"{kind}{counters[kind]}"
        node1, node2 = (node, 0) if is_shunt else (node, node + 1)
        elements.append(CircuitElement(name, node1, node2, kind, value, logical_name=name))
        if not is_shunt:
            node += 1

    if capacitors or inductors:
        raise ValueError("Component lists longer than the ladder order")
    return NamedCircuit(category, node, tuple(elements), 1, node)


def _build_named_bandpass_top_c(result: Mapping) -> NamedCircuit:
    n = _required(result, "n_resonators")
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("n_resonators must be a positive integer")
    tank_caps = _component_list(result, "c_tank")
    coupling_caps = _component_list(result, "c_coupling")
    if len(tank_caps) != n or len(coupling_caps) != n - 1:
        raise ValueError("Bandpass component lists do not match n_resonators")

    inductance = _required(result, "L_resonant")
    elements: list[CircuitElement] = []
    for index, capacitance in enumerate(tank_caps, start=1):
        elements.append(
            CircuitElement(f"CT{index}", index, 0, "C", capacitance, logical_name=f"CT{index}")
        )
        elements.append(
            CircuitElement(f"LT{index}", index, 0, "L", inductance, logical_name=f"LT{index}")
        )
    for index, capacitance in enumerate(coupling_caps, start=1):
        elements.append(
            CircuitElement(
                f"CK{index}",
                index,
                index + 1,
                "C",
                capacitance,
                logical_name=f"CK{index}",
            )
        )

    c_end_in = result.get("c_end_in")
    c_end_out = result.get("c_end_out")
    if c_end_in is None and c_end_out is None:
        return NamedCircuit("bandpass", n, tuple(elements), 1, n)
    if c_end_in is None or c_end_out is None:
        raise ValueError("c_end_in and c_end_out must both be present or both absent")

    source_node, load_node = n + 1, n + 2
    elements.extend(
        (
            CircuitElement("CIN", source_node, 1, "C", c_end_in, logical_name="CIN"),
            CircuitElement("COUT", n, load_node, "C", c_end_out, logical_name="COUT"),
        )
    )
    return NamedCircuit("bandpass", n + 2, tuple(elements), source_node, load_node)


def build_named_circuit(result: dict, category: str) -> NamedCircuit:
    """Build the authoritative exact named circuit for a synthesis result."""
    if not isinstance(result, Mapping):
        raise ValueError("result must be a mapping")
    if not isinstance(category, str):
        raise ValueError("category must be 'lowpass', 'highpass', or 'bandpass'")
    if category in {"lowpass", "highpass"}:
        return _build_named_ladder(result, category)
    if category == "bandpass":
        return _build_named_bandpass_top_c(result)
    raise ValueError(f"Unknown category {category!r}")


def build_lp_netlist(result: dict) -> tuple[int, list[Branch], int, int]:
    """Compatibility lowpass netlist derived from the named circuit."""
    return build_named_circuit(result, "lowpass").as_legacy_netlist()


def build_hp_netlist(result: dict) -> tuple[int, list[Branch], int, int]:
    """Compatibility highpass netlist derived from the named circuit."""
    return build_named_circuit(result, "highpass").as_legacy_netlist()


def build_bandpass_top_c_netlist(result: dict) -> tuple[int, list[Branch], int, int]:
    """Compatibility Top-C bandpass netlist derived from the named circuit."""
    return build_named_circuit(result, "bandpass").as_legacy_netlist()
