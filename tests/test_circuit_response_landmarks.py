"""Sampled-response landmarks worked by hand: half-power edges, passband extremes, grids.

``find_3db_edges`` interpolates linearly between the last sample outside and the first
sample inside the half-power level (peak / sqrt(2)); a region that reaches the end of
the grid reports the grid frequency itself.
"""

import math

import pytest

from filter_lib.shared.response_measurement import find_3db_edges, logspace, passband_ripple_db
from filter_lib.shared.transfer_functions import MAX_FREQUENCY_POINTS

HALF_POWER = 1 / math.sqrt(2)


def test_edges_interpolate_on_the_actual_frequency_spacing():
    """1 MHz spacing: (0.7071 - 0.6) / (1.0 - 0.6) = 0.2678 of a step from each 0.6 sample."""
    freqs = [1e6, 2e6, 3e6, 4e6, 5e6]
    mags = [0.2, 0.6, 1.0, 0.6, 0.2]
    fraction = (HALF_POWER - 0.6) / 0.4

    f_low, f_high = find_3db_edges(freqs, mags)

    assert f_low == pytest.approx(2e6 + fraction * 1e6, rel=1e-12, abs=0)
    assert f_high == pytest.approx(4e6 - fraction * 1e6, rel=1e-12, abs=0)
    assert (f_low, f_high) == pytest.approx((2.267767e6, 3.732233e6), rel=1e-6, abs=0)


def test_region_reaching_the_last_sample_reports_the_grid_end():
    """Highpass-like: above half power from 0.9 through the last sample."""
    f_low, f_high = find_3db_edges([1.0, 2.0, 3.0, 4.0], [0.1, 0.5, 0.9, 1.0])

    assert f_low == pytest.approx(2.0 + (HALF_POWER - 0.5) / 0.4, rel=1e-12, abs=0)
    assert f_high == 4.0


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        # Nearest local maximum (0.8 at 5 Hz) sets the level 0.5657; its lone sample is the band.
        (5.0, (4.0 + (0.8 * HALF_POWER - 0.3) / 0.5, 6.0 - (0.8 * HALF_POWER - 0.3) / 0.5)),
        # Without a reference the global peak (1.0 at 2 Hz) is measured instead.
        (None, (1.0 + (HALF_POWER - 0.2) / 0.8, 3.0 - (HALF_POWER - 0.2) / 0.8)),
    ],
)
def test_reference_selects_the_nearest_local_peak_not_the_global_one(reference, expected):
    freqs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    mags = [0.2, 1.0, 0.2, 0.3, 0.8, 0.3]

    edges = find_3db_edges(freqs, mags, reference_frequency=reference)

    assert edges == pytest.approx(expected, rel=1e-12, abs=0)


def test_equidistant_local_peaks_resolve_to_the_higher_one():
    """0.6 at 2 Hz and 1.0 at 6 Hz are both 2 Hz from the 4 Hz reference."""
    freqs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    mags = [0.1, 0.6, 0.3, 0.2, 0.3, 1.0, 0.1]

    edges = find_3db_edges(freqs, mags, reference_frequency=4.0)

    assert edges == pytest.approx(
        (5.0 + (HALF_POWER - 0.3) / 0.7, 7.0 - (HALF_POWER - 0.1) / 0.9), rel=1e-12, abs=0
    )


def test_slope_sample_at_the_reference_is_not_mistaken_for_a_peak():
    """The 0.9 sample at 3 Hz is on the falling side of the 1.0 peak, which sets the level."""
    freqs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    mags = [0.1, 1.0, 0.9, 0.5, 0.2, 0.6, 0.1]

    edges = find_3db_edges(freqs, mags, reference_frequency=3.0)

    assert edges == pytest.approx(
        (1.0 + (HALF_POWER - 0.1) / 0.9, 4.0 - (HALF_POWER - 0.5) / 0.4), rel=1e-12, abs=0
    )


def test_band_is_anchored_at_the_reference_when_a_nearer_narrow_peak_sets_the_level():
    """Local maxima 0.9 (2 Hz) and 1.0 (7 Hz): the 2 Hz one is nearer 4 Hz and sets the level
    0.6364. The 4 Hz sample itself clears that level, so its 4-7 Hz region is reported."""
    freqs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    mags = [0.1, 0.9, 0.1, 0.8, 0.85, 0.9, 1.0, 0.1, 0.1]
    level = 0.9 * HALF_POWER

    edges = find_3db_edges(freqs, mags, reference_frequency=4.0)

    assert edges == pytest.approx(
        (3.0 + (level - 0.1) / 0.7, 8.0 - (level - 0.1) / 0.9), rel=1e-12, abs=0
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (([0.0, 1.0], [1.0, 0.5]), "^frequencies must be positive and finite$"),
        (([1.0, 2.0], [1.0, 0.5], 0.0), "^reference_frequency must be positive and finite$"),
    ],
)
def test_edge_finder_rejects_zero_frequencies(arguments, message):
    with pytest.raises(ValueError, match=message):
        find_3db_edges(*arguments)


def test_passband_extremes_include_the_limit_sample_in_decibels():
    """|H| = 1.0 and 0.5 up to and including f_limit: 0 dB and 20·log10(0.5) = -6.0206 dB."""
    maximum, minimum = passband_ripple_db([1.0, 2.0, 3.0], [1.0, 0.5, 0.1], 2.0)

    assert maximum == 0.0
    assert minimum == pytest.approx(-6.020599913, rel=1e-9, abs=0)


def test_zero_passband_magnitude_is_minus_infinity_decibels():
    assert passband_ripple_db([1.0, 2.0], [1.0, 0.0], 2.0) == (0.0, -math.inf)


def test_passband_limit_of_zero_is_rejected_by_name():
    with pytest.raises(ValueError, match="^f_limit must be positive and finite$"):
        passband_ripple_db([1.0, 2.0], [1.0, 0.5], 0.0)


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ((0, 1, 2), [1.0, 10.0]),
        ((0, 2, 3), [1.0, 10.0, 100.0]),
        ((-1, 1, 5), [0.1, 10**-0.5, 1.0, 10**0.5, 10.0]),
        ((6, 8, 3), [1e6, 1e7, 1e8]),
    ],
)
def test_logspace_points_are_equal_decade_fractions_including_both_ends(arguments, expected):
    assert logspace(*arguments) == pytest.approx(expected, rel=1e-14, abs=0)


def test_logspace_accepts_the_maximum_point_count():
    grid = logspace(0, 1, MAX_FREQUENCY_POINTS)

    assert len(grid) == MAX_FREQUENCY_POINTS
    assert (grid[0], grid[-1]) == pytest.approx((1.0, 10.0), rel=1e-14, abs=0)
