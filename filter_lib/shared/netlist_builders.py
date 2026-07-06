"""Netlist builders that turn the tool's own result dicts into branch lists.

Each builder returns ``(n_nodes, branches, in_node, out_node)`` for
``netlist_simulation.solve_s21``. Builders read the production result dicts
directly, so any drift in synthesis output breaks the simulation tests.
"""

from .netlist_simulation import Branch

# Ladder position rules: (filter category, topology) -> (kind of odd
# positions, whether odd positions are shunt). Even positions are always
# the other kind in the other placement.
#
# Two independent facts combine here. Topology fixes PLACEMENT: Pi starts
# with a shunt element, T starts with a series element. Filter category
# fixes which KIND lives in each placement: lowpass puts C in shunt and L
# in series (each shorts/blocks highs), highpass is the dual (L in shunt,
# C in series, each shorts/blocks lows). That is why LP-Pi and HP-T both
# start with a capacitor despite one being shunt and the other series —
# the first component's kind is placement × category, never topology
# alone. This table must stay consistent with
# lp_hp_base_calculations._component_kind, or simulated circuits would
# diverge from the component tables they are meant to validate.
_ODD_SLOT_RULES: dict[tuple[str, str], tuple[str, bool]] = {
    ("lowpass", "pi"): ("C", True),  # shunt C first, series L between
    ("lowpass", "t"): ("L", False),  # series L first, shunt C between
    ("highpass", "t"): ("C", False),  # series C first, shunt L between
    ("highpass", "pi"): ("L", True),  # shunt L first, series C between
}


def _build_ladder(
    capacitors: list[float],
    inductors: list[float],
    order: int,
    odd_kind: str,
    odd_is_shunt: bool,
) -> tuple[int, list[Branch], int, int]:
    """Walk ladder positions 1..order, consuming each list in output order.

    The calculation layer emits capacitors and inductors already sorted by
    ladder position, so interleaving by odd/even slot reconstructs the
    physical circuit. Leftover values after the walk mean the result dict
    and the claimed order disagree — fail loudly instead of simulating a
    circuit that is not the one displayed.

    Returns:
        (n_nodes, branches, in_node, out_node); input is node 1, output is
        the last series-created node.

    Raises:
        ValueError: If the component lists are longer than the ladder order.
    """
    caps = list(capacitors)
    inds = list(inductors)
    branches: list[Branch] = []
    node = 1
    for position in range(1, order + 1):
        is_odd = position % 2 == 1
        kind = odd_kind if is_odd else ("L" if odd_kind == "C" else "C")
        is_shunt = odd_is_shunt if is_odd else not odd_is_shunt
        value = caps.pop(0) if kind == "C" else inds.pop(0)
        if is_shunt:
            branches.append((node, 0, kind, value))
        else:
            branches.append((node, node + 1, kind, value))
            node += 1
    if caps or inds:
        raise ValueError("Component lists longer than the ladder order")
    return node, branches, 1, node


def _lp_hp_netlist(result: dict, category: str) -> tuple[int, list[Branch], int, int]:
    topology = result["topology"]
    try:
        odd_kind, odd_is_shunt = _ODD_SLOT_RULES[(category, topology)]
    except KeyError:
        raise ValueError(f"Unknown topology {topology!r}: use 'pi' or 't'") from None
    return _build_ladder(
        result["capacitors"], result["inductors"], result["order"], odd_kind, odd_is_shunt
    )


def build_lp_netlist(result: dict) -> tuple[int, list[Branch], int, int]:
    """Lowpass ladder from a CLI-style result dict (capacitors/inductors/order/topology)."""
    return _lp_hp_netlist(result, "lowpass")


def build_hp_netlist(result: dict) -> tuple[int, list[Branch], int, int]:
    """Highpass ladder from a CLI-style result dict (capacitors/inductors/order/topology)."""
    return _lp_hp_netlist(result, "highpass")


def build_bandpass_top_c_netlist(result: dict) -> tuple[int, list[Branch], int, int]:
    """Top-C coupled-resonator network from a bandpass result dict.

    Tanks sit at nodes 1..n (shunt C ∥ L), coupling caps connect adjacent
    tanks. When the result carries ``c_end_in``/``c_end_out`` end-coupling
    capacitors, the source and load attach through them at dedicated nodes;
    otherwise the source and load connect to the end tanks directly.
    """
    n = result["n_resonators"]
    inductance = result["L_resonant"]
    branches: list[Branch] = []
    for i in range(n):
        node = i + 1
        branches.append((node, 0, "C", result["c_tank"][i]))
        branches.append((node, 0, "L", inductance))
    for i in range(n - 1):
        branches.append((i + 1, i + 2, "C", result["c_coupling"][i]))

    c_end_in = result.get("c_end_in")
    c_end_out = result.get("c_end_out")
    if c_end_in is None and c_end_out is None:
        return n, branches, 1, n
    if c_end_in is None or c_end_out is None:
        raise ValueError("c_end_in and c_end_out must both be present or both absent")

    source_node, load_node = n + 1, n + 2
    branches.append((source_node, 1, "C", c_end_in))
    branches.append((n, load_node, "C", c_end_out))
    return n + 2, branches, source_node, load_node
