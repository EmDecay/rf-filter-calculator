"""Form fields map onto the shared request with the CLI's defaults and parsers."""

from __future__ import annotations

import pytest

from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.cli_aliases import (
    DEFAULT_COMPONENTS,
    DEFAULT_ESERIES,
    DEFAULT_IMPEDANCE,
    DEFAULT_RESONATORS,
    DEFAULT_RIPPLE_DB,
)
from filter_lib.web.form_parsing import form_defaults, parse_design_form


def test_blank_fields_take_the_cli_defaults():
    parsed = parse_design_form("lowpass", {"frequency": "10MHz", "components": " ", "ripple": ""})

    request = parsed.request
    assert (request.filter_type, request.topology) == ("butterworth", "pi")
    assert request.impedance == float(DEFAULT_IMPEDANCE)
    assert request.order == DEFAULT_COMPONENTS
    assert request.ripple_db == DEFAULT_RIPPLE_DB
    assert request.build is None
    assert parsed.options.eseries == DEFAULT_ESERIES
    assert parsed.options.output_format == "table"
    assert (parsed.options.include_toroids, parsed.options.toroid_full) == (True, False)
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


@pytest.mark.parametrize(
    "toroids, include, compact, full",
    [
        ("best", True, False, False),
        ("full", True, False, True),
        ("compact", True, True, False),
        ("none", False, False, False),
    ],
)
def test_toroid_choices_map_to_render_options(toroids, include, compact, full):
    options = parse_design_form("highpass", {"frequency": "1MHz", "toroids": toroids}).options

    assert (options.include_toroids, options.toroid_compact, options.toroid_full) == (
        include,
        compact,
        full,
    )


@pytest.mark.parametrize("value", ["on", "true", "1", "yes", "ON"])
def test_checked_boxes_are_recognized(value):
    parsed = parse_design_form("lowpass", {"frequency": "1MHz", "raw": value, "svg_plot": value})

    assert parsed.options.raw and parsed.svg_plot


def test_build_fields_are_ignored_until_the_build_section_is_enabled():
    form = {"frequency": "1MHz", "build_capacitor_tolerance_pct": "not a number", "eseries": "E96"}

    parsed = parse_design_form("lowpass", form)

    assert parsed.request.build is None
    assert parsed.spice_config == BuildConfig(eseries="E96")


def test_build_fields_follow_make_build_config():
    form = {
        "frequency": "10MHz",
        "eseries": "E12",
        "sim_build": "on",
        "build_capacitor_tolerance_pct": "2",
        "build_inductor_tolerance_pct": "",
        "build_inductor_q": "150",
        "build_source_resistance": "1k",
        "build_reference_frequency": "5MHz",
        "build_sample_count": "4",
        "build_seed": "9",
        "build_grid_points": "201",
        "toroid_build": "off",
    }

    config = parse_design_form("lowpass", form).request.build

    assert config == BuildConfig(
        eseries="E12",
        capacitor_tolerance_pct=2.0,
        inductor_tolerance_pct=10.0,
        inductor_q=150.0,
        source_resistance_ohm=1000.0,
        reference_frequency_hz=5e6,
        sample_count=4,
        seed=9,
        grid_points=201,
        use_toroid_candidates=False,
    )


def test_no_toroids_also_disables_toroid_substitution():
    form = {"frequency": "10MHz", "sim_build": "on", "toroids": "none"}

    assert parse_design_form("lowpass", form).request.build.use_toroid_candidates is False


@pytest.mark.parametrize("category", ["lowpass", "highpass", "bandpass"])
def test_fresh_form_defaults_parse_into_a_valid_design(category):
    defaults = form_defaults(category)

    parsed = parse_design_form(category, defaults)

    assert parsed.svg_plot is True
    assert parsed.options.eseries == DEFAULT_ESERIES
    assert defaults["impedance"] == DEFAULT_IMPEDANCE


def test_unknown_category_is_rejected():
    with pytest.raises(ValueError, match="^Unknown filter category$"):
        form_defaults("notch")
