"""Edge case tests for plotting and display modules.

Tests extreme values, boundary conditions, and error handling for:
- ASCII plotting functions
- Display formatters (JSON, CSV, quiet)
- Component formatting functions
- E-series matching display
"""

import json

import pytest

from filter_lib.shared.display_common import (
    format_csv_result,
    format_json_result,
    format_quiet_result,
)
from filter_lib.shared.display_helpers import format_component_value, format_eseries_match
from filter_lib.shared.formatting import format_capacitance, format_frequency, format_inductance
from filter_lib.shared.plotting import (
    _find_3db_frequency,
    _format_freq_compact,
    export_csv,
    export_json,
    render_ascii_plot,
    render_bandpass_plot,
)


class TestFormatFreqCompact:
    """Tests for _format_freq_compact helper."""

    def test_extreme_low_frequency(self):
        """Format 1 Hz correctly."""
        result = _format_freq_compact(1.0)
        assert result == "1"

    def test_extreme_high_frequency(self):
        """Format 10 GHz correctly."""
        result = _format_freq_compact(10e9)
        assert "G" in result
        assert "10" in result

    def test_sub_hz_frequency(self):
        """Format fractional Hz."""
        result = _format_freq_compact(0.5)
        assert result == "0.5"

    def test_kilohertz_boundary(self):
        """Format exactly 1 kHz."""
        result = _format_freq_compact(1000.0)
        assert "k" in result.lower()

    def test_megahertz_boundary(self):
        """Format exactly 1 MHz."""
        result = _format_freq_compact(1e6)
        assert "M" in result

    def test_gigahertz_boundary(self):
        """Format exactly 1 GHz."""
        result = _format_freq_compact(1e9)
        assert "G" in result

    def test_very_small_frequency(self):
        """Format millihertz."""
        result = _format_freq_compact(0.001)
        assert result == "0.001"


class TestFind3dbFrequency:
    """Tests for _find_3db_frequency helper."""

    def test_empty_lists(self):
        """Empty lists return None."""
        result = _find_3db_frequency([], [], "falling")
        assert result is None

    def test_single_point(self):
        """Single point returns None (no crossing)."""
        result = _find_3db_frequency([1000], [-5], "falling")
        assert result is None

    def test_no_crossing_all_above(self):
        """No crossing when all points above -3dB."""
        freqs = [100, 200, 300]
        response = [-1, -2, -2.5]
        result = _find_3db_frequency(freqs, response, "falling")
        assert result is None

    def test_no_crossing_all_below(self):
        """No crossing when all points below -3dB."""
        freqs = [100, 200, 300]
        response = [-10, -15, -20]
        result = _find_3db_frequency(freqs, response, "falling")
        assert result is None

    def test_exact_crossing_falling(self):
        """Exact -3dB point in falling response."""
        freqs = [100, 200, 300]
        response = [-1, -3, -10]
        result = _find_3db_frequency(freqs, response, "falling")
        assert result is not None
        # Allow floating point tolerance
        assert 100 < result <= 200.001

    def test_exact_crossing_rising(self):
        """Exact -3dB point in rising response (highpass)."""
        freqs = [100, 200, 300]
        response = [-10, -3, -1]
        result = _find_3db_frequency(freqs, response, "rising")
        assert result is not None
        # Allow floating point tolerance
        assert 100 < result <= 200.001

    def test_interpolation_accuracy(self):
        """Interpolation returns reasonable value."""
        freqs = [1000, 2000]
        response = [-2, -4]
        result = _find_3db_frequency(freqs, response, "falling")
        assert result is not None
        assert 1000 < result < 2000

    def test_flat_response_at_crossing(self):
        """Flat response at -3dB returns first point or None."""
        freqs = [100, 200, 300]
        response = [-1, -3, -3]
        result = _find_3db_frequency(freqs, response, "falling")
        # Flat response means no crossing through -3dB, so None is acceptable
        # (response never goes below -3dB, just equals it)
        # This is an edge case - implementation returns None which is reasonable
        assert result is None or (result is not None and 100 <= result <= 200)


class TestRenderAsciiPlotEdgeCases:
    """Edge case tests for render_ascii_plot."""

    def test_empty_data(self):
        """Empty lists return error message."""
        result = render_ascii_plot([], [], 1000, title="Empty")
        assert "No data" in result

    def test_single_frequency_point(self):
        """Single point doesn't crash."""
        freqs = [1000]
        response = [-3]
        result = render_ascii_plot(freqs, response, 1000)
        assert "Frequency Response" in result

    def test_mismatched_lengths(self):
        """Mismatched freq/response raises error."""
        with pytest.raises(ValueError, match="same length"):
            render_ascii_plot([100, 200], [-3], 150)

    def test_extreme_low_frequency_1hz(self):
        """1 Hz frequency doesn't crash."""
        freqs = [1, 10, 100]
        response = [-3, -10, -20]
        result = render_ascii_plot(freqs, response, 10)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_extreme_high_frequency_10ghz(self):
        """10 GHz frequency doesn't crash."""
        freqs = [1e9, 5e9, 10e9]
        response = [-3, -10, -20]
        result = render_ascii_plot(freqs, response, 5e9)
        assert isinstance(result, str)
        assert "G" in result  # GHz label

    def test_very_narrow_bandwidth(self):
        """Very narrow frequency span."""
        f0 = 1e6
        freqs = [f0 * 0.9999, f0, f0 * 1.0001]
        response = [-10, -3, -10]
        result = render_ascii_plot(freqs, response, f0)
        assert isinstance(result, str)

    def test_very_wide_bandwidth(self):
        """Very wide frequency span (1 Hz to 10 GHz)."""
        freqs = [1, 1e3, 1e6, 1e9, 10e9]
        response = [-3, -3, -3, -10, -20]
        result = render_ascii_plot(freqs, response, 1e6)
        assert isinstance(result, str)

    def test_response_at_minus_100db_floor(self):
        """Response at -100 dB floor."""
        freqs = [100, 1000, 10000]
        response = [-3, -50, -100]
        result = render_ascii_plot(freqs, response, 1000)
        assert isinstance(result, str)
        assert "-100" not in result  # Should be clamped to -60 + margin

    def test_all_zero_db_response(self):
        """All points at 0 dB."""
        freqs = [100, 1000, 10000]
        response = [0, 0, 0]
        result = render_ascii_plot(freqs, response, 1000)
        assert isinstance(result, str)

    def test_minimum_plot_dimensions(self):
        """Minimum width/height enforced."""
        freqs = [100, 1000, 10000]
        response = [-3, -10, -20]
        result = render_ascii_plot(freqs, response, 1000, width=10, height=3)
        assert isinstance(result, str)
        # Should enforce minimum dimensions

    def test_large_plot_dimensions(self):
        """Large plot dimensions don't crash."""
        freqs = [100, 1000, 10000]
        response = [-3, -10, -20]
        result = render_ascii_plot(freqs, response, 1000, width=120, height=30)
        assert isinstance(result, str)

    def test_highpass_filter_type(self):
        """Highpass filter type works correctly."""
        freqs = [100, 1000, 10000]
        response = [-20, -3, -1]
        result = render_ascii_plot(freqs, response, 1000, filter_type="highpass")
        assert isinstance(result, str)

    def test_bandpass_filter_type(self):
        """Bandpass filter type works correctly."""
        freqs = [100, 1000, 10000]
        response = [-20, -3, -20]
        result = render_ascii_plot(freqs, response, 1000, filter_type="bandpass")
        assert isinstance(result, str)

    def test_zero_frequency_in_list(self):
        """Zero frequency causes error (log10 undefined)."""
        freqs = [0, 100, 1000]
        response = [-50, -3, -10]
        # Zero frequency causes log10 error - this is expected behavior
        # The function should receive pre-filtered valid data
        with pytest.raises(ValueError):
            render_ascii_plot(freqs, response, 100)

    def test_negative_frequency(self):
        """Negative frequencies cause error (log10 undefined)."""
        freqs = [-100, 100, 1000]
        response = [-50, -3, -10]
        # Negative frequency causes log10 error - this is expected behavior
        # The function should receive pre-filtered valid data
        with pytest.raises(ValueError):
            render_ascii_plot(freqs, response, 100)


class TestRenderBandpassPlotEdgeCases:
    """Edge case tests for render_bandpass_plot."""

    def test_empty_sweep_data(self):
        """Empty sweep data returns error message."""
        result = render_bandpass_plot([], 1e6, 100e3)
        assert "No data" in result

    def test_single_point_bandpass(self):
        """Single point doesn't crash."""
        sweep_data = [(1e6, -3)]
        result = render_bandpass_plot(sweep_data, 1e6, 100e3)
        assert isinstance(result, str)

    def test_extreme_narrow_bandwidth(self):
        """Very narrow bandwidth (1 Hz)."""
        f0 = 1e6
        sweep_data = [(f0 - 0.5, -10), (f0, -3), (f0 + 0.5, -10)]
        result = render_bandpass_plot(sweep_data, f0, 1)
        assert isinstance(result, str)

    def test_extreme_wide_bandwidth(self):
        """Very wide bandwidth."""
        f0 = 1e6
        bw = 900e3  # 90% fractional bandwidth
        sweep_data = [(f0 - bw, -20), (f0, -3), (f0 + bw, -20)]
        result = render_bandpass_plot(sweep_data, f0, bw)
        assert isinstance(result, str)

    def test_zero_center_frequency(self):
        """Zero center frequency doesn't crash."""
        sweep_data = [(100, -10), (200, -3), (300, -10)]
        result = render_bandpass_plot(sweep_data, 0, 100)
        assert isinstance(result, str)

    def test_negative_frequency_in_sweep(self):
        """Negative frequency in sweep is skipped."""
        sweep_data = [(-100, -50), (100, -3), (200, -10)]
        result = render_bandpass_plot(sweep_data, 100, 50)
        assert isinstance(result, str)

    def test_all_points_at_floor(self):
        """All points at -60 dB floor."""
        sweep_data = [(100, -60), (200, -60), (300, -60)]
        result = render_bandpass_plot(sweep_data, 200, 100)
        assert isinstance(result, str)

    def test_large_plot_dimensions_bandpass(self):
        """Large bandpass plot dimensions."""
        sweep_data = [(1e6, -20), (1.5e6, -3), (2e6, -20)]
        result = render_bandpass_plot(sweep_data, 1.5e6, 500e3, width=100, height=20)
        assert isinstance(result, str)


class TestExportJsonEdgeCases:
    """Edge case tests for export_json."""

    def test_empty_sweep_data(self):
        """Empty sweep data produces valid JSON."""
        result = export_json([], 1e6, 100e3, "butterworth", 3)
        data = json.loads(result)
        assert data["data"] == []

    def test_single_point_json(self):
        """Single point exports correctly."""
        sweep_data = [(1e6, -3.0)]
        result = export_json(sweep_data, 1e6, 100e3, "butterworth", 3)
        data = json.loads(result)
        assert len(data["data"]) == 1
        assert data["data"][0]["frequency_hz"] == 1e6

    def test_extreme_frequencies_in_json(self):
        """Extreme frequencies export correctly."""
        sweep_data = [(1, -50), (10e9, -50)]
        result = export_json(sweep_data, 1e6, 100e3, "butterworth", 3)
        data = json.loads(result)
        assert data["data"][0]["frequency_hz"] == 1
        assert data["data"][1]["frequency_hz"] == 10e9

    def test_extreme_db_values(self):
        """Extreme dB values export correctly."""
        sweep_data = [(1e6, 0), (2e6, -150.5)]
        result = export_json(sweep_data, 1e6, 100e3, "butterworth", 3)
        data = json.loads(result)
        assert data["data"][0]["magnitude_db"] == 0
        assert data["data"][1]["magnitude_db"] == -150.5

    def test_ripple_none_not_in_output(self):
        """None ripple not included in JSON."""
        result = export_json([], 1e6, 100e3, "butterworth", 3, ripple_db=None)
        data = json.loads(result)
        assert "ripple_db" not in data

    def test_ripple_value_in_output(self):
        """Non-None ripple included in JSON."""
        result = export_json([], 1e6, 100e3, "chebyshev", 3, ripple_db=0.5)
        data = json.loads(result)
        assert data["ripple_db"] == 0.5

    def test_rounding_precision(self):
        """dB values rounded to 2 decimals."""
        sweep_data = [(1e6, -3.14159265)]
        result = export_json(sweep_data, 1e6, 100e3, "butterworth", 3)
        data = json.loads(result)
        assert data["data"][0]["magnitude_db"] == -3.14


class TestExportCsvEdgeCases:
    """Edge case tests for export_csv."""

    def test_empty_sweep_csv(self):
        """Empty sweep produces header only."""
        result = export_csv([])
        lines = result.strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "frequency_hz,magnitude_db"

    def test_single_point_csv(self):
        """Single point exports correctly."""
        result = export_csv([(1e6, -3.0)])
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert "1000000" in lines[1]

    def test_extreme_values_csv(self):
        """Extreme values format correctly."""
        sweep_data = [(1, -100), (10e9, 0)]
        result = export_csv(sweep_data)
        lines = result.strip().split("\n")
        assert "1," in lines[1]
        assert "10000000000" in lines[2]

    def test_csv_decimal_precision(self):
        """dB values have 2 decimal places."""
        result = export_csv([(1e6, -3.14159)])
        lines = result.strip().split("\n")
        assert "-3.14" in lines[1]


class TestFormatJsonResultEdgeCases:
    """Edge case tests for format_json_result."""

    def test_empty_component_lists(self):
        """Empty component lists produce valid JSON."""
        result_dict = {
            "filter_type": "butterworth",
            "freq_hz": 1e6,
            "impedance": 50.0,
            "order": 0,
            "capacitors": [],
            "inductors": [],
            "ripple": None,
        }
        output = format_json_result(result_dict)
        data = json.loads(output)
        assert data["components"]["capacitors"] == []
        assert data["components"]["inductors"] == []

    def test_single_component(self):
        """Single component in each list."""
        result_dict = {
            "filter_type": "butterworth",
            "freq_hz": 1e6,
            "impedance": 50.0,
            "order": 1,
            "capacitors": [1e-12],
            "inductors": [1e-9],
            "ripple": None,
        }
        output = format_json_result(result_dict)
        data = json.loads(output)
        assert len(data["components"]["capacitors"]) == 1
        assert len(data["components"]["inductors"]) == 1

    def test_extreme_component_values(self):
        """Extreme component values preserved."""
        result_dict = {
            "filter_type": "butterworth",
            "freq_hz": 1e6,
            "impedance": 50.0,
            "order": 2,
            "capacitors": [1e-15, 1e-3],  # femtofarad to millifarad
            "inductors": [1e-12, 1],  # picohenry to henry
            "ripple": None,
        }
        output = format_json_result(result_dict)
        data = json.loads(output)
        assert data["components"]["capacitors"][0]["value_farads"] == 1e-15
        assert data["components"]["capacitors"][1]["value_farads"] == 1e-3
        assert data["components"]["inductors"][0]["value_henries"] == 1e-12
        assert data["components"]["inductors"][1]["value_henries"] == 1


class TestFormatCsvResultEdgeCases:
    """Edge case tests for format_csv_result."""

    def test_empty_components_csv(self):
        """Empty component lists produce header only."""
        result_dict = {"capacitors": [], "inductors": []}
        output = format_csv_result(result_dict)
        lines = output.strip().split("\n")
        assert lines[0] == "Component,Value,Unit"
        assert len(lines) == 1

    def test_extreme_capacitance_values(self):
        """Extreme capacitance formats correctly."""
        result_dict = {
            "capacitors": [1e-15, 1e-3],  # 1 fF, 1 mF
            "inductors": [],
        }
        output = format_csv_result(result_dict)
        lines = output.strip().split("\n")
        assert "C1" in lines[1]
        assert "C2" in lines[2]

    def test_extreme_inductance_values(self):
        """Extreme inductance formats correctly."""
        result_dict = {
            "capacitors": [],
            "inductors": [1e-12, 1.0],  # 1 pH, 1 H
        }
        output = format_csv_result(result_dict)
        lines = output.strip().split("\n")
        assert "L1" in lines[1]
        assert "L2" in lines[2]


class TestFormatQuietResultEdgeCases:
    """Edge case tests for format_quiet_result."""

    def test_empty_components_quiet(self):
        """Empty components produce empty output."""
        result_dict = {"capacitors": [], "inductors": []}
        output = format_quiet_result(result_dict)
        assert output == ""

    def test_raw_mode_extreme_values(self):
        """Raw mode shows scientific notation for extreme values."""
        result_dict = {"capacitors": [1e-15], "inductors": [1.0]}
        output = format_quiet_result(result_dict, raw=True)
        assert "e" in output.lower() or "E" in output

    def test_formatted_mode_extreme_values(self):
        """Formatted mode uses engineering notation."""
        result_dict = {"capacitors": [1e-12], "inductors": [1e-6]}
        output = format_quiet_result(result_dict, raw=False)
        # Should contain unit suffixes like pF, µH, etc.
        assert any(unit in output for unit in ["pF", "nF", "µF", "nH", "µH", "mH"])


class TestFormatComponentValueEdgeCases:
    """Edge case tests for format_component_value."""

    def test_zero_value_formatted(self):
        """Zero value formats without crashing."""
        result = format_component_value("C1", 0, format_capacitance, raw=False)
        assert "C1" in result

    def test_zero_value_raw(self):
        """Zero value in raw mode."""
        result = format_component_value("C1", 0, format_capacitance, raw=True)
        assert "C1" in result
        assert "e" in result.lower() or "0.000000e+00" in result

    def test_very_small_value(self):
        """Very small value (femtofarad)."""
        result = format_component_value("C1", 1e-15, format_capacitance, raw=False)
        assert "C1" in result

    def test_very_large_value(self):
        """Very large value (farads)."""
        result = format_component_value("C1", 1.0, format_capacitance, raw=False)
        assert "C1" in result


class TestFormattingFunctionsEdgeCases:
    """Edge case tests for formatting.py functions."""

    def test_format_capacitance_zero(self):
        """Zero capacitance."""
        result = format_capacitance(0)
        assert "pF" in result  # Should use smallest unit

    def test_format_capacitance_femtofarad(self):
        """Femtofarad range."""
        result = format_capacitance(1e-15)
        assert "pF" in result

    def test_format_capacitance_millifarad(self):
        """Millifarad range."""
        result = format_capacitance(1e-3)
        assert "mF" in result

    def test_format_inductance_zero(self):
        """Zero inductance."""
        result = format_inductance(0)
        assert "nH" in result  # Should use smallest unit

    def test_format_inductance_picohenry(self):
        """Picohenry range."""
        result = format_inductance(1e-12)
        assert "nH" in result

    def test_format_inductance_henry(self):
        """Henry range."""
        result = format_inductance(1.0)
        assert "H" in result

    def test_format_frequency_zero(self):
        """Zero frequency."""
        result = format_frequency(0)
        assert "Hz" in result

    def test_format_frequency_subhertz(self):
        """Sub-hertz frequency."""
        result = format_frequency(0.1)
        assert "Hz" in result

    def test_format_frequency_terahertz(self):
        """Terahertz range."""
        result = format_frequency(1e12)
        assert "GHz" in result  # Should use GHz as highest unit

    def test_negative_capacitance(self):
        """Negative capacitance (physically invalid but should not crash)."""
        result = format_capacitance(-1e-12)
        assert "-" in result or "pF" in result

    def test_negative_inductance(self):
        """Negative inductance (physically invalid but should not crash)."""
        result = format_inductance(-1e-6)
        assert "-" in result or "µH" in result


class TestFormatEseriesMatchEdgeCases:
    """Edge case tests for format_eseries_match."""

    def test_zero_value_eseries(self):
        """Zero value E-series matching."""
        # This might not be physically meaningful but should not crash
        try:
            result = format_eseries_match(0, "E12", format_capacitance, parallel_mode="additive")
            assert isinstance(result, list)
        except (ValueError, ZeroDivisionError):
            # Acceptable to raise error for zero
            pass

    def test_very_small_value_eseries(self):
        """Very small value E-series matching."""
        result = format_eseries_match(1e-15, "E12", format_capacitance, parallel_mode="additive")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_very_large_value_eseries(self):
        """Very large value E-series matching."""
        result = format_eseries_match(1.0, "E12", format_capacitance, parallel_mode="additive")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_exact_match_zero_error(self):
        """Exact E-series match (0% error)."""
        # 100 pF is in E12 series
        result = format_eseries_match(100e-12, "E12", format_capacitance, parallel_mode="additive")
        assert isinstance(result, list)
        # Should show match info

    def test_parallel_mode_additive(self):
        """Parallel mode additive."""
        result = format_eseries_match(150e-12, "E12", format_capacitance, parallel_mode="additive")
        assert isinstance(result, list)

    def test_parallel_mode_harmonic(self):
        """Parallel mode harmonic (for inductors)."""
        result = format_eseries_match(150e-9, "E12", format_inductance, parallel_mode="harmonic")
        assert isinstance(result, list)

    def test_parallel_display_keeps_units_on_both_values(self):
        """A decade-spanning pair must show units on each value, not just the second."""
        # 2.9 nF in E12 matches best as 680 pF || 2.2 nF — a bare "680.00"
        # would be misread as nF
        result = format_eseries_match(2.9e-9, "E12", format_capacitance, parallel_mode="additive")
        parallel_lines = [ln for ln in result if "||" in ln]
        assert parallel_lines, "expected a parallel match line"
        left, right = parallel_lines[0].split("||")
        assert "pF" in left
        assert "nF" in right
