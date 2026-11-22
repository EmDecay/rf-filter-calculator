"""HF output may change only in listed, permitted ways (see ``tests/hf_baseline_tool.py``).

Each corpus design is recalculated through the CLI and compared item by item with the
committed baseline. A changed item must appear in the allow-list with a reason, a
permitted kind that can explain a change to that item, and the reviewed new value it must
equal; a listed item must still change.
"""

from __future__ import annotations

import pytest

from tests import hf_baseline_tool as tool

CORPUS = tool.load_corpus()["designs"]
ALLOWED = tool.load_allowed()
DESIGNS = tool.designs()


def test_corpus_covers_every_design_and_dimension():
    assert [design.case_id for design in DESIGNS] == list(CORPUS)
    categories = {design.category for design in DESIGNS}
    assert categories == {"lowpass", "highpass", "bandpass"}
    orders = {design.argv[design.argv.index("-n") + 1] for design in DESIGNS}
    assert orders == {"3", "5", "9"}
    built = {design.build_series for design in DESIGNS if design.build_series}
    assert built == set(tool.SERIES)
    assert any(design.build_series is None for design in DESIGNS)
    for items in CORPUS.values():
        for series in tool.SERIES:
            assert any(item.startswith(f"capacitor:{series}:") for item in items)


def test_allow_list_entries_are_permitted_and_explained():
    cases = set(CORPUS)
    for (case_id, item), entry in ALLOWED.items():
        assert case_id in cases, case_id
        kinds = entry["kinds"]
        assert kinds, (case_id, item)
        permitted = tool.ITEM_KINDS.get(tool.item_type(item), frozenset())
        assert set(kinds) <= permitted, (case_id, item, kinds)
        assert entry["reason"].strip(), (case_id, item)


@pytest.mark.parametrize("design", DESIGNS, ids=[design.case_id for design in DESIGNS])
def test_hf_design_matches_baseline_or_allowed_change(design):
    changes = tool.changed_items(CORPUS[design.case_id], tool.record(design))
    unexplained = sorted(item for item in changes if (design.case_id, item) not in ALLOWED)
    assert not unexplained, {item: changes[item] for item in unexplained}
    # A listed item must equal the value reviewed for it, so no other change can hide in it.
    unreviewed = sorted(
        item
        for item, (_before, after) in changes.items()
        if not tool._same(item, ALLOWED[(design.case_id, item)]["after"], after)
    )
    assert not unreviewed, unreviewed
    stale = sorted(
        item for case_id, item in ALLOWED if case_id == design.case_id and item not in changes
    )
    assert not stale, f"listed changes that no longer happen: {stale}"


def test_a_chip_substitution_is_recognised_only_with_its_inductor_kept():
    """A CSELF_ branch explains a changed inductor only when that inductor stays on its
    terminals and the branch is across them; a removed inductor is never a chip."""
    design = next(item for item in tool.designs() if item.case_id == "hp-ch-pi-28MHz-n9")
    before = [["L1", "1", "0", 1e-7], ["C1", "1", "2", 1e-11]]
    chip = [["L1", "1", "0", 9.97e-8], ["CSELF_L1", "1", "0", 7.8e-14], ["C1", "1", "2", 1e-11]]
    removed = [["CSELF_L1", "99", "0", 1.0], ["C1", "1", "2", 1e-11]]
    moved = [["L1", "1", "0", 9.97e-8], ["CSELF_L1", "2", "0", 7.8e-14], ["C1", "1", "2", 1e-11]]
    # A real chip substitution beside an unrelated removal, and a "chip" across a capacitor.
    two = [["L1", "1", "0", 1e-7], ["L2", "2", "0", 1e-7], ["C1", "1", "2", 1e-11]]
    chip_and_removal = [
        ["L1", "1", "0", 9.97e-8],
        ["CSELF_L1", "1", "0", 7.8e-14],
        ["C1", "1", "2", 1e-11],
    ]
    capacitor = [["L1", "1", "0", 1e-7], ["C1", "1", "2", 1e-11], ["CSELF_C1", "1", "2", 1e-14]]

    kinds, reason = tool.classify(design, "spice_nominal", before, chip, {}, {})
    assert (kinds, reason) == (
        ["b", "c"],
        "inductors built as chip inductors with their self-capacitance (L1)",
    )
    for after in (removed, moved, capacitor):
        assert tool.classify(design, "spice_nominal", before, after, {}, {})[0] == []
    assert tool.classify(design, "spice_nominal", two, chip_and_removal, {}, {})[0] == []
