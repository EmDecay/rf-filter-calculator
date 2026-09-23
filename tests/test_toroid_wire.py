"""Toroid wire gauge, winding length, DC resistance, and winding-capacity screening."""

import dataclasses

import pytest

from filter_lib.shared.toroid_core_data import get_core, list_cores
from filter_lib.shared.toroid_wire import (
    awg_to_diameter_mm,
    dc_resistance_ohms,
    default_awg_for_core,
    fit_wire,
    max_turns,
    wire_length_mm,
)


@pytest.mark.parametrize(
    ("awg", "expected_mm", "tol"),
    [
        (0, 8.251, 0.001),
        (10, 2.588, 0.001),
        (20, 0.8118, 0.0001),
        (22, 0.6438, 0.0001),
        (30, 0.2546, 0.0001),
        (36, 0.127, 1e-12),  # defining anchor of the AWG scale
        (40, 0.0799, 0.0001),
        (50, 0.02505, 0.00001),
    ],
)
def test_awg_diameter_matches_standard_wire_table(awg, expected_mm, tol):
    assert awg_to_diameter_mm(awg) == pytest.approx(expected_mm, abs=tol)


def test_t50_2_ten_turns_awg22_wire_length_hand_calculation():
    """Per turn: 2π·r_wire + 2·H + (OD − ID) = 2π·0.3219 + 9.66 + 5.0 = 16.683 mm.

    Ten turns: 166.83 mm radially; circumferential advance π·(OD + ID)/2 =
    32.04 mm; √(166.83² + 32.04²) = 169.88 mm.
    """
    assert wire_length_mm(get_core("T50-2"), 10, 22) == pytest.approx(169.875, abs=0.01)


def test_t68_2_twelve_turns_awg14_wire_length_hand_calculation():
    """Per turn: 2π·0.8139 + 2·4.83 + (17.5 − 9.4) = 22.874 mm; twelve turns 274.48 mm.

    Circumferential advance π·(17.5 + 9.4)/2 = 42.25 mm; √(274.48² + 42.25²) = 277.72 mm.
    """
    assert wire_length_mm(get_core("T68-2"), 12, 14) == pytest.approx(277.717, abs=0.01)


def test_wire_length_uses_a_supplied_datasheet_diameter():
    """The T68-2 datasheet lists AWG 14 at 1.600 mm, not the formula's 1.628 mm.

    Per turn: 2π·0.800 + 2·4.83 + (17.5 − 9.4) = 22.787 mm; twelve turns 273.44 mm;
    √(273.44² + 42.25²) = 276.68 mm.
    """
    length = wire_length_mm(get_core("T68-2"), 12, 14, wire_diameter_mm=1.6)

    assert length == pytest.approx(276.684, abs=0.01)


@pytest.mark.parametrize("diameter", [0.0, -1.0, float("nan"), float("inf"), True, "1.6"])
def test_wire_length_rejects_invalid_wire_diameter(diameter):
    with pytest.raises(ValueError, match="wire_diameter_mm must be positive and finite"):
        wire_length_mm(get_core("T68-2"), 12, 14, wire_diameter_mm=diameter)


def test_copper_dc_resistance_per_metre_of_awg22():
    """ρ/A = 1.724e-8 Ω·m / (π·(0.32190e-3 m)²) = 52.96 mΩ/m at 20 °C.

    IACS annealed copper is the basis of the standard AWG table, which also lists 52.96 mΩ/m.
    """
    assert dc_resistance_ohms(1000.0, 22) == pytest.approx(0.052959, rel=1e-4)
    assert dc_resistance_ohms(0.0, 22) == 0.0


def test_published_single_layer_fit_reports_gauge_length_and_scaled_dcr():
    """T68-2 datasheet: AWG 14 holds 12 single-layer turns at 2.4 mΩ."""
    fit = fit_wire(get_core("T68-2"), 12)

    assert fit.awg == 14
    assert fit.wire_diameter_mm == 1.6  # published metric diameter for the row
    assert (fit.n_max, fit.single_layer_capacity, fit.full_winding_capacity) == (12, 12, 12)
    assert fit.fits is True
    assert fit.capacity_status == "manufacturer_single_layer"
    assert fit.winding_style == "single_layer"
    assert fit.capacity_source_id == "micrometals-t68-2-datasheet"
    # Length uses the reported 1.600 mm datasheet diameter (see the hand calculation above).
    assert fit.wire_length_mm == pytest.approx(276.684, abs=0.01)
    assert fit.dc_resistance_ohm == pytest.approx(0.0024)
    assert fit.dcr_method == "manufacturer_table_scaled_by_turn_count"


@pytest.mark.parametrize(
    ("turns", "awg", "status", "fits", "dcr_ohm"),
    [
        # Thickest single-layer rows: AWG 16 holds 12 turns, AWG 20 holds 20.
        (10, 16, "manufacturer_single_layer", True, 0.0032 * 10 / 12),
        (17, 20, "manufacturer_single_layer", True, 0.0135 * 17 / 20),
        # No single-layer row holds 200 turns; AWG 30 is the thickest full winding (259).
        (200, 30, "manufacturer_full_winding", True, 1.8 * 200 / 259),
        # Beyond every published row (max 962 turns of AWG 36): exceeded, not a fit.
        (1000, 36, "manufacturer_exceeded", False, 26.6 * 1000 / 962),
    ],
)
def test_published_table_selects_thickest_wire_that_holds_the_turns(
    turns, awg, status, fits, dcr_ohm
):
    fit = fit_wire(get_core("T50-2"), turns)

    assert (fit.awg, fit.capacity_status, fit.fits) == (awg, status, fits)
    assert fit.dc_resistance_ohm == pytest.approx(dcr_ohm)
    assert fit.capacity_source_id == "micrometals-t50-2-datasheet"


@pytest.mark.parametrize(
    ("turns", "status", "fits"),
    [
        (13, "manufacturer_single_layer", True),
        (14, "manufacturer_full_winding", True),
        (15, "manufacturer_full_winding", True),
        (16, "manufacturer_exceeded", False),
    ],
)
def test_explicit_published_gauge_uses_manufacturer_capacity_boundaries(turns, status, fits):
    """T25-6 datasheet, AWG 26: 13 single-layer turns, 15 full-winding turns."""
    core = get_core("T25-6")

    fit = fit_wire(core, turns, awg=26)

    assert max_turns(core, 26) == 15
    assert (fit.awg, fit.capacity_status, fit.fits) == (26, status, fits)


def test_explicit_published_gauge_scales_the_matching_table_row():
    fit = fit_wire(get_core("T50-2"), 10, awg=24)  # AWG 24: 32 turns at 54.6 mΩ

    assert (fit.awg, fit.capacity_status, fit.n_max) == (24, "manufacturer_single_layer", 70)
    assert fit.dc_resistance_ohm == pytest.approx(0.0546 * 10 / 32)


def test_unpublished_gauge_on_sourced_core_falls_back_to_labeled_estimate():
    """T50-2 publishes even gauges only, so AWG 23 (0.5733 mm) gets a geometry estimate.

    Capacity: 0.9 fill of π·7.7 mm by 1.07 × 0.5733 mm enamelled wire = 35.5 -> 35 turns.
    Length: √((10·(2π·0.2867 + 9.66 + 5.0))² + 32.04²) = 167.70 mm of copper, so
    DCR = 1.724e-8 Ω·m × 0.16770 m / (π·(0.2867e-3 m)²) = 11.20 mΩ.
    """
    fit = fit_wire(get_core("T50-2"), 10, awg=23)

    assert (fit.awg, fit.n_max, fit.fits) == (23, 35, True)
    assert fit.capacity_status == "estimated"
    assert fit.capacity_source_id is None
    assert fit.dcr_method == "geometry_estimate"
    assert fit.wire_length_mm == pytest.approx(167.70, abs=0.01)
    assert fit.dc_resistance_ohm == pytest.approx(0.011196, rel=1e-3)
    assert max_turns(get_core("T50-2"), 22) == 45  # published row wins over geometry


def test_legacy_core_capacity_is_an_estimate_with_the_family_default_gauge():
    """T25-2 (ID 3.05 mm), default AWG 26 (0.4049 mm): 0.9·π·3.05 / (1.07·0.4049) = 19.9."""
    core = get_core("T25-2")

    fit = fit_wire(core, 30)

    assert (fit.awg, fit.n_max, fit.fits) == (26, 19, False)
    assert (fit.capacity_status, fit.winding_style) == ("estimated", "estimated_single_layer")
    assert fit.capacity_source_id is None
    assert fit.full_winding_capacity is None


@pytest.mark.parametrize(("turns", "fits"), [(41, True), (42, False)])
def test_estimated_capacity_is_an_inclusive_limit_that_pins_the_enamel_allowance(turns, fits):
    """T80-2 (ID 12.6 mm), AWG 20 (0.8118 mm): 0.9·π·12.6 / (1.07·0.8118) = 41.01 -> 41.

    The estimate sits just above 41, so a 1 % larger enamel allowance would give 40.
    """
    fit = fit_wire(get_core("T80-2"), turns)

    assert (fit.awg, fit.n_max, fit.capacity_status) == (20, 41, "estimated")
    assert fit.fits is fits


def test_every_catalog_core_has_a_default_gauge():
    for core in list_cores():
        assert 14 <= default_awg_for_core(core) <= 26, core.name


def test_unknown_core_family_has_no_default_gauge():
    unknown_family = dataclasses.replace(get_core("T37-2"), name="T12-2")

    with pytest.raises(ValueError, match="No default AWG known for family 'T12'"):
        default_awg_for_core(unknown_family)


@pytest.mark.parametrize("awg", [-1, 51, True, 20.5, "20", None])
def test_wire_helpers_require_integer_awg_in_range(awg):
    core = get_core("T50-2")
    with pytest.raises(ValueError, match="AWG out of range"):
        awg_to_diameter_mm(awg)
    with pytest.raises(ValueError, match="AWG out of range"):
        max_turns(core, awg)
    with pytest.raises(ValueError, match="AWG out of range"):
        wire_length_mm(core, 10, awg)
    with pytest.raises(ValueError, match="AWG out of range"):
        dc_resistance_ohms(100, awg)
    if awg is not None:  # None intentionally selects the published/default gauge.
        with pytest.raises(ValueError, match="AWG out of range"):
            fit_wire(core, 10, awg)


@pytest.mark.parametrize("turns", [0, -1, True, 1.5, "10", None])
def test_wire_helpers_require_positive_integer_turns(turns):
    core = get_core("T50-2")
    with pytest.raises(ValueError, match="^n must be a positive integer$"):
        wire_length_mm(core, turns, 20)
    with pytest.raises(ValueError, match="^n_turns must be a positive integer$"):
        fit_wire(core, turns)


@pytest.mark.parametrize("length", [-1.0, True, "100", None, float("inf"), float("nan")])
def test_dc_resistance_requires_nonnegative_finite_length(length):
    with pytest.raises(ValueError, match="length_mm must be non-negative and finite"):
        dc_resistance_ohms(length, 20)


@pytest.mark.parametrize(
    ("function", "args"),
    [
        (wire_length_mm, (10, 20)),
        (fit_wire, (10,)),
        (max_turns, (20,)),
        (default_awg_for_core, ()),
    ],
)
def test_wire_helpers_reject_invalid_core_type(function, args):
    with pytest.raises(ValueError, match="core must be a ToroidCore"):
        function("T50-2", *args)
