"""Accuracy regressions for bandpass response display sampling."""

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.display import PLOT_POINTS
from filter_lib.bandpass.transfer import netlist_frequency_sweep
from filter_lib.shared.plotting import find_db_thresholds


def test_display_sweep_resolves_both_skirts_of_one_percent_filter() -> None:
    result = calculate_bandpass_filter(
        f0=14.2e6,
        bw=142e3,
        z0=50.0,
        n_resonators=5,
        filter_type="butterworth",
        coupling="top",
    )

    sweep = netlist_frequency_sweep(result, points=PLOT_POINTS)
    thresholds = find_db_thresholds(
        [frequency for frequency, _ in sweep],
        [magnitude_db for _, magnitude_db in sweep],
        levels=[-3.01029995664],
        filter_type="bandpass",
        reference_frequency=result["f0"],
        relative_to_peak=True,
    )

    lower, upper = thresholds[-3.01029995664]
    assert lower is not None
    assert upper is not None
    assert lower < result["f0"] < upper
