"""Tests for toroid core database (Phase 1)."""

import pytest

from filter_lib.shared.toroid_core_data import (
    ToroidCore,
    get_core,
    get_source,
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
    assert c.freq_min_hz == 2_000_000
    assert c.freq_max_hz == 30_000_000


def test_mix_2_guidance_has_primary_source_provenance():
    core = get_core("T50-2")

    assert core.provenance_status == "primary_verified"
    assert core.is_auto_selectable
    source = get_source(core.frequency_source_id)
    assert source.publisher == "Amidon Corp."
    assert source.url == "https://www.amidoncorp.com/2ipt/"
    assert source.accessed_on == "2026-07-19"


def test_mix_2_material_guidance_is_correct_even_for_legacy_core_records():
    mix_2_cores = [core for core in list_cores() if core.mix == "2"]

    assert mix_2_cores
    assert all(core.freq_min_hz == 2_000_000 for core in mix_2_cores)
    assert all(core.freq_max_hz == 30_000_000 for core in mix_2_cores)
    assert all(core.frequency_source_id == "amidon-mix-2-guidance" for core in mix_2_cores)
    assert sum(core.is_auto_selectable for core in mix_2_cores) == 2


def test_exact_core_datasheet_provenance_is_not_bulk_claimed():
    verified = get_core("T68-2")
    legacy = get_core("T37-2")

    assert verified.core_source_id == "micrometals-t68-2-datasheet"
    assert get_source(verified.core_source_id).source_type == "manufacturer_datasheet"
    assert legacy.provenance_status == "legacy_unverified"
    assert not legacy.is_auto_selectable


def test_t25_6_has_sourced_awg26_winding_capacity():
    core = get_core("T25-6")
    row = core.winding_spec_for_awg(26)

    assert row is not None
    assert row.single_layer_turns == 13
    assert row.full_winding_turns == 15
    assert core.winding_source_id == "micrometals-t25-6-datasheet"


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
