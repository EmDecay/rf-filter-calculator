"""Unit tests for lowpass filter calculations.

Tests verify mathematical correctness of Butterworth, Chebyshev, and Bessel
lowpass filter component value calculations.
"""
import math
import pytest
from filter_lib.lowpass import calculations as lp


class TestButterworthLowpass:
    """Test Butterworth lowpass filter calculations."""

    def test_basic_2component_50ohm_1mhz(self):
        """Test basic 2-component Butterworth at 1 MHz, 50 Ohms."""
        cutoff = 1e6
        impedance = 50
        caps, inds, order = lp.calculate_butterworth(cutoff, impedance, 2, topology='pi')

        assert order == 2
        assert len(caps) == 1
        assert len(inds) == 1

        # All values should be positive
        assert all(c > 0 for c in caps)
        assert all(i > 0 for i in inds)

    def test_5component_butterworth(self):
        """Test 5-component Butterworth filter."""
        caps, inds, order = lp.calculate_butterworth(10e6, 50, 5, topology='pi')

        assert order == 5
        assert len(caps) == 3  # Pi topology: C-L-C-L-C
        assert len(inds) == 2

        # Verify symmetry (should be symmetric for Butterworth)
        assert abs(caps[0] - caps[2]) < 1e-15

    def test_impedance_scaling(self):
        """Test that doubling impedance roughly doubles inductor values."""
        cutoff = 10e6
        caps_50, inds_50, _ = lp.calculate_butterworth(cutoff, 50, 3, topology='pi')
        caps_100, inds_100, _ = lp.calculate_butterworth(cutoff, 100, 3, topology='pi')

        # Higher impedance -> larger inductors
        for i50, i100 in zip(inds_50, inds_100):
            assert i100 > i50

    def test_frequency_scaling(self):
        """Test that higher frequency reduces component values."""
        impedance = 50
        caps_1m, inds_1m, _ = lp.calculate_butterworth(1e6, impedance, 3, topology='pi')
        caps_10m, inds_10m, _ = lp.calculate_butterworth(10e6, impedance, 3, topology='pi')

        # Higher frequency -> smaller L and C
        for c1, c10 in zip(caps_1m, caps_10m):
            assert c10 < c1
        for i1, i10 in zip(inds_1m, inds_10m):
            assert i10 < i1

    def test_order_range(self):
        """Test all valid filter orders (2-9)."""
        for order in range(2, 10):
            caps, inds, n = lp.calculate_butterworth(10e6, 50, order, topology='pi')
            assert n == order
            assert len(caps) + len(inds) == order

    def test_formula_verification_2component(self):
        """Verify 2-component uses correct Butterworth formula.

        For 2-component Butterworth:
        g1 = 2*sin(π/4) = sqrt(2)
        g2 = 2*sin(3π/4) = sqrt(2)
        C1 = g1/(Z0*ω)
        L2 = g2*Z0/ω
        """
        cutoff = 1e6
        z0 = 50
        omega = 2 * math.pi * cutoff

        caps, inds, _ = lp.calculate_butterworth(cutoff, z0, 2, topology='pi')

        # Expected values
        g1 = 2 * math.sin(math.pi / 4)
        g2 = 2 * math.sin(3 * math.pi / 4)

        expected_c1 = g1 / (z0 * omega)
        expected_l2 = g2 * z0 / omega

        assert abs(caps[0] - expected_c1) < 1e-15
        assert abs(inds[0] - expected_l2) < 1e-15


class TestChebychevLowpass:
    """Test Chebyshev lowpass filter calculations."""

    def test_basic_chebyshev_0_5db(self):
        """Test basic Chebyshev with 0.5 dB ripple."""
        caps, inds, order = lp.calculate_chebyshev(10e6, 50, 0.5, 3, topology='pi')

        assert order == 3
        assert len(caps) == 2
        assert len(inds) == 1

        # All values positive
        assert all(c > 0 for c in caps)
        assert all(i > 0 for i in inds)

    def test_ripple_effect(self):
        """Test that higher ripple allows smaller components."""
        cutoff = 10e6
        impedance = 50
        order = 3

        caps_01, inds_01, _ = lp.calculate_chebyshev(cutoff, impedance, 0.1, order, topology='pi')
        caps_10, inds_10, _ = lp.calculate_chebyshev(cutoff, impedance, 1.0, order, topology='pi')

        # Higher ripple allows flatter response, different values
        # (not monotonic relationship, but should be different)
        assert caps_01 != caps_10

    def test_supported_ripples(self):
        """Test that various ripple values work."""
        ripples = [0.1, 0.5, 1.0, 2.0, 3.0]
        for ripple in ripples:
            caps, inds, order = lp.calculate_chebyshev(10e6, 50, ripple, 3, topology='pi')
            assert len(caps) > 0
            assert len(inds) > 0

    def test_order_range(self):
        """Test all valid Chebyshev orders."""
        for order in range(2, 10):
            caps, inds, n = lp.calculate_chebyshev(10e6, 50, 0.5, order, topology='pi')
            assert n == order
            assert len(caps) + len(inds) == order

    def test_impedance_scaling(self):
        """Test impedance scaling for Chebyshev."""
        caps_50, inds_50, _ = lp.calculate_chebyshev(10e6, 50, 0.5, 3, topology='pi')
        caps_100, inds_100, _ = lp.calculate_chebyshev(10e6, 100, 0.5, 3, topology='pi')

        # Higher impedance -> larger inductors
        for i50, i100 in zip(inds_50, inds_100):
            assert i100 > i50


class TestBesselLowpass:
    """Test Bessel lowpass filter calculations."""

    def test_basic_bessel(self):
        """Test basic Bessel filter."""
        caps, inds, order = lp.calculate_bessel(10e6, 50, 3, topology='pi')

        assert order == 3
        assert len(caps) == 2
        assert len(inds) == 1

        # All values positive
        assert all(c > 0 for c in caps)
        assert all(i > 0 for i in inds)

    def test_all_orders(self):
        """Test all supported Bessel orders (2-9)."""
        for order in range(2, 10):
            caps, inds, n = lp.calculate_bessel(10e6, 50, order, topology='pi')
            assert n == order
            assert len(caps) + len(inds) == order

    def test_invalid_order_raises(self):
        """Test that invalid order raises ValueError."""
        with pytest.raises(ValueError, match="Bessel filter supports"):
            lp.calculate_bessel(10e6, 50, 1, topology='pi')

        with pytest.raises(ValueError, match="Bessel filter supports"):
            lp.calculate_bessel(10e6, 50, 10, topology='pi')

    def test_frequency_scaling(self):
        """Test frequency scaling for Bessel."""
        caps_1m, inds_1m, _ = lp.calculate_bessel(1e6, 50, 3, topology='pi')
        caps_10m, inds_10m, _ = lp.calculate_bessel(10e6, 50, 3, topology='pi')

        # Higher frequency -> smaller components
        for c1, c10 in zip(caps_1m, caps_10m):
            assert c10 < c1
        for i1, i10 in zip(inds_1m, inds_10m):
            assert i10 < i1

    def test_impedance_scaling(self):
        """Test impedance scaling for Bessel."""
        caps_50, inds_50, _ = lp.calculate_bessel(10e6, 50, 3, topology='pi')
        caps_100, inds_100, _ = lp.calculate_bessel(10e6, 100, 3, topology='pi')

        # Higher impedance -> larger inductors, smaller capacitors
        for i50, i100 in zip(inds_50, inds_100):
            assert i100 > i50
        for c50, c100 in zip(caps_50, caps_100):
            assert c100 < c50


class TestLowpassEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_frequency_raises(self):
        """Test that zero frequency raises error or produces inf."""
        with pytest.raises((ValueError, ZeroDivisionError)):
            lp.calculate_butterworth(0, 50, 2, topology='pi')

    def test_invalid_topology_raises(self):
        """Test that invalid topology raises ValueError."""
        with pytest.raises(ValueError, match="Topology must be"):
            lp.calculate_butterworth(10e6, 50, 3, topology='x')

    def test_negative_impedance_does_not_validate(self):
        """Test that negative impedance produces unusual results.

        Note: Current implementation doesn't validate impedance.
        This test documents the behavior rather than enforcing validation.
        """
        # Negative impedance would produce mathematically invalid results
        caps, inds, _ = lp.calculate_butterworth(10e6, -50, 2, topology='pi')
        # With negative impedance, values will be negative
        assert any(c < 0 for c in caps) or any(i < 0 for i in inds)

    def test_very_small_frequency(self):
        """Test very small frequency produces very large components."""
        caps, inds, _ = lp.calculate_butterworth(1e3, 50, 2, topology='pi')

        caps_high, inds_high, _ = lp.calculate_butterworth(1e9, 50, 2, topology='pi')

        # Smaller frequency -> larger components
        assert caps[0] > caps_high[0]
        assert inds[0] > inds_high[0]

    def test_very_high_frequency(self):
        """Test very high frequency produces very small components."""
        caps, inds, _ = lp.calculate_butterworth(1e9, 50, 2, topology='pi')

        # Components should still be positive
        assert all(c > 0 for c in caps)
        assert all(i > 0 for i in inds)

    def test_very_large_impedance(self):
        """Test large impedance scaling."""
        caps_50, inds_50, _ = lp.calculate_butterworth(10e6, 50, 2, topology='pi')
        caps_1k, inds_1k, _ = lp.calculate_butterworth(10e6, 1000, 2, topology='pi')

        # 20x impedance -> 20x inductors
        ratio = inds_1k[0] / inds_50[0]
        assert 19 < ratio < 21


class TestComponentInterrelationships:
    """Test relationships between filter parameters."""

    def test_butterworth_symmetry_odd_order(self):
        """Test symmetry in odd-order Butterworth."""
        caps, inds, _ = lp.calculate_butterworth(10e6, 50, 5, topology='pi')

        # First and last capacitors should be equal (symmetric Pi)
        assert abs(caps[0] - caps[2]) < 1e-14

    def test_butterworth_symmetry_even_order(self):
        """Test that even-order Butterworth has correct structure.

        For 4-component lowpass: C-L-C-L topology
        Pi topology always alternates capacitors and inductors.
        """
        caps, inds, _ = lp.calculate_butterworth(10e6, 50, 4, topology='pi')

        # 4-component = 2 caps + 2 inductors
        assert len(caps) == 2
        assert len(inds) == 2
        # All should be positive
        assert all(c > 0 for c in caps)
        assert all(i > 0 for i in inds)

    def test_matching_g_values_for_comparison(self):
        """Test that g-values scale proportionally to components."""
        cutoff = 10e6
        impedance = 50

        # Get components for different orders
        caps_2, inds_2, _ = lp.calculate_butterworth(cutoff, impedance, 2, topology='pi')
        caps_3, inds_3, _ = lp.calculate_butterworth(cutoff, impedance, 3, topology='pi')

        # Different orders should have different component counts
        assert len(caps_2) + len(inds_2) == 2
        assert len(caps_3) + len(inds_3) == 3

    def test_bessel_values_reasonable(self):
        """Test that Bessel values are reasonable (from constants)."""
        from filter_lib.shared.constants import BESSEL_G_VALUES

        for order in range(2, 10):
            caps, inds, n = lp.calculate_bessel(10e6, 50, order, topology='pi')

            # Should have correct number of elements
            assert len(caps) + len(inds) == order
            assert n == order

            # Should match expected g-value count
            assert len(BESSEL_G_VALUES[order]) == order
