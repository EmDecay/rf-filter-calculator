"""ASCII frequency-response renderers: axes, filled curve, and -3 dB annotations."""

import math
import re

import pytest

from filter_lib.highpass.transfer import chebyshev_response as hp_chebyshev_response
from filter_lib.lowpass.transfer import butterworth_response, chebyshev_response
from filter_lib.shared.plot_ascii_renderers import (
    _format_freq_compact,
    render_ascii_plot,
    render_bandpass_plot,
)
from filter_lib.shared.transfer_functions import generate_frequency_points, magnitude_to_db

FC = 10e6
BLOCK = "█"
# Order-5, 0.5 dB Chebyshev: -3 dB at cosh(acosh(1/epsilon)/5) times the ripple edge.
CHEBYSHEV_3DB_RATIO = math.cosh(math.acosh(1 / math.sqrt(10**0.05 - 1)) / 5)


def _marked_minus_3db_hz(label_line: str) -> float:
    """Parse the "▲<freq>M(-3dB)" annotation printed under the frequency axis."""
    match = re.fullmatch(r"▲(\d+(?:\.\d+)?)M\(-3dB\)", label_line.strip())
    assert match, label_line
    return float(match.group(1)) * 1e6


def _lp_hp_rows(plot: str, height: int) -> list[str]:
    """Grid rows of an LP/HP plot (title and blank line precede them)."""
    return plot.split("\n")[2 : 2 + height - 2]


def _dense_response(response, *args) -> tuple[list[float], list[float]]:
    freqs = generate_frequency_points(FC, num_points=401)
    return freqs, [magnitude_to_db(response(f, FC, *args)) for f in freqs]


class TestFormatFreqCompact:
    @pytest.mark.parametrize(
        ("frequency_hz", "label"),
        [
            (0.001, "0.001"),
            (0.5, "0.5"),
            (1.0, "1"),
            (999.0, "999"),
            (1e3, "1k"),
            (500e3, "500k"),
            (1e6, "1M"),
            (1.234e6, "1.23M"),
            (14.2e6, "14.2M"),
            (1e9, "1G"),
            (2.4e9, "2.4G"),
            (10e9, "10G"),
            (999e9, "999G"),
        ],
    )
    def test_uses_suffix_and_three_significant_figures(self, frequency_hz, label):
        assert _format_freq_compact(frequency_hz) == label

    @pytest.mark.parametrize(
        ("frequency_hz", "label"),
        [
            (999.6, "1k"),
            (999.6e3, "1M"),
            (999.6e6, "1G"),
            (999_999_999.9999999, "1G"),
            # No prefix above G: from 1000G the label is scientific notation in Hz.
            (999.6e9, "1e+12"),
            (1.5e12, "1.5e+12"),
        ],
    )
    def test_rounding_up_to_a_thousand_uses_the_next_prefix(self, frequency_hz, label):
        assert _format_freq_compact(frequency_hz) == label


class TestRenderAsciiPlot:
    def test_empty_input_returns_placeholder(self):
        assert render_ascii_plot([], [], FC) == "No data to plot"

    def test_bandpass_plot_accepts_an_exact_response(self):
        """Bandpass thresholds come back as (lower, upper) edges; unpacking one crashed."""

        def response(frequency):
            # Third-order Butterworth bandpass, f0 = 10 MHz, BW = 1 MHz.
            return -10 * math.log10(1 + ((frequency**2 - FC**2) / (1e6 * frequency)) ** 6)

        freqs = [1e6 * 10 ** (index / 50) for index in range(101)]
        response_db = [response(frequency) for frequency in freqs]

        refined = render_ascii_plot(
            freqs, response_db, FC, filter_type="bandpass", response_fn=response
        )

        assert refined == render_ascii_plot(freqs, response_db, FC, filter_type="bandpass")

    def test_rejects_mismatched_lengths(self):
        with pytest.raises(ValueError, match="same length"):
            render_ascii_plot([100, 200], [-3], 150)

    @pytest.mark.parametrize("first_frequency", [0.0, -100.0])
    def test_non_positive_samples_are_skipped_before_axis_ranging(self, first_frequency):
        plot = render_ascii_plot([first_frequency, 100, 1000], [-50, -3, -10], 100)

        assert plot == render_ascii_plot([100, 1000], [-3, -10], 100)

    def test_all_non_positive_samples_return_placeholder(self):
        assert render_ascii_plot([0.0, -1.0], [-3.0, -6.0], 100) == "No data to plot"

    @pytest.mark.parametrize("frequency", [math.nan, math.inf, "100"])
    def test_non_finite_frequency_is_rejected_not_skipped(self, frequency):
        with pytest.raises(ValueError, match="Plot frequencies must be finite real numbers"):
            render_ascii_plot([frequency, 100, 1000], [-50, -3, -10], 100)

    def test_default_lowpass_grid_leaves_no_gap_column(self):
        freqs = generate_frequency_points(FC)
        assert len(freqs) == 51
        response_db = [magnitude_to_db(butterworth_response(f, FC, 5)) for f in freqs]

        grid = [row[7:] for row in _lp_hp_rows(render_ascii_plot(freqs, response_db, FC), 12)]

        filled_columns = {col for row in grid for col, cell in enumerate(row) if cell == BLOCK}
        assert filled_columns == set(range(52))

    def test_gap_column_is_interpolated_in_log_frequency(self):
        # Columns 0 and 51 hold the two samples; column 17's centre (17.5) interpolates
        # to -9 * 17.5 / 51 = -3.09 dB.
        rows = _lp_hp_rows(
            render_ascii_plot([1e3, 1e6], [0.0, -9.0], 1e4, width=60, db_floor=-10), 12
        )
        grid = [row[7:] for row in rows]

        def filled(column: int) -> int:
            return sum(row[column] == BLOCK for row in grid)

        # -3.09 dB maps to row int(3.09 / 10 * 9) = 2, so 8 of 10 rows are filled.
        assert [filled(0), filled(17), filled(51)] == [10, 8, 2]

    def test_minimum_dimensions_are_enforced(self):
        plot = render_ascii_plot([100, 1000, 10000], [-3, -10, -20], 1000, width=10, height=3)
        lines = plot.split("\n")

        rows = lines[2:6]
        assert len(lines) == 8  # title, blank, 4 rows, axis, labels
        assert all(len(row) == 7 + 32 for row in rows)
        assert lines[6].startswith("      +") and len(lines[6]) == 7 + 32

    def test_custom_dimensions_size_the_grid(self):
        plot = render_ascii_plot([100, 1000, 10000], [-3, -10, -20], 1000, width=80, height=16)

        rows = _lp_hp_rows(plot, 16)
        assert len(rows) == 14
        assert all(len(row) == 7 + 72 for row in rows)

    @pytest.mark.parametrize(
        ("response_db", "bottom_label"),
        [([-1, -10, -20], "  -25 │"), ([-3, -50, -100], "  -60 │")],
        ids=["five-db-below-deepest", "clamped-at-minus-60"],
    )
    def test_auto_range_puts_zero_on_top_and_floor_below_data(self, response_db, bottom_label):
        rows = _lp_hp_rows(render_ascii_plot([100, 1000, 10000], response_db, 1000), 12)

        assert rows[0].startswith("    0 │")
        assert rows[-1].startswith(bottom_label)

    def test_fixed_floor_sets_axis_minimum_and_draws_minus_3db_reference(self):
        rows = _lp_hp_rows(render_ascii_plot([100, 1e3, 1e4], [-1, -10, -50], 1e3, db_floor=-6), 12)

        minus_3_rows = [row for row in rows if row.startswith("   -3 │")]
        assert rows[-1].startswith("   -6 │")
        assert len(minus_3_rows) == 1
        assert "·" in minus_3_rows[0]
        assert not any("-50" in row or "-30" in row for row in rows)

    def test_filled_area_height_tracks_magnitude(self):
        rows = _lp_hp_rows(render_ascii_plot([1e3, 1e4, 1e5], [0, -5, -10], 1e4, db_floor=-10), 12)
        grid = [row[7:] for row in rows]

        def filled(column: int) -> int:
            return sum(row[column] == BLOCK for row in grid)

        # 10 plot rows spanning 0..-10 dB: row = int(-dB / 10 * 9), filled to the bottom.
        assert [filled(0), filled(25), filled(51)] == [10, 6, 1]

    def test_frequency_axis_shows_span_cutoff_and_1_2_5_ticks(self):
        freqs, response_db = _dense_response(butterworth_response, 5)
        lines = render_ascii_plot(freqs, response_db, FC).split("\n")

        axis, labels = lines[12], lines[13]
        assert axis.count("┼") == 7  # 1, 2, 5, 10, 20, 50, 100 MHz
        assert labels.split() == ["1M", "10M(fc)", "100M"]

    def test_butterworth_minus_3db_at_cutoff_is_not_marked(self):
        freqs, response_db = _dense_response(butterworth_response, 5)

        plot = render_ascii_plot(freqs, response_db, FC, db_floor=-6)

        assert "●" not in plot
        assert "▲" not in plot
        assert "(-3dB)" not in plot

    def test_chebyshev_minus_3db_point_beyond_cutoff_is_marked(self):
        freqs, response_db = _dense_response(chebyshev_response, 5, 0.5)

        lines = render_ascii_plot(freqs, response_db, FC, db_floor=-6).split("\n")

        rows = lines[2:12]
        assert "●" in rows[4]  # the -3 dB row of a 0..-6 dB axis
        assert "▲" in lines[12]
        assert _marked_minus_3db_hz(lines[-1]) == pytest.approx(FC * CHEBYSHEV_3DB_RATIO, rel=2e-3)

    def test_highpass_marker_uses_the_rising_crossing(self):
        freqs, response_db = _dense_response(hp_chebyshev_response, 5, 0.5)

        plot = render_ascii_plot(freqs, response_db, FC, filter_type="highpass", db_floor=-6)

        marked = _marked_minus_3db_hz(plot.split("\n")[-1])
        assert marked == pytest.approx(FC / CHEBYSHEV_3DB_RATIO, rel=2e-3)


class TestRenderBandpassPlot:
    _SWEEP = [(5e6, -40.0), (8e6, -10.0), (10e6, 0.0), (12.5e6, -10.0), (20e6, -40.0)]

    def test_empty_sweep_returns_placeholder(self):
        assert render_bandpass_plot([], 1e6, 100e3) == "No data to plot"

    def test_default_edge_labels_are_the_geometric_minus_3db_edges(self):
        labels = render_bandpass_plot(self._SWEEP, 10e6, 4e6).split("\n")[-1]

        # sqrt(f0^2 + (bw/2)^2) +/- bw/2, not the arithmetic f0 +/- bw/2 = 8M/12M.
        assert labels.split() == ["5M", "8.2M", "10M(f₀)", "12.2M", "20M"]

    def test_explicit_edges_override_computed_labels(self):
        labels = render_bandpass_plot(self._SWEEP, 10e6, 4e6, f_low_hz=8e6, f_high_hz=12e6).split(
            "\n"
        )[-1]

        assert labels.split() == ["5M", "8M", "10M(f₀)", "12M", "20M"]

    def test_label_row_is_truncated_to_the_plot_frame(self):
        labels = render_bandpass_plot(self._SWEEP, 10e6, 4e6, width=40).split("\n")[-1]

        assert len(labels) == 6 + 40

    def test_center_marker_and_axis_labels_on_fixed_floor(self):
        plot = render_bandpass_plot([(5e6, -40.0), (20e6, -40.0)], 10e6, 4e6, db_floor=-6)
        rows = plot.split("\n")[2:12]

        center_column = 6 + 29  # f0 is the log midpoint of 5..20 MHz on 60 columns
        # The clamped -40 dB response fills the bottom row, which the marker never erases.
        assert [row[center_column] for row in rows] == ["│"] * 4 + ["┼"] + ["│"] * 4 + [BLOCK]
        assert rows[0].startswith("   0 │")
        assert rows[4].startswith("  -3 │")
        assert rows[-1].startswith("  -6 │")

    def test_non_positive_center_falls_back_to_arithmetic_edge_labels(self):
        plot = render_bandpass_plot([(100, -10), (200, -3), (300, -10)], 0, 100)

        assert plot.split("\n")[-1].split() == ["100", "-50", "0(f₀)", "50", "300"]
        assert "│" not in "".join(row[6:] for row in plot.split("\n")[2:12])

    @pytest.mark.parametrize("first_frequency", [0.0, -100.0])
    def test_non_positive_sweep_frequencies_are_skipped_before_axis_ranging(self, first_frequency):
        plot = render_bandpass_plot([(first_frequency, -50), (100, -3), (200, -10)], 150, 50)

        assert plot == render_bandpass_plot([(100, -3), (200, -10)], 150, 50)
        assert plot.split("\n")[-1].split()[0] == "100"

    @pytest.mark.parametrize("frequency", [math.nan, -math.inf, None])
    def test_non_finite_sweep_frequency_is_rejected_not_skipped(self, frequency):
        with pytest.raises(ValueError, match="Plot frequencies must be finite real numbers"):
            render_bandpass_plot([(frequency, -50), (100, -3), (200, -10)], 150, 50)

    def test_all_non_positive_sweep_returns_placeholder(self):
        assert render_bandpass_plot([(0.0, -3.0), (-5.0, -6.0)], 1e6, 1e5) == "No data to plot"

    def test_one_sample_peak_keeps_its_height_after_gap_fill(self):
        # Sparse skirts leave empty columns; the lone 0 dB sample must stay a full column.
        sweep = [(9e6, -40.0), (9.9e6, -30.0), (10e6, 0.0), (10.1e6, -30.0), (11e6, -40.0)]
        plot = render_bandpass_plot(sweep, 10.5e6, 1e6, db_floor=-45)
        grid = [row[6:] for row in plot.split("\n")[2:12]]

        heights = [sum(row[col] == BLOCK for row in grid) for col in range(60)]
        peak_column = int((math.log10(10e6) - math.log10(9e6)) / math.log10(11 / 9) * 59)
        assert heights[peak_column] == 10
        assert max(h for col, h in enumerate(heights) if col != peak_column) < 10
        assert all(heights)
