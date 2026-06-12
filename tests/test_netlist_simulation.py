"""Simulation-gated acceptance tests: build the prescribed circuits, measure them.

The solver itself is validated against analytic references; LP/HP designs are
locked in as regression (their math is known-good), and the bandpass Top-C
acceptance matrix gates the synthesized response against the design spec.
"""

import math

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.shared.lp_hp_base_calculations import (
    calculate_highpass_bessel,
    calculate_highpass_butterworth,
    calculate_highpass_chebyshev,
    calculate_lowpass_bessel,
    calculate_lowpass_butterworth,
    calculate_lowpass_chebyshev,
)
from filter_lib.shared.netlist_builders import (
    build_bandpass_top_c_netlist,
    build_hp_netlist,
    build_lp_netlist,
)
from filter_lib.shared.netlist_simulation import (
    find_3db_edges,
    logspace,
    passband_ripple_db,
    solve_s21,
)


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

    def test_passband_ripple_requires_points(self):
        with pytest.raises(ValueError, match="below f_limit"):
            passband_ripple_db([10.0], [1.0], 5.0)


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


class TestBandpassTopCAcceptance:
    """The Top-C circuit as prescribed must realize the designed response.

    Simulation-proven support is capped at 10% fractional bandwidth: every
    cell of this matrix must land within 3% of the designed -3 dB bandwidth
    and 0.5% of the designed center frequency. Above 10% FBW the synthesis
    emits a warning instead (accuracy degrades gradually).
    """

    @pytest.mark.parametrize("fbw", [0.02, 0.05, 0.10])
    @pytest.mark.parametrize("n", [2, 3, 5, 7])
    def test_butterworth_matrix(self, n, fbw):
        f0 = 10e6
        result = calculate_bandpass_filter(f0, f0 * fbw, 50, n, "butterworth", "top")
        bw_meas, f0_meas = _measure_top_c(result, f0, fbw)
        assert bw_meas == pytest.approx(f0 * fbw, rel=0.03)
        assert f0_meas == pytest.approx(f0, rel=0.005)

    @pytest.mark.parametrize("fbw", [0.02, 0.05, 0.10])
    @pytest.mark.parametrize("n", [3, 5, 7])
    def test_chebyshev_matrix(self, n, fbw):
        """Chebyshev bw is the true -3 dB bandwidth (wider than the ripple band)."""
        f0 = 10e6
        result = calculate_bandpass_filter(f0, f0 * fbw, 50, n, "chebyshev", "top", ripple_db=0.5)
        bw_meas, f0_meas = _measure_top_c(result, f0, fbw)
        assert bw_meas == pytest.approx(f0 * fbw, rel=0.03)
        assert f0_meas == pytest.approx(f0, rel=0.005)

    @pytest.mark.parametrize("fbw", [0.02, 0.05, 0.10])
    @pytest.mark.parametrize("n", [2, 3, 5, 7])
    def test_bessel_matrix(self, n, fbw):
        f0 = 10e6
        result = calculate_bandpass_filter(f0, f0 * fbw, 50, n, "bessel", "top")
        bw_meas, f0_meas = _measure_top_c(result, f0, fbw)
        assert bw_meas == pytest.approx(f0 * fbw, rel=0.03)
        assert f0_meas == pytest.approx(f0, rel=0.005)

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

    def test_wide_fbw_emits_simulation_range_warning(self):
        result = calculate_bandpass_filter(10e6, 1.2e6, 50, 3, "butterworth", "top")
        assert any("simulation-validated" in w for w in result["warnings"])

    def test_supported_fbw_has_no_simulation_range_warning(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 3, "butterworth", "top")
        assert not any("simulation-validated" in w for w in result["warnings"])


class TestBuilders:
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
