"""dB-threshold crossing detection and the threshold summary table.

Crossings are interpolated linearly in log10(frequency), so a crossing halfway
(in dB) between two samples lands at their geometric mean, not the arithmetic
mean. Expected values below follow from that rule or from the analytic
Butterworth attenuation f = fc * (10^(A/10) - 1)^(1/2n).
"""

import math
import re
import sys

import pytest

from filter_lib import cli
from filter_lib.highpass.transfer import butterworth_response as hp_butterworth_response
from filter_lib.lowpass.transfer import butterworth_response as lp_butterworth_response
from filter_lib.shared.plot_ascii_renderers import _format_freq_compact
from filter_lib.shared.plot_threshold_analysis import (
    ThresholdRegion,
    _find_3db_frequency,
    _find_db_crossing,
    find_db_thresholds,
    find_threshold_regions,
    format_threshold_table,
)
from filter_lib.shared.transfer_functions import generate_frequency_points, magnitude_to_db
from filter_lib.shared.transfer_response_dispatch import make_hp_response_db, make_lp_response_db
from filter_lib.wizard.calculation_handler import calculate_and_format
from filter_lib.wizard.state import FilterState

FC = 10e6


def _butterworth_attenuation_frequency(attenuation_db: float, order: int) -> float:
    """Lowpass frequency where a Butterworth response is down ``attenuation_db``."""
    return FC * (10 ** (attenuation_db / 10) - 1) ** (1 / (2 * order))


class TestDbCrossing:
    @pytest.mark.parametrize(
        ("freqs", "response_db", "threshold_db", "direction", "expected_hz"),
        [
            ([1000, 2000], [-2, -4], -3.0, "falling", math.sqrt(1000 * 2000)),
            ([1000, 2000], [-4, -2], -3.0, "rising", math.sqrt(1000 * 2000)),
            ([100, 200, 300], [-1, -3, -10], -3.0, "falling", 200.0),
            ([100, 200, 300], [-10, -3, -1], -3.0, "rising", 200.0),
            (
                [100, 200, 300, 400],
                [-50, -60, -75, -90],
                -80.0,
                "falling",
                300 * (4 / 3) ** (1 / 3),
            ),
            (
                [100, 150, 200, 250, 300],
                [-1, -10, -1, -10, -1],
                -3.0,
                "falling",
                100 * 1.5 ** (2 / 9),
            ),
        ],
        ids=[
            "falling-geometric-midpoint",
            "rising-geometric-midpoint",
            "falling-exact-sample",
            "rising-exact-sample",
            "deep-threshold",
            "first-of-several",
        ],
    )
    def test_interpolates_crossing_in_log_frequency(
        self, freqs, response_db, threshold_db, direction, expected_hz
    ):
        crossing = _find_db_crossing(freqs, response_db, threshold_db, direction)

        assert crossing == pytest.approx(expected_hz, rel=1e-12)

    @pytest.mark.parametrize(
        ("freqs", "response_db", "direction"),
        [
            ([], [], "falling"),
            ([1000], [-5], "falling"),
            ([100, 200, 300], [-1, -2, -2.5], "falling"),
            ([100, 200, 300], [-10, -15, -20], "falling"),
            ([100, 200, 300], [-3, -3, -3], "falling"),
            ([100, 200, 300], [-1, -5, -10], "rising"),
        ],
        ids=["empty", "single-point", "all-above", "all-below", "flat-at-threshold", "wrong-way"],
    )
    def test_returns_none_without_a_crossing_in_the_requested_direction(
        self, freqs, response_db, direction
    ):
        assert _find_db_crossing(freqs, response_db, -3.0, direction) is None

    @pytest.mark.parametrize(
        ("response_db", "direction"),
        [([-1, -5, -10, -20], "falling"), ([-20, -10, -5, -1], "rising")],
    )
    def test_3db_helper_is_the_minus_3db_crossing(self, response_db, direction):
        freqs = [100, 200, 300, 400]

        assert _find_3db_frequency(freqs, response_db, direction) == _find_db_crossing(
            freqs, response_db, -3.0, direction
        )


class TestThresholdRegions:
    def test_returns_every_connected_region_with_open_grid_edges(self):
        regions = find_threshold_regions([1, 2, 3, 4, 5, 6, 7], [-1, -1, -10, -1, -1, -10, -1], -3)

        assert [(r.start_index, r.end_index, r.peak_db) for r in regions] == [
            (0, 1, -1),
            (3, 4, -1),
            (6, 6, -1),
        ]
        assert all(isinstance(region, ThresholdRegion) for region in regions)
        assert regions[0].f_low is None
        assert regions[0].f_high == pytest.approx(2 * 1.5 ** (2 / 9), rel=1e-12)
        assert regions[1].f_low == pytest.approx(3 * (4 / 3) ** (7 / 9), rel=1e-12)
        assert regions[1].f_high == pytest.approx(5 * 1.2 ** (2 / 9), rel=1e-12)
        assert regions[2].f_low == pytest.approx(6 * (7 / 6) ** (7 / 9), rel=1e-12)
        assert regions[2].f_high is None

    def test_exact_threshold_samples_belong_to_region(self):
        regions = find_threshold_regions([1, 2, 3, 4], [-10, -3, -3, -10], -3)
        assert len(regions) == 1
        assert regions[0].start_index == 1
        assert regions[0].end_index == 2
        assert regions[0].f_low == 2
        assert regions[0].f_high == 3

    @pytest.mark.parametrize(
        ("freqs", "response_db", "threshold_db", "message"),
        [
            ([1, 2], [-1], -3, "same length"),
            ([1, 1], [-1, -5], -3, "strictly increasing"),
            ([0, 1], [-5, -1], -3, "frequencies must be positive and finite"),
            ([1, float("inf")], [-5, -1], -3, "frequencies must be positive and finite"),
            ([1, 2], [-5, float("nan")], -3, "response_db values must be finite"),
            ([1, 2], [-5, -1], float("nan"), "threshold_db must be finite"),
            ([1, 2], [-5, -1], True, "threshold_db must be finite"),
        ],
    )
    def test_rejects_invalid_grids_and_values(self, freqs, response_db, threshold_db, message):
        with pytest.raises(ValueError, match=message):
            find_threshold_regions(freqs, response_db, threshold_db)


class TestFindDbThresholds:
    def test_lowpass_butterworth_crossings_match_analytic_attenuation(self):
        freqs = generate_frequency_points(FC, decades=2.0, points_per_decade=200)
        response_db = [magnitude_to_db(lp_butterworth_response(f, FC, 5)) for f in freqs]

        thresholds = find_db_thresholds(freqs, response_db, filter_type="lowpass")

        assert list(thresholds) == [-3, -10, -20]
        for level, (crossing,) in thresholds.items():
            expected = _butterworth_attenuation_frequency(-level, 5)
            assert crossing == pytest.approx(expected, rel=5e-5)

    def test_highpass_butterworth_crossings_match_analytic_attenuation(self):
        freqs = generate_frequency_points(FC, decades=2.0, points_per_decade=200)
        response_db = [magnitude_to_db(hp_butterworth_response(f, FC, 5)) for f in freqs]

        thresholds = find_db_thresholds(freqs, response_db, filter_type="highpass")

        for level, (crossing,) in thresholds.items():
            expected = FC**2 / _butterworth_attenuation_frequency(-level, 5)
            assert crossing == pytest.approx(expected, rel=5e-5)

    def test_custom_levels_are_reported_in_request_order(self):
        thresholds = find_db_thresholds(
            [100, 200, 300, 400, 500], [0, -2, -6, -15, -30], levels=[-2, -6, -15]
        )

        assert list(thresholds) == [-2, -6, -15]
        assert thresholds[-2] == [200]
        assert thresholds[-6] == [300]
        assert thresholds[-15] == [400]

    def test_lowpass_requires_passband_connected_to_the_lowest_frequency(self):
        thresholds = find_db_thresholds([1, 2, 3, 4], [-10, -1, -1, -10], levels=[-3])

        assert thresholds == {-3: [None]}

    def test_highpass_uses_region_connected_to_the_highest_frequency(self):
        thresholds = find_db_thresholds(
            [1, 2, 3, 4, 5], [-1, -10, -1, -10, -1], levels=[-3], filter_type="highpass"
        )

        assert thresholds[-3] == pytest.approx([4 * 1.25 ** (7 / 9)], rel=1e-12)

    @pytest.mark.parametrize(
        ("response_db", "expected"),
        [
            ([0, 0, 0], {-3: [None], -10: [None], -20: [None]}),
            ([-1, -2, -3], {-3: [None], -10: [None], -20: [None]}),
            ([-5, -5, -5], {-3: [None], -10: [None], -20: [None]}),
        ],
        ids=["flat-passband", "never-reaches-10db", "flat-between-levels"],
    )
    def test_levels_without_a_bounded_crossing_are_none(self, response_db, expected):
        assert find_db_thresholds([100, 200, 300], response_db) == expected

    def test_empty_response_reports_none_for_every_level(self):
        assert find_db_thresholds([], [], filter_type="lowpass") == {
            -3: [None],
            -10: [None],
            -20: [None],
        }

    def test_bandpass_reports_both_true_edges_of_an_ideal_sweep(self):
        from filter_lib.bandpass.transfer import frequency_sweep

        f0, bw = 1e6, 100e3
        sweep = frequency_sweep(f0, bw, 3, "butterworth", points=401)

        thresholds = find_db_thresholds(
            [f for f, _ in sweep], [db for _, db in sweep], filter_type="bandpass"
        )

        f_high = bw / 2 + math.sqrt((bw / 2) ** 2 + f0**2)
        assert thresholds[-3] == pytest.approx([f0**2 / f_high, f_high], rel=1e-4)

    def test_bandpass_without_reference_selects_the_highest_region(self):
        thresholds = find_db_thresholds(
            [1, 2, 3, 4, 5, 6, 7, 8, 9],
            [-20, -1, -20, -20, -2, 0, -2, -20, -20],
            levels=[-3],
            filter_type="bandpass",
        )

        assert thresholds[-3] == pytest.approx(
            [4 * 1.25 ** (17 / 18), 7 * (8 / 7) ** (1 / 18)], rel=1e-12
        )

    def test_bandpass_selects_region_containing_reference_frequency(self):
        """An earlier disconnected spur must not donate the lower skirt."""
        result = find_db_thresholds(
            [1, 2, 3, 4, 5, 6, 7, 8, 9],
            [-20, -1, -20, -20, -6, -1, -1, -6, -20],
            levels=[-3],
            filter_type="bandpass",
            reference_frequency=6.5,
        )

        assert result[-3][0] is not None and 5 < result[-3][0] < 6
        assert result[-3][1] is not None and 7 < result[-3][1] < 8

    def test_bandpass_reference_outside_every_region_selects_the_nearest_edge(self):
        # 4.2 Hz lies between regions 2-3 Hz and 5-9 Hz; the 5 Hz lower skirt is nearest.
        thresholds = find_db_thresholds(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            [-20, -1, -1, -20, -1, 0, 0, 0, -1, -20],
            levels=[-3],
            filter_type="bandpass",
            reference_frequency=4.2,
        )

        assert thresholds[-3] == pytest.approx(
            [4 * 1.25 ** (17 / 19), 9 * (10 / 9) ** (2 / 19)], rel=1e-12
        )

    def test_peak_relative_bandpass_ignores_higher_disconnected_spur(self):
        result = find_db_thresholds(
            [1, 2, 3, 4, 5, 6, 7, 8, 9],
            [-20, 0, -20, -20, -12, -5, -5, -12, -20],
            levels=[-3],
            filter_type="bandpass",
            reference_frequency=6.5,
            relative_to_peak=True,
        )

        assert result[-3][0] is not None and 5 < result[-3][0] < 6
        assert result[-3][1] is not None and 7 < result[-3][1] < 8

    def test_peak_relative_levels_without_reference_use_the_global_peak(self):
        # Peak is +2 dB at 2 Hz, so "-3 dB" means -1 dB absolute.
        thresholds = find_db_thresholds(
            [1, 2, 3, 4], [1, 2, 0, -10], levels=[-3], relative_to_peak=True
        )

        assert thresholds[-3] == pytest.approx([3 * (4 / 3) ** (1 / 10)], rel=1e-12)

    @pytest.mark.parametrize("relative_to_peak", [False, True])
    @pytest.mark.parametrize("reference", [0.0, -1.0, float("nan"), float("inf"), True])
    def test_bandpass_rejects_invalid_reference_frequency(self, reference, relative_to_peak):
        with pytest.raises(ValueError, match="reference_frequency must be positive and finite"):
            find_db_thresholds(
                [1, 2, 3],
                [-10, 0, -10],
                filter_type="bandpass",
                reference_frequency=reference,
                relative_to_peak=relative_to_peak,
            )

    @pytest.mark.parametrize(
        ("filter_type", "response"),
        [("lowpass", lp_butterworth_response), ("highpass", hp_butterworth_response)],
    )
    def test_response_function_refines_coarse_crossings(self, filter_type, response):
        freqs = generate_frequency_points(FC, num_points=11)

        def response_db(frequency: float) -> float:
            return magnitude_to_db(response(frequency, FC, 5))

        sampled = [response_db(f) for f in freqs]
        coarse = find_db_thresholds(freqs, sampled, levels=[-3], filter_type=filter_type)
        refined = find_db_thresholds(
            freqs, sampled, levels=[-3], filter_type=filter_type, response_fn=response_db
        )

        exact = _butterworth_attenuation_frequency(3, 5)
        if filter_type == "highpass":
            exact = FC**2 / exact
        assert abs(coarse[-3][0] / exact - 1) > 1e-3
        assert refined[-3][0] == pytest.approx(exact, rel=1e-6)

    @pytest.mark.parametrize("first_frequency", [-100, 0])
    def test_malformed_lowpass_grid_uses_permissive_first_crossing(self, first_frequency):
        thresholds = find_db_thresholds([first_frequency, 100, 200, 300], [-10, -1, -5, -20])

        assert thresholds[-3] == pytest.approx([math.sqrt(100 * 200)], rel=1e-12)
        assert thresholds[-10] == pytest.approx([200 * 1.5 ** (1 / 3)], rel=1e-12)
        assert thresholds[-20] == [None]

    def test_malformed_highpass_grid_uses_permissive_rising_crossing(self):
        thresholds = find_db_thresholds(
            [100, 200, 200, 400], [-20, -10, -10, -1], levels=[-3], filter_type="highpass"
        )

        assert thresholds[-3] == pytest.approx([200 * 2 ** (7 / 9)], rel=1e-12)

    def test_malformed_bandpass_grid_pairs_rising_and_falling_crossings(self):
        thresholds = find_db_thresholds(
            [1, 2, 2, 3, 4], [-20, -1, -1, -2, -20], levels=[-3, -30], filter_type="bandpass"
        )

        assert thresholds[-3] == pytest.approx([2 ** (17 / 19), 3 * (4 / 3) ** (1 / 18)])
        assert thresholds[-30] == [None, None]

    def test_malformed_bandpass_grid_keeps_a_missing_skirt_as_none(self):
        thresholds = find_db_thresholds(
            [1, 2, 2, 3], [-1, -1, -2, -20], levels=[-3], filter_type="bandpass"
        )

        assert thresholds[-3][0] is None
        assert thresholds[-3][1] == pytest.approx(2 * 1.5 ** (1 / 18), rel=1e-12)


class TestFormatThresholdTable:
    def test_lowpass_table_lists_falling_crossings(self):
        table = format_threshold_table({-3: [10e6], -10: [None], -20: [25e6]}, "lowpass")

        assert table.split("\n") == [
            "",
            "dB Threshold Summary",
            "┌────────┬──────────────┐",
            "│ Level  │  Frequency   │",
            "├────────┼──────────────┤",
            "│ -3 dB  │    ↓ 10M     │",
            "│ -10 dB │     N/A      │",
            "│ -20 dB │    ↓ 25M     │",
            "└────────┴──────────────┘",
        ]

    def test_highpass_table_sorts_levels_descending_with_rising_arrows(self):
        table = format_threshold_table(
            {-10: [5e6], -3.5: [1.234e6], 1: [9e6], -3: [10e6], 0: [12e6]}, "highpass"
        )

        assert table.split("\n")[5:10] == [
            "│ +1 dB  │     ↑ 9M     │",
            "│ +0 dB  │    ↑ 12M     │",
            "│ -3 dB  │    ↑ 10M     │",
            "│-3.5 dB │   ↑ 1.23M    │",
            "│ -10 dB │     ↑ 5M     │",
        ]

    def test_bandpass_table_has_low_and_high_columns(self):
        table = format_threshold_table({-3: [9.5e6, 10.5e6], -10: [None, 11e6]}, "bandpass")

        assert table.split("\n") == [
            "",
            "dB Threshold Summary",
            "┌────────┬──────────────┬──────────────┐",
            "│ Level  │    f_low     │    f_high    │",
            "├────────┼──────────────┼──────────────┤",
            "│ -3 dB  │     9.5M     │    10.5M     │",
            "│ -10 dB │     N/A      │     11M      │",
            "└────────┴──────────────┴──────────────┘",
        ]

    def test_empty_thresholds_render_header_and_frame_only(self):
        assert format_threshold_table({}, "lowpass").split("\n") == [
            "",
            "dB Threshold Summary",
            "┌────────┬──────────────┐",
            "│ Level  │  Frequency   │",
            "├────────┼──────────────┤",
            "└────────┴──────────────┘",
        ]


class TestLadderPlotLabelsAreTheResponseCrossings:
    """``--plot`` labels, in the CLI and the wizard, name the analytic response's crossings.

    Interpolating the 25-point-per-decade plot grid misplaced steep high-order crossings by
    up to 1.6%, which changed the printed three-figure label (10.7M instead of 10.9M).
    """

    @staticmethod
    def _exact_crossing(response, low: float, high: float, level: float, falling: bool):
        for _ in range(200):
            middle = math.sqrt(low * high)
            if (response(middle) >= level) == falling:
                low = middle
            else:
                high = middle
        return low

    @staticmethod
    def _threshold_labels(text: str) -> dict[int, str]:
        labels = {}
        for line in text.splitlines():
            cells = [cell.strip() for cell in line.split("│")[1:-1]]
            if len(cells) == 2 and cells[0].endswith(" dB"):
                labels[int(cells[0].removesuffix(" dB"))] = cells[1]
        return labels

    @staticmethod
    def _cli_and_wizard_text(monkeypatch, capsys, state: FilterState) -> tuple[str, str]:
        command = "lp" if state.category == "lowpass" else "hp"
        alias = {"butterworth": "bw", "chebyshev": "ch"}[state.filter_type]
        argv = [command, alias, "pi", f"{state.frequency_hz:g}", "-n", str(state.order)]
        if state.filter_type == "chebyshev":
            argv += ["-r", f"{state.ripple_db:g}"]
        monkeypatch.setattr(sys, "argv", ["filter-calc", *argv, "--plot", "--no-match"])
        cli.main()
        outcome = calculate_and_format(state)
        assert outcome.succeeded, outcome.error
        return capsys.readouterr().out, outcome.output_text

    @pytest.mark.parametrize("category", ["lowpass", "highpass"])
    def test_threshold_rows_and_marker_are_the_bisected_crossings(
        self, monkeypatch, capsys, category
    ):
        factory = make_lp_response_db if category == "lowpass" else make_hp_response_db
        response = factory("chebyshev", FC, 9, 0.01)
        falling = category == "lowpass"
        low, high = (FC, 100 * FC) if falling else (FC / 100, FC)
        arrow = "↓" if falling else "↑"
        expected = {
            level: _format_freq_compact(self._exact_crossing(response, low, high, level, falling))
            for level in (-3, -10, -20)
        }
        state = FilterState(
            category=category,
            filter_type="chebyshev",
            topology="pi",
            frequency_hz=FC,
            order=9,
            ripple_db=0.01,
            eseries="none",
            show_plot=True,
        )

        for text in self._cli_and_wizard_text(monkeypatch, capsys, state):
            assert self._threshold_labels(text) == {
                level: f"{arrow} {label}" for level, label in expected.items()
            }
            # The -3 dB marker under the plot names the same frequency as the table.
            markers = re.findall(r"▲(\S+)\(-3dB\)", text)
            assert markers and set(markers) == {expected[-3]}

    def test_crossing_that_rounds_to_a_thousand_rolls_over_to_the_next_prefix(
        self, monkeypatch, capsys
    ):
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            topology="pi",
            frequency_hz=1e9,
            order=9,
            eseries="none",
            show_plot=True,
        )

        for text in self._cli_and_wizard_text(monkeypatch, capsys, state):
            assert self._threshold_labels(text)[-3] == "↓ 1G"
            assert "e+" not in text
