"""Form fields map onto the shared request with the CLI's defaults and parsers."""

from __future__ import annotations

import pytest

from filter_lib.design import design
from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.cli_aliases import (
    DEFAULT_COMPONENTS,
    DEFAULT_ESERIES,
    DEFAULT_IMPEDANCE,
    DEFAULT_RESONATORS,
    DEFAULT_RIPPLE_DB,
)
from filter_lib.shared.inductor_suggestion import INDUCTOR_DETAILS, SUGGESTIONS_NOT_USED
from filter_lib.web.form_parsing import form_defaults, parse_design_form


def test_blank_fields_take_the_cli_defaults():
    parsed = parse_design_form("lowpass", {"frequency": "10MHz", "components": " ", "ripple": ""})

    request = parsed.request
    assert (request.filter_type, request.topology) == ("butterworth", "pi")
    assert request.impedance == float(DEFAULT_IMPEDANCE)
    assert request.order == DEFAULT_COMPONENTS
    assert request.ripple_db == DEFAULT_RIPPLE_DB
    assert request.run_build_analysis is False
    assert request.eseries == DEFAULT_ESERIES
    assert parsed.options.output_format == "table"
    assert (request.inductor_suggestions, request.build_inductors) == ("best", "auto")
    assert parsed.svg_plot is False


def test_bandpass_defaults_and_aliases():
    parsed = parse_design_form(
        "bandpass",
        {"filter_type": "ch", "frequency": "14MHz", "bandwidth": "500kHz", "ripple": "1"},
    )

    assert parsed.request.filter_type == "chebyshev"
    assert parsed.request.topology == "top"
    assert parsed.request.order == DEFAULT_RESONATORS
    assert parsed.request.bandwidth_hz == 500e3


def test_band_edges_set_center_width_and_requested_edges():
    parsed = parse_design_form(
        "bandpass", {"band_spec": "edges", "f_low": "14MHz", "f_high": "14.35MHz", "frequency": "x"}
    )

    request = parsed.request
    assert (request.requested_f_low_hz, request.requested_f_high_hz) == (14e6, 14.35e6)
    assert request.bandwidth_hz == pytest.approx(0.35e6)
    assert request.frequency_hz == pytest.approx((14e6 * 14.35e6) ** 0.5)


@pytest.mark.parametrize("detail", INDUCTOR_DETAILS)
def test_inductor_suggestion_choices_map_to_the_request(detail):
    form = {"frequency": "1MHz", "inductor_suggestions": detail}

    assert parse_design_form("highpass", form).request.inductor_suggestions == detail


@pytest.mark.parametrize("value", ["on", "true", "1", "yes", "ON"])
def test_checked_boxes_are_recognized(value):
    parsed = parse_design_form("lowpass", {"frequency": "1MHz", "raw": value, "svg_plot": value})

    assert parsed.options.raw and parsed.svg_plot


def test_build_fields_are_ignored_until_the_build_section_is_enabled():
    form = {
        "frequency": "1MHz",
        "build_inductor_tolerance_pct": "not a number",
        "eseries": "E96",
        "build_inductors": "toroid",
    }

    parsed = parse_design_form("lowpass", form)

    assert parsed.request.run_build_analysis is False
    assert parsed.request.eseries == "E96"
    assert parsed.request.realization == BuildConfig()
    assert parsed.request.build_inductors == "auto"


def test_build_fields_follow_make_build_config():
    form = {
        "frequency": "10MHz",
        "eseries": "E12",
        "sim_build": "on",
        "capacitor_tolerance_pct": "2",
        "build_inductor_tolerance_pct": "",
        "build_inductor_q": "150",
        "build_source_resistance": "1k",
        "build_reference_frequency": "5MHz",
        "build_sample_count": "4",
        "build_seed": "9",
        "build_grid_points": "201",
        "build_inductors": "calculated",
    }

    request = parse_design_form("lowpass", form).request

    assert (request.eseries, request.run_build_analysis) == ("E12", True)
    assert request.build_inductors == "calculated"
    assert request.capacitor_tolerance_pct == 2.0
    assert request.realization == BuildConfig(
        inductor_tolerance_pct=None,
        inductor_q=150.0,
        source_resistance_ohm=1000.0,
        reference_frequency_hz=5e6,
        sample_count=4,
        seed=9,
        grid_points=201,
    )


def test_no_inductor_suggestions_also_leave_them_out_of_the_build():
    form = {"frequency": "10MHz", "sim_build": "on", "inductor_suggestions": "none"}
    request = parse_design_form("lowpass", form).request

    inductors = design(request).parts.inductors.values()

    assert (request.inductor_suggestions, request.build_inductors) == ("none", "auto")
    assert inductors
    assert all(part.build_pick is None for part in inductors)
    assert {part.build_status for part in inductors} == {SUGGESTIONS_NOT_USED}


@pytest.mark.parametrize("category", ["lowpass", "highpass", "bandpass"])
def test_fresh_form_defaults_parse_into_a_valid_design(category):
    defaults = form_defaults(category)

    parsed = parse_design_form(category, defaults)

    assert parsed.svg_plot is True
    assert parsed.request.eseries == DEFAULT_ESERIES
    assert defaults["impedance"] == DEFAULT_IMPEDANCE


def test_unknown_category_is_rejected():
    with pytest.raises(ValueError, match="^Unknown filter category$"):
        form_defaults("notch")
