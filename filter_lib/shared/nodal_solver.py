"""Small-matrix AC nodal solver for passive RLC circuits."""

import math

from .branch_admittance import (
    _branch_admittance_at_frequency,
    is_finite_number,
    normalise_branch,
)
from .circuit_model import Branch
from .decimal_nodal_solver import solve_decimal_nodal

_DECIMAL_FALLBACK_LOG_RANGE = math.log(1e7)


def _finite_complex(value: complex) -> bool:
    return math.isfinite(value.real) and math.isfinite(value.imag)


def _solve_complex_linear(matrix: list[list[complex]], rhs: list[complex]) -> list[complex]:
    """Solve A*x = b by Gaussian elimination with partial pivoting."""
    n = len(matrix)
    for col in range(n):
        pivot_row = max(range(col, n), key=lambda row: abs(matrix[row][col]))
        if matrix[pivot_row][col] == 0 or not _finite_complex(matrix[pivot_row][col]):
            raise ValueError("Singular nodal matrix: circuit has a floating or shorted node")
        if pivot_row != col:
            matrix[col], matrix[pivot_row] = matrix[pivot_row], matrix[col]
            rhs[col], rhs[pivot_row] = rhs[pivot_row], rhs[col]

        pivot = matrix[col][col]
        for row in range(col + 1, n):
            factor = matrix[row][col] / pivot
            if factor == 0:
                continue
            for index in range(col, n):
                matrix[row][index] -= factor * matrix[col][index]
            rhs[row] -= factor * rhs[col]

    solution: list[complex] = [0j] * n
    for row in range(n - 1, -1, -1):
        acc = rhs[row]
        for index in range(row + 1, n):
            acc -= matrix[row][index] * solution[index]
        solution[row] = acc / matrix[row][row]
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
) -> list[tuple[int, int, str, float, float]]:
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
    return normalised


def _solve_output_voltages(
    n_nodes: int,
    branches: list[Branch],
    rs: float,
    rl: float,
    in_node: int,
    out_node: int,
    freqs: list[float],
) -> list[complex]:
    normalised = _validate_and_normalise(n_nodes, branches, rs, rl, in_node, out_node, freqs)
    result: list[complex] = []
    for frequency in freqs:
        polar_stamps: list[tuple[int, int, float, complex]] = []
        for n1, n2, kind, value, series_resistance in normalised:
            log_magnitude, unit = _branch_admittance_at_frequency(
                kind, value, frequency, series_resistance
            )
            polar_stamps.append((n1, n2, log_magnitude, unit))
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
        if log_scale - log_minimum >= _DECIMAL_FALLBACK_LOG_RANGE:
            result.append(
                solve_decimal_nodal(
                    n_nodes,
                    polar_stamps,
                    source_log_admittance,
                    in_node,
                    out_node,
                )
            )
            continue
        matrix: list[list[complex]] = [[0j] * n_nodes for _ in range(n_nodes)]
        for n1, n2, log_magnitude, unit in polar_stamps:
            scaled_admittance = unit * math.exp(log_magnitude - log_scale)
            _stamp(matrix, n1, n2, scaled_admittance)
        rhs: list[complex] = [0j] * n_nodes
        rhs[in_node - 1] = math.exp(source_log_admittance - log_scale)
        voltages = _solve_complex_linear(matrix, rhs)
        result.append(voltages[out_node - 1])
    return result


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
    gains: list[float] = []
    for voltage in voltages:
        magnitude = abs(voltage)
        if not math.isfinite(magnitude):
            raise ValueError("output voltage magnitude must be finite")
        if magnitude == 0:
            gains.append(0.0)
            continue
        log_gain = math.log(4.0) + (math.log(rs) - math.log(rl)) + 2.0 * math.log(magnitude)
        try:
            gain = math.exp(log_gain)
        except OverflowError as error:
            raise ValueError("transducer power gain is outside the finite numeric range") from error
        if not math.isfinite(gain) or gain < 0:
            raise ValueError("transducer power gain is outside the finite numeric range")
        gains.append(gain)
    return gains


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
