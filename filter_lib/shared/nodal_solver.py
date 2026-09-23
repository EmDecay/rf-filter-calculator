"""Small-matrix AC nodal solver for passive RLC circuits."""

import math
from collections.abc import Callable

from .branch_admittance import (
    branch_admittance_from_logs,
    branch_log_terms,
    is_finite_number,
    log_angular_frequency,
    normalise_branch,
)
from .circuit_model import Branch
from .decimal_nodal_solver import solve_decimal_nodal

_DECIMAL_FALLBACK_LOG_RANGE = math.log(1e7)
# A pinned port row is divided by its conductance, leaving branch terms of about
# 10**-7 / ratio; below this ratio they stay normal binary64 numbers.
_PINNED_LOAD_LOG_LIMIT = math.log(1e250)

# (node 1, node 2, kind, log(value), log(series resistance) or None when lossless)
PreparedBranch = tuple[int, int, str, float, float | None]


def _finite_complex(value: complex) -> bool:
    return math.isfinite(value.real) and math.isfinite(value.imag)


def _solve_complex_linear(matrix: list[list[complex]], rhs: list[complex]) -> list[complex]:
    """Solve A*x = b by Gaussian elimination with partial pivoting.

    Ladder nodal matrices are banded, so elimination and back substitution visit only
    the nonzero entries of each pivot row. Subtracting ``factor * 0`` could change at
    most the sign of an exact zero, so skipping those terms leaves every nonzero
    intermediate, and therefore every solution magnitude, bit-identical.
    """
    n = len(matrix)
    for col in range(n):
        magnitudes = [abs(matrix[row][col]) for row in range(col, n)]
        pivot_row = col + magnitudes.index(max(magnitudes))
        if matrix[pivot_row][col] == 0 or not _finite_complex(matrix[pivot_row][col]):
            raise ValueError("Singular nodal matrix: circuit has a floating or shorted node")
        if pivot_row != col:
            matrix[col], matrix[pivot_row] = matrix[pivot_row], matrix[col]
            rhs[col], rhs[pivot_row] = rhs[pivot_row], rhs[col]

        pivot_values = matrix[col]
        pivot = pivot_values[col]
        pivot_entries = [
            (index, pivot_values[index]) for index in range(col, n) if pivot_values[index] != 0
        ]
        for row in range(col + 1, n):
            entry = matrix[row][col]
            if entry == 0:
                continue
            factor = entry / pivot
            if factor == 0:
                continue
            row_values = matrix[row]
            for index, value in pivot_entries:
                row_values[index] -= factor * value
            rhs[row] -= factor * rhs[col]

    solution: list[complex] = [0j] * n
    for row in range(n - 1, -1, -1):
        acc = rhs[row]
        row_values = matrix[row]
        for index in range(row + 1, n):
            if row_values[index] != 0:
                acc -= row_values[index] * solution[index]
        solution[row] = acc / row_values[row]
        if not _finite_complex(solution[row]):
            raise ValueError("Nodal solution is outside the finite numeric range")
    return solution


def _stamp(matrix: list[list[complex]], n1: int, n2: int, admittance: complex) -> None:
    """Stamp an admittance between two nodes into the nodal matrix."""
    if n1 > 0:
        matrix[n1 - 1][n1 - 1] += admittance
    if n2 > 0:
        matrix[n2 - 1][n2 - 1] += admittance
    if n1 > 0 and n2 > 0:
        matrix[n1 - 1][n2 - 1] -= admittance
        matrix[n2 - 1][n1 - 1] -= admittance


def _validate_and_normalise(
    n_nodes: int,
    branches: list[Branch],
    rs: float,
    rl: float,
    in_node: int,
    out_node: int,
    freqs: list[float],
) -> list[PreparedBranch]:
    if not isinstance(n_nodes, int) or isinstance(n_nodes, bool) or n_nodes < 1:
        raise ValueError("n_nodes must be a positive integer")
    if not is_finite_number(rs) or rs <= 0:
        raise ValueError("rs must be positive and finite")
    if not is_finite_number(rl) or rl <= 0:
        raise ValueError("rl must be positive and finite")
    if any(isinstance(node, bool) or not isinstance(node, int) for node in (in_node, out_node)):
        raise ValueError("in_node and out_node must be integers")
    if not (1 <= in_node <= n_nodes and 1 <= out_node <= n_nodes):
        raise ValueError("in_node and out_node must be within 1..n_nodes")
    if any(not is_finite_number(frequency) or frequency <= 0 for frequency in freqs):
        raise ValueError("frequencies must be positive and finite")

    normalised = [normalise_branch(branch) for branch in branches]
    for n1, n2, _kind, _value, _loss in normalised:
        if not (
            isinstance(n1, int)
            and not isinstance(n1, bool)
            and isinstance(n2, int)
            and not isinstance(n2, bool)
            and 0 <= n1 <= n_nodes
            and 0 <= n2 <= n_nodes
        ):
            raise ValueError(f"Branch node out of range: ({n1}, {n2})")
    # Branch logarithms do not depend on frequency, so a sweep computes them once.
    return [
        (n1, n2, kind, *branch_log_terms(value, series_resistance))
        for n1, n2, kind, value, series_resistance in normalised
    ]


PortStamp = tuple[int, float, bool]  # (node, log conductance, is the source port)


def _pinned_ports(
    branch_stamps: list[tuple[int, int, float, complex]], ports: tuple[PortStamp, PortStamp]
) -> tuple[float, dict[int, float]] | None:
    """Return the float scale and pinned nodes when only huge ports exceed the float range.

    A port conductance above every branch admittance pins its node's voltage: it is a
    positive real on the diagonal that no passive stamp can cancel. Dividing that node's
    row by its largest port conductance leaves every matrix entry at most of order one, so
    partial-pivoting elimination keeps the float path's accuracy for the network, which
    must itself lie within the float range. Port conductances at or below the largest
    branch admittance can be the only damping of a lossless resonance, so they stay in
    the range test. Returns ``None`` when the high-precision solver is still needed.
    """
    if not branch_stamps:
        return None
    branch_logs = [log_magnitude for _n1, _n2, log_magnitude, _unit in branch_stamps]
    log_scale = max(branch_logs)
    ranged = branch_logs + [log for _node, log, _source in ports if log <= log_scale]
    if log_scale - min(ranged) >= _DECIMAL_FALLBACK_LOG_RANGE:
        return None
    pinned: dict[int, float] = {}
    for node, log, _source in ports:
        if log > log_scale:
            pinned[node] = max(log, pinned.get(node, log))
    for node, pinned_log in pinned.items():
        # A node pinned by the source only needs V close to the source voltage; any other
        # pinned node's voltage is the small branch terms themselves, which must stay normal.
        pinned_by_source = any(
            source and port_node == node and log == pinned_log for port_node, log, source in ports
        )
        if not pinned_by_source and pinned_log - log_scale >= _PINNED_LOAD_LOG_LIMIT:
            return None
    return log_scale, pinned


def _output_voltage_at(
    n_nodes: int,
    prepared: list[PreparedBranch],
    rs: float,
    rl: float,
    in_node: int,
    out_node: int,
    frequency: float,
) -> complex:
    """Solve one checked frequency for branches from ``_validate_and_normalise``."""
    log_omega = log_angular_frequency(frequency)
    polar_stamps: list[tuple[int, int, float, complex]] = [
        (n1, n2, *branch_admittance_from_logs(kind, log_value, log_omega, log_loss))
        for n1, n2, kind, log_value, log_loss in prepared
    ]
    source_log_admittance = -math.log(rs)
    load_log_admittance = -math.log(rl)
    polar_stamps.extend(
        (
            (in_node, 0, source_log_admittance, 1 + 0j),
            (out_node, 0, load_log_admittance, 1 + 0j),
        )
    )
    log_scale = max(log_magnitude for _n1, _n2, log_magnitude, _unit in polar_stamps)
    if not math.isfinite(log_scale):
        raise ValueError("nodal admittance scale must be positive and finite")
    log_minimum = min(log_magnitude for _n1, _n2, log_magnitude, _unit in polar_stamps)
    if log_scale - log_minimum < _DECIMAL_FALLBACK_LOG_RANGE:
        return _solve_scaled_float(
            n_nodes, polar_stamps, source_log_admittance, in_node, out_node, log_scale
        )
    ports = ((in_node, source_log_admittance, True), (out_node, load_log_admittance, False))
    pinned = _pinned_ports(polar_stamps[: len(prepared)], ports)
    if pinned is None:
        return solve_decimal_nodal(
            n_nodes,
            polar_stamps,
            source_log_admittance,
            in_node,
            out_node,
        )
    return _solve_pinned_float(n_nodes, polar_stamps[: len(prepared)], ports, out_node, *pinned)


def _solve_scaled_float(
    n_nodes: int,
    polar_stamps: list[tuple[int, int, float, complex]],
    source_log_admittance: float,
    in_node: int,
    out_node: int,
    log_scale: float,
) -> complex:
    """Solve in float with every admittance scaled by the largest one, ``exp(log_scale)``."""
    matrix: list[list[complex]] = [[0j] * n_nodes for _ in range(n_nodes)]
    for n1, n2, log_magnitude, unit in polar_stamps:
        scaled_admittance = unit * math.exp(log_magnitude - log_scale)
        _stamp(matrix, n1, n2, scaled_admittance)
    rhs: list[complex] = [0j] * n_nodes
    rhs[in_node - 1] = math.exp(source_log_admittance - log_scale)
    voltages = _solve_complex_linear(matrix, rhs)
    return voltages[out_node - 1]


def _solve_pinned_float(
    n_nodes: int,
    branch_stamps: list[tuple[int, int, float, complex]],
    ports: tuple[PortStamp, PortStamp],
    out_node: int,
    log_scale: float,
    pinned: dict[int, float],
) -> complex:
    """Solve in float with each pinned node's row divided by its largest port conductance.

    Row division is exact algebra: the equations and their solution are unchanged, and no
    huge port conductance is ever materialized as a float. Pinned nodes are renumbered to
    be eliminated last. Otherwise partial pivoting can choose a divided pinned row to
    eliminate an unpinned column (a parallel pair or fill-in can make its order-one
    branch entry the largest). The pinned node's small voltage would then emerge as the
    residual of order-one terms, with no significant digits left.
    """
    elimination_order = [node for node in range(1, n_nodes + 1) if node not in pinned]
    elimination_order += sorted(pinned)
    position = {node: index + 1 for index, node in enumerate(elimination_order)}
    position[0] = 0

    matrix: list[list[complex]] = [[0j] * n_nodes for _ in range(n_nodes)]
    for n1, n2, log_magnitude, unit in branch_stamps:
        _stamp(matrix, position[n1], position[n2], unit * math.exp(log_magnitude - log_scale))
    rhs: list[complex] = [0j] * n_nodes
    for node, log, source in ports:
        # Ports at or below the branch scale are stamped like branches, even on a pinned
        # node, whose whole row is divided below.
        if log <= log_scale:
            row = position[node] - 1
            matrix[row][row] += math.exp(log - log_scale)
            if source:
                rhs[row] += math.exp(log - log_scale)
    for node, pinned_log in pinned.items():
        row = position[node] - 1
        # exp() may underflow to zero: those branch terms are below binary64 resolution
        # relative to the port conductance that now carries this row.
        factor = math.exp(log_scale - pinned_log)
        matrix[row] = [entry * factor for entry in matrix[row]]
        rhs[row] *= factor
        for port_node, log, source in ports:
            if port_node == node and log > log_scale:
                matrix[row][row] += math.exp(log - pinned_log)
                if source:
                    rhs[row] += math.exp(log - pinned_log)
    voltages = _solve_complex_linear(matrix, rhs)
    return voltages[position[out_node] - 1]


def _solve_output_voltages(
    n_nodes: int,
    branches: list[Branch],
    rs: float,
    rl: float,
    in_node: int,
    out_node: int,
    freqs: list[float],
) -> list[complex]:
    prepared = _validate_and_normalise(n_nodes, branches, rs, rl, in_node, out_node, freqs)
    return [
        _output_voltage_at(n_nodes, prepared, rs, rl, in_node, out_node, frequency)
        for frequency in freqs
    ]


def _transducer_gain_from_voltage(voltage: complex, rs: float, rl: float) -> float:
    try:
        # abs() raises once the magnitude exceeds the float range.
        magnitude = abs(voltage)
    except OverflowError as error:
        raise ValueError("output voltage magnitude must be finite") from error
    if not math.isfinite(magnitude):
        raise ValueError("output voltage magnitude must be finite")
    if magnitude == 0:
        return 0.0
    log_gain = math.log(4.0) + (math.log(rs) - math.log(rl)) + 2.0 * math.log(magnitude)
    try:
        gain = math.exp(log_gain)
    except OverflowError as error:
        raise ValueError("transducer power gain is outside the finite numeric range") from error
    if not math.isfinite(gain) or gain < 0:
        raise ValueError("transducer power gain is outside the finite numeric range")
    return gain


def solve_transducer_power_gain(
    n_nodes: int,
    branches: list[Branch],
    rs: float,
    rl: float,
    in_node: int,
    out_node: int,
    freqs: list[float],
) -> list[float]:
    """Return transducer power gain for finite, independently specified ports."""
    voltages = _solve_output_voltages(n_nodes, branches, rs, rl, in_node, out_node, freqs)
    return [_transducer_gain_from_voltage(voltage, rs, rl) for voltage in voltages]


def make_transducer_gain_evaluator(
    n_nodes: int,
    branches: list[Branch],
    rs: float,
    rl: float,
    in_node: int,
    out_node: int,
) -> Callable[[float], float]:
    """Validate a circuit once and return a single-frequency transducer-gain function.

    Each call runs exactly the arithmetic of ``solve_transducer_power_gain`` for one
    frequency, so results are bit-identical; only the per-call circuit validation and
    branch normalisation are skipped.
    """
    prepared = _validate_and_normalise(n_nodes, branches, rs, rl, in_node, out_node, [])

    def evaluate(frequency: float) -> float:
        if not is_finite_number(frequency) or frequency <= 0:
            raise ValueError("frequencies must be positive and finite")
        voltage = _output_voltage_at(n_nodes, prepared, rs, rl, in_node, out_node, frequency)
        return _transducer_gain_from_voltage(voltage, rs, rl)

    return evaluate


def solve_s21(
    n_nodes: int,
    branches: list[Branch],
    rs: float,
    rl: float,
    in_node: int,
    out_node: int,
    freqs: list[float],
) -> list[float]:
    """Return the historical normalised voltage-transfer magnitude."""
    gains = solve_transducer_power_gain(n_nodes, branches, rs, rl, in_node, out_node, freqs)
    return [math.sqrt(gain) for gain in gains]
