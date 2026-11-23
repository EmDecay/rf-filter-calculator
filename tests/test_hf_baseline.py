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


def test_the_peak_fix_explains_a_change_only_where_recomputing_shows_it():
    """Kind (f) needs the item recorded under the old peak rule to differ from the new one;
    an ideal band-pass measurement may change by (f) alone."""
    design = next(item for item in tool.designs() if item.case_id == "bp-bw-top-1.9MHz-50kHz-n3")
    before = {"f_low_hz": 1.0, "f_high_hz": 2.0, "worst_design_passband_gain_db": -3.0}
    after = {**before, "f_low_hz": 1.1}
    worse = {**before, "worst_design_passband_gain_db": -300.0}

    fixed = tool.classify(
        design, "build_calculated", before, after, {}, {}, {"build_calculated": before}
    )
    assert fixed[0] == ["f"]
    # Recomputing under the old rule gives the same regression: the fix did not cause it.
    assert (
        tool.classify(
            design, "build_calculated", before, worse, {}, {}, {"build_calculated": worse}
        )[0]
        == []
    )
    assert tool.classify(design, "build_calculated", before, after, {}, {}, None)[0] == []


def test_a_capacitor_change_explains_only_that_capacitor_s_rows():
    design = next(item for item in tool.designs() if item.case_id == "hp-ch-pi-28MHz-n9")
    before = [["L1", "1", "0", 1e-7], ["L2", "2", "0", 1e-7], ["C1", "1", "2", 1e-11]]
    # A real chip substitution, a changed C1, and L2 removed.
    after = [["L1", "1", "0", 9.97e-8], ["CSELF_L1", "1", "0", 7.8e-14], ["C1", "1", "2", 1.1e-11]]
    changes = {"capacitor:E24:C1": ({"parts": [1e-11]}, {"parts": [1.1e-11]})}

    assert tool.classify(design, "spice_nominal", before, after, changes, {})[0] == []
    kept = [*after[:2], ["L2", "2", "0", 1e-7], after[2]]
    assert sorted(tool.classify(design, "spice_nominal", before, kept, changes, {})[0]) == [
        "a",
        "b",
        "c",
    ]


def test_a_capacitor_change_must_be_its_recorded_parts_and_a_stray_a_pair_s():
    design = next(item for item in tool.designs() if item.case_id == "hp-ch-pi-28MHz-n9")
    before = [["L1", "1", "0", 1e-7], ["C1", "1", "2", 1e-11]]
    changes = {"capacitor:E24:C1": ({"parts": [1e-11]}, {"parts": [1.1e-11]})}

    def kinds(after, recorded=changes):
        return tool.classify(design, "spice_nominal", before, after, recorded, {})[0]

    assert kinds([["L1", "1", "0", 1e-7], ["C1", "1", "2", 1.1e-11]]) == ["a"]
    assert kinds([["L1", "1", "0", 1e-7]]) == []  # deleted
    assert kinds([["L1", "1", "0", 1e-7], ["C1", "1", "0", 1.1e-11]]) == []  # moved
    assert kinds([["L1", "1", "0", 1e-7], ["C1", "1", "2", 1.2e-11]]) == []  # other value
    # A stray must be the assumed 0.2 pF across a pair of the same capacitor.
    pair = [["L1", "1", "0", 1e-7], ["C1A", "1", "2", 4.7e-12], ["C1B", "1", "2", 5.6e-12]]
    pair_changes = {"capacitor:E24:C1": ({"parts": [1e-11]}, {"parts": [4.7e-12, 5.6e-12]})}
    assert sorted(kinds([*pair, ["CSTRAY_C1", "1", "2", 2e-13]], pair_changes)) == ["a", "c"]
    assert kinds([*before, ["CSTRAY_L1", "1", "0", 1.0]], {}) == []


def test_a_trimmer_split_explains_only_its_own_tanks_rows():
    design = next(item for item in tool.designs() if item.case_id == "bp-bs-top-21.2MHz-500kHz-n3")
    splits = tool.split_rows(design)
    others = [["LT1", "1", "0", 3.6e-7], ["CK1", "1", "2", 6.2e-12], ["COUT", "3", "5", 1.5e-11]]
    untrimmed = [[tank, tank.removeprefix("CT"), "0", 1.2e-10] for tank in sorted(splits)]
    trimmed = [row for tank in sorted(splits) for row in splits[tank]]
    before = {"spice_nominal": [*untrimmed, *others]}

    def kinds(rows):
        actual = {"spice_nominal": rows}
        return tool._classify_with_trimmers(design, "spice_nominal", {}, actual, before, {}, None)[
            0
        ]

    assert splits and kinds([*trimmed, *others]) == ["d"]
    tank_rows = splits["CT1"]
    fixed = next(row for row in tank_rows if row[0].startswith("CT1"))
    trimmer = next(row for row in tank_rows if row[0] == "CTRIM_CT1")
    inductance = next(row for row in tank_rows if row[0] == "LTRIM_CT1")
    stray = next(row for row in tank_rows if row[0] == "CSTRAY_CT1")

    def without(*rows):
        return [row for row in trimmed if row not in rows]

    def replacing(row, replacement):
        return [replacement if item is row else item for item in trimmed]

    # Adding trimmers does not explain a removed end capacitor ...
    assert kinds([*trimmed, *others[:-1]]) == []
    # ... nor a trimmer moved to ground without its series inductance ...
    assert (
        kinds([*without(trimmer, inductance), ["CTRIM_CT1", "0", "0", trimmer[3]], *others]) == []
    )
    # ... nor a trimmer on another tank's node ...
    assert kinds([*replacing(trimmer, ["CTRIM_CT1", "2", *trimmer[2:]]), *others]) == []
    # ... nor a missing fixed part or stray, a changed series inductance, or an extra part.
    assert kinds([*without(fixed), *others]) == []
    assert kinds([*without(stray), *others]) == []
    assert kinds([*replacing(inductance, [*inductance[:3], 100.0]), *others]) == []
    assert kinds([*trimmed, ["CT1Z", "1", "0", 1.0], *others]) == []
    # A tank the build does not split is not explained either.
    assert kinds([*without(*tank_rows), ["CT1", "1", "0", 1.2e-10], *others]) == []
