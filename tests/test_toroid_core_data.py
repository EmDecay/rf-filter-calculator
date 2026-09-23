"""Packaged iron-powder toroid catalog: provenance, eligibility, and lookups."""

from dataclasses import FrozenInstanceError

import pytest

from filter_lib.shared.toroid_core_data import (
    get_core,
    get_source,
    iter_auto_selectable_cores_for_frequency,
    iter_cores_for_frequency,
    list_cores,
)


def test_catalog_loads_every_record_sorted_by_outer_diameter():
    cores = list_cores()

    assert len(cores) == 43
    keys = [(core.od_mm, core.name) for core in cores]
    assert keys == sorted(keys)


def test_only_the_three_primary_verified_parts_are_auto_selectable():
    """Automatic selection is limited to exact parts checked against a datasheet."""
    assert {core.name for core in list_cores() if core.is_auto_selectable} == {
        "T25-6",
        "T50-2",
        "T68-2",
    }
    for name in ("T25-6", "T50-2", "T68-2"):
        core = get_core(name)
        assert core.provenance_status == "primary_verified"
        assert core.manufacturer == "Micrometals, Inc."
        assert core.manufacturer_part_number == name
        assert get_source(core.core_source_id).source_type == "manufacturer_datasheet"
        # Every eligible part carries a published winding table, so automatic
        # candidates never depend on the unsourced geometric capacity estimate.
        assert core.winding_table

    legacy = get_core("T37-2")
    assert legacy.provenance_status == "legacy_unverified"
    assert legacy.core_source_id == "legacy-research-snapshot"
    assert not legacy.is_auto_selectable


@pytest.mark.parametrize(
    ("name", "amidon_al_uh_per_100_turns", "dimensions_in"),
    [
        ("T25-6", 27, (0.255, 0.120, 0.096)),
        ("T50-2", 49, (0.500, 0.303, 0.190)),
        ("T68-2", 57, (0.690, 0.370, 0.190)),
    ],
)
def test_verified_core_data_matches_published_catalog_values(
    name, amidon_al_uh_per_100_turns, dimensions_in
):
    """A_L and OD/ID/height agree with the Amidon/Micrometals catalog tables.

    1 µH per 100 turns is 1e-6 H / 1e4 turns², i.e. 0.1 nH/turn².
    """
    core = get_core(name)

    assert core.al_nh_per_turn2 == pytest.approx(amidon_al_uh_per_100_turns / 10)
    assert core.al_tolerance_pct == 5.0
    assert (core.od_mm, core.id_mm, core.height_mm) == pytest.approx(
        tuple(inches * 25.4 for inches in dimensions_in), abs=0.03
    )


@pytest.mark.parametrize(
    ("freq_hz", "expected"),
    [
        (1.99e6, []),
        (2e6, ["T50-2", "T68-2"]),
        (9.99e6, ["T50-2", "T68-2"]),
        (10e6, ["T25-6", "T50-2", "T68-2"]),
        (30e6, ["T25-6", "T50-2", "T68-2"]),
        (30.01e6, ["T25-6"]),
        (50e6, ["T25-6"]),
        (50.01e6, []),
    ],
)
def test_auto_selectable_cores_follow_published_material_ranges(freq_hz, expected):
    """Amidon guidance: mix 2 covers 2–30 MHz and mix 6 covers 10–50 MHz, inclusive."""
    names = [core.name for core in iter_auto_selectable_cores_for_frequency(freq_hz)]

    assert names == expected


def test_mix_2_guidance_has_primary_source_provenance():
    source = get_source(get_core("T50-2").frequency_source_id)

    assert source.publisher == "Amidon Corp."
    assert source.url == "https://www.amidoncorp.com/2ipt/"
    assert source.accessed_on == "2026-07-19"


def test_material_guidance_overrides_legacy_ranges_for_every_mix_2_record():
    mix_2_cores = [core for core in list_cores() if core.mix == "2"]

    assert len(mix_2_cores) > 2  # legacy records share the material guidance
    for core in mix_2_cores:
        assert (core.freq_min_hz, core.freq_max_hz) == (2e6, 30e6), core.name
        assert core.frequency_source_id == "amidon-mix-2-guidance", core.name


@pytest.mark.parametrize(
    ("freq_hz", "expected_mixes"),
    [
        (5e6, {"2", "7"}),
        (100e6, {"0", "10", "17"}),
        (500e6, set()),
    ],
)
def test_inspectable_cores_are_filtered_by_their_recorded_material_range(freq_hz, expected_mixes):
    cores = list(iter_cores_for_frequency(freq_hz))

    assert {core.mix for core in cores} == expected_mixes
    assert all(core.freq_min_hz <= freq_hz <= core.freq_max_hz for core in cores)


def test_field_level_sources_separate_exact_part_and_material_data():
    sources = dict(get_core("T68-2").field_sources)

    assert sources["al"] == "micrometals-t68-2-datasheet"
    assert sources["dimensions"] == "micrometals-t68-2-datasheet"
    assert sources["temperature_coefficient"] == "micrometals-rf-materials"
    assert sources["frequency_guidance"] == "amidon-mix-2-guidance"
    assert "not_recorded" not in sources
    assert "al" not in dict(get_core("T37-2").field_sources)


def test_winding_table_lookup_returns_published_row_or_none():
    core = get_core("T25-6")
    row = core.winding_spec_for_awg(26)

    assert (row.single_layer_turns, row.full_winding_turns) == (13, 15)
    assert core.winding_source_id == "micrometals-t25-6-datasheet"
    assert core.winding_spec_for_awg(25) is None
    assert get_core("T37-2").winding_spec_for_awg(26) is None


def test_every_record_has_physical_geometry_and_resolvable_https_sources():
    for core in list_cores():
        assert 0 < core.id_mm < core.od_mm and core.height_mm > 0, core.name
        assert core.al_nh_per_turn2 > 0, core.name
        assert 0 < core.freq_min_hz <= core.freq_max_hz, core.name
        cited = {
            core.core_source_id,
            core.frequency_source_id,
            core.winding_source_id,
            *(source_id for _, source_id in core.field_sources),
        } - {None}
        assert all(get_source(sid).url.startswith("https://") for sid in cited), core.name


def test_legacy_records_keep_their_distinct_material_values():
    assert get_core("T37-17").temp_coeff_ppm_per_c == 50
    assert get_core("T50-1").al_tolerance_pct == 10.0


def test_core_family_strips_the_mix_suffix():
    assert get_core("T50-2").family == "T50"
    assert get_core("T200-2B").family == "T200"


def test_catalog_records_are_immutable():
    with pytest.raises(FrozenInstanceError):
        get_core("T50-2").al_nh_per_turn2 = 99.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("function", "args", "message"),
    [
        (get_core, ("NOPE",), "Unknown toroid core: 'NOPE'"),
        (get_core, (50,), "toroid core name must be a string"),
        (get_source, ("nope",), "Unknown toroid source: 'nope'"),
        (get_source, (None,), "Unknown toroid source: None"),
        (lambda freq: list(iter_cores_for_frequency(freq)), (0,), "freq_hz must be positive"),
        (get_core("T50-2").winding_spec_for_awg, (True,), r"awg must be an integer in \[0, 50\]"),
        (get_core("T50-2").winding_spec_for_awg, (51,), r"awg must be an integer in \[0, 50\]"),
    ],
    ids=[
        "unknown-core",
        "non-string-core",
        "unknown-source",
        "missing-source",
        "non-positive-frequency",
        "bool-awg",
        "out-of-range-awg",
    ],
)
def test_public_lookups_reject_invalid_input_with_value_error(function, args, message):
    with pytest.raises(ValueError, match=message):
        function(*args)
