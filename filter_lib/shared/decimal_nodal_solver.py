"""Adaptive high-precision fallback for ill-conditioned nodal matrices."""

import math
from decimal import Context, Decimal, localcontext

PolarStamp = tuple[int, int, float, complex]
DecimalComplex = tuple[Decimal, Decimal]

_ZERO: DecimalComplex = (Decimal(0), Decimal(0))

# Stamp magnitudes and unit phases derive from binary64 values, which carry at most
# 17 significant digits, so 20 digits hold them exactly enough. Only the elimination
# needs more digits: enough to keep the smallest conductance beside the largest.
_STAMP_CONTEXT = Context(prec=20)
# Working digits for splitting an exponent into decades; ln(10) carries 50 digits.
_SPLIT_CONTEXT = Context(prec=40)
_DECIMAL_LN10 = Context(prec=50).ln(Decimal(10))
_LOG_TEN = math.log(10.0)
# Above this exponent math.exp is a normal float whose exact decimal expansion is short
# enough to convert directly; below it, splitting off the power of ten is cheaper.
_DIRECT_EXPONENT_MIN = -100.0


def _scaled_magnitude(log_magnitude: float, log_scale: float) -> Decimal:
    """Return ``exp(log_magnitude - log_scale)`` to binary64 relative accuracy.

    Splitting the exponent into ``decades * ln(10) + remainder`` keeps ``math.exp`` in
    its normal range and applies the power of ten exactly, however small the magnitude.
    Evaluating ``Decimal.exp`` at elimination precision instead cost tens of seconds
    per sweep for extreme but valid port resistances or Q, without adding information.
    """
    exponent = log_magnitude - log_scale
    if exponent >= _DIRECT_EXPONENT_MIN and _difference_is_exact(
        log_magnitude, log_scale, exponent
    ):
        return _STAMP_CONTEXT.create_decimal_from_float(math.exp(exponent))
    # An extreme port can set a scale near 690, where binary64 spaces values 1e-13 apart;
    # a rounded difference would give every branch magnitude that relative error, enough
    # to erase a near-resonant cancellation. The Decimal difference of the two logs is exact.
    exact_exponent = _SPLIT_CONTEXT.subtract(
        Decimal.from_float(log_magnitude), Decimal.from_float(log_scale)
    )
    decades = math.floor(exponent / _LOG_TEN)
    remainder = float(
        _SPLIT_CONTEXT.subtract(exact_exponent, _SPLIT_CONTEXT.multiply(decades, _DECIMAL_LN10))
    )
    return _STAMP_CONTEXT.create_decimal_from_float(math.exp(remainder)).scaleb(decades)


def _difference_is_exact(minuend: float, subtrahend: float, difference: float) -> bool:
    """Whether the binary64 ``difference = minuend - subtrahend`` lost nothing to rounding.

    This is Knuth's TwoSum error term for ``minuend + (-subtrahend)``, which recovers the
    exact rounding error of one addition.
    """
    negated = -subtrahend
    recovered_negated = difference - minuend
    recovered_minuend = difference - recovered_negated
    error = (minuend - recovered_minuend) + (negated - recovered_negated)
    return error == 0.0


def _stamp_part(value: float) -> Decimal:
    """Convert one unit-phase component; exact zeros stay zero."""
    return _STAMP_CONTEXT.create_decimal_from_float(value) if value else _ZERO[0]


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
        candidates = [
            (_norm_squared(matrix[row][column]), row)
            for row in range(column, size)
            if matrix[row][column] != _ZERO
        ]
        if not candidates:
            raise ValueError("Singular nodal matrix: circuit has a floating or shorted node")
        # The first row with the largest magnitude, as ``max`` over all rows would pick.
        pivot_row = max(candidates, key=lambda candidate: candidate[0])[1]
        if pivot_row != column:
            matrix[column], matrix[pivot_row] = matrix[pivot_row], matrix[column]
            rhs[column], rhs[pivot_row] = rhs[pivot_row], rhs[column]
        pivot = matrix[column][column]
        # Ladder matrices are banded. Subtracting an exact zero product leaves a Decimal
        # unchanged, so only nonzero entries of the pivot row take part. The update is
        # ``_subtract(entry, _multiply(factor, value))`` written out, with the same
        # operations in the same order, because it is the innermost loop of every sweep.
        pivot_entries = [
            (index, matrix[column][index])
            for index in range(column, size)
            if matrix[column][index] != _ZERO
        ]
        for row in range(column + 1, size):
            if matrix[row][column] == _ZERO:
                continue
            factor_real, factor_imag = _divide(matrix[row][column], pivot)
            if factor_real == 0 and factor_imag == 0:
                continue
            row_values = matrix[row]
            for index, (value_real, value_imag) in pivot_entries:
                entry_real, entry_imag = row_values[index]
                row_values[index] = (
                    entry_real - (factor_real * value_real - factor_imag * value_imag),
                    entry_imag - (factor_real * value_imag + factor_imag * value_real),
                )
            rhs[row] = _subtract(rhs[row], _multiply((factor_real, factor_imag), rhs[column]))

    solution = [_ZERO] * size
    for row in range(size - 1, -1, -1):
        accumulator = rhs[row]
        row_values = matrix[row]
        for index in range(row + 1, size):
            if row_values[index] != _ZERO:
                accumulator = _subtract(accumulator, _multiply(row_values[index], solution[index]))
        solution[row] = _divide(accumulator, row_values[row])
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
    # Accumulation must hold the smallest conductance beside the largest, so elimination
    # runs with ``dynamic_decades`` extra digits; the magnitudes themselves do not.
    magnitudes = [_scaled_magnitude(log_magnitude, log_scale) for log_magnitude in log_values]
    source_magnitude = _scaled_magnitude(source_log_admittance, log_scale)
    with localcontext() as context:
        context.prec = max(50, dynamic_decades + 34)
        matrix = [[_ZERO for _column in range(n_nodes)] for _row in range(n_nodes)]
        for (n1, n2, _log_magnitude, unit), magnitude in zip(stamps, magnitudes):
            admittance = (
                magnitude * _stamp_part(unit.real),
                magnitude * _stamp_part(unit.imag),
            )
            _stamp(matrix, n1, n2, admittance)
        rhs = [_ZERO for _node in range(n_nodes)]
        rhs[in_node - 1] = (source_magnitude, Decimal(0))
        value = _solve(matrix, rhs)[out_node - 1]

    result = complex(float(value[0]), float(value[1]))
    if not math.isfinite(result.real) or not math.isfinite(result.imag):
        raise ValueError("Nodal solution is outside the finite numeric range")
    return result
