"""AC nodal-analysis solver for RLC ladder networks (pure stdlib).

Solves |S21|(f) for the exact circuits the tool prescribes, so synthesis
changes are accepted against simulated behavior rather than formula
expectations. No numpy: complex Gaussian elimination with partial pivoting
is fast enough for the small (< ~25 node) matrices filters need.

Branch model: ``(node1, node2, kind, value)`` with ``kind`` one of
``"C"``, ``"L"``, ``"R"``; node 0 is ground.
"""

import math

Branch = tuple[int, int, str, float]


def _solve_complex_linear(matrix: list[list[complex]], rhs: list[complex]) -> list[complex]:
    """Solve A·x = b by Gaussian elimination with partial pivoting.

    Mutates its arguments (callers pass freshly built rows).
    Raises ValueError on a singular (or numerically singular) matrix.
    """
    n = len(matrix)
    for col in range(n):
        # Partial pivoting: largest-magnitude entry on or below the diagonal
        pivot_row = max(range(col, n), key=lambda r: abs(matrix[r][col]))
        if abs(matrix[pivot_row][col]) < 1e-300:
            raise ValueError("Singular nodal matrix: circuit has a floating or shorted node")
        if pivot_row != col:
            matrix[col], matrix[pivot_row] = matrix[pivot_row], matrix[col]
            rhs[col], rhs[pivot_row] = rhs[pivot_row], rhs[col]

        pivot = matrix[col][col]
        for row in range(col + 1, n):
            factor = matrix[row][col] / pivot
            if factor == 0:
                continue
            for k in range(col, n):
                matrix[row][k] -= factor * matrix[col][k]
            rhs[row] -= factor * rhs[col]

    solution: list[complex] = [0j] * n
    for row in range(n - 1, -1, -1):
        acc = rhs[row]
        for k in range(row + 1, n):
            acc -= matrix[row][k] * solution[k]
        solution[row] = acc / matrix[row][row]
    return solution


def _stamp(matrix: list[list[complex]], n1: int, n2: int, y: complex) -> None:
    """Stamp an admittance between two nodes into the nodal matrix (0 = ground)."""
    if n1 > 0:
        matrix[n1 - 1][n1 - 1] += y
    if n2 > 0:
        matrix[n2 - 1][n2 - 1] += y
    if n1 > 0 and n2 > 0:
        matrix[n1 - 1][n2 - 1] -= y
        matrix[n2 - 1][n1 - 1] -= y


def _branch_admittance(kind: str, value: float, omega: float) -> complex:
    if kind == "C":
        return 1j * omega * value
    if kind == "L":
        return 1 / (1j * omega * value)
    if kind == "R":
        return 1 / value
    raise ValueError(f"Unknown branch kind {kind!r}: use 'C', 'L', or 'R'")


def solve_s21(
    n_nodes: int,
    branches: list[Branch],
    rs: float,
    rl: float,
    in_node: int,
    out_node: int,
    freqs: list[float],
) -> list[float]:
    """Return |S21| at each frequency for an RLC network.

    The source is the Norton equivalent of a 1 V Thevenin source with
    series ``rs`` (current 1/rs with rs shunt at ``in_node``); ``rl``
    shunts ``out_node``. ``S21 = 2·V_out·sqrt(rs/rl)``.

    Why that scaling makes a matched, lossless passband read exactly 1.0:
    |S21|^2 is power delivered to the load over power available from the
    source. Available power is V_th^2/(4·rs) = 1/(4·rs); delivered power is
    V_out^2/rl. Their ratio is (2·V_out·sqrt(rs/rl))^2 — a lossless network
    presenting a matched input delivers all available power, so |S21| = 1.
    Changing the scale factor would silently re-baseline every dB value the
    plots, threshold tables, and acceptance tests consume.

    Args:
        n_nodes: Number of non-ground nodes (numbered 1..n_nodes; 0 = ground)
        branches: (node1, node2, kind, value) with kind 'C'/'L'/'R',
            values in F/H/Ohms
        rs: Source resistance in Ohms
        rl: Load resistance in Ohms
        in_node: Node the source drives
        out_node: Node the load shunts
        freqs: Frequencies in Hz to sweep

    Returns:
        |S21| magnitude (linear, unitless) per frequency, same order as freqs.

    Raises:
        ValueError: If rs/rl is not positive and finite, a port node is
            outside 1..n_nodes, a branch references an unknown node, or the
            circuit produces a singular nodal matrix.
    """
    if not math.isfinite(rs) or rs <= 0:
        raise ValueError("rs must be positive and finite")
    if not math.isfinite(rl) or rl <= 0:
        raise ValueError("rl must be positive and finite")
    if not (1 <= in_node <= n_nodes and 1 <= out_node <= n_nodes):
        raise ValueError("in_node and out_node must be within 1..n_nodes")
    for n1, n2, _kind, _value in branches:
        if not (0 <= n1 <= n_nodes and 0 <= n2 <= n_nodes):
            raise ValueError(f"Branch node out of range: ({n1}, {n2})")

    scale = 2.0 * math.sqrt(rs / rl)
    result: list[float] = []
    for f in freqs:
        omega = 2 * math.pi * f
        matrix: list[list[complex]] = [[0j] * n_nodes for _ in range(n_nodes)]
        for n1, n2, kind, value in branches:
            _stamp(matrix, n1, n2, _branch_admittance(kind, value, omega))
        _stamp(matrix, in_node, 0, 1 / rs)
        _stamp(matrix, out_node, 0, 1 / rl)

        rhs: list[complex] = [0j] * n_nodes
        rhs[in_node - 1] = 1 / rs
        voltages = _solve_complex_linear(matrix, rhs)
        result.append(abs(voltages[out_node - 1]) * scale)
    return result


def find_3db_edges(freqs: list[float], mags: list[float]) -> tuple[float | None, float | None]:
    """Find the -3 dB band edges relative to the passband maximum.

    Linearly interpolates across the threshold crossings. Returns the grid
    boundary frequency when the response never drops below the threshold on
    that side, and (None, None) when nothing reaches the threshold.
    """
    peak = max(mags)
    threshold = peak / math.sqrt(2)
    above = [i for i, m in enumerate(mags) if m >= threshold]
    if not above:
        return None, None
    lo_i, hi_i = above[0], above[-1]

    def interp(i_outside: int, i_inside: int) -> float:
        m1, m2 = mags[i_outside], mags[i_inside]
        f1, f2 = freqs[i_outside], freqs[i_inside]
        if m2 == m1:
            return f1
        return f1 + (threshold - m1) / (m2 - m1) * (f2 - f1)

    f_lo = interp(lo_i - 1, lo_i) if lo_i > 0 else freqs[0]
    f_hi = interp(hi_i + 1, hi_i) if hi_i < len(mags) - 1 else freqs[-1]
    return f_lo, f_hi


def passband_ripple_db(
    freqs: list[float], mags: list[float], f_limit: float
) -> tuple[float, float]:
    """Return (max_db, min_db) of the response over freqs <= f_limit.

    dB values are absolute (0 dB = unity |S21|), so a matched Chebyshev
    passband reads max ≈ 0 and min ≈ -ripple.

    Raises:
        ValueError: If no frequency point lies at or below f_limit.
    """
    in_band = [m for f, m in zip(freqs, mags) if f <= f_limit]
    if not in_band:
        raise ValueError("No frequency points at or below f_limit")
    db = [20 * math.log10(m) if m > 0 else -math.inf for m in in_band]
    return max(db), min(db)


def logspace(start_exp: float, stop_exp: float, points: int) -> list[float]:
    """Log-spaced grid from 10**start_exp to 10**stop_exp inclusive."""
    if points < 2:
        raise ValueError("points must be >= 2")
    step = (stop_exp - start_exp) / (points - 1)
    return [10 ** (start_exp + i * step) for i in range(points)]
