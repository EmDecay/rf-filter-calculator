"""Text, JSON, and CSV rendering of toroid winding suggestions.

The reference candidate is T68-2 wound for 0.8208 µH at 5 MHz: 12 turns of
AWG 14 (A_L 5.7 nH/turn² × 144), 276.7 mm of 1.600 mm wire, and 2.4 mΩ from the
datasheet's single-layer row, giving a wire-only ωL/DCR of 10,744.
"""

import dataclasses
import json

import pytest

from filter_lib.shared import toroid_selection
from filter_lib.shared.toroid_core_data import get_core
from filter_lib.shared.toroid_display import (
    CSV_TOROID_HEADER,
    build_json_recommendations,
    csv_columns_for_best,
    format_recommendation_block,
    format_recommendation_block_compact,
    format_winding_candidate_section,
    has_winding_suggestion,
    inductor_note_line,
)
from filter_lib.shared.toroid_selection import recommend_cores

T68_DATASHEET = "https://datasheets.micrometals.com/T68-2-DataSheet.pdf"
MIX_2_GUIDANCE = "https://www.amidoncorp.com/2ipt/"
NOT_ASSESSED_WARNING = (
    "Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use."
)
CHECKED_LINE = (
    "Checked: rated frequency range, whole-turn inductance within A_L tolerance, wire fit."
)
# Names all three rejection reasons: frequency rating, whole-turn accuracy, winding fit.
EMPTY_MESSAGE = [
    "  No suitable core in the built-in list. A core must be rated for this frequency,",
    "  reach this inductance within its A_L tolerance using whole turns, and fit the",
    "  winding. Choose a core manually.",
]
SECTION_RULE = "─" * 50
SUB_RULE = "  " + "─" * 48


@pytest.fixture(scope="module")
def t68_candidate():
    [candidate] = recommend_cores(0.8208e-6, 5e6, top_n=1)
    return candidate


def test_full_block_reports_hand_computed_winding_values(t68_candidate):
    lines = format_recommendation_block("L1", 0.8208e-6, 5e6, [t68_candidate])

    assert lines == [
        "  L1 target: 820.80 nH at 5 MHz",
        SUB_RULE,
        "  1. T68-2  (mix 2, red/clear, 95 ppm/°C)",
        "     12 turns of AWG 14   L: 820.80 nH (+0.00% vs target)",
        "     L range (A_L ±5%): 779.76 nH – 861.84 nH",
        "     Wire: 277 mm of AWG 14 (1.600 mm dia.)   DCR: 2.4 mΩ   Fit: single layer (datasheet)",
        "     Q limit from wire DCR alone (ωL/DCR): 10,744 at 5 MHz. Real Q is lower.",
        "     Size: 17.50 × 9.40 × 4.83 mm (OD × ID × H)   Source: Micrometals, Inc. datasheet",
    ]


def test_compact_line_reports_the_same_candidate_on_one_line(t68_candidate):
    lines = format_recommendation_block_compact("L1", 0.8208e-6, 5e6, [t68_candidate])

    # Same target line, inductance unit, and DCR text as the full block; the
    # not-checked caveat is stated once in the section header, not per line.
    assert lines == [
        "  L1 target: 820.80 nH at 5 MHz",
        "  1. T68-2    12 turns AWG 14   820.80 nH (+0.00%)   DCR 2.4 mΩ   Q limit (wire DCR): 10,744",
    ]


def test_full_block_shows_negative_error_and_ohm_scale_dcr():
    """T25-6 at 27 µH/40 MHz: 100 single-layer AWG 44 turns, 11.1 Ω × 100/112 = 9.911 Ω.

    T50-2 at 1 µH/5 MHz: 14 turns, 0.9604 µH (-3.96%).
    """
    [thin_wire] = recommend_cores(27e-6, 40e6)
    ohm_text = "\n".join(format_recommendation_block("L1", 27e-6, 40e6, [thin_wire]))
    under = recommend_cores(1e-6, 5e6)[1]
    under_text = "\n".join(format_recommendation_block("L1", 1e-6, 5e6, [under]))

    assert "100 turns of AWG 44" in ohm_text
    assert "DCR: 9.911 Ω" in ohm_text
    assert "14 turns of AWG 18" in under_text
    assert "(-3.96% vs target)" in under_text


@pytest.mark.parametrize(
    ("formatter", "expected"),
    [
        (
            format_recommendation_block,
            ["  L1 target: 1.00 µH at 500 MHz", SUB_RULE, *EMPTY_MESSAGE],
        ),
        (format_recommendation_block_compact, ["  L1 target: 1.00 µH at 500 MHz", *EMPTY_MESSAGE]),
    ],
)
def test_blocks_without_candidates_explain_the_empty_screen(formatter, expected):
    assert formatter("L1", 1e-6, 500e6, []) == expected


@pytest.mark.parametrize(
    ("compact", "top_n", "shown"), [(False, 1, 1), (False, 3, 3), (True, 1, 1)]
)
def test_section_lists_up_to_top_n_ranked_candidates_per_target(compact, top_n, shown):
    """1.3 µH at 10 MHz qualifies T25-6, T68-2, and T50-2 in that order."""
    lines = format_winding_candidate_section(
        [("L1", 1.3e-6), ("L2", 1.3e-6)], 10e6, compact=compact, top_n=top_n
    )

    assert lines[:5] == [
        "",
        "Toroid Winding Suggestions (iron-powder T-series)",
        SECTION_RULE,
        CHECKED_LINE,
        NOT_ASSESSED_WARNING,
    ]
    assert lines.count(NOT_ASSESSED_WARNING) == 1
    has_accuracy_note = "L range: the same turns across the core's ±5% A_L tolerance." in lines
    assert has_accuracy_note is not compact
    assert ("% vs target: error from rounding to whole turns." in lines) is not compact
    compact_note = "% in parentheses: error vs target from rounding to whole turns."
    assert (compact_note in lines) is compact
    ranked = ["T25-6", "T68-2", "T50-2"][:shown]
    for label in ("L1", "L2"):
        start = next(i for i, line in enumerate(lines) if line.startswith(f"  {label} target:"))
        block = lines[start : lines.index("", start)]
        numbered = [line for line in block if line.startswith(tuple(f"  {n}. " for n in "1234"))]
        assert [line.split()[1] for line in numbered] == ranked
    assert lines[-1] == ""


def test_json_record_carries_values_provenance_and_assessments(t68_candidate):
    [record] = build_json_recommendations([t68_candidate])

    assert json.loads(json.dumps(record, allow_nan=False)) == record
    assert record["rank"] == 1
    assert record["candidate_status"] == "screened_candidate"
    core = record["core"]
    assert (core["name"], core["manufacturer_part_number"], core["mix"]) == ("T68-2", "T68-2", "2")
    assert core["provenance_status"] == "primary_verified"
    assert core["core_source"]["url"] == T68_DATASHEET
    assert core["frequency_source"]["url"] == MIX_2_GUIDANCE
    assert (core["freq_min_hz"], core["freq_max_hz"]) == (2e6, 30e6)
    winding = record["winding"]
    assert winding["turns"] == 12
    assert winding["l_target_henries"] == 0.8208e-6
    assert winding["l_actual_henries"] == pytest.approx(0.8208e-6)
    assert winding["error_pct"] == pytest.approx(0.0, abs=1e-9)
    assert (winding["l_min_henries"], winding["l_max_henries"]) == pytest.approx(
        (0.77976e-6, 0.86184e-6)
    )
    assert [option["turns"] for option in winding["turn_options"]] == [11, 12]
    assert winding["turn_options"][0]["error_pct"] == pytest.approx(-15.9722, abs=1e-4)
    wire = record["wire"]
    assert (wire["awg"], wire["diameter_mm"], wire["n_max"], wire["fits"]) == (14, 1.6, 12, True)
    assert wire["length_mm"] == pytest.approx(276.684, abs=0.01)
    assert wire["dc_resistance_ohm"] == pytest.approx(0.0024)
    assert wire["capacity_status"] == "manufacturer_single_layer"
    assert wire["capacity_source"]["url"] == T68_DATASHEET
    assert record["wire_dcr_reactance_ratio_ceiling"] == pytest.approx(10744.25, abs=0.01)
    assert record["q_dc_upper_bound"] == record["wire_dcr_reactance_ratio_ceiling"]
    assert record["design_freq_hz"] == 5e6
    assessments = record["assessments"]
    assert assessments["frequency_guidance"]["status"] == "within_published_guidance"
    assert assessments["mechanical_capacity"]["status"] == "manufacturer_single_layer"
    for name in ("rf_q", "srf", "power"):
        assert assessments[name]["status"] == "not_assessed"
    assert (
        assessments["rf_q"]["note"]
        == "ωL/DCR uses the wire's DC resistance only; it is an upper limit, not RF Q."
    )
    assert record["warnings"] == [NOT_ASSESSED_WARNING]


def test_json_ranks_follow_candidate_order():
    records = build_json_recommendations(recommend_cores(1.3e-6, 10e6))

    assert [(r["rank"], r["core"]["name"]) for r in records] == [
        (1, "T25-6"),
        (2, "T68-2"),
        (3, "T50-2"),
    ]
    assert build_json_recommendations([]) == []


def test_csv_columns_align_with_header_for_best_candidate(t68_candidate):
    runner_up = recommend_cores(0.8208e-6, 5e6)[1]

    row = dict(zip(CSV_TOROID_HEADER, csv_columns_for_best([t68_candidate, runner_up])))

    assert row == {
        "ToroidCore": "T68-2",
        "ToroidMix": "2",
        "ToroidTurns": "12",
        "ToroidAWG": "14",
        "ToroidActualL_uH": "0.8208",
        "ToroidErrorPct": "0.00",
        "ToroidWireLength_mm": "276.7",
        "ToroidDCR_mohm": "2.40",
        "ToroidWireDCRReactanceRatioCeiling": "10744",
        "ToroidTempCoeff_ppm": "95",
        "ToroidCandidateStatus": "screened_candidate",
        "ToroidProvenanceStatus": "primary_verified",
        "ToroidCoreSourceURL": T68_DATASHEET,
        "ToroidFrequencySourceURL": MIX_2_GUIDANCE,
        "ToroidMechanicalStatus": "manufacturer_single_layer",
        "ToroidMechanicalSourceURL": T68_DATASHEET,
        "ToroidRFQStatus": "not_assessed",
        "ToroidSRFStatus": "not_assessed",
        "ToroidPowerStatus": "not_assessed",
        "ToroidWarnings": NOT_ASSESSED_WARNING,
    }
    assert "ToroidQ_DC_Upper" not in CSV_TOROID_HEADER


def test_csv_columns_are_blank_without_a_candidate():
    assert csv_columns_for_best([]) == [""] * len(CSV_TOROID_HEADER)


def test_estimated_capacity_is_reported_without_a_source(monkeypatch):
    estimated = dataclasses.replace(
        toroid_selection.fit_wire(get_core("T50-2"), 10, awg=36),
        capacity_status="estimated",
        capacity_source_id=None,
    )
    monkeypatch.setattr(toroid_selection, "fit_wire", lambda *_args, **_kwargs: estimated)
    recs = recommend_cores(1e-6, 10e6, top_n=1)

    [record] = build_json_recommendations(recs)
    row = dict(zip(CSV_TOROID_HEADER, csv_columns_for_best(recs)))

    assert record["wire"]["capacity_status"] == "estimated"
    assert record["wire"]["capacity_source"] is None
    assert row["ToroidMechanicalStatus"] == "estimated"
    assert row["ToroidMechanicalSourceURL"] == ""
    assert "geometry estimate" in row["ToroidWarnings"]


def _with_tolerance(candidate, tolerance_pct):
    return dataclasses.replace(
        candidate, core=dataclasses.replace(candidate.core, al_tolerance_pct=tolerance_pct)
    )


@pytest.mark.parametrize(
    ("tolerances", "note"),
    [
        ((3.0, 3.0), "L range: the same turns across the core's ±3% A_L tolerance."),
        ((3.0, 8.0), "L range: the same turns across each core's A_L tolerance."),
        ((), None),
    ],
    ids=["shared", "mixed", "no-candidates"],
)
def test_accuracy_note_is_derived_from_the_candidates_shown(
    monkeypatch, t68_candidate, tolerances, note
):
    candidates = [_with_tolerance(t68_candidate, value) for value in tolerances]
    monkeypatch.setattr(
        "filter_lib.shared.toroid_display.recommend_cores",
        lambda *_args, **_kwargs: candidates,
    )

    lines = format_winding_candidate_section([("L1", 0.8208e-6)], 5e6, top_n=3)

    accuracy = [line for line in lines if line.startswith(("% vs target", "L range:"))]
    turn_note = "% vs target: error from rounding to whole turns."
    assert accuracy == ([turn_note, note] if note else [])
    assert lines[4] == NOT_ASSESSED_WARNING
    # Each candidate's own tolerance stays visible in its L range line.
    l_ranges = [line for line in lines if line.startswith("     L range (A_L ±")]
    assert [line.split("±")[1].split("%")[0] for line in l_ranges] == [
        f"{value:g}" for value in tolerances
    ]


def test_near_zero_negative_turn_error_prints_unsigned_zero(t68_candidate):
    winding = dataclasses.replace(t68_candidate.winding, error_pct=-0.001)
    candidate = dataclasses.replace(t68_candidate, winding=winding)

    full = format_recommendation_block("L1", 0.8208e-6, 5e6, [candidate])
    compact = format_recommendation_block_compact("L1", 0.8208e-6, 5e6, [candidate])
    columns = csv_columns_for_best([candidate])

    assert full[3].endswith("(+0.00% vs target)")
    assert "(+0.00%)" in compact[1]
    assert columns[CSV_TOROID_HEADER.index("ToroidErrorPct")] == "0.00"


@pytest.mark.parametrize(
    ("capacity_status", "label"),
    [
        ("manufacturer_full_winding", "Fit: full winding (datasheet)"),
        ("estimated", "Fit: estimated from core size"),
    ],
)
def test_table_maps_capacity_status_to_a_plain_label(t68_candidate, capacity_status, label):
    """Table text never shows the raw enum value; JSON and CSV keep it."""
    mechanical = dataclasses.replace(t68_candidate.mechanical, capacity_status=capacity_status)
    candidate = dataclasses.replace(t68_candidate, mechanical=mechanical)

    wire_line = format_recommendation_block("L1", 0.8208e-6, 5e6, [candidate])[5]

    assert wire_line.endswith(label)
    assert "_" not in wire_line


def test_size_line_says_when_the_core_source_is_unavailable(t68_candidate):
    core = dataclasses.replace(t68_candidate.core, core_source_id=None)
    candidate = dataclasses.replace(t68_candidate, core=core)

    size_line = format_recommendation_block("L1", 0.8208e-6, 5e6, [candidate])[7]

    assert size_line.endswith("Source: unavailable")


def test_inductor_note_points_at_the_section_only_when_it_has_suggestions():
    assert inductor_note_line(True) == (
        "Inductors: no standard values; wind to the calculated value "
        "(see Toroid Winding Suggestions)."
    )
    assert (
        inductor_note_line(False) == "Inductors: no standard values; wind to the calculated value."
    )
    assert has_winding_suggestion([0.8208e-6], 5e6)
    assert not has_winding_suggestion([1e-6], 500e6)


def test_compact_legend_only_when_a_candidate_is_shown():
    """500 MHz qualifies no core, so there is no percentage to explain."""
    lines = format_winding_candidate_section([("L1", 1e-6)], 500e6, compact=True)

    assert not any(line.startswith("% in parentheses") for line in lines)
