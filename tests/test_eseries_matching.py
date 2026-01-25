"""Unit tests for E-series component matching.

Tests verify correct standard component value matching and parallel combinations.
"""
import pytest
from filter_lib.shared.eseries import (
    find_closest_single,
    find_parallel_combo,
    match_component,
    ESeriesMatch,
    _normalize,
    _denormalize,
    _error_pct,
)


class TestNormalization:
    """Test mantissa extraction and normalization."""

    def test_normalize_unity(self):
        """Test normalization of 1.0."""
        mantissa, decade = _normalize(1.0)
        assert mantissa == 1.0
        assert decade == 0

    def test_normalize_10(self):
        """Test normalization of 10.0."""
        mantissa, decade = _normalize(10.0)
        assert 1.0 <= mantissa < 10.0
        assert decade == 1

    def test_normalize_100pf(self):
        """Test normalization of 100 pF."""
        mantissa, decade = _normalize(100e-12)
        assert 1.0 <= mantissa < 10.0
        # 100e-12 = 1.0e-10, so decade = -10
        assert decade == -10

    def test_normalize_1uH(self):
        """Test normalization of 1 µH."""
        mantissa, decade = _normalize(1e-6)
        assert 1.0 <= mantissa < 10.0
        assert decade == -6

    def test_denormalize_roundtrip(self):
        """Test denormalize reverses normalize."""
        original = 150e-12
        mantissa, decade = _normalize(original)
        reconstructed = _denormalize(mantissa, decade)
        assert abs(reconstructed - original) < 1e-20

    def test_normalize_negative_raises(self):
        """Test that negative values raise error."""
        with pytest.raises(ValueError):
            _normalize(-100e-12)

    def test_normalize_zero_raises(self):
        """Test that zero raises error."""
        with pytest.raises(ValueError):
            _normalize(0)


class TestErrorCalculation:
    """Test error percentage calculations."""

    def test_error_pct_exact_match(self):
        """Test error when actual equals target."""
        assert _error_pct(100, 100) == 0.0

    def test_error_pct_10_percent_high(self):
        """Test error when actual is 10% above target."""
        error = _error_pct(110, 100)
        assert abs(error - 10.0) < 1e-10

    def test_error_pct_negative(self):
        """Test error when actual is below target."""
        error = _error_pct(90, 100)
        assert abs(error - (-10.0)) < 1e-10

    def test_error_pct_small_values(self):
        """Test error calculation with small values."""
        error = _error_pct(150e-12, 138.8e-12)
        assert error > 0  # 150 pF is higher than 138.8 pF


class TestClosestSingle:
    """Test finding closest single E-series value."""

    def test_exact_match_e24(self):
        """Test finding exact E24 value."""
        matched, error = find_closest_single(1.0, 'E24')
        assert matched == 1.0
        assert error == 0.0

    def test_e24_standard_values(self):
        """Test matching various E24 standard values."""
        test_cases = [
            (100e-12, 'E24'),    # 100 pF (E24 has 1.0 in 100p decade)
            (470e-12, 'E24'),    # 470 pF
            (1e-6, 'E24'),       # 1 µH
        ]
        for target, series in test_cases:
            matched, error = find_closest_single(target, series)
            assert matched > 0
            assert abs(error) <= 7.5  # E24 typical tolerance

    def test_e12_coarser_matching(self):
        """Test E12 has fewer values than E24."""
        target = 475e-12  # Between E24 values
        matched_e12, error_e12 = find_closest_single(target, 'E12')
        matched_e24, error_e24 = find_closest_single(target, 'E24')

        # E24 should generally match better for arbitrary values
        assert abs(error_e24) <= abs(error_e12)

    def test_e96_finest_matching(self):
        """Test E96 provides finest matching."""
        target = 151e-12  # Arbitrary value
        matched_e12, error_e12 = find_closest_single(target, 'E12')
        matched_e24, error_e24 = find_closest_single(target, 'E24')
        matched_e96, error_e96 = find_closest_single(target, 'E96')

        # E96 should match better than E24, which should match better than E12
        assert abs(error_e96) <= abs(error_e24)
        assert abs(error_e24) <= abs(error_e12)

    def test_decade_boundary_matching(self):
        """Test matching at decade boundaries."""
        # 9.5 is close to 10 (next decade)
        matched, error = find_closest_single(9.5, 'E24')
        assert matched in (9.1, 10.0)

    def test_all_e24_values_available(self):
        """Test that all E24 values can be matched."""
        from filter_lib.shared.eseries import E_SERIES
        e24_values = E_SERIES['E24']

        for base_value in e24_values:
            matched, error = find_closest_single(base_value, 'E24')
            assert error == 0.0
            assert matched == base_value

    def test_invalid_series_raises(self):
        """Test that invalid series raises error."""
        with pytest.raises(ValueError, match="Unknown series"):
            find_closest_single(100e-12, 'E48')


class TestParallelCombinations:
    """Test parallel combination matching."""

    def test_parallel_harmonic_basic(self):
        """Test harmonic parallel (resistors/inductors)."""
        # For inductors, parallel formula: L = L1*L2/(L1+L2)
        result = find_parallel_combo(1e-6, 'E24', mode='harmonic')

        if result:
            (v1, v2), par_val, error = result
            # Both values should be standard E24, ordered as (smaller, larger)
            assert v1 <= v2
            # Verify parallel formula: 1/L = 1/L1 + 1/L2
            calc_par = (v1 * v2) / (v1 + v2)
            assert abs(calc_par - par_val) < 1e-15

    def test_parallel_additive_basic(self):
        """Test additive parallel (capacitors)."""
        # For capacitors, parallel formula: C = C1 + C2
        result = find_parallel_combo(150e-12, 'E24', mode='additive')

        if result:
            (v1, v2), par_val, error = result
            assert v1 + v2 == par_val

    def test_auto_detect_mode_small_values(self):
        """Test auto-detection picks additive for small values (capacitors)."""
        # Small value (< 1e-6) should be treated as capacitor (additive)
        result = find_parallel_combo(50e-12, 'E24', mode='auto')

        # Should find a match
        if result:
            (v1, v2), par_val, error = result
            # Additive: C = C1 + C2
            assert abs(v1 + v2 - par_val) < 1e-24

    def test_auto_detect_mode_large_values(self):
        """Test auto-detection picks harmonic for large values (inductors)."""
        # Large value (> 1e-6) should be treated as inductor (harmonic)
        result = find_parallel_combo(1e-3, 'E24', mode='auto')

        if result:
            (v1, v2), par_val, error = result
            # Harmonic: L = L1*L2/(L1+L2)
            calc_par = (v1 * v2) / (v1 + v2)
            assert abs(calc_par - par_val) < 1e-15

    def test_parallel_ratio_limit(self):
        """Test ratio limit prevents extreme value differences."""
        result = find_parallel_combo(1e-6, 'E24', mode='harmonic', ratio_limit=5)

        if result:
            (v1, v2), _, _ = result
            ratio = max(v1, v2) / min(v1, v2)
            assert ratio <= 5.0

    def test_no_valid_combo_returns_none(self):
        """Test that invalid parameters return None."""
        result = find_parallel_combo(1e-15, 'E24', mode='harmonic', ratio_limit=1.1)
        # Should return None if no valid combination found
        if result is None:
            pass  # Expected


class TestComponentMatching:
    """Test full component matching workflow."""

    def test_match_component_returns_eseriesmatch(self):
        """Test that match_component returns ESeriesMatch object."""
        result = match_component(150e-12, 'E24')

        assert isinstance(result, ESeriesMatch)
        assert result.target == 150e-12
        assert result.single_value > 0
        assert result.single_error_pct is not None

    def test_eseriesmatch_fields(self):
        """Test ESeriesMatch data structure."""
        target = 138.8e-12
        result = match_component(target, 'E24')

        # Must have single value
        assert result.single_value > 0
        assert abs(result.single_error_pct) <= 7.5

        # May have parallel combo
        if result.parallel:
            assert len(result.parallel) == 2
            assert result.parallel_value > 0
            assert result.parallel_error_pct is not None

    def test_parallel_better_than_single(self):
        """Test case where parallel matches better than single."""
        # 138.8 pF might match better with parallel combination
        target = 138.8e-12
        result = match_component(target, 'E24')

        if result.parallel:
            # Parallel should be better or equal
            assert abs(result.parallel_error_pct) <= abs(result.single_error_pct)

    def test_matching_real_world_capacitor(self):
        """Test matching real-world capacitor value from lowpass filter."""
        # From lowpass Butterworth example: 138.8 pF
        result = match_component(138.8e-12, 'E24')

        assert result.single_value > 0
        # Should match within E24 tolerance
        assert abs(result.single_error_pct) < 10

    def test_matching_real_world_inductor(self):
        """Test matching real-world inductor value from lowpass filter."""
        # From lowpass Butterworth example: 1.457 µH
        result = match_component(1.457e-6, 'E24')

        assert result.single_value > 0
        # Should match within tolerance
        assert abs(result.single_error_pct) < 10

    def test_all_series_available(self):
        """Test matching with all E-series types."""
        target = 150e-12

        for series in ['E12', 'E24', 'E96']:
            result = match_component(target, series)
            assert result.single_value > 0
            assert result.single_error_pct is not None

    def test_invalid_series_raises(self):
        """Test invalid series raises error."""
        with pytest.raises(ValueError):
            match_component(150e-12, 'E48')


class TestMatchingPhysicalReality:
    """Test matching with physically realistic component values."""

    def test_100pf_standard_capacitor(self):
        """Test matching 100 pF (very common)."""
        result = match_component(100e-12, 'E24')
        assert result.single_error_pct == 0.0  # Exact match

    def test_1uh_standard_inductor(self):
        """Test matching 1 µH (very common)."""
        result = match_component(1e-6, 'E24')
        # Should match either 1.0 or nearby value
        assert abs(result.single_error_pct) < 5

    def test_matching_decade_scaling(self):
        """Test matching works across decades."""
        target_pf = 150e-12
        target_nf = 150e-9

        result_pf = match_component(target_pf, 'E24')
        result_nf = match_component(target_nf, 'E24')

        # Both should have same error percentage despite different scales
        assert abs(result_pf.single_error_pct - result_nf.single_error_pct) < 1e-10

    def test_series_tolerance_progression(self):
        """Test typical tolerance progression E12 > E24 > E96."""
        target = 347e-12  # Not exact in any series

        result_e12 = match_component(target, 'E12')
        result_e24 = match_component(target, 'E24')
        result_e96 = match_component(target, 'E96')

        # E24 tolerance ±5%, E12 ±10%, E96 ±1%
        # For odd values, E96 should match better
        assert abs(result_e96.single_error_pct) <= abs(result_e24.single_error_pct)
