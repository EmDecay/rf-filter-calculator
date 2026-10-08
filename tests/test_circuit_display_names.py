"""Readable bandpass part names in build text and the SPICE name map."""

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.circuit_display_names import display_component_name, format_name_list
from filter_lib.shared.eseries import MatchPolicy
from filter_lib.shared.spice_export import export_spice_deck


@pytest.mark.parametrize(
    "circuit_name, table_name",
    [
        ("CT1", "Cp1"),
        ("LT3", "L3"),
        ("CK1", "Cs12"),
        ("CK2", "Cs23"),
        ("CIN", "Ce_in"),
        ("COUT", "Ce_out"),
        ("CK1A", "Cs12 (part A)"),
        ("COUTB", "Ce_out (part B)"),
        # Low-pass and high-pass names already match their table.
        ("C1", "C1"),
        ("L2", "L2"),
        ("C3A", "C3A"),
    ],
)
def test_circuit_names_map_to_component_table_names(circuit_name, table_name):
    assert display_component_name(circuit_name) == table_name


@pytest.mark.parametrize(
    "names, joined",
    [
        (["L1", "L2"], "L1, L2"),
        (["L1", "L2", "L3"], "L1–L3"),
        (["L1", "L3"], "L1, L3"),
        (["Cs12", "Cs23", "Ce_in", "Ce_out"], "Cs12, Cs23, Ce_in, Ce_out"),
        (["C1", "C2", "C3", "L1"], "C1–C3, L1"),
        (["C1", "C1"], "C1"),
    ],
)
def test_name_lists_collapse_three_or_more_consecutive_parts(names, joined):
    assert format_name_list(names) == joined


def _deck_element_names(deck: str) -> list[str]:
    return [
        line.split()[0]
        for line in deck.splitlines()
        if line[:1].isalpha() and not line.startswith(("VINPUT", "RSOURCE", "RLOAD", "RLOSS"))
    ]


@pytest.mark.parametrize("realization", ["exact", "nominal_build"])
def test_bandpass_deck_maps_every_element_name_once(realization):
    result = calculate_bandpass_filter(10e6, 0.5e6, 50.0, 3, "butterworth", "top")

    deck = export_spice_deck(result, "bandpass", realization=realization)

    (names_line,) = [line for line in deck.splitlines() if line.startswith("* names: ")]
    mapped = [
        name
        for pair in names_line.removeprefix("* names: ").split()
        for name in pair.split("=")[0].split("+")
    ]
    assert sorted(mapped) == sorted(_deck_element_names(deck))
    assert "CT1=Cp1" in names_line and "LT1=L1" in names_line and "COUT" in names_line


def test_parallel_sub_pf_parts_are_grouped_under_one_table_name():
    result = calculate_bandpass_filter(500e6, 10e6, 50.0, 3, "butterworth", "top")

    deck = export_spice_deck(
        result,
        "bandpass",
        realization="nominal_build",
        config=BuildConfig(match_policy=MatchPolicy(allow_sub_pf=True)),
    )

    assert "CK1A+CK1B=Cs12" in deck
    assert "\nCK1A " in deck and "\nCK1B " in deck


def test_ladder_deck_has_no_name_map():
    from filter_lib.lowpass.calculations import calculate_butterworth

    capacitors, inductors, order = calculate_butterworth(10e6, 50.0, 3, "pi")
    result = {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": capacitors,
        "inductors": inductors,
        "order": order,
        "topology": "pi",
    }

    assert "* names:" not in export_spice_deck(result, "lowpass", realization="nominal_build")
