"""Full-range plus zoomed passband-detail plot pairs for LP/HP and bandpass."""

import math

import pytest

from filter_lib.highpass.transfer import chebyshev_response as hp_chebyshev_response
from filter_lib.lowpass.transfer import butterworth_response
from filter_lib.shared.plot_ascii_renderers import render_ascii_plot, render_bandpass_plot
from filter_lib.shared.plot_zoom_pairs import (
    _compute_zoom_range,
    _generate_zoom_freqs,
    render_bandpass_plot_pair,
    render_plot_pair,
)
from filter_lib.shared.transfer_functions import generate_frequency_points, magnitude_to_db

FC = 10e6


def _butterworth_db(frequency: float) -> float:
    return magnitude_to_db(butterworth_response(frequency, FC, 5))


def _split_pair(pair: str) -> tuple[str, str]:
    """Split a plot pair at the zoomed plot's title (each plot also has blank lines)."""
    full, zoomed = pair.split("\n\nPassband Detail")
    return full, "Passband Detail" + zoomed


@pytest.fixture
def lowpass_response():
    freqs = generate_frequency_points(FC, num_points=41)
    return freqs, [_butterworth_db(f) for f in freqs]


class TestZoomHelpers:
    @pytest.mark.parametrize(
        ("ripple_db", "zoom_db"),
        [(None, 6.0), (0.0, 6.0), (0.5, 6.0), (3.0, 6.0), (3.5, 7.0), (4.0, 8.0), (10.0, 20.0)],
    )
    def test_zoom_depth_is_twice_ripple_with_6db_minimum(self, ripple_db, zoom_db):
        assert _compute_zoom_range(ripple_db) == zoom_db

    def test_zoom_grid_spans_input_range_log_uniformly(self):
        zoom = _generate_zoom_freqs([1e5, 3e5, 1e7], num_points=5)

        assert zoom == pytest.approx([1e5, 10**5.5, 1e6, 10**6.5, 1e7], rel=1e-12)

    def test_single_point_zoom_grid_is_the_lowest_frequency(self):
        assert _generate_zoom_freqs([1e5, 1e7], num_points=1) == pytest.approx([1e5], rel=1e-12)

    def test_degenerate_input_span_repeats_the_frequency(self):
        zoom = _generate_zoom_freqs([1e6, 1e6, 1e6], num_points=3)

        assert zoom == pytest.approx([1e6, 1e6, 1e6], rel=1e-12)


class TestRenderPlotPair:
    def test_appends_zoomed_detail_of_the_same_data(self, lowpass_response):
        freqs, response_db = lowpass_response

        pair = render_plot_pair(freqs, response_db, FC, filter_type="lowpass")

        full = render_ascii_plot(freqs, response_db, FC, filter_type="lowpass")
        zoomed = render_ascii_plot(
            freqs, response_db, FC, db_floor=-6.0, title="Passband Detail (0 to -6 dB)"
        )
        assert pair == full + "\n\n" + zoomed

    @pytest.mark.parametrize(
        ("ripple_db", "title", "bottom_label"),
        [
            (None, "Passband Detail (0 to -6 dB)", "   -6 │"),
            (1.0, "Passband Detail (0 to -6 dB)", "   -6 │"),
            (4.0, "Passband Detail (0 to -8 dB)", "   -8 │"),
        ],
    )
    def test_zoom_depth_follows_ripple(self, lowpass_response, ripple_db, title, bottom_label):
        freqs, response_db = lowpass_response

        _, zoomed = _split_pair(render_plot_pair(freqs, response_db, FC, ripple_db=ripple_db))

        lines = zoomed.split("\n")
        assert lines[0] == title
        assert lines[11].startswith(bottom_label)

    def test_flat_passband_skips_the_zoom(self):
        freqs, response_db = [100, 1e3, 1e4], [0.0, -0.05, 0.0]

        pair = render_plot_pair(freqs, response_db, 1e3)

        assert pair == render_ascii_plot(freqs, response_db, 1e3)

    def test_response_function_resamples_zoom_at_double_density(self, lowpass_response):
        freqs, response_db = lowpass_response
        sampled = []

        def response_fn(frequency: float) -> float:
            sampled.append(frequency)
            return _butterworth_db(frequency)

        pair = render_plot_pair(freqs, response_db, FC, response_fn=response_fn)

        steps = {round(math.log10(b / a), 9) for a, b in zip(sampled, sampled[1:])}
        assert len(sampled) == 2 * len(freqs)
        assert sampled[0] == pytest.approx(freqs[0], rel=1e-12)
        assert sampled[-1] == pytest.approx(freqs[-1], rel=1e-12)
        assert len(steps) == 1
        assert "Passband Detail (0 to -6 dB)" in pair

    def test_size_applies_to_both_plots_and_title_only_to_the_full_plot(self, lowpass_response):
        freqs, response_db = lowpass_response

        full, zoomed = _split_pair(
            render_plot_pair(freqs, response_db, FC, title="LP Custom", width=50, height=8)
        )

        full_lines, zoom_lines = full.split("\n"), zoomed.split("\n")
        assert full_lines[0] == "LP Custom"
        assert zoom_lines[0] == "Passband Detail (0 to -6 dB)"
        grid_rows = full_lines[2:8] + zoom_lines[2:8]  # height 8 leaves 6 grid rows each
        assert all(len(row) == 7 + 42 and row[6] == "│" for row in grid_rows)
        assert full_lines[8].startswith("      +") and zoom_lines[8].startswith("      +")

    def test_highpass_zoom_marks_the_rising_minus_3db_crossing(self):
        freqs = generate_frequency_points(FC, num_points=401)
        response_db = [magnitude_to_db(hp_chebyshev_response(f, FC, 5, 0.5)) for f in freqs]

        pair = render_plot_pair(freqs, response_db, FC, filter_type="highpass", ripple_db=0.5)

        _, zoomed = _split_pair(pair)
        annotation = zoomed.split("\n")[-1].strip()
        ratio_3db = math.cosh(math.acosh(1 / math.sqrt(10**0.05 - 1)) / 5)
        assert annotation.startswith("▲") and annotation.endswith("M(-3dB)")
        assert float(annotation[1:-7]) * 1e6 == pytest.approx(FC / ratio_3db, rel=2e-3)


class TestRenderBandpassPlotPair:
    _SWEEP = [
        (5e6, -40.0),
        (8e6, -10.0),
        (9e6, -2.0),
        (10e6, 0.0),
        (11e6, -2.0),
        (12.5e6, -10.0),
        (20e6, -40.0),
    ]

    def test_appends_zoomed_detail_with_the_same_edges(self):
        pair = render_bandpass_plot_pair(
            self._SWEEP, 10e6, 4e6, f_low_hz=8e6, f_high_hz=12e6, title="BP Custom"
        )

        full = render_bandpass_plot(
            self._SWEEP, 10e6, 4e6, f_low_hz=8e6, f_high_hz=12e6, title="BP Custom"
        )
        zoomed = render_bandpass_plot(
            self._SWEEP,
            10e6,
            4e6,
            f_low_hz=8e6,
            f_high_hz=12e6,
            title="Passband Detail (0 to -6 dB)",
            db_floor=-6.0,
        )
        assert pair == full + "\n\n" + zoomed

    def test_ripple_sets_zoom_depth(self):
        pair = render_bandpass_plot_pair(self._SWEEP, 10e6, 4e6, ripple_db=4.0)

        zoom_lines = _split_pair(pair)[1].split("\n")
        assert zoom_lines[0] == "Passband Detail (0 to -8 dB)"
        assert zoom_lines[11].startswith("  -8 │")

    def test_flat_passband_skips_the_zoom(self):
        sweep = [(9e6, -0.05), (10e6, 0.0), (11e6, -0.05)]

        assert render_bandpass_plot_pair(sweep, 10e6, 2e6) == render_bandpass_plot(sweep, 10e6, 2e6)
