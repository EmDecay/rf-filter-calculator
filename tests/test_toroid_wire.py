"""Tests for toroid wire/mechanical module (Phase 3)."""

import pytest

from filter_lib.shared.toroid_core_data import get_core
from filter_lib.shared.toroid_wire import (
    MechanicalFit,
    awg_to_diameter_mm,
    dc_resistance_ohms,
    default_awg_for_core,
    fit_wire,
    max_turns,
    wire_length_mm,
)


@pytest.mark.parametrize(
    "awg,expected_mm,tol",
    [
        (10, 2.588, 0.005),
        (20, 0.8118, 0.002),
        (22, 0.6438, 0.002),
        (30, 0.2546, 0.002),
        (40, 0.0799, 0.002),
    ],
)
def test_awg_to_diameter_mm(awg, expected_mm, tol):
    assert awg_to_diameter_mm(awg) == pytest.approx(expected_mm, abs=tol)


def test_awg_out_of_range_low():
    with pytest.raises(ValueError):
        awg_to_diameter_mm(-1)


def test_awg_out_of_range_high():
    with pytest.raises(ValueError):
        awg_to_diameter_mm(51)


def test_default_awg_for_each_family():
    """Every non-anomaly family has a default AWG."""
    for family_core in ("T25-2", "T37-2", "T50-2", "T68-2", "T80-2", "T106-2", "T200-2"):
        awg = default_awg_for_core(get_core(family_core))
        assert 10 <= awg <= 30


def test_t50_2_n10_awg22_wire_length():
    """T50-2 N=10 AWG22 ≈ 170 mm.

    Analytic: cross/turn = 2π·0.3219 + 2·4.83 + (12.7 − 7.7) = 16.68 mm,
    ×10 turns = 166.8 mm; axial = π·(12.7+7.7)/2 = 32.04 mm;
    √(166.8² + 32.04²) ≈ 169.9 mm.
    """
    length = wire_length_mm(get_core("T50-2"), 10, 22)
    assert 169 <= length <= 171


def test_t50_2_n10_awg22_dcr():
    """T50-2 N=10 AWG22 DCR ≈ 8.8 mOhm (169.9 mm of AWG22 copper at 20 C)."""
    length = wire_length_mm(get_core("T50-2"), 10, 22)
    r = dc_resistance_ohms(length, 22)
    assert 0.008 <= r <= 0.009


def test_wire_length_n_zero_raises():
    with pytest.raises(ValueError):
        wire_length_mm(get_core("T50-2"), 0, 22)


def test_dc_resistance_negative_length_raises():
    with pytest.raises(ValueError):
        dc_resistance_ohms(-1, 22)


def test_t25_2_n30_does_not_fit():
    """T25 is tiny (ID=3.05 mm); AWG 26 cannot fit 30 turns single-layer."""
    m = fit_wire(get_core("T25-2"), 30)
    assert m.fits is False


def test_t25_6_awg26_uses_manufacturer_capacity_not_geometry_guess():
    core = get_core("T25-6")

    assert max_turns(core, 26) == 15
    assert fit_wire(core, 14, awg=26).capacity_status == "manufacturer_full_winding"
    assert fit_wire(core, 16, awg=26).capacity_status == "manufacturer_exceeded"


def test_sourced_table_selects_thickest_single_layer_wire_that_fits():
    fit = fit_wire(get_core("T50-2"), 17)

    assert fit.awg == 20
    assert fit.capacity_status == "manufacturer_single_layer"
    assert fit.capacity_source_id == "micrometals-t50-2-datasheet"


def test_unsourced_capacity_is_labeled_estimated():
    fit = fit_wire(get_core("T37-2"), 10)

    assert fit.capacity_status == "estimated"
    assert fit.capacity_source_id is None


def test_t200_2_has_plenty_of_room():
    """T200-2 AWG 22 should fit at least 100 turns."""
    assert max_turns(get_core("T200-2"), 22) >= 100


def test_fit_wire_default_awg_applied():
    """fit_wire uses the thickest published single-layer gauge that fits."""
    m = fit_wire(get_core("T50-2"), 10)
    assert m.awg == 16


def test_fit_wire_explicit_awg():
    """Caller can override the default AWG."""
    m = fit_wire(get_core("T50-2"), 10, awg=24)
    assert m.awg == 24


def test_fit_wire_result_shape():
    """MechanicalFit carries every expected field."""
    m = fit_wire(get_core("T50-2"), 10)
    assert isinstance(m, MechanicalFit)
    assert m.wire_length_m == pytest.approx(m.wire_length_mm * 1e-3)
    assert m.dc_resistance_ohm > 0
    assert m.n_max > 0


def test_max_turns_prefers_published_capacity_over_geometry_estimate():
    import math

    c = get_core("T50-2")
    awg = 22
    d_insulated = awg_to_diameter_mm(awg) * 1.07
    theoretical = math.pi * c.id_mm / d_insulated
    assert max_turns(c, awg) == 45
    assert max_turns(c, awg) != pytest.approx(theoretical * 0.9, abs=1)


@pytest.mark.parametrize("awg", [True, 20.5, "20", None])
def test_wire_helpers_require_integer_awg(awg):
    core = get_core("T50-2")
    with pytest.raises(ValueError):
        awg_to_diameter_mm(awg)
    with pytest.raises(ValueError):
        max_turns(core, awg)
    with pytest.raises(ValueError):
        wire_length_mm(core, 10, awg)
    with pytest.raises(ValueError):
        dc_resistance_ohms(100, awg)
    if awg is not None:  # None intentionally selects the default/published gauge.
        with pytest.raises(ValueError):
            fit_wire(core, 10, awg)


@pytest.mark.parametrize("turns", [True, 1.5, "10", None])
def test_wire_helpers_require_positive_integer_turns(turns):
    core = get_core("T50-2")
    with pytest.raises(ValueError, match="positive integer"):
        wire_length_mm(core, turns, 20)
    with pytest.raises(ValueError, match="positive integer"):
        fit_wire(core, turns)


@pytest.mark.parametrize("length", [True, "100", None, float("inf"), float("nan")])
def test_dc_resistance_requires_nonnegative_finite_length(length):
    with pytest.raises(ValueError, match="non-negative and finite"):
        dc_resistance_ohms(length, 20)


@pytest.mark.parametrize("function,args", [(wire_length_mm, (10, 20)), (fit_wire, (10,))])
def test_wire_helpers_reject_invalid_core_type(function, args):
    with pytest.raises(ValueError, match="ToroidCore"):
        function("T50-2", *args)
