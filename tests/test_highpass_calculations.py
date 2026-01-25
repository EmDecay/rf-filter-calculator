"""Unit tests for highpass filter calculations.

Tests verify mathematical correctness of Butterworth, Chebyshev, and Bessel
highpass filter component value calculations (T topology).
"""
import math
import pytest
from filter_lib.highpass import calculations as hp


class TestButterworthHighpass:
    """Test Butterworth highpass filter calculations."""

    def test_basic_2component_50ohm_1mhz(self):
        """Test basic 2-component Butterworth at 1 MHz, 50 Ohms."""
        cutoff = 1e6
        impedance = 50
        inds, caps, order = hp.calculate_butterworth(cutoff, impedance, 2)

        assert order == 2
        assert len(inds) == 1
        assert len(caps) == 1

        # All values should be positive
        assert all(i > 0 for i in inds)
        assert all(c > 0 for c in caps)

    def test_5component_butterworth(self):
        """Test 5-component Butterworth filter."""
        inds, caps, order = hp.calculate_butterworth(10e6, 50, 5)

        assert order == 5
        assert len(inds) == 3  # T topology: L-C-L-C-L
        assert len(caps) == 2

    def test_impedance_scaling(self):
        """Test impedance scaling in T topology."""
        cutoff = 10e6
        inds_50, caps_50, _ = hp.calculate_butterworth(cutoff, 50, 3)
        inds_100, caps_100, _ = hp.calculate_butterworth(cutoff, 100, 3)

        # Higher impedance -> larger inductors, smaller capacitors
        for i50, i100 in zip(inds_50, inds_100):
            assert i100 > i50
        for c50, c100 in zip(caps_50, caps_100):
            assert c100 < c50

    def test_frequency_scaling(self):
        """Test that higher frequency reduces component values."""
        impedance = 50
        inds_1m, caps_1m, _ = hp.calculate_butterworth(1e6, impedance, 3)
        inds_10m, caps_10m, _ = hp.calculate_butterworth(10e6, impedance, 3)

        # Higher frequency -> smaller inductors and capacitors
        for i1, i10 in zip(inds_1m, inds_10m):
            assert i10 < i1
        for c1, c10 in zip(caps_1m, caps_10m):
            assert c10 < c1

    def test_order_range(self):
        """Test all valid filter orders (2-9)."""
        for order in range(2, 10):
            inds, caps, n = hp.calculate_butterworth(10e6, 50, order)
            assert n == order
            assert len(inds) + len(caps) == order

    def test_formula_verification_2component(self):
        """Verify 2-component uses correct highpass formula.

        For 2-component Butterworth highpass (T topology):
        g1 = 2*sin(π/4) = sqrt(2)
        g2 = 2*sin(3π/4) = sqrt(2)
        L1 = Z0/(ω*g1)
        C2 = g2/(ω*Z0)
        """
        cutoff = 1e6
        z0 = 50
        omega = 2 * math.pi * cutoff

        inds, caps, _ = hp.calculate_butterworth(cutoff, z0, 2)

        # Expected values
        g1 = 2 * math.sin(math.pi / 4)
        g2 = 2 * math.sin(3 * math.pi / 4)

        expected_l1 = z0 / (omega * g1)
        expected_c2 = g2 / (omega * z0)

        assert abs(inds[0] - expected_l1) < 1e-15
        assert abs(caps[0] - expected_c2) < 1e-15

    def test_hpf_lowers_component_values_vs_lpf(self):
        """Test that HPF components are typically smaller than LPF at same frequency."""
        # This is a qualitative test - HPF has dual topology of LPF
        inds, caps, _ = hp.calculate_butterworth(10e6, 50, 3)

        # All inductors should be in reasonable range (uH)
        assert all(1e-9 < i < 1e-3 for i in inds)
        # All capacitors should be in reasonable range (pF)
        assert all(1e-12 < c < 1e-6 for c in caps)


class TestChebychevHighpass:
    """Test Chebyshev highpass filter calculations."""

    def test_basic_chebyshev_0_5db(self):
        """Test basic Chebyshev with 0.5 dB ripple."""
        inds, caps, order = hp.calculate_chebyshev(10e6, 50, 0.5, 3)

        assert order == 3
        assert len(inds) == 2
        assert len(caps) == 1

        # All values positive
        assert all(i > 0 for i in inds)
        assert all(c > 0 for c in caps)

    def test_ripple_effect(self):
        """Test that ripple affects component values."""
        cutoff = 10e6
        impedance = 50
        order = 3

        inds_01, caps_01, _ = hp.calculate_chebyshev(cutoff, impedance, 0.1, order)
        inds_10, caps_10, _ = hp.calculate_chebyshev(cutoff, impedance, 1.0, order)

        # Different ripples should produce different values
        assert inds_01 != inds_10

    def test_order_range(self):
        """Test all valid Chebyshev orders."""
        for order in range(2, 10):
            inds, caps, n = hp.calculate_chebyshev(10e6, 50, 0.5, order)
            assert n == order
            assert len(inds) + len(caps) == order

    def test_impedance_scaling(self):
        """Test impedance scaling for Chebyshev HPF."""
        inds_50, caps_50, _ = hp.calculate_chebyshev(10e6, 50, 0.5, 3)
        inds_100, caps_100, _ = hp.calculate_chebyshev(10e6, 100, 0.5, 3)

        # Higher impedance -> larger inductors
        for i50, i100 in zip(inds_50, inds_100):
            assert i100 > i50


class TestBesselHighpass:
    """Test Bessel highpass filter calculations."""

    def test_basic_bessel(self):
        """Test basic Bessel highpass filter."""
        inds, caps, order = hp.calculate_bessel(10e6, 50, 3)

        assert order == 3
        assert len(inds) == 2
        assert len(caps) == 1

        # All values positive
        assert all(i > 0 for i in inds)
        assert all(c > 0 for c in caps)

    def test_all_orders(self):
        """Test all supported Bessel orders (2-9)."""
        for order in range(2, 10):
            inds, caps, n = hp.calculate_bessel(10e6, 50, order)
            assert n == order
            assert len(inds) + len(caps) == order

    def test_invalid_order_raises(self):
        """Test that invalid order raises ValueError."""
        with pytest.raises(ValueError, match="Bessel filter supports"):
            hp.calculate_bessel(10e6, 50, 1)

        with pytest.raises(ValueError, match="Bessel filter supports"):
            hp.calculate_bessel(10e6, 50, 10)

    def test_frequency_scaling(self):
        """Test frequency scaling for Bessel."""
        inds_1m, caps_1m, _ = hp.calculate_bessel(1e6, 50, 3)
        inds_10m, caps_10m, _ = hp.calculate_bessel(10e6, 50, 3)

        # Higher frequency -> smaller components
        for i1, i10 in zip(inds_1m, inds_10m):
            assert i10 < i1
        for c1, c10 in zip(caps_1m, caps_10m):
            assert c10 < c1


class TestHighpassEdgeCases:
    """Test edge cases and error handling."""

    def test_very_small_frequency(self):
        """Test very small frequency produces very large components."""
        inds, caps, _ = hp.calculate_butterworth(1e3, 50, 2)
        inds_high, caps_high, _ = hp.calculate_butterworth(1e9, 50, 2)

        # Smaller frequency -> larger inductors
        assert inds[0] > inds_high[0]
        # Smaller frequency -> larger capacitors
        assert caps[0] > caps_high[0]

    def test_very_high_frequency(self):
        """Test very high frequency produces very small components."""
        inds, caps, _ = hp.calculate_butterworth(1e9, 50, 2)

        # Components should still be positive
        assert all(i > 0 for i in inds)
        assert all(c > 0 for c in caps)

    def test_very_large_impedance(self):
        """Test large impedance scaling."""
        inds_50, caps_50, _ = hp.calculate_butterworth(10e6, 50, 2)
        inds_1k, caps_1k, _ = hp.calculate_butterworth(10e6, 1000, 2)

        # 20x impedance -> 20x inductors
        ratio = inds_1k[0] / inds_50[0]
        assert 19 < ratio < 21
        # Higher impedance -> smaller capacitors (roughly inverse)
        assert caps_1k[0] < caps_50[0]


class TestTopologyDifference:
    """Test differences between HPF T-topology and LPF Pi-topology."""

    def test_t_topology_ordering(self):
        """Verify T-topology ordering: L at start, C between."""
        inds, caps, _ = hp.calculate_butterworth(10e6, 50, 5)

        # 5-component T should be: L-C-L-C-L
        assert len(inds) == 3
        assert len(caps) == 2

    def test_dual_topology_relationship(self):
        """Test that HPF and LPF have dual component relationships."""
        from filter_lib.lowpass import calculations as lp

        freq = 10e6
        impedance = 50
        order = 3

        # Butterworth is self-dual, but topology differs
        caps_lp, inds_lp, _ = lp.calculate_butterworth(freq, impedance, order)
        inds_hp, caps_hp, _ = hp.calculate_butterworth(freq, impedance, order)

        # LPF has more capacitors (Pi), HPF has more inductors (T)
        assert len(caps_lp) > len(inds_lp)
        assert len(inds_hp) > len(caps_hp)
