"""Simulation-gated acceptance tests: build the prescribed circuits, measure them.

The solver itself is validated against analytic references; LP/HP designs are
locked in as regression (their math is known-good), and the bandpass Top-C
acceptance matrix gates the synthesized response against the design spec.
"""

import math
import time

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.transfer import (
    chebyshev_3db_deviation,
    frequency_from_deviation,
    magnitude_db,
)
from filter_lib.shared.lp_hp_base_calculations import (
    calculate_highpass_bessel,
    calculate_highpass_butterworth,
    calculate_highpass_chebyshev,
    calculate_lowpass_bessel,
    calculate_lowpass_butterworth,
    calculate_lowpass_chebyshev,
)
from filter_lib.shared.netlist_builders import (
    CircuitElement,
    NamedCircuit,
    build_bandpass_top_c_netlist,
    build_hp_netlist,
    build_lp_netlist,
    build_named_circuit,
)
from filter_lib.shared.netlist_simulation import (
    Branch,
    find_3db_edges,
    logspace,
    passband_ripple_db,
    solve_s21,
    solve_transducer_power_gain,
)


def test_netlist_facades_preserve_models_builders_solver_and_measurements():
    from filter_lib.shared import netlist_builders, netlist_simulation
    from filter_lib.shared.circuit_model import (
        Branch as ExtractedBranch,
    )
    from filter_lib.shared.circuit_model import (
        CircuitElement as ExtractedCircuitElement,
    )
    from filter_lib.shared.circuit_model import (
        NamedCircuit as ExtractedNamedCircuit,
    )
    from filter_lib.shared.nodal_solver import solve_s21 as extracted_solve_s21
    from filter_lib.shared.response_measurement import (
        find_3db_edges as extracted_find_3db_edges,
    )

    assert CircuitElement is ExtractedCircuitElement
    assert NamedCircuit is ExtractedNamedCircuit
    assert Branch == ExtractedBranch
    assert netlist_builders.CircuitElement is ExtractedCircuitElement
    assert netlist_simulation.solve_s21 is extracted_solve_s21
    assert netlist_simulation.find_3db_edges is extracted_find_3db_edges


def _lp_result(filter_type: str, fc: float, z0: float, n: int, topology: str, ripple=0.5) -> dict:
    if filter_type == "butterworth":
        caps, inds, order = calculate_lowpass_butterworth(fc, z0, n, topology)
    elif filter_type == "chebyshev":
        caps, inds, order = calculate_lowpass_chebyshev(fc, z0, ripple, n, topology)
    else:
        caps, inds, order = calculate_lowpass_bessel(fc, z0, n, topology)
    return {"capacitors": caps, "inductors": inds, "order": order, "topology": topology}


def _hp_result(filter_type: str, fc: float, z0: float, n: int, topology: str, ripple=0.5) -> dict:
    if filter_type == "butterworth":
        inds, caps, order = calculate_highpass_butterworth(fc, z0, n, topology)
    elif filter_type == "chebyshev":
        inds, caps, order = calculate_highpass_chebyshev(fc, z0, ripple, n, topology)
    else:
        inds, caps, order = calculate_highpass_bessel(fc, z0, n, topology)
    return {"capacitors": caps, "inductors": inds, "order": order, "topology": topology}


class TestSolverSelfTests:
    """Solver vs analytic references."""

    def test_rc_shunt_matches_analytic(self):
        """Shunt C between 50 Ω source and load: |S21| = |2/(2 + jωC·50)|."""
        rs = rl = 50.0
        c = 100e-12
        freqs = logspace(5, 9, 41)
        mags = solve_s21(1, [(1, 0, "C", c)], rs, rl, 1, 1, freqs)
        for f, measured in zip(freqs, mags):
            omega = 2 * math.pi * f
            analytic = abs(2 / (2 + 1j * omega * c * rs))
            assert abs(measured - analytic) <= 1e-9

    def test_series_resistor_matches_analytic(self):
        """Series R: |S21| = 2·rl/(rs + R + rl), flat over frequency."""
        rs, rl, r = 50.0, 50.0, 100.0
        mags = solve_s21(2, [(1, 2, "R", r)], rs, rl, 1, 2, [1e3, 1e6, 1e9])
        analytic = 2 * rl / (rs + r + rl)
        for measured in mags:
            assert abs(measured - analytic) <= 1e-9

    def test_floating_node_raises(self):
        with pytest.raises(ValueError, match="[Ss]ingular"):
            # Node 3 has no connection at all -> zero row in the nodal matrix
            solve_s21(3, [(1, 2, "R", 50.0)], 50.0, 50.0, 1, 2, [1e6])

    def test_non_positive_terminations_rejected(self):
        with pytest.raises(ValueError, match="must be positive"):
            solve_s21(1, [(1, 0, "C", 1e-12)], 0.0, 50.0, 1, 1, [1e6])
        with pytest.raises(ValueError, match="must be positive"):
            solve_s21(1, [(1, 0, "C", 1e-12)], 50.0, float("inf"), 1, 1, [1e6])

    def test_unknown_branch_kind_rejected(self):
        with pytest.raises(ValueError, match="Unknown branch kind"):
            solve_s21(1, [(1, 0, "X", 1.0)], 50.0, 50.0, 1, 1, [1e6])

    def test_branch_node_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="out of range"):
            solve_s21(1, [(1, 2, "C", 1e-12)], 50.0, 50.0, 1, 1, [1e6])

    @pytest.mark.parametrize("node", [True, 1.0, "1"])
    @pytest.mark.parametrize("solver", [solve_s21, solve_transducer_power_gain])
    def test_port_nodes_require_exact_integers(self, solver, node):
        with pytest.raises(ValueError, match="must be integers"):
            solver(1, [], 50.0, 50.0, node, 1, [1e6])
        with pytest.raises(ValueError, match="must be integers"):
            solver(1, [], 50.0, 50.0, 1, node, [1e6])

    def test_unequal_ports_report_analytic_transducer_power_gain(self):
        """A direct Rs/Rl divider has Gt = 4*Rs*Rl/(Rs+Rl)^2."""
        rs, rl = 25.0, 100.0
        (gain,) = solve_transducer_power_gain(1, [], rs, rl, 1, 1, [1e6])
        assert gain == pytest.approx(4.0 * rs * rl / (rs + rl) ** 2, rel=1e-12)

    @pytest.mark.parametrize(
        ("rs", "rl"),
        [
            (1e308, 1.0),
            (1e300, 1.0),
            (1.0, 1e-300),
            (1e308, 1e308),
            (1e-308, 1e-308),
            (1e-309, 1e-309),
            (1e-320, 1e-320),
            (5e-324, 5e-324),
        ],
    )
    def test_direct_divider_is_scale_safe_for_extreme_finite_ports(self, rs, rl):
        (gain,) = solve_transducer_power_gain(1, [], rs, rl, 1, 1, [1e6])
        ratio = min(rs, rl) / max(rs, rl)
        expected = 4.0 * ratio / (1.0 + ratio) ** 2

        assert math.isfinite(gain)
        assert gain == pytest.approx(expected, rel=1e-12)

    @pytest.mark.parametrize("series_resistance", [1e-8, 1e-10, 1e-12, 1e-14, 1e-16])
    def test_near_short_series_resistor_retains_analytic_passive_gain(self, series_resistance):
        (gain,) = solve_transducer_power_gain(
            2,
            [(1, 2, "R", series_resistance)],
            1.0,
            1.0,
            1,
            2,
            [1e6],
        )
        expected = 4.0 / (2.0 + series_resistance) ** 2

        assert gain <= 1.0
        assert gain == pytest.approx(expected, rel=1e-12, abs=1e-15)

    def test_subnormal_series_resistor_with_tiny_ports_is_not_false_singular(self):
        rs = rl = 1e-200
        (gain,) = solve_transducer_power_gain(2, [(1, 2, "R", 5e-324)], rs, rl, 1, 2, [1e6])
        expected = 4.0 / (2.0 + 5e-324 / rs) ** 2

        assert gain <= 1.0
        assert gain == pytest.approx(expected, rel=1e-12)

    def test_equal_port_s21_remains_sqrt_transducer_gain(self):
        branches = [(1, 2, "R", 25.0)]
        gains = solve_transducer_power_gain(2, branches, 50.0, 50.0, 1, 2, [1e6])
        mags = solve_s21(2, branches, 50.0, 50.0, 1, 2, [1e6])
        assert mags[0] ** 2 == pytest.approx(gains[0], rel=1e-12)

    @pytest.mark.parametrize("kind, value, series_resistance", [("L", 2e-6, 3.0), ("C", 1e-9, 4.0)])
    def test_lossy_reactive_branch_matches_series_impedance(self, kind, value, series_resistance):
        rs, rl, freq = 50.0, 75.0, 2e6
        omega = 2.0 * math.pi * freq
        reactance = 1j * omega * value if kind == "L" else 1.0 / (1j * omega * value)
        expected = 4.0 * rs * rl / abs(rs + rl + series_resistance + reactance) ** 2

        (gain,) = solve_transducer_power_gain(
            2,
            [(1, 2, kind, value, series_resistance)],
            rs,
            rl,
            1,
            2,
            [freq],
        )

        assert gain == pytest.approx(expected, rel=1e-12)

    @pytest.mark.parametrize(
        "branches, freqs, message",
        [
            ([(1, 1, "C", 1e-9, -1.0)], [1e6], "series resistance"),
            ([(1, 1, "L", float("inf"))], [1e6], "value"),
            ([], [0.0], "frequencies"),
        ],
    )
    def test_lossy_solver_rejects_invalid_values(self, branches, freqs, message):
        with pytest.raises(ValueError, match=message):
            solve_transducer_power_gain(1, branches, 50.0, 50.0, 1, 1, freqs)


class TestNamedCircuitBuilders:
    @pytest.mark.parametrize(
        "category, result, names",
        [
            (
                "lowpass",
                {
                    "topology": "pi",
                    "order": 3,
                    "capacitors": [1e-9, 2e-9],
                    "inductors": [3e-6],
                },
                ["C1", "L1", "C2"],
            ),
            (
                "highpass",
                {
                    "topology": "t",
                    "order": 3,
                    "capacitors": [1e-9, 2e-9],
                    "inductors": [3e-6],
                },
                ["C1", "L1", "C2"],
            ),
            (
                "bandpass",
                {
                    "n_resonators": 2,
                    "L_resonant": 1e-6,
                    "c_tank": [10e-12, 11e-12],
                    "c_coupling": [2e-12],
                    "c_end_in": 3e-12,
                    "c_end_out": 4e-12,
                },
                ["CT1", "LT1", "CT2", "LT2", "CK1", "CIN", "COUT"],
            ),
        ],
    )
    def test_named_topology_is_deterministic(self, category, result, names):
        circuit = build_named_circuit(result, category)
        assert [element.name for element in circuit.elements] == names
        assert len(set(names)) == len(names)

    @pytest.mark.parametrize(
        "category, builder, result",
        [
            (
                "lowpass",
                build_lp_netlist,
                {
                    "topology": "pi",
                    "order": 3,
                    "capacitors": [1e-9, 2e-9],
                    "inductors": [3e-6],
                },
            ),
            (
                "highpass",
                build_hp_netlist,
                {
                    "topology": "t",
                    "order": 3,
                    "capacitors": [1e-9, 2e-9],
                    "inductors": [3e-6],
                },
            ),
            (
                "bandpass",
                build_bandpass_top_c_netlist,
                {
                    "n_resonators": 2,
                    "L_resonant": 1e-6,
                    "c_tank": [10e-12, 11e-12],
                    "c_coupling": [2e-12],
                    "c_end_in": 3e-12,
                    "c_end_out": 4e-12,
                },
            ),
        ],
    )
    def test_legacy_branch_builders_derive_from_named_topology(self, category, builder, result):
        circuit = build_named_circuit(result, category)
        assert builder(result) == circuit.as_legacy_netlist()


class TestSolverInputValidation:
    def test_out_of_range_port_node_rejected(self):
        with pytest.raises(ValueError, match="in_node and out_node"):
            solve_s21(n_nodes=2, branches=[], rs=50, rl=50, in_node=1, out_node=3, freqs=[1e6])

    def test_logspace_requires_two_points(self):
        with pytest.raises(ValueError, match="points must be >= 2"):
            logspace(0, 1, 1)


class TestEdgeFinding:
    def test_find_3db_edges_interpolates(self):
        """Synthetic triangle response: edges at the sqrt(1/2) crossings."""
        freqs = [1.0, 2.0, 3.0, 4.0, 5.0]
        mags = [0.1, 0.9, 1.0, 0.9, 0.1]
        f_lo, f_hi = find_3db_edges(freqs, mags)
        threshold = 1 / math.sqrt(2)
        expected_lo = 1.0 + (threshold - 0.1) / (0.9 - 0.1)
        expected_hi = 5.0 + (threshold - 0.1) / (0.9 - 0.1) * (4.0 - 5.0)
        assert f_lo == pytest.approx(expected_lo)
        assert f_hi == pytest.approx(expected_hi)

    def test_find_3db_edges_grid_boundary(self):
        """Response above threshold at the grid edge returns the boundary freq."""
        freqs = [1.0, 2.0, 3.0]
        mags = [1.0, 0.9, 0.1]
        f_lo, f_hi = find_3db_edges(freqs, mags)
        assert f_lo == 1.0
        assert 2.0 < f_hi < 3.0

    def test_find_3db_edges_uses_reference_passband_peak(self):
        """A stronger disconnected spur cannot re-baseline the intended passband."""
        freqs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        mags = [0.1, 0.7, 0.55, 0.1, 0.1, 1.0, 0.8, 0.1, 0.1]

        f_lo, f_hi = find_3db_edges(freqs, mags, reference_frequency=2.0)

        assert f_lo is not None and 1.0 < f_lo < 2.0
        assert f_hi is not None and 3.0 < f_hi < 4.0

    def test_passband_ripple_requires_points(self):
        with pytest.raises(ValueError, match="below f_limit"):
            passband_ripple_db([10.0], [1.0], 5.0)

    @pytest.mark.parametrize("reference", [True, "2", float("nan")])
    def test_find_edges_rejects_non_real_reference(self, reference):
        with pytest.raises(ValueError, match="positive and finite"):
            find_3db_edges([1.0, 2.0], [0.5, 1.0], reference_frequency=reference)

    @pytest.mark.parametrize("limit", [True, "2", float("inf")])
    def test_passband_ripple_rejects_non_real_limit(self, limit):
        with pytest.raises(ValueError, match="positive and finite"):
            passband_ripple_db([1.0, 2.0], [1.0, 1.0], limit)

    @pytest.mark.parametrize(
        ("freqs", "mags", "message"),
        [
            ([1.0, float("nan")], [1.0, 0.5], "frequencies"),
            ([1.0, 2.0], [1.0, float("inf")], "magnitudes"),
            ([1.0, True], [1.0, 0.5], "frequencies"),
            ([1.0, 2.0], [1.0, True], "magnitudes"),
        ],
    )
    def test_measurement_helpers_reject_invalid_arrays(self, freqs, mags, message):
        with pytest.raises(ValueError, match=message):
            find_3db_edges(freqs, mags)
        with pytest.raises(ValueError, match=message):
            passband_ripple_db(freqs, mags, 2.0)

    def test_empty_edges_still_validate_reference(self):
        with pytest.raises(ValueError, match="reference_frequency"):
            find_3db_edges([], [], reference_frequency=True)

    @pytest.mark.parametrize(
        "arguments",
        [(True, 1.0, 3), (0.0, "1", 3), (0.0, 1.0, True), (0.0, 400.0, 3)],
    )
    def test_logspace_rejects_invalid_or_nonfinite_grid(self, arguments):
        with pytest.raises(ValueError, match="finite|points"):
            logspace(*arguments)


class TestLowpassHighpassAcceptance:
    """Simulated -3 dB cutoffs for known-good LP/HP synthesis (regression lock)."""

    @pytest.mark.parametrize("n", [3, 5])
    @pytest.mark.parametrize("topology", ["pi", "t"])
    def test_lp_butterworth_cutoff(self, n, topology):
        fc = 10e6
        result = _lp_result("butterworth", fc, 50, n, topology)
        n_nodes, branches, in_node, out_node = build_lp_netlist(result)
        freqs = logspace(5.5, 8.5, 4001)
        mags = solve_s21(n_nodes, branches, 50, 50, in_node, out_node, freqs)
        _, f_hi = find_3db_edges(freqs, mags)
        assert f_hi == pytest.approx(fc, rel=0.005)

    @pytest.mark.parametrize("n", [3, 5])
    @pytest.mark.parametrize("topology", ["pi", "t"])
    def test_hp_butterworth_cutoff(self, n, topology):
        fc = 10e6
        result = _hp_result("butterworth", fc, 50, n, topology)
        n_nodes, branches, in_node, out_node = build_hp_netlist(result)
        freqs = logspace(5.5, 8.5, 4001)
        mags = solve_s21(n_nodes, branches, 50, 50, in_node, out_node, freqs)
        f_lo, _ = find_3db_edges(freqs, mags)
        assert f_lo == pytest.approx(fc, rel=0.005)

    @pytest.mark.parametrize("topology", ["pi", "t"])
    def test_lp_chebyshev_ripple_and_edge(self, topology):
        """0.5 dB Chebyshev n=5: ripple stays in [-0.52, 0.02] dB; fc is the ripple edge."""
        fc = 10e6
        result = _lp_result("chebyshev", fc, 50, 5, topology, ripple=0.5)
        n_nodes, branches, in_node, out_node = build_lp_netlist(result)
        freqs = logspace(6, 8, 8001)
        mags = solve_s21(n_nodes, branches, 50, 50, in_node, out_node, freqs)
        max_db, min_db = passband_ripple_db(freqs, mags, fc)
        assert max_db <= 0.02
        assert min_db >= -0.52
        # Chebyshev passband edge: attenuation equals the ripple at fc
        (mag_fc,) = solve_s21(n_nodes, branches, 50, 50, in_node, out_node, [fc])
        assert 20 * math.log10(mag_fc) == pytest.approx(-0.5, abs=0.05)

    def test_lp_bessel_cutoff(self):
        fc = 10e6
        result = _lp_result("bessel", fc, 50, 3, "pi")
        n_nodes, branches, in_node, out_node = build_lp_netlist(result)
        freqs = logspace(5.5, 8.5, 4001)
        mags = solve_s21(n_nodes, branches, 50, 50, in_node, out_node, freqs)
        _, f_hi = find_3db_edges(freqs, mags)
        assert f_hi == pytest.approx(fc, rel=0.01)

    def test_hp_bessel_cutoff(self):
        fc = 10e6
        result = _hp_result("bessel", fc, 50, 3, "t")
        n_nodes, branches, in_node, out_node = build_hp_netlist(result)
        freqs = logspace(5.5, 8.5, 4001)
        mags = solve_s21(n_nodes, branches, 50, 50, in_node, out_node, freqs)
        f_lo, _ = find_3db_edges(freqs, mags)
        assert f_lo == pytest.approx(fc, rel=0.01)

    @pytest.mark.parametrize("fc", [1e3, 1e9])
    def test_lp_extreme_frequency_corners(self, fc):
        """Numerical stability at extreme component ratios (1 kHz and 1 GHz)."""
        result = _lp_result("butterworth", fc, 50, 5, "pi")
        n_nodes, branches, in_node, out_node = build_lp_netlist(result)
        center = math.log10(fc)
        freqs = logspace(center - 1.5, center + 1.5, 4001)
        mags = solve_s21(n_nodes, branches, 50, 50, in_node, out_node, freqs)
        _, f_hi = find_3db_edges(freqs, mags)
        assert f_hi == pytest.approx(fc, rel=0.005)


def _measure_top_c(result: dict, f0: float, fbw: float) -> tuple[float, float]:
    """Simulate a Top-C design and return (measured_bw, measured_f0)."""
    n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
    # A span of a few designed bandwidths captures both edges; threshold
    # interpolation recovers edge accuracy well below the grid step.
    lo, hi = f0 * (1 - 3 * fbw), f0 * (1 + 3 * fbw)
    step = (hi - lo) / 3000
    freqs = [lo + i * step for i in range(3001)]
    mags = solve_s21(n_nodes, branches, 50, 50, in_node, out_node, freqs)
    f_lo, f_hi = find_3db_edges(freqs, mags)
    assert f_lo is not None and lo < f_lo, "lower band edge must lie inside the sweep"
    assert f_hi is not None and f_hi < hi, "upper band edge must lie inside the sweep"
    return f_hi - f_lo, math.sqrt(f_lo * f_hi)


_MATRIX_FBWS = (0.01, 0.02, 0.05, 0.10)
_MATRIX_RIPPLES = (0.1, 0.5, 1.0, 3.0)
_UNSUPPORTED_MATRIX_CELLS = {
    ("bessel", 8, 0.10, None): "too wide to realize",
    ("bessel", 9, 0.10, None): "too wide to realize",
    ("chebyshev", 5, 0.02, 3.0): "Top-C calibration",
    ("chebyshev", 7, 0.01, 3.0): "Top-C calibration",
    ("chebyshev", 9, 0.02, 3.0): "Top-C calibration",
}
_STOPBAND_SAMPLE_ERROR_LIMIT_DB = 8.0

_EXHAUSTIVE_BANDPASS_MATRIX = tuple(
    (filter_type, order, fbw, None)
    for filter_type in ("butterworth", "bessel")
    for order in range(2, 10)
    for fbw in _MATRIX_FBWS
) + tuple(
    ("chebyshev", order, fbw, ripple_db)
    for order in (3, 5, 7, 9)
    for fbw in _MATRIX_FBWS
    for ripple_db in _MATRIX_RIPPLES
)


def _matrix_case_id(case: tuple[str, int, float, float | None]) -> str:
    filter_type, order, fbw, ripple_db = case
    ripple_suffix = "" if ripple_db is None else f"-r{ripple_db:g}"
    return f"{filter_type}-n{order}-fbw{fbw:g}{ripple_suffix}"


def _independent_top_c_validation(
    result: dict, f0: float, bw: float, *, points: int = 2001
) -> dict:
    """Dense verifier deliberately independent of production validation helpers."""
    deltas = [-4.0 + 8.0 * index / (points - 1) for index in range(points)]
    freqs = [frequency_from_deviation(delta, f0, bw) for delta in deltas]
    n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
    mags = solve_s21(n_nodes, branches, result["z0"], result["z0"], in_node, out_node, freqs)

    local_maxima = [
        index
        for index, value in enumerate(mags)
        if (index == 0 or value >= mags[index - 1])
        and (index == len(mags) - 1 or value >= mags[index + 1])
    ]
    center_index = min(
        local_maxima,
        key=lambda index: (abs(freqs[index] - f0), -mags[index]),
    )
    peak = mags[center_index]
    threshold = peak / math.sqrt(2.0)

    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(mags):
        if mags[index] < threshold:
            index += 1
            continue
        start = index
        while index + 1 < len(mags) and mags[index + 1] >= threshold:
            index += 1
        runs.append((start, index))
        index += 1
    selected_start, selected_end = next(run for run in runs if run[0] <= center_index <= run[1])

    def interpolate(outside: int, inside: int) -> float:
        fraction = (threshold - mags[outside]) / (mags[inside] - mags[outside])
        return freqs[outside] + fraction * (freqs[inside] - freqs[outside])

    measured_low = interpolate(selected_start - 1, selected_start)
    measured_high = interpolate(selected_end + 1, selected_end)
    first_start, last_end = runs[0][0], runs[-1][1]
    outer_low = freqs[0] if first_start == 0 else interpolate(first_start - 1, first_start)
    outer_high = freqs[-1] if last_end == len(freqs) - 1 else interpolate(last_end + 1, last_end)

    normalized_db = [20.0 * math.log10(mag / peak) for mag in mags]
    ripple_limit = 1.0
    ripple_db = result.get("ripple_db") or 0.5
    if result["filter_type"] == "chebyshev":
        ripple_limit = 1.0 / chebyshev_3db_deviation(result["n_resonators"], ripple_db)
    passband_errors = [
        abs(
            actual_db
            - magnitude_db(
                freq,
                f0,
                bw,
                result["n_resonators"],
                result["filter_type"],
                ripple_db,
            )
        )
        for freq, delta, actual_db in zip(freqs, deltas, normalized_db)
        if abs(delta) <= 1.0 + 1e-12
    ]
    ripple_samples = [
        actual_db
        for delta, actual_db in zip(deltas, normalized_db)
        if abs(delta) <= ripple_limit + 1e-12
    ]
    stopband_samples = {}
    for delta in (-2.0, -1.5, 1.5, 2.0):
        sample_index = round((delta + 4.0) * (points - 1) / 8.0)
        actual_db = normalized_db[sample_index]
        ideal_db = magnitude_db(
            freqs[sample_index],
            f0,
            bw,
            result["n_resonators"],
            result["filter_type"],
            ripple_db,
        )
        stopband_samples[f"{delta:+g}"] = (actual_db, ideal_db)

    return {
        "f_low": measured_low,
        "f_high": measured_high,
        "outer_f_low": outer_low,
        "outer_f_high": outer_high,
        "connected_region_count": len(runs),
        "max_passband_shape_error_db": max(passband_errors),
        "measured_ripple_db": max(ripple_samples) - min(ripple_samples),
        "stopband_samples": stopband_samples,
    }


class TestBandpassTopCAcceptance:
    """The Top-C circuit as prescribed must realize the designed response.

    The exhaustive matrix studies edge calibration through 10% FBW, but only
    individual cells whose independently measured edge, shape, and region
    gates pass may carry a ``validated`` response claim.
    """

    def test_matrix_definition_has_all_128_requested_cells(self):
        assert len(_EXHAUSTIVE_BANDPASS_MATRIX) == 128

    @pytest.mark.parametrize(
        "filter_type, order, fbw, ripple_db",
        _EXHAUSTIVE_BANDPASS_MATRIX,
        ids=[_matrix_case_id(case) for case in _EXHAUSTIVE_BANDPASS_MATRIX],
    )
    def test_exhaustive_response_matrix(self, filter_type, order, fbw, ripple_db):
        f0 = 10e6
        kwargs = {} if ripple_db is None else {"ripple_db": ripple_db}
        cell = (filter_type, order, fbw, ripple_db)
        if cell in _UNSUPPORTED_MATRIX_CELLS:
            with pytest.raises(ValueError, match=_UNSUPPORTED_MATRIX_CELLS[cell]):
                calculate_bandpass_filter(f0, f0 * fbw, 50, order, filter_type, "top", **kwargs)
            return

        result = calculate_bandpass_filter(f0, f0 * fbw, 50, order, filter_type, "top", **kwargs)
        independent = _independent_top_c_validation(result, f0, f0 * fbw)
        validation = result["synthesis_validation"]

        lower_error = independent["f_low"] / result["f_low"] - 1.0
        upper_error = independent["f_high"] / result["f_high"] - 1.0
        outer_lower_error = independent["outer_f_low"] / result["f_low"] - 1.0
        outer_upper_error = independent["outer_f_high"] / result["f_high"] - 1.0
        assert abs(lower_error) <= 1e-3
        assert abs(upper_error) <= 1e-3
        assert validation["measured_f_low_hz"] == pytest.approx(independent["f_low"], rel=2e-5)
        assert validation["measured_f_high_hz"] == pytest.approx(independent["f_high"], rel=2e-5)
        assert validation["measured_outer_f_low_hz"] == pytest.approx(
            independent["outer_f_low"], rel=2e-5
        )
        assert validation["measured_outer_f_high_hz"] == pytest.approx(
            independent["outer_f_high"], rel=2e-5
        )
        assert validation["connected_region_count"] == independent["connected_region_count"]
        assert validation["internal_hole_count"] == max(
            0, independent["connected_region_count"] - 1
        )

        max_stopband_error = max(
            abs(actual_db - ideal_db)
            for actual_db, ideal_db in independent["stopband_samples"].values()
        )
        shape_ok = (
            independent["max_passband_shape_error_db"] <= 0.30
            and max_stopband_error <= _STOPBAND_SAMPLE_ERROR_LIMIT_DB
        )
        if filter_type == "chebyshev":
            shape_ok = shape_ok and independent["measured_ripple_db"] <= ripple_db + 0.20
        independently_validated = (
            shape_ok
            and independent["connected_region_count"] == 1
            and max(abs(lower_error), abs(upper_error)) <= 1e-3
            and max(abs(outer_lower_error), abs(outer_upper_error)) <= 1e-3
        )
        assert validation["shape_validated"] is shape_ok
        assert validation["validated"] is independently_validated
        assert validation["outer_skirt_edge_validated"] is (
            independent["connected_region_count"] == 1
            and max(abs(outer_lower_error), abs(outer_upper_error)) <= 1e-3
        )
        assert result["response_validation_status"] == (
            "validated" if independently_validated else "outside_validated_envelope"
        )

        for key, (actual_db, ideal_db) in independent["stopband_samples"].items():
            assert math.isfinite(actual_db)
            assert math.isfinite(ideal_db)
            recorded = validation["stopband_samples"][key]
            assert recorded["actual_db"] == pytest.approx(actual_db, abs=1e-9)
            assert recorded["ideal_db"] == pytest.approx(ideal_db, abs=1e-9)
        assert validation["max_stopband_sample_error_db"] == pytest.approx(
            max_stopband_error, abs=1e-9
        )
        assert validation["stopband_samples_validated"] is (
            max_stopband_error <= _STOPBAND_SAMPLE_ERROR_LIMIT_DB
        )
        assert validation["validation_limits"] == {
            "edge_error_rel": 1e-3,
            "passband_shape_error_db": 0.30,
            "chebyshev_ripple_allowance_db": 0.20,
            "representative_stopband_sample_error_db": _STOPBAND_SAMPLE_ERROR_LIMIT_DB,
        }
        if independently_validated:
            assert max_stopband_error <= _STOPBAND_SAMPLE_ERROR_LIMIT_DB

        assert validation["iterations"] <= 12
        assert validation["calibration_points"] == 401
        assert validation["validation_points"] == 2001

        if filter_type == "chebyshev" and ripple_db == 3.0:
            assert independent["connected_region_count"] > 1
            assert validation["outer_skirt_edge_validated"] is False
            assert result["response_validation_status"] == "outside_validated_envelope"
            assert any(
                "overall outer envelope is not validated" in warning
                for warning in result["warnings"]
            )

    @pytest.mark.parametrize("order", [3, 9])
    def test_calibration_runtime_is_bounded(self, order):
        started = time.perf_counter()
        calculate_bandpass_filter(10e6, 0.5e6, 50, order, "butterworth", "top")
        assert time.perf_counter() - started < 2.0

    def test_chebyshev_arbitrary_ripple(self):
        """Formula-based g-values: a ripple between former table entries simulates true."""
        f0, fbw = 10e6, 0.05
        result = calculate_bandpass_filter(f0, f0 * fbw, 50, 3, "chebyshev", "top", ripple_db=0.25)
        bw_meas, f0_meas = _measure_top_c(result, f0, fbw)
        assert bw_meas == pytest.approx(f0 * fbw, rel=0.03)
        assert f0_meas == pytest.approx(f0, rel=0.005)

    def test_bessel_asymmetric_prototype_has_distinct_end_caps(self):
        """Bessel g-values are asymmetric, so Qe_in != Qe_out and Ce_in != Ce_out."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 4, "bessel", "top")
        assert result["qe_in"] != pytest.approx(result["qe_out"])
        assert result["c_end_in"] != pytest.approx(result["c_end_out"])
        bw_meas, f0_meas = _measure_top_c(result, 10e6, 0.05)
        assert bw_meas == pytest.approx(0.5e6, rel=0.03)
        assert f0_meas == pytest.approx(10e6, rel=0.005)

    def test_infeasible_end_coupling_raises(self):
        """High-order Bessel at wide FBW needs Rp <= Z0: no real series-C exists."""
        with pytest.raises(ValueError, match="too wide to realize"):
            calculate_bandpass_filter(10e6, 1.5e6, 50, 7, "bessel", "top")

    def test_wide_fbw_emits_edge_calibration_range_warning(self):
        result = calculate_bandpass_filter(10e6, 1.2e6, 50, 3, "butterworth", "top")
        assert any("studied edge-calibration range" in w for w in result["warnings"])

    def test_studied_fbw_has_no_edge_calibration_range_warning(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 3, "butterworth", "top")
        assert not any("studied edge-calibration range" in w for w in result["warnings"])


class TestBuilders:
    @pytest.mark.parametrize("result", [None, 1, [], "result"])
    def test_builder_requires_result_mapping(self, result):
        with pytest.raises(ValueError, match="result must be a mapping"):
            build_named_circuit(result, "lowpass")

    @pytest.mark.parametrize("category", [None, 1, [], {}])
    def test_builder_requires_string_category(self, category):
        with pytest.raises(ValueError, match="category must be"):
            build_named_circuit({}, category)

    @pytest.mark.parametrize(
        "result",
        [
            {},
            {"topology": [], "capacitors": [], "inductors": [], "order": 1},
            {"topology": "pi", "capacitors": 1, "inductors": [], "order": 1},
        ],
    )
    def test_ladder_builder_rejects_malformed_result_shape(self, result):
        with pytest.raises(ValueError):
            build_lp_netlist(result)

    @pytest.mark.parametrize(
        "result",
        [
            {},
            {"n_resonators": 1, "c_tank": 1, "c_coupling": [], "L_resonant": 1e-6},
        ],
    )
    def test_bandpass_builder_rejects_malformed_result_shape(self, result):
        with pytest.raises(ValueError):
            build_bandpass_top_c_netlist(result)

    def test_lp_builder_unknown_topology_rejected(self):
        result = {"capacitors": [1e-12], "inductors": [], "order": 1, "topology": "x"}
        with pytest.raises(ValueError, match="Unknown topology"):
            build_lp_netlist(result)

    def test_ladder_rejects_excess_components(self):
        result = {
            "capacitors": [1e-12, 1e-12, 1e-12],
            "inductors": [1e-6],
            "order": 3,
            "topology": "pi",
        }
        with pytest.raises(ValueError, match="longer than the ladder"):
            build_lp_netlist(result)

    def test_bandpass_builder_without_end_caps_uses_end_tanks(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 3, "butterworth", "top")
        result = {**result, "c_end_in": None, "c_end_out": None}
        n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
        assert (n_nodes, in_node, out_node) == (3, 1, 3)
        # 3 tanks (C+L each) + 2 coupling caps
        assert len(branches) == 8

    def test_bandpass_builder_with_end_caps_adds_source_load_nodes(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 3, "butterworth", "top")
        result = {**result, "c_end_in": 100e-12, "c_end_out": 100e-12}
        n_nodes, branches, in_node, out_node = build_bandpass_top_c_netlist(result)
        assert (n_nodes, in_node, out_node) == (5, 4, 5)
        assert (4, 1, "C", 100e-12) in branches
        assert (3, 5, "C", 100e-12) in branches

    def test_bandpass_builder_rejects_one_sided_end_caps(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 3, "butterworth", "top")
        result = {**result, "c_end_out": None}
        with pytest.raises(ValueError, match="both"):
            build_bandpass_top_c_netlist(result)
