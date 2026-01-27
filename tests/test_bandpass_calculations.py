"""Unit tests for bandpass filter calculations.

Tests verify coupled resonator calculations for bandpass filter design.
"""
import math
import pytest
from filter_lib.bandpass.calculations import (
    calculate_coupling_coefficients,
    calculate_external_q,
    calculate_resonator_components,
    calculate_coupling_capacitors,
    calculate_tank_capacitors,
)


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

    def test_coupling_zero_fbw_warning(self):
        """Test behavior with zero bandwidth."""
        g_values = [1.0, 1.3, 2.0]
        fbw = 0  # Zero bandwidth

        k_values = calculate_coupling_coefficients(g_values, fbw)

        # Zero bandwidth -> zero coupling
        assert all(k == 0 for k in k_values)


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

        l, c = calculate_resonator_components(f0, z0)

        assert l > 0
        assert c > 0

    def test_resonator_formula(self):
        """Test resonator formula: L = Z0/ω0, C = 1/(ω0*Z0)."""
        f0 = 14.175e6
        z0 = 50
        omega0 = 2 * math.pi * f0

        l, c = calculate_resonator_components(f0, z0)

        expected_l = z0 / omega0
        expected_c = 1 / (omega0 * z0)

        assert abs(l - expected_l) < 1e-15
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

        l, c = calculate_resonator_components(f0, z0)

        # LC product should match: LC = 1/(4π²f0²)
        lc_product = l * c
        expected_lc = 1 / (4 * math.pi**2 * f0**2)

        assert abs(lc_product - expected_lc) < 1e-25


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
        fbw = 350e3 / f0  # 350 kHz bandwidth
        z0 = 50

        l, c = calculate_resonator_components(f0, z0)

        # Should produce reasonable component values
        assert 1e-9 < l < 1e-6  # nH to µH range
        assert 1e-12 < c < 1e-9  # pF to nF range

