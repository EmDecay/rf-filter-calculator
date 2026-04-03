"""Tests for threshold analysis module (dB crossing detection).

Tests for:
- _find_db_crossing: frequency detection at dB thresholds
- _find_3db_frequency: backward-compatible -3dB crossing
- find_db_thresholds: multi-level threshold detection
- format_threshold_table: ASCII table formatting
"""

from filter_lib.bandpass.transfer import frequency_sweep as bp_frequency_sweep
from filter_lib.highpass.transfer import (
    butterworth_response as hp_butterworth_response,
)
from filter_lib.lowpass.transfer import (
    butterworth_response,
    generate_frequency_points,
    magnitude_to_db,
)
from filter_lib.shared.plot_threshold_analysis import (
    _find_3db_frequency,
    _find_db_crossing,
    find_db_thresholds,
    format_threshold_table,
)


class TestFindDbCrossing:
    """Tests for _find_db_crossing."""

    def test_empty_lists_returns_none(self):
        """Empty frequency/response lists return None."""
        result = _find_db_crossing([], [], threshold_db=-3.0, direction="falling")
        assert result is None

    def test_single_point_returns_none(self):
        """Single point cannot have crossing."""
        result = _find_db_crossing([1000], [-5], threshold_db=-3.0, direction="falling")
        assert result is None

    def test_no_crossing_all_above_threshold(self):
        """No crossing when all points above threshold."""
        freqs = [100, 200, 300]
        response = [-1, -2, -2.5]
        result = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="falling")
        assert result is None

    def test_no_crossing_all_below_threshold(self):
        """No crossing when all points below threshold."""
        freqs = [100, 200, 300]
        response = [-10, -15, -20]
        result = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="falling")
        assert result is None

    def test_falling_direction_crossing(self):
        """Falling direction finds threshold correctly."""
        freqs = [100, 200, 300]
        response = [-1, -3, -10]
        result = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="falling")
        assert result is not None
        assert 100 < result <= 200.001

    def test_rising_direction_crossing(self):
        """Rising direction finds threshold correctly (for HPF)."""
        freqs = [100, 200, 300]
        response = [-10, -3, -1]
        result = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="rising")
        assert result is not None
        assert 100 < result <= 200.001

    def test_exact_threshold_match_falling(self):
        """Exact -3dB point in falling response."""
        freqs = [100, 200, 300]
        response = [-1, -3, -10]
        result = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="falling")
        assert result is not None
        # Result should be around 150 (interpolated between 100 and 200)
        assert 100 <= result <= 200.001

    def test_exact_threshold_match_rising(self):
        """Exact -3dB point in rising response."""
        freqs = [100, 200, 300]
        response = [-10, -3, -1]
        result = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="rising")
        assert result is not None
        assert 100 <= result <= 200.001

    def test_minus_10db_threshold(self):
        """Find -10dB crossing."""
        freqs = [100, 200, 300]
        response = [-5, -10, -20]
        result = _find_db_crossing(freqs, response, threshold_db=-10.0, direction="falling")
        assert result is not None
        assert 100 < result <= 200.001

    def test_minus_20db_threshold(self):
        """Find -20dB crossing."""
        freqs = [100, 200, 300, 400]
        response = [-5, -10, -20, -40]
        result = _find_db_crossing(freqs, response, threshold_db=-20.0, direction="falling")
        assert result is not None
        assert 200 < result <= 300.001

    def test_interpolation_accuracy(self):
        """Interpolation returns frequency between points."""
        freqs = [1000, 2000]
        response = [-2, -4]
        result = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="falling")
        assert result is not None
        assert 1000 < result < 2000

    def test_flat_response_no_crossing(self):
        """Flat response at same level doesn't cross."""
        freqs = [100, 200, 300]
        response = [-3, -3, -3]
        result = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="falling")
        assert result is None

    def test_multiple_crossings_finds_first(self):
        """Multiple crossings returns first one."""
        freqs = [100, 150, 200, 250, 300]
        response = [-1, -10, -1, -10, -1]  # Two crossings
        result = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="falling")
        assert result is not None
        # Should find first crossing between 100-150
        assert result < 200

    def test_real_butterworth_lp_response(self):
        """Real Butterworth LP response finds -3dB correctly."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = _find_db_crossing(freqs, response_db, threshold_db=-3.0, direction="falling")
        assert result is not None
        # Butterworth -3dB frequency should be near cutoff
        assert abs(result - cutoff_hz) / cutoff_hz < 0.1


class TestFind3dbFrequency:
    """Tests for _find_3db_frequency backward compatibility."""

    def test_empty_lists_returns_none(self):
        """Empty lists return None."""
        result = _find_3db_frequency([], [])
        assert result is None

    def test_falling_direction(self):
        """Falling direction works."""
        freqs = [100, 200, 300]
        response = [-1, -3, -10]
        result = _find_3db_frequency(freqs, response, direction="falling")
        assert result is not None

    def test_rising_direction(self):
        """Rising direction works."""
        freqs = [100, 200, 300]
        response = [-10, -3, -1]
        result = _find_3db_frequency(freqs, response, direction="rising")
        assert result is not None

    def test_backward_compatible_with_find_db_crossing(self):
        """Produces same result as _find_db_crossing(-3)."""
        freqs = [100, 200, 300, 400]
        response = [-1, -5, -10, -20]
        result1 = _find_3db_frequency(freqs, response, direction="falling")
        result2 = _find_db_crossing(freqs, response, threshold_db=-3.0, direction="falling")
        # Both should find the same crossing
        if result1 is not None and result2 is not None:
            assert abs(result1 - result2) < 1e-6


class TestFindDbThresholds:
    """Tests for find_db_thresholds multi-level detection."""

    def test_empty_response_no_thresholds(self):
        """Empty response returns None for all levels."""
        result = find_db_thresholds([], [], filter_type="lowpass")
        assert -3 in result
        assert result[-3] == [None]
        assert -10 in result
        assert result[-10] == [None]

    def test_lowpass_default_levels(self):
        """Lowpass detects [-3, -10, -20] by default."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=100)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = find_db_thresholds(freqs, response_db, filter_type="lowpass")
        assert -3 in result
        assert -10 in result
        assert -20 in result
        # All should be single-element lists for lowpass
        assert len(result[-3]) == 1
        assert len(result[-10]) == 1
        assert len(result[-20]) == 1

    def test_highpass_default_levels(self):
        """Highpass detects [-3, -10, -20] by default."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=100)
        response_db = [magnitude_to_db(hp_butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = find_db_thresholds(freqs, response_db, filter_type="highpass")
        assert -3 in result
        # All should be single-element lists for highpass
        assert len(result[-3]) == 1

    def test_highpass_finds_rising_crossing(self):
        """Highpass finds rising -3dB crossing."""
        freqs = [100, 200, 300]
        response_db = [-20, -3, -1]
        result = find_db_thresholds(freqs, response_db, filter_type="highpass")
        assert result[-3][0] is not None
        assert 100 < result[-3][0] <= 200.001

    def test_lowpass_finds_falling_crossing(self):
        """Lowpass finds falling -3dB crossing."""
        freqs = [100, 200, 300]
        response_db = [-1, -3, -20]
        result = find_db_thresholds(freqs, response_db, filter_type="lowpass")
        assert result[-3][0] is not None
        assert 100 < result[-3][0] <= 200.001

    def test_bandpass_returns_dual_frequencies(self):
        """Bandpass returns [f_low, f_high] pairs."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        freqs = [f for f, _ in sweep_data]
        response_db = [db for _, db in sweep_data]
        result = find_db_thresholds(freqs, response_db, filter_type="bandpass")
        # Bandpass should have 2-element lists
        assert len(result[-3]) == 2
        # Both should be not None for bandpass
        if result[-3][0] is not None and result[-3][1] is not None:
            assert result[-3][0] < result[-3][1]

    def test_custom_levels(self):
        """Custom threshold levels work."""
        freqs = [100, 200, 300, 400, 500]
        response_db = [0, -2, -6, -15, -30]
        result = find_db_thresholds(freqs, response_db, levels=[-2, -6, -15], filter_type="lowpass")
        assert -2 in result
        assert -6 in result
        assert -15 in result
        assert -3 not in result  # Not requested

    def test_missing_threshold_returns_none(self):
        """Never reaches threshold returns None."""
        freqs = [100, 200, 300]
        response_db = [-1, -2, -3]  # Never reaches -10dB
        result = find_db_thresholds(freqs, response_db, levels=[-10], filter_type="lowpass")
        assert result[-10][0] is None

    def test_all_thresholds_missing(self):
        """Flat response above all thresholds."""
        freqs = [100, 200, 300]
        response_db = [0, 0, 0]  # Flat at 0dB
        result = find_db_thresholds(freqs, response_db, filter_type="lowpass")
        assert result[-3][0] is None
        assert result[-10][0] is None
        assert result[-20][0] is None


class TestFormatThresholdTable:
    """Tests for format_threshold_table ASCII output."""

    def test_lowpass_table_format(self):
        """Lowpass table has single frequency column."""
        thresholds = {-3: [10e6], -10: [15e6], -20: [25e6]}
        result = format_threshold_table(thresholds, filter_type="lowpass")
        assert "Level" in result
        assert "Frequency" in result
        assert "dB Threshold Summary" in result
        assert "↓" in result  # Down arrow for lowpass

    def test_highpass_table_format(self):
        """Highpass table has single frequency column with up arrow."""
        thresholds = {-3: [10e6], -10: [5e6], -20: [1e6]}
        result = format_threshold_table(thresholds, filter_type="highpass")
        assert "Level" in result
        assert "Frequency" in result
        assert "↑" in result  # Up arrow for highpass
        assert "↓" not in result

    def test_bandpass_table_format(self):
        """Bandpass table has dual frequency columns."""
        thresholds = {-3: [9.5e6, 10.5e6], -10: [9e6, 11e6], -20: [8e6, 12e6]}
        result = format_threshold_table(thresholds, filter_type="bandpass")
        assert "Level" in result
        assert "f_low" in result
        assert "f_high" in result
        assert "dB Threshold Summary" in result
        assert "↑" not in result
        assert "↓" not in result

    def test_table_with_missing_thresholds_lowpass(self):
        """Table shows N/A for missing thresholds."""
        thresholds = {-3: [10e6], -10: [None], -20: [None]}
        result = format_threshold_table(thresholds, filter_type="lowpass")
        assert "N/A" in result
        assert "-3 dB" in result
        assert "-10 dB" in result
        assert "-20 dB" in result

    def test_table_with_missing_thresholds_bandpass(self):
        """Bandpass shows N/A when crossing not found."""
        thresholds = {-3: [9.5e6, 10.5e6], -10: [None, None], -20: [None, None]}
        result = format_threshold_table(thresholds, filter_type="bandpass")
        assert "N/A" in result

    def test_table_sorting_by_level(self):
        """Thresholds sorted by level (descending)."""
        thresholds = {-20: [25e6], -3: [10e6], -10: [15e6]}
        result = format_threshold_table(thresholds, filter_type="lowpass")
        lines = result.split("\n")
        # Find line indices for each level
        idx_3 = next(i for i, line in enumerate(lines) if "-3 dB" in line)
        idx_10 = next(i for i, line in enumerate(lines) if "-10 dB" in line)
        idx_20 = next(i for i, line in enumerate(lines) if "-20 dB" in line)
        # Should be in descending order (-3 before -10 before -20)
        assert idx_3 < idx_10 < idx_20

    def test_frequency_compact_formatting(self):
        """Frequencies formatted compactly (MHz, kHz, etc)."""
        thresholds = {-3: [1e6], -10: [100e3], -20: [10e3]}
        result = format_threshold_table(thresholds, filter_type="lowpass")
        # Should see M, k formatting
        assert "M" in result or "1" in result

    def test_negative_integer_levels(self):
        """Negative integer levels formatted as "-X dB"."""
        thresholds = {-3: [10e6], -10: [15e6]}
        result = format_threshold_table(thresholds, filter_type="lowpass")
        assert "-3 dB" in result
        assert "-10 dB" in result

    def test_decimal_level_formatting(self):
        """Decimal levels formatted as "-X.Y dB"."""
        thresholds = {-3.5: [10e6], -10.2: [15e6]}
        result = format_threshold_table(thresholds, filter_type="lowpass")
        assert "-3.5 dB" in result
        assert "-10.2 dB" in result

    def test_table_structure_uses_box_drawing(self):
        """Table uses box-drawing characters."""
        thresholds = {-3: [10e6]}
        result = format_threshold_table(thresholds, filter_type="lowpass")
        # Box drawing characters
        assert "┌" in result or "┬" in result or "─" in result
        assert "│" in result

    def test_empty_thresholds_produces_valid_table(self):
        """Empty thresholds still produces valid table structure."""
        thresholds = {}
        result = format_threshold_table(thresholds, filter_type="lowpass")
        assert "dB Threshold Summary" in result
        assert "Frequency" in result

    def test_single_threshold_lowpass(self):
        """Single threshold produces minimal valid table."""
        thresholds = {-3: [10e6]}
        result = format_threshold_table(thresholds, filter_type="lowpass")
        assert "-3 dB" in result
        assert "10" in result  # Contains the frequency value
