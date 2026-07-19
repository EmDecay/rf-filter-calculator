"""Machine-readable component exports must never emit NaN or Infinity."""

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.formatters import format_csv as format_bandpass_csv
from filter_lib.highpass.display import format_csv as format_highpass_csv
from filter_lib.lowpass.display import format_csv as format_lowpass_csv


@pytest.mark.parametrize("formatter", [format_lowpass_csv, format_highpass_csv])
def test_lp_hp_csv_rejects_non_finite_component(formatter) -> None:
    result = {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": [float("nan")],
        "inductors": [1e-6],
        "order": 2,
        "ripple": None,
        "topology": "pi",
    }

    with pytest.raises(ValueError, match="finite"):
        formatter(result, include_toroids=False)


def test_bandpass_csv_rejects_non_finite_component() -> None:
    result = calculate_bandpass_filter(
        f0=14.2e6,
        bw=500e3,
        z0=50.0,
        n_resonators=3,
        filter_type="butterworth",
        coupling="top",
    )
    result["c_tank"][0] = float("inf")

    with pytest.raises(ValueError, match="finite"):
        format_bandpass_csv(result, include_toroids=False)
