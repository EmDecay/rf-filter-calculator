"""Tests for toroid core database (Phase 1)."""

import pytest

from filter_lib.shared.toroid_core_data import (
    ToroidCore,
    get_core,
    iter_cores_for_frequency,
    list_cores,
)


def test_loads_expected_count():
    """All 43 iron-powder T-series cores are loaded (plan said 42; actual is 43)."""
    assert len(list_cores()) == 43


def test_list_cores_sorted_by_od():
    """list_cores returns cores sorted by outer diameter ascending."""
    cores = list_cores()
    ods = [c.od_mm for c in cores]
    assert ods == sorted(ods)


def test_get_core_t50_2_al():
    """T50-2 canonical fixture: A_L=4.9 nH/turn^2."""
    c = get_core("T50-2")
    assert c.al_nh_per_turn2 == 4.9
    assert c.freq_min_hz == 250_000
    assert c.freq_max_hz == 10_000_000


def test_get_core_t37_17_temp_coeff():
    """T37-17 temperature coefficient is 50 ppm/C."""
    assert get_core("T37-17").temp_coeff_ppm_per_c == 50


def test_get_core_mix_1_has_wider_tolerance():
    """Mix 1 iron-powder has 10% tolerance (rest are 5%)."""
    assert get_core("T50-1").al_tolerance_pct == 10.0


def test_get_core_unknown_raises_value_error():
    """Unknown core name raises ValueError with the bad name."""
    with pytest.raises(ValueError, match="NOPE"):
        get_core("NOPE")


def test_iter_cores_for_frequency_hf():
    """5 MHz should match several HF cores, all covering that freq."""
    cores = list(iter_cores_for_frequency(5_000_000))
    assert len(cores) > 0
    for c in cores:
        assert c.freq_min_hz <= 5_000_000 <= c.freq_max_hz


def test_iter_cores_for_frequency_vhf():
    """100 MHz should match several VHF-capable cores."""
    cores = list(iter_cores_for_frequency(100_000_000))
    assert len(cores) > 0


def test_iter_cores_for_frequency_500mhz_empty():
    """500 MHz is beyond the iron-powder range (max 350 MHz for mix 0)."""
    cores = list(iter_cores_for_frequency(500_000_000))
    assert cores == []


def test_core_family_property():
    """ToroidCore.family strips the mix suffix."""
    assert get_core("T50-2").family == "T50"
    assert get_core("T200-2B").family == "T200"


def test_core_is_frozen():
    """ToroidCore dataclass is frozen (immutable)."""
    c = get_core("T50-2")
    with pytest.raises((AttributeError, Exception)):
        c.al_nh_per_turn2 = 99.0  # type: ignore[misc]


def test_all_cores_have_positive_dimensions():
    """Every core must have positive OD, ID, height, and A_L."""
    for c in list_cores():
        assert isinstance(c, ToroidCore)
        assert c.od_mm > 0
        assert c.id_mm > 0
        assert c.height_mm > 0
        assert c.al_nh_per_turn2 > 0
        assert 0 < c.id_mm < c.od_mm
