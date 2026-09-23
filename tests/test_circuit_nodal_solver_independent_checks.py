"""Nodal-solver results checked against arithmetic that shares no code with the solver.

References are a cascaded ABCD two-port, Cramer's rule on the textbook nodal matrix,
reciprocity, and closed-form dividers. Port resistances far from the branch
admittances push the same circuits through the high-precision fallback, so both
solver paths are held to the same independent answer.
"""

import math

import pytest

from filter_lib.shared.nodal_solver import solve_transducer_power_gain

FREQ = 10e6
OMEGA = 2 * math.pi * FREQ


def _impedance(kind, value, series_resistance=0.0):
    if kind == "R":
        return value
    reactance = 1j * OMEGA * value if kind == "L" else 1 / (1j * OMEGA * value)
    return series_resistance + reactance


def _abcd_pi_gain(c1, inductance, c2, rs, rl):
    """Shunt C1, series L, shunt C2 as a cascade of elementary two-ports."""
    y1, z, y2 = 1 / _impedance("C", c1), _impedance("L", inductance), 1 / _impedance("C", c2)
    a, b, c, d = 1, 0, y1, 1
    a, b, c, d = a, a * z + b, c, c * z + d
    a, b, c, d = a + b * y2, b, c + d * y2, d
    return 4 * rs * rl / abs(a * rl + b + c * rs * rl + d * rs) ** 2


# Scaled 10 MHz Butterworth-like pi section. The 1 uOhm source makes the port
# conductance 1e6 S against ~0.02 S branches, beyond the float solver's 1e7 range.
PI = (318.3e-12, 1.5915e-6, 318.3e-12)
PORTS = [(50.0, 50.0), (1e-6, 50.0)]
PORT_IDS = ["float-path", "decimal-path"]


@pytest.mark.parametrize(("rs", "rl"), PORTS, ids=PORT_IDS)
def test_ground_first_branches_match_node_first_branches_and_abcd(rs, rl):
    """A shunt part is the same part whichever terminal is listed first."""
    c1, inductance, c2 = PI
    node_first = [(1, 0, "C", c1), (1, 2, "L", inductance), (2, 0, "C", c2)]
    ground_first = [(0, 1, "C", c1), (2, 1, "L", inductance), (0, 2, "C", c2)]
    expected = _abcd_pi_gain(c1, inductance, c2, rs, rl)

    for branches in (node_first, ground_first):
        (gain,) = solve_transducer_power_gain(2, branches, rs, rl, 1, 2, [FREQ])
        assert gain == pytest.approx(expected, rel=1e-9, abs=0)


@pytest.mark.parametrize(("rs", "rl"), [(25.0, 100.0), (1e-6, 1e6)], ids=PORT_IDS)
def test_passive_network_is_reciprocal_when_ports_are_swapped(rs, rl):
    """Gt(1 -> 2 with Rs, Rl) equals Gt(2 -> 1 with Rl, Rs) for any passive RLC network."""
    branches = [
        (1, 0, "C", 100e-12),
        (1, 2, "L", 1e-6, 2.0),
        (2, 0, "R", 200.0),
        (2, 0, "C", 47e-12),
    ]

    forward = solve_transducer_power_gain(2, branches, rs, rl, 1, 2, [FREQ])
    reverse = solve_transducer_power_gain(2, branches, rl, rs, 2, 1, [FREQ])

    # Independent forward value: shunt C, lossy series L, then shunt R || C at the load.
    y1 = 1 / _impedance("C", 100e-12)
    z = _impedance("L", 1e-6, 2.0)
    y2 = 1 / 200.0 + 1 / _impedance("C", 47e-12)
    a, b, c, d = 1 + z * y2, z, y1 + y2 + y1 * z * y2, 1 + y1 * z
    expected = 4 * rs * rl / abs(a * rl + b + c * rs * rl + d * rs) ** 2
    assert forward[0] == pytest.approx(expected, rel=1e-9, abs=0)
    assert reverse[0] == pytest.approx(expected, rel=1e-9, abs=0)


def _det3(m):
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


@pytest.mark.parametrize(("rs", "rl"), [(50.0, 75.0), (1e12, 1e12)], ids=PORT_IDS)
def test_bridged_network_matches_cramers_rule(rs, rl):
    """A branch from node 1 straight to node 3 closes a loop, so no ladder shortcut applies."""
    y12 = 1 / 100.0
    y23 = 1 / _impedance("C", 1e-9)
    y13 = 1 / _impedance("L", 1e-6)
    y2g = 1 / _impedance("L", 2e-6)
    matrix = [
        [1 / rs + y12 + y13, -y12, -y13],
        [-y12, y12 + y23 + y2g, -y23],
        [-y13, -y23, y23 + y13 + 1 / rl],
    ]
    rhs = [1 / rs, 0, 0]  # 1 V behind Rs as a Norton current source
    numerator = [row[:2] + [value] for row, value in zip(matrix, rhs)]
    v_out = _det3(numerator) / _det3(matrix)
    expected = 4 * rs / rl * abs(v_out) ** 2

    branches = [(1, 2, "R", 100.0), (2, 3, "C", 1e-9), (1, 3, "L", 1e-6), (2, 0, "L", 2e-6)]
    (gain,) = solve_transducer_power_gain(3, branches, rs, rl, 1, 3, [FREQ])

    assert gain == pytest.approx(expected, rel=1e-9, abs=0)


@pytest.mark.parametrize(("rs", "rl"), [(1.0, 4.0), (1e-8, 4e-8)], ids=PORT_IDS)
def test_series_resonant_internal_node_needs_row_pivoting(rs, rl):
    """1 H and 1 F in series through internal node 1 resonate at omega = 1 rad/s.

    Their admittances cancel exactly on node 1's diagonal, so elimination must pivot on
    another row. At resonance the pair is a short: Gt = 4*Rs*Rl / (Rs + Rl)^2 = 0.64.
    """
    frequency = math.exp(-math.log(2 * math.pi))  # log(omega) is exactly zero
    branches = [(1, 2, "C", 1.0), (1, 3, "L", 1.0)]

    (gain,) = solve_transducer_power_gain(3, branches, rs, rl, 2, 3, [frequency])

    assert gain == pytest.approx(4 * rs * rl / (rs + rl) ** 2, rel=1e-12, abs=0)


@pytest.mark.parametrize(
    ("kind", "value"),
    [("L", 1e-6), ("C", 1e-8)],
    ids=["inductor", "capacitor"],
)
def test_resistance_dominated_lossy_branch_matches_series_impedance(kind, value):
    """Q < 1: 100 Ohm of series loss against 6.3 Ohm (1 uH) or 15.9 Ohm (10 nF) at 1 MHz."""
    freq, rs, rl, loss = 1e6, 50.0, 50.0, 100.0
    omega = 2 * math.pi * freq
    reactance = 1j * omega * value if kind == "L" else 1 / (1j * omega * value)
    assert abs(reactance) < loss
    shunt = 1 / (loss + reactance)
    v_out = (1 / rs) / (1 / rs + 1 / rl + shunt)

    (gain,) = solve_transducer_power_gain(1, [(1, 0, kind, value, loss)], rs, rl, 1, 1, [freq])

    assert gain == pytest.approx(4 * rs / rl * abs(v_out) ** 2, rel=1e-12, abs=0)


def test_near_short_between_huge_ports_keeps_the_port_conductances():
    """1e-40 Ohm between 1e20 Ohm ports: Gt = 4 / (2 + 1e-60)^2, i.e. 1 to double precision.

    Eliminating the 1e40 S branch cancels about 60 digits before the 1e-20 S port
    conductance survives, so the fallback must size its precision to the full range.
    """
    (gain,) = solve_transducer_power_gain(2, [(1, 2, "R", 1e-40)], 1e20, 1e20, 1, 2, [FREQ])

    assert gain == pytest.approx(1.0, rel=1e-12, abs=0)


def test_transducer_gain_below_the_binary64_range_underflows_to_zero():
    """1e200 Ohm in series between 50 Ohm ports gives Gt = 1e-396, which is not representable."""
    assert solve_transducer_power_gain(2, [(1, 2, "R", 1e200)], 50.0, 50.0, 1, 2, [FREQ]) == [0.0]


@pytest.mark.parametrize(
    ("branch", "message"),
    [
        ((1, 0, ["C"], 1e-9), "Unknown branch kind"),
        ((1, 0, "C", "1e-9"), "^branch value must be positive and finite$"),
        ((1, 0, "L", 1e-6, "3"), "^branch series resistance must be finite and non-negative$"),
        ((1, 0, "L", 1e-6, 10**400), "^branch series resistance must be finite and non-negative$"),
    ],
    ids=["list-kind", "text-value", "text-loss", "huge-integer-loss"],
)
def test_non_real_branch_fields_are_value_errors(branch, message):
    """Malformed public input must not surface as TypeError or OverflowError."""
    with pytest.raises(ValueError, match=message):
        solve_transducer_power_gain(1, [branch], 50.0, 50.0, 1, 1, [FREQ])


@pytest.mark.parametrize(("rs", "rl", "name"), [(0.0, 50.0, "rs"), (50.0, 0.0, "rl")])
def test_zero_port_resistance_is_rejected_by_name(rs, rl, name):
    with pytest.raises(ValueError, match=f"^{name} must be positive and finite$"):
        solve_transducer_power_gain(1, [(1, 0, "C", 1e-9)], rs, rl, 1, 1, [FREQ])
