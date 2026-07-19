"""Adaptive high-precision fallback for ill-conditioned nodal matrices."""

import math
from decimal import Decimal, localcontext

PolarStamp = tuple[int, int, float, complex]
DecimalComplex = tuple[Decimal, Decimal]

_ZERO: DecimalComplex = (Decimal(0), Decimal(0))


def _add(first: DecimalComplex, second: DecimalComplex) -> DecimalComplex:
    return first[0] + second[0], first[1] + second[1]


def _subtract(first: DecimalComplex, second: DecimalComplex) -> DecimalComplex:
    return first[0] - second[0], first[1] - second[1]


def _multiply(first: DecimalComplex, second: DecimalComplex) -> DecimalComplex:
    return (
        first[0] * second[0] - first[1] * second[1],
        first[0] * second[1] + first[1] * second[0],
    )


def _divide(numerator: DecimalComplex, denominator: DecimalComplex) -> DecimalComplex:
    scale = denominator[0] * denominator[0] + denominator[1] * denominator[1]
    if scale == 0:
        raise ValueError("Singular nodal matrix: circuit has a floating or shorted node")
    return (
        (numerator[0] * denominator[0] + numerator[1] * denominator[1]) / scale,
        (numerator[1] * denominator[0] - numerator[0] * denominator[1]) / scale,
    )


def _norm_squared(value: DecimalComplex) -> Decimal:
    return value[0] * value[0] + value[1] * value[1]


def _stamp(
    matrix: list[list[DecimalComplex]], n1: int, n2: int, admittance: DecimalComplex
) -> None:
    if n1 > 0:
        matrix[n1 - 1][n1 - 1] = _add(matrix[n1 - 1][n1 - 1], admittance)
    if n2 > 0:
        matrix[n2 - 1][n2 - 1] = _add(matrix[n2 - 1][n2 - 1], admittance)
    if n1 > 0 and n2 > 0:
        matrix[n1 - 1][n2 - 1] = _subtract(matrix[n1 - 1][n2 - 1], admittance)
        matrix[n2 - 1][n1 - 1] = _subtract(matrix[n2 - 1][n1 - 1], admittance)


def _solve(matrix: list[list[DecimalComplex]], rhs: list[DecimalComplex]) -> list[DecimalComplex]:
    size = len(matrix)
    for column in range(size):
        pivot_row = max(range(column, size), key=lambda row: _norm_squared(matrix[row][column]))
        if _norm_squared(matrix[pivot_row][column]) == 0:
            raise ValueError("Singular nodal matrix: circuit has a floating or shorted node")
        if pivot_row != column:
            matrix[column], matrix[pivot_row] = matrix[pivot_row], matrix[column]
            rhs[column], rhs[pivot_row] = rhs[pivot_row], rhs[column]
        pivot = matrix[column][column]
        for row in range(column + 1, size):
            factor = _divide(matrix[row][column], pivot)
            if factor == _ZERO:
                continue
            for index in range(column, size):
                matrix[row][index] = _subtract(
                    matrix[row][index], _multiply(factor, matrix[column][index])
                )
            rhs[row] = _subtract(rhs[row], _multiply(factor, rhs[column]))

    solution = [_ZERO] * size
    for row in range(size - 1, -1, -1):
        accumulator = rhs[row]
        for index in range(row + 1, size):
            accumulator = _subtract(accumulator, _multiply(matrix[row][index], solution[index]))
        solution[row] = _divide(accumulator, matrix[row][row])
    return solution


def solve_decimal_nodal(
    n_nodes: int,
    stamps: list[PolarStamp],
    source_log_admittance: float,
    in_node: int,
    out_node: int,
) -> complex:
    """Solve one frequency while retaining conductance differences below float epsilon."""
    log_values = [log_magnitude for _n1, _n2, log_magnitude, _unit in stamps]
    log_scale = max(log_values)
    dynamic_decades = math.ceil((log_scale - min(log_values)) / math.log(10.0))
    with localcontext() as context:
        context.prec = max(50, dynamic_decades + 34)
        matrix = [[_ZERO for _column in range(n_nodes)] for _row in range(n_nodes)]
        for n1, n2, log_magnitude, unit in stamps:
            magnitude = Decimal.from_float(log_magnitude - log_scale).exp()
            admittance = (
                magnitude * Decimal.from_float(unit.real),
                magnitude * Decimal.from_float(unit.imag),
            )
            _stamp(matrix, n1, n2, admittance)
        rhs = [_ZERO for _node in range(n_nodes)]
        source_magnitude = Decimal.from_float(source_log_admittance - log_scale).exp()
        rhs[in_node - 1] = (source_magnitude, Decimal(0))
        value = _solve(matrix, rhs)[out_node - 1]

    result = complex(float(value[0]), float(value[1]))
    if not math.isfinite(result.real) or not math.isfinite(result.imag):
        raise ValueError("Nodal solution is outside the finite numeric range")
    return result
