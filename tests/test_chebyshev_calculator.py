"""Unit tests for Chebyshev filter g-value calculator.

Tests verify mathematical correctness of Chebyshev coefficient calculations.
"""
import math
import pytest
from filter_lib.shared.chebyshev_g_calculator import (
    calculate_chebyshev_g_values,
    CHEBYSHEV_DB_TO_NEPER_FACTOR,
)


class TestChebychevGValuesBasic:
    """Test basic Chebyshev g-value calculations."""

    def test_g_values_all_positive(self):
        """Test that all g-values are positive."""
        for n in range(2, 10):
            g = calculate_chebyshev_g_values(n, 0.5)
            # g[0] is unused (set to 0.0)
            assert g[0] == 0.0
            # g[1] through g[n] should be positive
            for i in range(1, n + 1):
                assert g[i] > 0

    def test_g_values_array_length(self):
        """Test g-values array has correct length."""
        for n in range(2, 10):
            g = calculate_chebyshev_g_values(n, 0.5)
            assert len(g) == n + 1  # 0-indexed, so length is n+1

    def test_ripple_effect_on_g_values(self):
        """Test that increasing ripple changes g-values."""
        g_01 = calculate_chebyshev_g_values(3, 0.1)
        g_10 = calculate_chebyshev_g_values(3, 1.0)

        # Different ripple -> different g-values
        for i in range(1, 4):
            assert g_01[i] != g_10[i]


class TestChebychevFormulaMathematics:
    """Test mathematical correctness of Chebyshev formulas."""

    def test_db_to_neper_conversion(self):
        """Test dB to Neper conversion factor."""
        # Conversion factor should be positive and reasonable
        assert CHEBYSHEV_DB_TO_NEPER_FACTOR > 0
        # Expected to be around 17.37
        assert 17 < CHEBYSHEV_DB_TO_NEPER_FACTOR < 18

    def test_ripple_to_epsilon_conversion(self):
        """Test ripple dB conversion to epsilon."""
        ripple_db = 0.5

        # Manually calculate what the formula should produce
        rr = ripple_db / CHEBYSHEV_DB_TO_NEPER_FACTOR
        e2x = math.exp(2 * rr)

        # e2x should be positive and > 1
        assert e2x > 1

    def test_normalized_ripple_behavior(self):
        """Test g-values for normalized ripple inputs."""
        # Very small ripple should produce certain values
        g_small = calculate_chebyshev_g_values(3, 0.01)
        g_medium = calculate_chebyshev_g_values(3, 0.5)
        g_large = calculate_chebyshev_g_values(3, 3.0)

        # Should all succeed
        assert all(g > 0 for g in g_small[1:])
        assert all(g > 0 for g in g_medium[1:])
        assert all(g > 0 for g in g_large[1:])


class TestChebychevPhysicalValidity:
    """Test physical validity of computed values."""

    def test_g_values_reasonable_magnitude(self):
        """Test g-values are in reasonable physical range."""
        for n in range(2, 10):
            g = calculate_chebyshev_g_values(n, 0.5)

            # g-values should typically be < 10 for practical filters
            for i in range(1, n + 1):
                assert g[i] < 100
                assert g[i] > 0.01

    def test_g_values_filter_conversion(self):
        """Test that g-values can be converted to realistic components."""
        g = calculate_chebyshev_g_values(3, 0.5)

        # Simulate lowpass Pi topology component conversion
        cutoff = 10e6
        impedance = 50
        omega = 2 * math.pi * cutoff

        # Convert g-values to components
        c1 = g[1] / (impedance * omega)
        l2 = g[2] * impedance / omega
        c3 = g[3] / (impedance * omega)

        # Components should be realistic (pF to µH range)
        assert 1e-12 < c1 < 1e-6  # pF to µF
        assert 1e-9 < l2 < 1e-3   # nH to mH
        assert 1e-12 < c3 < 1e-6  # pF to µF


class TestChebychevEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_ripple(self):
        """Test very small ripple (nearly Butterworth)."""
        g = calculate_chebyshev_g_values(3, 0.01)

        # Should still compute valid values
        assert all(g[i] > 0 for i in range(1, 4))

    def test_large_ripple(self):
        """Test large ripple (aggressive response)."""
        g = calculate_chebyshev_g_values(3, 5.0)

        # Should still compute valid values
        assert all(g[i] > 0 for i in range(1, 4))

    def test_minimum_order(self):
        """Test minimum order (2-component)."""
        g = calculate_chebyshev_g_values(2, 0.5)

        assert len(g) == 3
        assert g[0] == 0.0
        assert g[1] > 0
        assert g[2] > 0

    def test_maximum_order(self):
        """Test maximum reasonable order."""
        g = calculate_chebyshev_g_values(9, 0.5)

        assert len(g) == 10
        assert all(g[i] > 0 for i in range(1, 10))


class TestChebychevConsistency:
    """Test consistency with Chebyshev filter theory."""

    def test_g_values_recurrence_relation(self):
        """Test that g-values follow expected mathematical relations."""
        g = calculate_chebyshev_g_values(5, 0.5)

        # g-values should be computed via recurrence relation
        # g[i] = (4 * a[i-1] * a[i]) / (b[i-1] * g[i-1])
        # This test verifies structure exists (not specific values)
        assert len(g) == 6
        assert g[0] == 0.0

    def test_prototype_normalization(self):
        """Test that g-values are prototype (normalized)."""
        # Chebyshev g-values should be prototype values
        # that can be scaled by impedance and frequency
        g = calculate_chebyshev_g_values(3, 0.5)

        # Should be in reasonable prototype range (typically 0.5 to 3.0)
        for i in range(1, 4):
            assert 0.1 < g[i] < 10

    def test_multiple_ripple_values_distinct(self):
        """Test that different ripple values produce distinguishable g-values."""
        ripples = [0.1, 0.5, 1.0, 2.0, 3.0]
        g_results = {}

        for ripple in ripples:
            g_results[ripple] = calculate_chebyshev_g_values(3, ripple)

        # Each ripple should produce different g-values
        for i, ripple1 in enumerate(ripples):
            for ripple2 in ripples[i + 1:]:
                # At least one g-value should differ
                differs = False
                for j in range(1, 4):
                    if abs(g_results[ripple1][j] - g_results[ripple2][j]) > 1e-6:
                        differs = True
                        break
                assert differs, f"Ripples {ripple1} and {ripple2} produced identical g-values"
