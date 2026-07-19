"""Unit tests for bandpass filter calculations.

Tests verify coupled resonator calculations for bandpass filter design.
"""

import math

import pytest

from filter_lib.bandpass import calculate_bandpass_filter, compute_bandpass_3db_edges
from filter_lib.bandpass.calculations import (
    BANDPASS_EDGE_CALIBRATION_FBW_MAX,
    BANDPASS_LUMPED_MODEL_CAUTION_FBW,
    calculate_coupling_capacitors,
    calculate_coupling_coefficients,
    calculate_end_coupling,
    calculate_external_q,
    calculate_resonator_components,
    calculate_tank_capacitors,
    combine_resonator_q,
    estimate_insertion_loss,
)
from filter_lib.bandpass.transfer import magnitude_db


class TestEndCoupling:
    """Series end-coupling capacitor sizing (realizes the external Q)."""

    def test_reference_design_values(self):
        """Butterworth n=3, f0=10 MHz, BW=1 MHz, Z0=50: Ce ≈ 106.1 pF."""
        f0, z0 = 10e6, 50.0
        omega0 = 2 * math.pi * f0
        l_resonant = z0 / omega0
        qe = 1.0 / 0.1  # g1=1 (Butterworth n=3), fbw=10%
        ce, delta_c = calculate_end_coupling(qe, omega0, l_resonant, z0)
        assert ce == pytest.approx(106.1e-12, rel=0.001)
        assert 0 < delta_c < ce

    def test_transformation_identity(self):
        """Rp seen through the series cap equals Qe·ω0·L by construction."""
        f0, z0 = 14e6, 50.0
        omega0 = 2 * math.pi * f0
        l_resonant = z0 / omega0
        qe = 25.0
        ce, _ = calculate_end_coupling(qe, omega0, l_resonant, z0)
        q = 1 / (omega0 * z0 * ce)
        assert z0 * (1 + q * q) == pytest.approx(qe * omega0 * l_resonant, rel=1e-9)

    def test_infeasible_when_rp_at_or_below_z0(self):
        f0, z0 = 10e6, 50.0
        omega0 = 2 * math.pi * f0
        l_resonant = z0 / omega0  # makes Rp = qe * z0
        with pytest.raises(ValueError, match="too wide"):
            calculate_end_coupling(1.0, omega0, l_resonant, z0)
        with pytest.raises(ValueError, match="too wide"):
            calculate_end_coupling(0.5, omega0, l_resonant, z0)

    def test_result_dict_carries_end_caps_and_retuned_tanks(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 3, "butterworth", "top")
        assert result["c_end_in"] > 0
        assert result["c_end_out"] > 0
        # End tanks are retuned (smaller than the symmetric middle tank)
        assert result["c_tank"][0] < result["c_tank"][1]
        assert result["c_tank"][-1] < result["c_tank"][1]

    def test_shunt_coupling_rejected_as_removed(self):
        with pytest.raises(ValueError, match="Shunt-C coupling has been removed"):
            calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "shunt")


class TestCouplingCoefficients:
    """Test inter-resonator coupling coefficient calculations."""

    def test_basic_coupling_coefficients(self):
        """Test basic coupling coefficient calculation."""
        g_values = [1.0, 1.3, 2.0, 1.3, 1.0]
        fbw = 0.1

        k_values = calculate_coupling_coefficients(g_values, fbw)

        assert len(k_values) == 4  # 5 resonators -> 4 coupling coefficients
        assert all(k > 0 for k in k_values)

    def test_coupling_formula(self):
        """Test coupling coefficient formula: k = FBW / sqrt(g[i] * g[i+1])."""
        g_values = [1.0, 1.3, 2.0, 1.3, 1.0]
        fbw = 0.1

        k_values = calculate_coupling_coefficients(g_values, fbw)

        # Verify first coupling coefficient
        expected_k1 = fbw / math.sqrt(g_values[0] * g_values[1])
        assert abs(k_values[0] - expected_k1) < 1e-15

    def test_bandwidth_effect_on_coupling(self):
        """Test that higher bandwidth increases coupling coefficients."""
        g_values = [1.0, 1.3, 2.0, 1.3, 1.0]

        k_narrow = calculate_coupling_coefficients(g_values, 0.05)
        k_wide = calculate_coupling_coefficients(g_values, 0.2)

        # Higher bandwidth -> higher coupling
        for kn, kw in zip(k_narrow, k_wide):
            assert kw > kn

    def test_coupling_with_different_g_values(self):
        """Test coupling with asymmetric g-values."""
        g_values = [0.5, 1.0, 1.5, 1.0, 0.5]
        fbw = 0.1

        k_values = calculate_coupling_coefficients(g_values, fbw)

        assert len(k_values) == 4
        assert all(k > 0 for k in k_values)

    def test_coupling_zero_fbw_is_rejected(self):
        """Zero fractional bandwidth cannot produce a realizable coupling."""
        g_values = [1.0, 1.3, 2.0]

        with pytest.raises(ValueError, match="positive and finite"):
            calculate_coupling_coefficients(g_values, 0)


class TestExternalQ:
    """Test external Q factor calculations."""

    def test_basic_external_q(self):
        """Test basic external Q calculation."""
        g_values = [1.0, 1.3, 2.0, 1.3, 1.0]
        fbw = 0.1

        qe_in, qe_out = calculate_external_q(g_values, fbw)

        assert qe_in > 0
        assert qe_out > 0

    def test_external_q_formula(self):
        """Test external Q formula: Qe = g / FBW."""
        g_values = [1.0, 1.3, 2.0, 1.3, 1.0]
        fbw = 0.1

        qe_in, qe_out = calculate_external_q(g_values, fbw)

        # First and last g-values used for input and output
        expected_qe_in = g_values[0] / fbw
        expected_qe_out = g_values[-1] / fbw

        assert abs(qe_in - expected_qe_in) < 1e-15
        assert abs(qe_out - expected_qe_out) < 1e-15

    def test_external_q_symmetry(self):
        """Test that symmetric g-values produce symmetric Qe."""
        g_values = [1.0, 1.3, 2.0, 1.3, 1.0]  # Symmetric
        fbw = 0.1

        qe_in, qe_out = calculate_external_q(g_values, fbw)

        # Should be symmetric
        assert abs(qe_in - qe_out) < 1e-15

    def test_external_q_asymmetric(self):
        """Test that asymmetric g-values produce asymmetric Qe."""
        g_values = [1.0, 1.3, 2.0, 1.5, 0.8]  # Asymmetric
        fbw = 0.1

        qe_in, qe_out = calculate_external_q(g_values, fbw)

        # Should be different
        assert abs(qe_in - qe_out) > 1e-6

    def test_narrow_bandwidth_high_q(self):
        """Test that narrow bandwidth produces high Q."""
        g_values = [1.0, 1.3, 2.0]
        fbw_narrow = 0.01
        fbw_wide = 0.2

        qe_n_in, qe_n_out = calculate_external_q(g_values, fbw_narrow)
        qe_w_in, qe_w_out = calculate_external_q(g_values, fbw_wide)

        # Narrower bandwidth -> higher Q
        assert qe_n_in > qe_w_in
        assert qe_n_out > qe_w_out


class TestResonatorComponents:
    """Test LC tank component calculations."""

    def test_basic_resonator_components(self):
        """Test basic resonator L and C calculation."""
        f0 = 14.175e6  # 20m amateur band
        z0 = 50

        ind, c = calculate_resonator_components(f0, z0)

        assert ind > 0
        assert c > 0

    def test_resonator_formula(self):
        """Test resonator formula: L = Z0/ω0, C = 1/(ω0*Z0)."""
        f0 = 14.175e6
        z0 = 50
        omega0 = 2 * math.pi * f0

        ind, c = calculate_resonator_components(f0, z0)

        expected_l = z0 / omega0
        expected_c = 1 / (omega0 * z0)

        assert abs(ind - expected_l) < 1e-15
        assert abs(c - expected_c) < 1e-15

    def test_impedance_scaling(self):
        """Test impedance scaling of resonator components."""
        f0 = 14.175e6

        l_50, c_50 = calculate_resonator_components(f0, 50)
        l_75, c_75 = calculate_resonator_components(f0, 75)

        # Higher impedance -> larger L, smaller C
        assert l_75 > l_50
        assert c_75 < c_50

    def test_frequency_scaling(self):
        """Test frequency scaling of resonator components."""
        z0 = 50

        l_low, c_low = calculate_resonator_components(10e6, z0)
        l_high, c_high = calculate_resonator_components(100e6, z0)

        # Higher frequency -> smaller L and C
        assert l_high < l_low
        assert c_high < c_low

    def test_resonant_frequency_verification(self):
        """Test that L and C resonate at f0."""
        f0 = 14.175e6
        z0 = 50

        ind, c = calculate_resonator_components(f0, z0)

        # LC product should match: LC = 1/(4π²f0²)
        lc_product = ind * c
        expected_lc = 1 / (4 * math.pi**2 * f0**2)

        assert abs(lc_product - expected_lc) < 1e-25

    def test_explicit_resonator_impedance(self):
        f0 = 10e6
        ind, cap = calculate_resonator_components(f0, 50, resonator_impedance=200)
        omega0 = 2 * math.pi * f0
        assert ind == pytest.approx(200 / omega0)
        assert cap == pytest.approx(1 / (omega0 * 200))

    def test_fixed_inductance_is_preserved(self):
        f0 = 10e6
        chosen_l = 2.2e-6
        ind, cap = calculate_resonator_components(f0, 50, resonator_inductance=chosen_l)
        assert ind == chosen_l
        assert cap == pytest.approx(1 / ((2 * math.pi * f0) ** 2 * chosen_l))

    def test_resonator_choice_inputs_are_mutually_exclusive(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            calculate_resonator_components(
                10e6,
                50,
                resonator_impedance=100,
                resonator_inductance=1e-6,
            )


class TestCouplingCapacitors:
    """Test coupling capacitor calculations."""

    def test_basic_coupling_capacitors(self):
        """Test basic coupling capacitor calculation."""
        k_values = [0.05, 0.04, 0.05]
        c_resonant = 100e-12

        cs = calculate_coupling_capacitors(k_values, c_resonant)

        assert len(cs) == 3
        assert all(c > 0 for c in cs)

    def test_coupling_formula(self):
        """Test coupling capacitor formula: Cs = k * C_resonant."""
        k_values = [0.05, 0.04, 0.05]
        c_resonant = 100e-12

        cs = calculate_coupling_capacitors(k_values, c_resonant)

        # Verify formula
        for i, k in enumerate(k_values):
            expected_cs = k * c_resonant
            assert abs(cs[i] - expected_cs) < 1e-24

    def test_coupling_proportional_to_k(self):
        """Test that coupling capacitors are proportional to k."""
        c_resonant = 100e-12

        cs_small_k = calculate_coupling_capacitors([0.01, 0.01], c_resonant)
        cs_large_k = calculate_coupling_capacitors([0.1, 0.1], c_resonant)

        # Higher k -> larger coupling capacitors
        for cs, cl in zip(cs_small_k, cs_large_k):
            assert cl > cs

    def test_empty_k_values(self):
        """Test with no coupling values."""
        k_values = []
        c_resonant = 100e-12

        cs = calculate_coupling_capacitors(k_values, c_resonant)

        assert len(cs) == 0


class TestTankCapacitors:
    """Test tank capacitor compensation calculations."""

    def test_basic_tank_capacitors(self):
        """Test basic tank capacitor calculation."""
        n_resonators = 3
        c_resonant = 100e-12
        c_coupling = [5e-12, 4e-12]

        cp = calculate_tank_capacitors(n_resonators, c_resonant, c_coupling)

        assert len(cp) == 3

    def test_tank_capacitor_compensation(self):
        """Test that tank capacitors are reduced for coupling."""
        n_resonators = 3
        c_resonant = 100e-12
        c_coupling = [5e-12, 4e-12]

        cp = calculate_tank_capacitors(n_resonators, c_resonant, c_coupling)

        # First resonator: Cp1 = C_res - Cs12
        expected_cp1 = c_resonant - c_coupling[0]
        assert abs(cp[0] - expected_cp1) < 1e-24

        # Middle resonator: Cp2 = C_res - Cs12 - Cs23
        expected_cp2 = c_resonant - c_coupling[0] - c_coupling[1]
        assert abs(cp[1] - expected_cp2) < 1e-24

        # Last resonator: Cp3 = C_res - Cs23
        expected_cp3 = c_resonant - c_coupling[1]
        assert abs(cp[2] - expected_cp3) < 1e-24

    def test_tank_positive_values(self):
        """Test that tank capacitors remain positive."""
        n_resonators = 3
        c_resonant = 100e-12
        c_coupling = [10e-12, 15e-12]

        cp = calculate_tank_capacitors(n_resonators, c_resonant, c_coupling)

        # All should be positive (or close to zero if well-designed)
        assert all(c >= 0 for c in cp)

    def test_single_resonator_no_coupling(self):
        """Test single resonator with no coupling."""
        n_resonators = 1
        c_resonant = 100e-12
        c_coupling = []

        cp = calculate_tank_capacitors(n_resonators, c_resonant, c_coupling)

        assert len(cp) == 1
        assert cp[0] == c_resonant


class TestBandpassEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_narrow_bandwidth(self):
        """Test very narrow bandwidth."""
        g_values = [1.0, 1.3, 2.0]
        fbw = 0.001  # Very narrow

        k_values = calculate_coupling_coefficients(g_values, fbw)
        qe_in, qe_out = calculate_external_q(g_values, fbw)

        assert all(k > 0 for k in k_values)
        assert qe_in > 100  # High Q for narrow bandwidth

    def test_very_wide_bandwidth(self):
        """Test very wide bandwidth."""
        g_values = [1.0, 1.3, 2.0]
        fbw = 0.5  # Very wide

        k_values = calculate_coupling_coefficients(g_values, fbw)
        qe_in, qe_out = calculate_external_q(g_values, fbw)

        assert all(k > 0 for k in k_values)
        assert qe_in < 5  # Low Q for wide bandwidth

    def test_real_world_20m_bandpass(self):
        """Test realistic 20m amateur radio bandpass."""
        f0 = 14.175e6  # 20m band center
        z0 = 50

        ind, c = calculate_resonator_components(f0, z0)

        # Should produce reasonable component values
        assert 1e-9 < ind < 1e-6  # nH to µH range
        assert 1e-12 < c < 1e-9  # pF to nF range

    def test_chebyshev_arbitrary_ripple_synthesizes(self):
        """Ripple values between former table entries produce a complete design."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "chebyshev", "top", ripple_db=0.25)
        assert result["ripple_db"] == 0.25
        assert len(result["c_tank"]) == 3
        assert all(c > 0 for c in result["c_tank"])
        assert result["c_end_in"] > 0 and result["c_end_out"] > 0

    def test_chebyshev_ripple_above_ceiling_rejected(self):
        with pytest.raises(ValueError, match="at most 3.0 dB"):
            calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "chebyshev", "top", ripple_db=3.5)

    def test_bandwidth_too_wide_negative_tank_caps_rejected(self):
        """End-coupling deltas exceeding the tank capacitance raise a clear error."""
        with pytest.raises(ValueError, match="Bandwidth too wide"):
            calculate_bandpass_filter(10e6, 9e6, 50, 3, "butterworth", "top")


class TestInsertionLoss:
    """Cohn dissipation-loss estimate: IL ≈ 4.343·Σg/(FBW_synth·Qu) dB."""

    def test_butterworth_n3_spot_value(self):
        """n=3 Butterworth (g = 1, 2, 1 → Σg = 4), FBW=5%, Qu=100 → 3.47 dB."""
        g_values = [1.0, 2.0, 1.0]
        il = estimate_insertion_loss(g_values, 0.05, 100.0)
        assert il == pytest.approx(4.343 * 4.0 / (0.05 * 100.0), abs=1e-2)

    @pytest.mark.parametrize("qu", [0.0, -1.0, float("inf"), float("nan")])
    def test_invalid_qu_rejected(self, qu):
        with pytest.raises(ValueError, match="must be positive and finite"):
            estimate_insertion_loss([1.0, 2.0, 1.0], 0.05, qu)

    def test_result_dict_standard_estimates(self):
        """il_estimates carries the standard Qu=100/250 entries; q_min unchanged."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")
        assert set(result["il_estimates"]) == {"100", "250"}
        expected_100 = 4.343 * sum(result["g_values"]) / (result["fbw_synth"] * 100.0)
        assert result["il_estimates"]["100"] == pytest.approx(expected_100)
        # IL scales as 1/Qu
        assert result["il_estimates"]["250"] == pytest.approx(expected_100 * 100.0 / 250.0)
        assert result["q_min"] > 0

    def test_user_qu_adds_entry(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", qu=150.0)
        assert set(result["il_estimates"]) == {"100", "250", "150"}

    def test_user_qu_duplicate_of_standard_not_repeated(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", qu=100.0)
        assert set(result["il_estimates"]) == {"100", "250"}

    def test_user_qu_rendering_like_standard_keeps_standard_entry(self):
        """A user Qu whose "%g" rendering collides with a standard key must not
        overwrite the standard estimate."""
        result = calculate_bandpass_filter(
            10e6, 0.5e6, 50, 3, "butterworth", "top", qu=249.9999999999
        )
        assert set(result["il_estimates"]) == {"100", "250"}
        expected_250 = 4.343 * sum(result["g_values"]) / (result["fbw_synth"] * 250.0)
        assert result["il_estimates"]["250"] == pytest.approx(expected_250)

    def test_invalid_qu_in_calculate_rejected(self):
        with pytest.raises(ValueError, match="must be positive and finite"):
            calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top", qu=0.0)

    def test_fbw_synth_butterworth_equals_fbw(self):
        """Butterworth starts at user FBW, then calibration may correct it."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")
        assert result["fbw_synth_initial"] == pytest.approx(result["fbw"])
        assert result["fbw_synth"] > 0

    def test_fbw_synth_chebyshev_narrower_than_fbw(self):
        """Chebyshev ripple edge is narrower than the -3 dB BW (delta_3dB > 1)."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "chebyshev", "top", ripple_db=0.5)
        assert result["fbw_synth"] < result["fbw"]

    def test_chebyshev_il_uses_fbw_synth(self):
        """IL is computed against the prototype-mapped FBW, not the user's -3 dB FBW."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "chebyshev", "top", ripple_db=0.5)
        expected = 4.343 * sum(result["g_values"]) / (result["fbw_synth"] * 100.0)
        assert result["il_estimates"]["100"] == pytest.approx(expected)

    def test_separate_component_q_values_combine_as_resonator_q(self):
        assert combine_resonator_q(ql=200, qc=400) == pytest.approx(1 / (1 / 200 + 1 / 400))
        assert combine_resonator_q(ql=200) == 200
        assert combine_resonator_q(qc=400) == 400

    def test_component_q_combination_avoids_reciprocal_overflow(self):
        combined = combine_resonator_q(ql=1e-309, qc=1e-309)
        assert combined is not None and combined > 0
        assert combined == pytest.approx(5e-310, rel=1e-12, abs=0)

    def test_direct_qu_is_mutually_exclusive_with_component_q(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            combine_resonator_q(qu=100, ql=200)

    def test_result_records_truthful_q_model(self):
        result = calculate_bandpass_filter(
            10e6,
            0.5e6,
            50,
            3,
            "butterworth",
            "top",
            ql=200,
            qc=400,
        )
        assert result["q_model"]["resonator_qu"] == pytest.approx(133.3333333333)
        assert result["q_model"]["definition"] == "complete_resonator_unloaded_q"
        assert result["q_model"]["combination"] == "reciprocal_component_loss_sum"
        assert result["q_model"]["inductor_ql"] == 200
        assert result["q_model"]["capacitor_qc"] == 400
        assert result["q_min_resonator"] == result["q_min"]
        assert result["q_min_is_heuristic"] is True
        assert result["q_safety_compatibility_only"] is True


class TestBandpass3dBEdges:
    """compute_bandpass_3db_edges must return true -3 dB corner frequencies."""

    @pytest.mark.parametrize(
        "f0, bw",
        [
            (1.0e6, 400e3),  # 40% fractional BW — arithmetic approx fails here
            (14.175e6, 350e3),  # narrow, typical HF bandpass
            (100e6, 10e6),  # 10% fractional BW
            (1e9, 20e6),  # very narrow
        ],
    )
    def test_edges_hit_minus_3db_on_butterworth(self, f0, bw):
        f_low, f_high = compute_bandpass_3db_edges(f0, bw)
        # Both edges should be at exactly -3.0103 dB (10*log10(0.5))
        target_db = 10.0 * math.log10(0.5)
        low_db = magnitude_db(f_low, f0, bw, 3, "butterworth")
        high_db = magnitude_db(f_high, f0, bw, 3, "butterworth")
        assert low_db == pytest.approx(target_db, abs=1e-9)
        assert high_db == pytest.approx(target_db, abs=1e-9)

    @pytest.mark.parametrize("f0, bw", [(1e6, 400e3), (14.175e6, 350e3), (100e6, 10e6)])
    def test_width_equals_bw(self, f0, bw):
        f_low, f_high = compute_bandpass_3db_edges(f0, bw)
        assert f_high - f_low == pytest.approx(bw, rel=1e-12)

    @pytest.mark.parametrize("f0, bw", [(1e6, 400e3), (14.175e6, 350e3), (100e6, 10e6)])
    def test_geometric_center(self, f0, bw):
        """f0 is the geometric mean of the -3 dB edges."""
        f_low, f_high = compute_bandpass_3db_edges(f0, bw)
        assert math.sqrt(f_low * f_high) == pytest.approx(f0, rel=1e-12)

    def test_rejects_non_positive_inputs(self):
        with pytest.raises(ValueError):
            compute_bandpass_3db_edges(0, 100e3)
        with pytest.raises(ValueError):
            compute_bandpass_3db_edges(1e6, 0)
        with pytest.raises(ValueError):
            compute_bandpass_3db_edges(1e6, -1)

    def test_no_catastrophic_cancellation_for_extreme_bw(self):
        """f_low must remain accurate even when bw >> 2*f0."""
        f0 = 1.0
        bw = 1e20  # Pathological: bw orders of magnitude larger than f0
        f_low, f_high = compute_bandpass_3db_edges(f0, bw)
        # Geometric invariant must hold exactly
        assert math.sqrt(f_low * f_high) == pytest.approx(f0, rel=1e-12)
        # f_low must be strictly positive, not crushed to 0 by cancellation
        assert f_low > 0

    def test_result_dict_uses_true_edges(self):
        """calculate_bandpass_filter propagates the correct -3 dB edges in the result."""
        result = calculate_bandpass_filter(
            f0=1e6,
            bw=400e3,
            z0=50,
            n_resonators=3,
            filter_type="butterworth",
            coupling="top",
        )
        expected_low, expected_high = compute_bandpass_3db_edges(1e6, 400e3)
        assert result["f_low"] == pytest.approx(expected_low, rel=1e-12)
        assert result["f_high"] == pytest.approx(expected_high, rel=1e-12)
        # Sanity: arithmetic shortcut would be 800 kHz / 1.2 MHz — these are not that
        assert abs(result["f_low"] - 800e3) > 10e3
        assert abs(result["f_high"] - 1.2e6) > 10e3

    def test_stays_finite_near_float_limit(self):
        f_low, f_high = compute_bandpass_3db_edges(1e308, 1e307)
        assert math.isfinite(f_low)
        assert math.isfinite(f_high)
        assert math.sqrt(f_low / f_high) * f_high == pytest.approx(1e308)

    @pytest.mark.parametrize(
        ("f0", "bw", "z0"),
        [(1e307, 1e305, 10.0), (3e307, 1e305, 1.0), (1e308, 1e307, 50.0)],
    )
    def test_filter_accepts_extreme_frequency_when_final_components_are_finite(self, f0, bw, z0):
        result = calculate_bandpass_filter(f0, bw, z0, 3, "butterworth", "top")

        component_values = [
            result["L_resonant"],
            result["C_resonant"],
            result["c_end_in"],
            result["c_end_out"],
            *result["c_tank"],
            *result["c_coupling"],
        ]
        assert all(math.isfinite(value) and value > 0 for value in component_values)

    def test_filter_rejects_frequency_that_cannot_make_finite_components(self):
        with pytest.raises(ValueError, match="numeric range"):
            calculate_bandpass_filter(1e308, 1e307, 1e308, 3, "butterworth", "top")


class TestCalibratedBandpassSynthesis:
    @pytest.mark.parametrize("filter_type", ["butterworth", "bessel"])
    def test_monotonic_responses_do_not_mislabel_edge_variation_as_ripple(self, filter_type):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, filter_type, "top")
        validation = result["synthesis_validation"]

        assert validation["measured_passband_variation_db"] > 0
        assert "measured_ripple_db" not in validation

    def test_chebyshev_validation_reports_equal_ripple_band_variation(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "chebyshev", "top", ripple_db=0.5)
        validation = result["synthesis_validation"]

        assert validation["measured_ripple_db"] == validation["measured_passband_variation_db"]

    def test_requested_and_internal_parameters_are_distinct_and_verified(self):
        result = calculate_bandpass_filter(10e6, 1e6, 50, 9, "chebyshev", "top", ripple_db=0.5)
        validation = result["synthesis_validation"]
        assert result["f_low"] != result["f_high"]
        assert result["f_tank_hz"] != pytest.approx(result["f0"], rel=1e-4)
        assert result["fbw_synth_initial"] != pytest.approx(result["fbw_synth"], rel=1e-4)
        assert abs(validation["lower_edge_error_rel"]) <= 1e-3
        assert abs(validation["upper_edge_error_rel"]) <= 1e-3
        assert validation["connected_region_count"] >= 1
        assert validation["iterations"] <= 12
        assert validation["calibration_converged"] is True
        assert validation["calibration_method"] == "bounded_log_newton"
        assert validation["calibration_tolerance"] == 2e-5
        assert validation["calibration_max_iterations"] == 12

    def test_fixed_l_survives_calibration(self):
        chosen_l = 1.8e-6
        result = calculate_bandpass_filter(
            10e6,
            0.5e6,
            50,
            3,
            "butterworth",
            "top",
            resonator_inductance=chosen_l,
        )
        assert result["L_resonant"] == chosen_l
        assert result["resonator_selection"] == "fixed_inductance"
        assert abs(result["synthesis_validation"]["lower_edge_error_rel"]) <= 1e-3
        assert abs(result["synthesis_validation"]["upper_edge_error_rel"]) <= 1e-3

    def test_custom_resonator_impedance_survives_calibration(self):
        result = calculate_bandpass_filter(
            10e6,
            0.5e6,
            50,
            3,
            "butterworth",
            "top",
            resonator_impedance=200,
        )
        assert result["resonator_selection"] == "fixed_impedance"
        assert result["resonator_impedance"] == pytest.approx(200)
        assert math.sqrt(result["L_resonant"] / result["C_resonant"]) == pytest.approx(200)
        assert result["internal_synthesis_parameters"]["resonator_impedance_ohms"] == 200
        assert abs(result["synthesis_validation"]["lower_edge_error_rel"]) <= 1e-3
        assert abs(result["synthesis_validation"]["upper_edge_error_rel"]) <= 1e-3


class TestBandpassFbwGuidance:
    def test_public_guidance_boundaries_match_engine_contract(self):
        assert BANDPASS_EDGE_CALIBRATION_FBW_MAX == 0.10
        assert BANDPASS_LUMPED_MODEL_CAUTION_FBW == 0.40

    @pytest.mark.parametrize(
        "fbw, validation_warning, lumped_warning",
        [
            (BANDPASS_EDGE_CALIBRATION_FBW_MAX, False, False),
            (BANDPASS_EDGE_CALIBRATION_FBW_MAX + 1e-6, True, False),
            (BANDPASS_LUMPED_MODEL_CAUTION_FBW, True, False),
            (BANDPASS_LUMPED_MODEL_CAUTION_FBW + 1e-6, True, True),
        ],
    )
    def test_warning_boundaries_are_strict(self, fbw, validation_warning, lumped_warning):
        result = calculate_bandpass_filter(10e6, 10e6 * fbw, 50, 3, "butterworth", "top")
        warnings = result["warnings"]
        assert (
            any("studied edge-calibration range" in warning for warning in warnings)
            is validation_warning
        )
        assert any("transmission-line design" in warning for warning in warnings) is lumped_warning


class TestBandpassPublicInputTypes:
    """Public synthesis inputs reject bools and non-integral resonator counts."""

    @staticmethod
    def _arguments() -> dict:
        return {
            "f0": 10e6,
            "bw": 0.5e6,
            "z0": 50.0,
            "n_resonators": 3,
            "filter_type": "butterworth",
            "coupling": "top",
        }

    @pytest.mark.parametrize("n_resonators", [True, False, 3.0, 3.5, "3"])
    def test_rejects_non_integer_resonator_count(self, n_resonators):
        arguments = self._arguments()
        arguments["n_resonators"] = n_resonators
        with pytest.raises(ValueError, match="integer between 2 and 9"):
            calculate_bandpass_filter(**arguments)

    @pytest.mark.parametrize(
        "name,error",
        [
            ("q_safety", "q_safety"),
            ("qu", "Qu"),
            ("ql", "QL"),
            ("qc", "QC"),
            ("resonator_impedance", "resonator_impedance"),
            ("resonator_inductance", "resonator_inductance"),
        ],
    )
    def test_rejects_bool_advanced_numeric_input(self, name, error):
        arguments = self._arguments()
        arguments[name] = True
        with pytest.raises(ValueError, match=error):
            calculate_bandpass_filter(**arguments)

    @pytest.mark.parametrize(
        "name,error",
        [
            ("f0", "Center frequency"),
            ("bw", "Bandwidth"),
            ("z0", "Impedance"),
        ],
    )
    def test_rejects_bool_core_numeric_input(self, name, error):
        arguments = self._arguments()
        arguments[name] = True
        with pytest.raises(ValueError, match=error):
            calculate_bandpass_filter(**arguments)

    def test_rejects_bool_chebyshev_ripple(self):
        arguments = self._arguments()
        arguments.update(filter_type="chebyshev", ripple_db=True)
        with pytest.raises(ValueError, match="ripple_db must be positive and finite"):
            calculate_bandpass_filter(**arguments)


class TestBandpassCompatibilityFacades:
    """Legacy calculation and transfer import surfaces remain available."""

    def test_calculations_facade_keeps_existing_names(self):
        from filter_lib.bandpass import calculations

        expected_names = (
            "math",
            "Any",
            "BandpassResult",
            "BANDPASS_EDGE_CALIBRATION_FBW_MAX",
            "BANDPASS_LUMPED_MODEL_CAUTION_FBW",
            "STANDARD_QU_VALUES",
            "calculate_coupling_coefficients",
            "calculate_external_q",
            "_resolve_resonator_components",
            "calculate_resonator_components",
            "calculate_coupling_capacitors",
            "calculate_tank_capacitors",
            "calculate_end_coupling",
            "combine_resonator_q",
            "estimate_insertion_loss",
            "calculate_min_q",
            "compute_bandpass_3db_edges",
            "_validate_inputs",
            "_get_fbw_warnings",
            "_synthesize_top_c_raw",
            "_calibrate_top_c",
            "calculate_bandpass_filter",
        )
        assert all(hasattr(calculations, name) for name in expected_names)

    def test_transfer_facade_keeps_existing_names(self):
        from filter_lib.bandpass import transfer

        expected_names = (
            "math",
            "Any",
            "lowpass_bessel_response",
            "chebyshev_polynomial",
            "magnitude_to_db",
            "BANDPASS_EDGE_CALIBRATION_FBW_MAX",
            "THREE_DB_DOWN",
            "EDGE_ERROR_LIMIT_REL",
            "PASSBAND_SHAPE_ERROR_LIMIT_DB",
            "CHEBYSHEV_RIPPLE_ALLOWANCE_DB",
            "STOPBAND_SAMPLE_ERROR_LIMIT_DB",
            "chebyshev_3db_deviation",
            "_bandpass_deviation",
            "frequency_from_deviation",
            "_deviation_grid",
            "measure_netlist_passband",
            "validate_netlist_shape",
            "magnitude_butterworth",
            "magnitude_chebyshev",
            "magnitude_bessel",
            "magnitude_db",
            "frequency_sweep",
            "netlist_frequency_sweep",
            "generate_frequency_points",
            "_log_sweep_frequencies",
            "frequency_response",
        )
        assert all(hasattr(transfer, name) for name in expected_names)
