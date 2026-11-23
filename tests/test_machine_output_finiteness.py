"""Machine-readable component exports must never emit NaN or Infinity."""

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.formatters import format_csv as format_bandpass_csv
from filter_lib.highpass.display import format_csv as format_highpass_csv
from filter_lib.lowpass.display import format_csv as format_lowpass_csv
from tests.parts_helpers import parts_for


@pytest.mark.parametrize(
    ("formatter", "category"),
    [(format_lowpass_csv, "lowpass"), (format_highpass_csv, "highpass")],
)
def test_lp_hp_csv_rejects_non_finite_component(formatter, category) -> None:
    result = {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": [1e-9],
        "inductors": [1e-6],
        "order": 2,
        "ripple": None,
        "topology": "pi",
    }
    # Parts resolve only for finite values; the export must still refuse a value that
    # became non-finite afterwards.
    parts = parts_for(result, category, None, inductor_detail="none")
    result["capacitors"][0] = float("nan")

    with pytest.raises(ValueError, match=r"\$\.capacitors\[0\] must be finite"):
        formatter(result, parts)


def test_bandpass_csv_rejects_non_finite_component() -> None:
    result = calculate_bandpass_filter(
        f0=14.2e6,
        bw=500e3,
        z0=50.0,
        n_resonators=3,
        filter_type="butterworth",
        coupling="top",
    )
    parts = parts_for(result, "bandpass", None, inductor_detail="none")
    result["c_tank"][0] = float("inf")

    with pytest.raises(ValueError, match=r"\$\.tank_capacitors\[0\] must be finite"):
        format_bandpass_csv(result, parts)
