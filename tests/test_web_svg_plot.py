"""The SVG response plot draws exactly the response-data samples, accessibly."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from filter_lib.design import DesignRequest, design, response_series
from filter_lib.web.svg_plot import _db_range, _frequency_ticks, render_response_svg

SVG = "{http://www.w3.org/2000/svg}"
REQUESTS = {
    "lowpass": DesignRequest("lowpass", "chebyshev", "pi", 10e6, 50.0, 5, ripple_db=0.5),
    "highpass": DesignRequest("highpass", "bessel", "t", 3.5e6, 75.0, 4),
    "bandpass": DesignRequest(
        "bandpass", "butterworth", "top", 14.175e6, 50.0, 3, bandwidth_hz=350e3
    ),
}


def _parse(svg: str) -> ET.Element:
    # The markup is an inline HTML element; give it the SVG namespace to parse as XML.
    return ET.fromstring(svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1))


@pytest.fixture(scope="module", params=list(REQUESTS))
def plotted(request):
    category = request.param
    freqs, response_db = response_series(design(REQUESTS[category]))
    return category, freqs, response_db, render_response_svg(freqs, response_db, category)


def test_trace_has_one_point_per_response_sample(plotted):
    _category, freqs, _db, svg = plotted
    root = _parse(svg)

    points = root.find(f"{SVG}polyline").get("points").split()

    assert len(points) == len(freqs) == int(root.get("data-samples"))


def test_frequency_extents_match_the_response_data(plotted):
    _category, freqs, _db, svg = plotted
    root = _parse(svg)

    assert float(root.get("data-f-min")) == freqs[0]
    assert float(root.get("data-f-max")) == freqs[-1]
    xs = [float(point.split(",")[0]) for point in root.find(f"{SVG}polyline").get("points").split()]
    assert xs == sorted(xs)


def test_guide_axes_and_accessible_name_are_present(plotted):
    category, freqs, _db, svg = plotted
    root = _parse(svg)
    texts = [text.text for text in root.iter(f"{SVG}text")]

    assert root.find(f"{SVG}line[@class='plot-guide']") is not None
    assert {"−3 dB", "Frequency", "Magnitude (dB)"} <= set(texts)
    assert root.get("role") == "img"
    assert root.find(f"{SVG}title").text == root.get("aria-label")
    assert f"{len(freqs)} frequency points" in root.get("aria-label")
    source = "(simulated circuit)" if category == "bandpass" else "(ideal transfer function)"
    assert source in root.get("aria-label")


def test_points_stay_inside_the_plot_area(plotted):
    _category, _freqs, _db, svg = plotted
    root = _parse(svg)
    frame = root.find(f"{SVG}rect[@class='plot-frame']")
    left, top = float(frame.get("x")), float(frame.get("y"))
    right, bottom = left + float(frame.get("width")), top + float(frame.get("height"))

    for point in root.find(f"{SVG}polyline").get("points").split():
        x, y = map(float, point.split(","))
        assert left - 0.01 <= x <= right + 0.01
        assert top - 0.01 <= y <= bottom + 0.01


def test_output_is_deterministic(plotted):
    category, freqs, response_db, svg = plotted

    assert render_response_svg(freqs, response_db, category) == svg


def test_narrow_bands_get_evenly_spaced_ticks():
    ticks = _frequency_ticks(13.9e6, 14.5e6)

    assert len(ticks) >= 3
    assert all(13.9e6 <= tick <= 14.5e6 for tick in ticks)
    steps = {round(b - a) for a, b in zip(ticks, ticks[1:])}
    assert len(steps) == 1


def test_wide_spans_use_decade_ticks():
    assert _frequency_ticks(1e6, 100e6) == [1e6, 2e6, 5e6, 10e6, 20e6, 50e6, 100e6]


@pytest.mark.parametrize(
    "response_db, expected",
    [
        ([0.0, -3.0, -41.0], (-60.0, 0.0)),
        ([1e-12, -150.0], (-100.0, 0.0)),
        ([0.0, -1.0], (-20.0, 0.0)),
    ],
)
def test_db_axis_starts_at_zero_and_is_bounded(response_db, expected):
    assert _db_range(response_db) == expected


@pytest.mark.parametrize("freqs, response_db", [([1.0], [0.0]), ([1.0, 2.0], [0.0])])
def test_mismatched_or_short_series_are_rejected(freqs, response_db):
    with pytest.raises(ValueError, match="matching frequency and magnitude series"):
        render_response_svg(freqs, response_db, "lowpass")


def test_result_fragment_has_the_plot_only_when_requested():
    pytest.importorskip("fastapi")
    from tests.web_helpers import HTMX, web_client

    form = {"filter_type": "butterworth", "topology": "pi", "frequency": "10MHz"}
    with web_client() as client:
        with_plot = client.post("/design/lowpass", data={**form, "svg_plot": "on"}, headers=HTMX)
        without = client.post("/design/lowpass", data=form, headers=HTMX)

    assert with_plot.text.count('<svg class="response-plot"') == 1
    assert "<svg" not in without.text
