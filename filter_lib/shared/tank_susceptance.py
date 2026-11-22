"""The admittance a band-pass tank node presents, for sizing and tuning its trimmer.

A tank node's admittance here is the driving-point admittance at that node with every
other tank node shorted to ground and the ports' voltage sources shorted, so each port is
its resistance to ground. A coupling capacitor to another tank node then counts in full
(the diagonal entry of the nodal matrix), an end capacitor counts in series with its
port's resistance (its effective shunt), and a branch through an internal node (a
trimmer's capacitance in series with its inductance) counts as the series chain. Every
element keeps its series resistance (its Q). The imaginary part is the node's
susceptance; at the calibrated tank frequency it is zero for the calculated design.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from .circuit_model import CircuitElement, NamedCircuit

TWO_PI = 2.0 * math.pi


def element_admittance(element: CircuitElement, omega: float) -> complex:
    """The admittance of one element with its series resistance at ``omega`` (rad/s)."""
    if element.kind == "R":
        return complex(1.0 / element.value)
    if element.kind == "L":
        reactance = omega * element.value
    else:
        reactance = omega * element.series_inductance_h - 1.0 / (omega * element.value)
    return 1.0 / complex(element.series_resistance_ohm, reactance)


def _reachable(
    circuit: NamedCircuit, node: int, grounded: frozenset[int], excluded: frozenset[str]
) -> list[int]:
    """``node`` first, then every node reached from it without passing a grounded node."""
    order = [node]
    position = 0
    while position < len(order):
        current = order[position]
        position += 1
        for element in circuit.elements:
            if element.name in excluded or current not in (element.node1, element.node2):
                continue
            other = element.node2 if element.node1 == current else element.node1
            if other != 0 and other not in grounded and other not in order:
                order.append(other)
    return order


def _solve(matrix: list[list[complex]], vector: list[complex]) -> list[complex]:
    """Solve a small dense complex system by Gaussian elimination with partial pivoting."""
    size = len(vector)
    rows = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda index: abs(rows[index][column]))
        if abs(rows[pivot][column]) == 0:
            raise ValueError("The tank node's network is singular at this frequency")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for index in range(column + 1, size):
            factor = rows[index][column] / rows[column][column]
            if factor:
                for position in range(column, size + 1):
                    rows[index][position] -= factor * rows[column][position]
    solution = [0j] * size
    for index in range(size - 1, -1, -1):
        total = rows[index][size] - sum(
            rows[index][position] * solution[position] for position in range(index + 1, size)
        )
        solution[index] = total / rows[index][index]
    return solution


def node_admittance(
    circuit: NamedCircuit,
    node: int,
    frequency_hz: float,
    tank_nodes: Iterable[int],
    ports: Mapping[int, float],
    excluded: Iterable[str] = (),
) -> complex:
    """The driving-point admittance at tank ``node`` (see the module docstring).

    ``tank_nodes`` are the resonator nodes; every one but ``node`` is shorted.
    ``ports`` maps each port node to its resistance. ``excluded`` names elements left out
    (the trimmer chain whose own admittance is solved separately).
    """
    omega = TWO_PI * frequency_hz
    grounded = frozenset(tank_nodes) - {node}
    skipped = frozenset(excluded)
    nodes = _reachable(circuit, node, grounded, skipped)
    index = {item: position for position, item in enumerate(nodes)}
    size = len(nodes)
    matrix = [[0j] * size for _ in range(size)]
    for item, resistance in ports.items():
        if item in index:
            matrix[index[item]][index[item]] += 1.0 / resistance
    for element in circuit.elements:
        if element.name in skipped:
            continue
        first, second = element.node1, element.node2
        if first not in index and second not in index:
            continue
        admittance = element_admittance(element, omega)
        for end in (first, second):
            if end in index:
                matrix[index[end]][index[end]] += admittance
        if first in index and second in index:
            matrix[index[first]][index[second]] -= admittance
            matrix[index[second]][index[first]] -= admittance
    if size == 1:
        return matrix[0][0]
    # Schur complement onto ``node`` (index 0): Y00 - Y0I · inv(YII) · YI0.
    inner = [row[1:] for row in matrix[1:]]
    coupling = [matrix[position][0] for position in range(1, size)]
    solved = _solve(inner, coupling)
    return matrix[0][0] - sum(
        matrix[0][position + 1] * solved[position] for position in range(size - 1)
    )


def node_susceptance(
    circuit: NamedCircuit,
    node: int,
    frequency_hz: float,
    tank_nodes: Iterable[int],
    ports: Mapping[int, float],
    excluded: Iterable[str] = (),
) -> float:
    """The imaginary part of :func:`node_admittance`, in siemens."""
    return node_admittance(circuit, node, frequency_hz, tank_nodes, ports, excluded).imag
