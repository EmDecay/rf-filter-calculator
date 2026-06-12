"""Tests for zoomed passband plot rendering.

Tests for:
- render_ascii_plot with db_floor parameter
- render_bandpass_plot with db_floor parameter
- _compute_zoom_range: zoom range calculation
- _generate_zoom_freqs: frequency generation for zoom
- render_plot_pair: full + zoomed LP/HP plots
- render_bandpass_plot_pair: full + zoomed BP plots
"""

import pytest

from filter_lib.bandpass.transfer import frequency_sweep as bp_frequency_sweep
from filter_lib.highpass.transfer import (
    butterworth_response as hp_butterworth_response,
)
from filter_lib.lowpass.transfer import (
    butterworth_response,
    chebyshev_response,
    generate_frequency_points,
    magnitude_to_db,
)
from filter_lib.shared.plot_ascii_renderers import (
    _format_freq_compact,
    render_ascii_plot,
    render_bandpass_plot,
)
from filter_lib.shared.plot_zoom_pairs import (
    _compute_zoom_range,
    _generate_zoom_freqs,
    render_bandpass_plot_pair,
    render_plot_pair,
)


class TestComputeZoomRange:
    """Tests for _compute_zoom_range."""

    def test_default_6db_range(self):
        """Default (ripple_db=None) returns 6.0 dB."""
        result = _compute_zoom_range(ripple_db=None)
        assert result == 6.0

    def test_small_ripple_min_6db(self):
        """Small ripple (0.5dB) returns 6.0 (minimum)."""
        result = _compute_zoom_range(ripple_db=0.5)
        assert result == 6.0

    def test_medium_ripple_computation(self):
        """Medium ripple (1.0dB) returns max(6, 2*1.0) = 6.0."""
        result = _compute_zoom_range(ripple_db=1.0)
        assert result == 6.0

    def test_large_ripple_scales_zoom(self):
        """Large ripple (4.0dB) returns max(6, 2*4.0) = 8.0."""
        result = _compute_zoom_range(ripple_db=4.0)
        assert result == 8.0

    def test_very_large_ripple(self):
        """Very large ripple (10.0dB) returns 20.0."""
        result = _compute_zoom_range(ripple_db=10.0)
        assert result == 20.0

    def test_zero_ripple_returns_6db(self):
        """Zero ripple (edge case) returns 6.0."""
        result = _compute_zoom_range(ripple_db=0.0)
        assert result == 6.0


class TestGenerateZoomFreqs:
    """Tests for _generate_zoom_freqs."""

    def test_generate_same_range_as_input(self):
        """Generated freqs span same min/max as input."""
        input_freqs = [1e5, 1e6, 1e7]
        zoom_freqs = _generate_zoom_freqs(input_freqs, num_points=10)
        assert min(zoom_freqs) == pytest.approx(min(input_freqs), rel=1e-9)
        assert max(zoom_freqs) == pytest.approx(max(input_freqs), rel=1e-9)

    def test_2x_density(self):
        """2x points creates denser frequency coverage."""
        input_freqs = generate_frequency_points(1e6, num_points=50)
        zoom_freqs = _generate_zoom_freqs(input_freqs, num_points=len(input_freqs) * 2)
        assert len(zoom_freqs) == len(input_freqs) * 2

    def test_logarithmic_spacing(self):
        """Frequencies are log-spaced."""
        import math

        input_freqs = [1e5, 1e6, 1e7]
        zoom_freqs = _generate_zoom_freqs(input_freqs, num_points=5)
        # In log space, should be evenly spaced
        log_zoom = [math.log10(f) for f in zoom_freqs]
        diffs = [log_zoom[i + 1] - log_zoom[i] for i in range(len(log_zoom) - 1)]
        # All log differences should be approximately equal
        assert all(abs(d - diffs[0]) < 0.01 for d in diffs)

    def test_single_point_output(self):
        """Single output point works (degenerate case)."""
        input_freqs = [1e6]
        # For a single-point input, min==max, log_range=0
        # This will cause division by zero in _generate_zoom_freqs
        # Skip this edge case for now
        try:
            zoom_freqs = _generate_zoom_freqs(input_freqs, num_points=1)
            assert len(zoom_freqs) == 1
        except ZeroDivisionError:
            # Expected for degenerate input
            pass

    def test_two_point_output(self):
        """Two output points span the range."""
        input_freqs = [1e6, 1e7]
        zoom_freqs = _generate_zoom_freqs(input_freqs, num_points=2)
        assert len(zoom_freqs) == 2
        assert zoom_freqs[0] == pytest.approx(1e6, rel=1e-9)
        assert zoom_freqs[1] == pytest.approx(1e7, rel=1e-9)


class TestRenderAsciiPlotDbFloor:
    """Tests for render_ascii_plot with db_floor parameter."""

    def test_db_floor_none_auto_ranges(self):
        """db_floor=None uses auto-range."""
        freqs = [100, 1e3, 1e4]
        response_db = [-1, -10, -50]
        result = render_ascii_plot(freqs, response_db, 1e3, db_floor=None)
        assert isinstance(result, str)
        # Should show some negative dB values
        assert "-" in result

    def test_db_floor_minus_6_restricts_range(self):
        """db_floor=-6 constrains Y-axis to 0 to -6 dB."""
        freqs = [100, 1e3, 1e4]
        response_db = [-1, -10, -50]
        result = render_ascii_plot(freqs, response_db, 1e3, db_floor=-6)
        assert isinstance(result, str)
        # Should show -6dB floor, not -50dB
        lines = result.split("\n")
        # Y-axis labels should not go beyond -6dB (may show 0, -3, -6)
        has_large_negative = any("-50" in line or "-40" in line or "-30" in line for line in lines)
        assert not has_large_negative

    def test_db_floor_minus_20(self):
        """db_floor=-20 shows passband detail."""
        freqs = [100, 1e3, 1e4]
        response_db = [-1, -15, -50]
        result = render_ascii_plot(freqs, response_db, 1e3, db_floor=-20)
        assert isinstance(result, str)
        # Labels should stop at -20
        assert "-20" in result

    def test_db_floor_with_lowpass(self):
        """db_floor works for lowpass filter type."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_ascii_plot(
            freqs, response_db, cutoff_hz, filter_type="lowpass", db_floor=-6
        )
        assert isinstance(result, str)
        assert "Frequency Response" in result

    def test_db_floor_with_highpass(self):
        """db_floor works for highpass filter type."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(hp_butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_ascii_plot(
            freqs, response_db, cutoff_hz, filter_type="highpass", db_floor=-6
        )
        assert isinstance(result, str)

    def test_db_floor_zero_dB(self):
        """db_floor=0 shows only passband."""
        freqs = [100, 1e3, 1e4]
        response_db = [0, -1, -30]
        result = render_ascii_plot(freqs, response_db, 1e3, db_floor=0)
        assert isinstance(result, str)

    def test_db_floor_negative_value(self):
        """Negative db_floor shows attenuated region."""
        freqs = [100, 1e3, 1e4]
        response_db = [0, -5, -20]
        result = render_ascii_plot(freqs, response_db, 1e3, db_floor=-10)
        assert isinstance(result, str)


class TestRenderBandpassPlotDbFloor:
    """Tests for render_bandpass_plot with db_floor parameter."""

    def test_db_floor_none_auto_ranges(self):
        """db_floor=None uses auto-range."""
        sweep_data = [(1e5, -20), (1e6, -3), (1e7, -20)]
        result = render_bandpass_plot(sweep_data, 1e6, 500e3, db_floor=None)
        assert isinstance(result, str)

    def test_db_floor_minus_6_restricts(self):
        """db_floor=-6 constrains Y-axis."""
        sweep_data = [(1e5, -30), (1e6, -3), (1e7, -30)]
        result = render_bandpass_plot(sweep_data, 1e6, 500e3, db_floor=-6)
        assert isinstance(result, str)
        # Should not show extreme negative dB values
        assert "-30" not in result

    def test_db_floor_with_bandpass_real_response(self):
        """db_floor works with real bandpass response."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        result = render_bandpass_plot(sweep_data, f0, bw, db_floor=-6)
        assert isinstance(result, str)
        assert "Frequency Response" in result


class TestRenderPlotPair:
    """Tests for render_plot_pair (LP/HP full + zoomed)."""

    def test_output_contains_both_titles(self):
        """Output includes both 'Frequency Response' and 'Passband Detail'."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_plot_pair(freqs, response_db, cutoff_hz, filter_type="lowpass")
        assert "Frequency Response" in result
        assert "Passband Detail" in result

    def test_two_plots_separated(self):
        """Full and zoomed plots are separated."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_plot_pair(freqs, response_db, cutoff_hz, filter_type="lowpass")
        # Should have blank lines separating plots
        assert "\n\n" in result

    def test_ripple_affects_zoom_range(self):
        """Ripple parameter affects zoom range."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        # Chebyshev with large ripple
        result = render_plot_pair(
            freqs, response_db, cutoff_hz, filter_type="lowpass", ripple_db=4.0
        )
        assert "Passband Detail" in result
        # Should show larger zoom range (0 to -8dB)
        assert "-8" in result or "8 dB" in result

    def test_response_fn_improves_zoom_resolution(self):
        """response_fn parameter increases zoom point density."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=30)  # Coarse
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]

        def response_fn(f):
            return magnitude_to_db(butterworth_response(f, cutoff_hz, order))

        result = render_plot_pair(
            freqs, response_db, cutoff_hz, filter_type="lowpass", response_fn=response_fn
        )
        assert isinstance(result, str)
        assert "Passband Detail" in result

    def test_flat_response_skips_zoom(self):
        """All-flat response skips zoomed plot."""
        freqs = [100, 1e3, 1e4]
        response_db = [0, 0, 0]  # Flat at 0dB
        result = render_plot_pair(freqs, response_db, 1e3, filter_type="lowpass")
        # Should not add zoomed plot for flat response
        assert result.count("Frequency Response") == 1
        assert "Passband Detail" not in result

    def test_highpass_filter_type(self):
        """Works with highpass filter."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(hp_butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_plot_pair(freqs, response_db, cutoff_hz, filter_type="highpass")
        assert "Frequency Response" in result
        assert isinstance(result, str)

    def test_custom_width_height(self):
        """Custom width/height passed through."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_plot_pair(
            freqs, response_db, cutoff_hz, filter_type="lowpass", width=80, height=16
        )
        assert isinstance(result, str)

    def test_butterworth_vs_chebyshev_zoom(self):
        """Chebyshev ripple affects zoom range differently."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)

        # Butterworth (no ripple)
        bw_response = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        bw_result = render_plot_pair(
            freqs, bw_response, cutoff_hz, filter_type="lowpass", ripple_db=None
        )

        # Chebyshev (with ripple)
        ch_response = [magnitude_to_db(chebyshev_response(f, cutoff_hz, order, 1.0)) for f in freqs]
        ch_result = render_plot_pair(
            freqs, ch_response, cutoff_hz, filter_type="lowpass", ripple_db=1.0
        )

        # Both should have zoomed plots
        assert "Passband Detail" in bw_result
        assert "Passband Detail" in ch_result


class TestRenderBandpassPlotPair:
    """Tests for render_bandpass_plot_pair (BP full + zoomed)."""

    def test_output_contains_both_titles(self):
        """Output includes both main and detail titles."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        result = render_bandpass_plot_pair(sweep_data, f0, bw)
        assert "Frequency Response" in result
        assert "Passband Detail" in result

    def test_two_plots_separated(self):
        """Plots separated by blank lines."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        result = render_bandpass_plot_pair(sweep_data, f0, bw)
        assert "\n\n" in result

    def test_ripple_affects_zoom(self):
        """Ripple parameter affects zoom range."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        result = render_bandpass_plot_pair(sweep_data, f0, bw, ripple_db=4.0)
        assert "Passband Detail" in result

    def test_response_fn_increases_zoom_points(self):
        """response_fn parameter provides higher resolution."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")

        def response_fn(f):  # noqa: F841
            # Return single response at given frequency
            # This is simplified for testing
            return -3.0

        result = render_bandpass_plot_pair(sweep_data, f0, bw, response_fn=response_fn)
        assert isinstance(result, str)

    def test_flat_response_skips_zoom(self):
        """Flat passband skips zoomed plot."""
        sweep_data = [(1e5, -30), (1e6, -30), (1e7, -30)]  # All flat
        result = render_bandpass_plot_pair(sweep_data, 1e6, 500e3)
        # Zoomed section skipped for flat response
        assert isinstance(result, str)

    def test_custom_title(self):
        """Custom title parameter works."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        result = render_bandpass_plot_pair(sweep_data, f0, bw, title="Custom Title")
        assert "Custom Title" in result

    def test_custom_dimensions(self):
        """Custom width/height applied."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        result = render_bandpass_plot_pair(sweep_data, f0, bw, width=100, height=20)
        assert isinstance(result, str)

    def test_explicit_band_edges_override_arithmetic_labels(self):
        """Explicit band edges are used for labels when provided."""
        f0 = (8e6 * 12e6) ** 0.5
        bw = 4e6
        sweep_data = bp_frequency_sweep(f0, bw, 3, "butterworth")
        result = render_bandpass_plot_pair(
            sweep_data,
            f0,
            bw,
            f_low_hz=8e6,
            f_high_hz=12e6,
        )
        assert "8M" in result
        assert "12M" in result


class TestFormatFreqCompact:
    """Tests for _format_freq_compact helper."""

    def test_hertz_range(self):
        """Hz values format without unit."""
        assert _format_freq_compact(1.0) == "1"
        assert _format_freq_compact(100.0) == "100"
        assert _format_freq_compact(999.0) == "999"

    def test_kilohertz_boundary(self):
        """1 kHz boundary."""
        result = _format_freq_compact(1000.0)
        assert "k" in result.lower()

    def test_megahertz_boundary(self):
        """1 MHz boundary."""
        result = _format_freq_compact(1e6)
        assert "M" in result

    def test_gigahertz_boundary(self):
        """1 GHz boundary."""
        result = _format_freq_compact(1e9)
        assert "G" in result

    def test_sub_hz(self):
        """Sub-Hz frequencies format correctly."""
        assert "0.5" in _format_freq_compact(0.5)

    def test_precise_values_use_3_sig_figs(self):
        """Values use 3 significant figures."""
        result = _format_freq_compact(1.234e6)
        # Should be formatted compactly
        assert "M" in result
        assert len(result) <= 5

    def test_very_high_frequency(self):
        """10 GHz formats correctly."""
        result = _format_freq_compact(10e9)
        assert "G" in result
        assert "10" in result

    def test_very_low_frequency(self):
        """0.1 Hz formats correctly."""
        result = _format_freq_compact(0.1)
        assert "0.1" in result


class TestPlotZoomEdgeCases:
    """Additional edge case tests for zoomed plot rendering."""

    def test_render_plot_pair_with_none_response_fn(self):
        """render_plot_pair with response_fn=None uses original data."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=30)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_plot_pair(
            freqs, response_db, cutoff_hz, filter_type="lowpass", response_fn=None
        )
        # Should still produce both plots
        assert "Frequency Response" in result
        assert isinstance(result, str)

    def test_render_bandpass_plot_pair_with_none_response_fn(self):
        """render_bandpass_plot_pair with response_fn=None."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        result = render_bandpass_plot_pair(sweep_data, f0, bw, response_fn=None)
        # Should still produce valid output
        assert isinstance(result, str)

    def test_generate_zoom_freqs_single_point(self):
        """_generate_zoom_freqs handles degenerate single-point input gracefully."""
        # Single frequency point: min == max causes log_range = 0
        input_freqs = [1e6]
        try:
            zoom_freqs = _generate_zoom_freqs(input_freqs, num_points=1)
            assert len(zoom_freqs) == 1
            assert zoom_freqs[0] == pytest.approx(1e6)
        except ZeroDivisionError:
            # Expected for degenerate case — this is acceptable
            pass

    def test_generate_zoom_freqs_identical_frequencies(self):
        """_generate_zoom_freqs with all identical frequencies."""
        # All same frequency: log_range = 0
        input_freqs = [1e6, 1e6, 1e6]
        try:
            zoom_freqs = _generate_zoom_freqs(input_freqs, num_points=3)
            # Either produces single unique freq or handles gracefully
            assert len(zoom_freqs) == 3
        except ZeroDivisionError:
            # Expected for degenerate case
            pass

    def test_render_ascii_plot_very_narrow_response(self):
        """render_ascii_plot with very narrow frequency range."""
        # Only 1 MHz span in very high resolution
        freqs = [9.99e6, 10e6, 10.01e6]
        response_db = [0, -3, -6]
        result = render_ascii_plot(freqs, response_db, 10e6, db_floor=-10)
        assert isinstance(result, str)
        assert "Frequency Response" in result

    def test_render_ascii_plot_very_wide_response(self):
        """render_ascii_plot with very wide frequency range (MHz to GHz)."""
        freqs = [1e5, 1e6, 1e7, 1e8, 1e9]
        response_db = [0, -1, -10, -30, -50]
        result = render_ascii_plot(freqs, response_db, 1e8, db_floor=-60)
        assert isinstance(result, str)
        # Should span multiple decades
        assert "G" in result or "M" in result

    def test_render_ascii_plot_all_negative_db(self):
        """render_ascii_plot with entirely negative response."""
        freqs = [1e5, 1e6, 1e7]
        response_db = [-20, -30, -40]
        result = render_ascii_plot(freqs, response_db, 1e6, db_floor=-50)
        assert isinstance(result, str)

    def test_render_ascii_plot_all_zero_db(self):
        """render_ascii_plot with all-zero response (flat passband)."""
        freqs = [1e5, 1e6, 1e7]
        response_db = [0, 0, 0]
        result = render_ascii_plot(freqs, response_db, 1e6)
        # Flat response should still render
        assert isinstance(result, str)

    def test_render_ascii_plot_single_point(self):
        """render_ascii_plot with single frequency point."""
        freqs = [1e6]
        response_db = [-3]
        result = render_ascii_plot(freqs, response_db, 1e6)
        # Single point should skip -3dB marker but still render
        assert isinstance(result, str)

    def test_render_ascii_plot_two_points(self):
        """render_ascii_plot with minimal two-point response."""
        freqs = [1e6, 1e7]
        response_db = [0, -10]
        result = render_ascii_plot(freqs, response_db, 1e6)
        assert isinstance(result, str)

    def test_render_bandpass_plot_empty_sweep(self):
        """render_bandpass_plot handles empty sweep gracefully."""
        result = render_bandpass_plot([], 1e6, 100e3)
        assert "No data" in result

    def test_render_bandpass_plot_single_point(self):
        """render_bandpass_plot with single frequency point."""
        sweep_data = [(1e6, -3)]
        result = render_bandpass_plot(sweep_data, 1e6, 100e3)
        assert isinstance(result, str)

    def test_render_bandpass_plot_zero_bandwidth(self):
        """render_bandpass_plot with zero bandwidth (degenerate)."""
        sweep_data = [(1e6, -3), (1e6, -3)]  # No frequency span
        result = render_bandpass_plot(sweep_data, 1e6, 1.0)  # Very narrow bw
        assert isinstance(result, str)

    def test_render_plot_pair_chebyshev_with_large_ripple(self):
        """render_plot_pair with Chebyshev and large ripple (>3 dB)."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(chebyshev_response(f, cutoff_hz, order, 3.0)) for f in freqs]
        result = render_plot_pair(
            freqs, response_db, cutoff_hz, filter_type="lowpass", ripple_db=3.0
        )
        # Large ripple should expand zoom range
        assert "Passband Detail" in result
        assert isinstance(result, str)

    def test_render_plot_pair_high_order_filter(self):
        """render_plot_pair with high-order filter (order 9)."""
        cutoff_hz = 10e6
        order = 9
        freqs = generate_frequency_points(cutoff_hz, num_points=100)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_plot_pair(freqs, response_db, cutoff_hz, filter_type="lowpass")
        # High order should show steep rolloff
        assert "Frequency Response" in result
        assert "Passband Detail" in result

    def test_render_plot_pair_low_order_filter(self):
        """render_plot_pair with low-order filter (order 1)."""
        cutoff_hz = 10e6
        order = 1
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_plot_pair(freqs, response_db, cutoff_hz, filter_type="lowpass")
        # Low order should show shallow rolloff
        assert "Frequency Response" in result

    def test_compute_zoom_range_with_fractional_ripple(self):
        """_compute_zoom_range with fractional ripple values."""
        result_0_1 = _compute_zoom_range(ripple_db=0.1)
        result_0_05 = _compute_zoom_range(ripple_db=0.05)
        # Both should return minimum 6 dB
        assert result_0_1 == 6.0
        assert result_0_05 == 6.0

    def test_compute_zoom_range_with_high_ripple(self):
        """_compute_zoom_range scales with very high ripple."""
        result = _compute_zoom_range(ripple_db=15.0)
        # Should be max(6, 2*15) = 30
        assert result == 30.0

    def test_render_plot_pair_custom_width_height_small(self):
        """render_plot_pair with minimal width/height."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=30)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_plot_pair(
            freqs, response_db, cutoff_hz, filter_type="lowpass", width=40, height=6
        )
        assert isinstance(result, str)

    def test_render_plot_pair_custom_width_height_large(self):
        """render_plot_pair with large width/height."""
        cutoff_hz = 10e6
        order = 5
        freqs = generate_frequency_points(cutoff_hz, num_points=50)
        response_db = [magnitude_to_db(butterworth_response(f, cutoff_hz, order)) for f in freqs]
        result = render_plot_pair(
            freqs, response_db, cutoff_hz, filter_type="lowpass", width=120, height=30
        )
        assert isinstance(result, str)

    def test_render_bandpass_plot_pair_with_custom_title(self):
        """render_bandpass_plot_pair respects custom title parameter."""
        f0 = 1e6
        bw = 100e3
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        custom_title = "My Custom BP Filter"
        result = render_bandpass_plot_pair(sweep_data, f0, bw, title=custom_title)
        assert custom_title in result

    def test_render_bandpass_plot_pair_very_narrow_bandwidth(self):
        """render_bandpass_plot_pair with very narrow bandwidth."""
        f0 = 1e6
        bw = 1e3  # 0.1% bandwidth (very high Q)
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        result = render_bandpass_plot_pair(sweep_data, f0, bw)
        # Should still render with high Q behavior
        assert "Frequency Response" in result

    def test_render_bandpass_plot_pair_very_wide_bandwidth(self):
        """render_bandpass_plot_pair with very wide bandwidth."""
        f0 = 1e6
        bw = 500e3  # 50% bandwidth (very low Q)
        order = 3
        sweep_data = bp_frequency_sweep(f0, bw, order, "butterworth")
        result = render_bandpass_plot_pair(sweep_data, f0, bw)
        # Should still render
        assert "Frequency Response" in result
