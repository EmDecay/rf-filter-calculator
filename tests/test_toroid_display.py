"""Text, JSON, and CSV rendering of screened toroid winding candidates.

The reference candidate is T68-2 wound for 0.8208 µH at 5 MHz: 12 turns of
AWG 14 (A_L 5.7 nH/turn² × 144), 276.7 mm of 1.600 mm wire, and 2.4 mΩ from the
datasheet's single-layer row, giving a wire-only ωL/Rdc of 10,744.
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
)
from filter_lib.shared.toroid_selection import recommend_cores

T68_DATASHEET = "https://datasheets.micrometals.com/T68-2-DataSheet.pdf"
MIX_2_GUIDANCE = "https://www.amidoncorp.com/2ipt/"
NOT_ASSESSED_WARNING = (
    "RF Q, core loss, SRF, saturation, thermal rise, and power handling are not assessed."
)
EMPTY_MESSAGE = (
    "  No iron-powder winding candidate with primary-verified core data covers "
    "this frequency and published capacity screen."
)


@pytest.fixture(scope="module")
def t68_candidate():
    [candidate] = recommend_cores(0.8208e-6, 5e6, top_n=1)
    return candidate


def test_full_block_reports_hand_computed_winding_values(t68_candidate):
    lines = format_recommendation_block("L1", 0.8208e-6, 5e6, [t68_candidate])

    assert lines == [
        "  L1 target: 820.80 nH  (design freq 5 MHz)",
        "  " + "─" * 60,
        "  1. T68-2 screened candidate  (Red/Clear, mix 2, 95 ppm/°C)",
        "     Turns: 12 of AWG 14   Actual L: 820.80 nH  (+0.00%)",
        "     L range (A_L ±5%): 779.76 nH – 861.84 nH",
        "     Wire: 277 mm of AWG 14 (1.600 mm)   DCR: 2.4 mΩ   Capacity: manufacturer_single_layer",
        "     Wire-only ωL/Rdc ceiling: 10,744 @ 5 MHz; RF Q: not assessed; "
        "SRF/power: not assessed/not assessed",
        "     Dims: 17.50 × 9.40 × 4.83 mm (OD × ID × H); "
        "data: primary_verified (Micrometals, Inc.)",
    ]


def test_compact_line_reports_the_same_candidate_on_one_line(t68_candidate):
    lines = format_recommendation_block_compact("L1", 0.8208e-6, 5e6, [t68_candidate])

    assert lines == [
        "  L1 target: 820.80 nH @ 5 MHz",
        "  1. T68-2    N=12 AWG14 L=0.821µH (+0.00%) Rdc=2mΩ ωL/Rdc≤10,744 "
        "[RF Q/SRF/power not assessed]",
    ]


def test_full_block_shows_negative_error_and_ohm_scale_dcr():
    """T25-6 at 27 µH/40 MHz: 100 single-layer AWG 44 turns, 11.1 Ω × 100/112 = 9.911 Ω.

    T50-2 at 1 µH/5 MHz: 14 turns, 0.9604 µH (-3.96%).
    """
    [thin_wire] = recommend_cores(27e-6, 40e6)
    ohm_text = "\n".join(format_recommendation_block("L1", 27e-6, 40e6, [thin_wire]))
    under = recommend_cores(1e-6, 5e6)[1]
    under_text = "\n".join(format_recommendation_block("L1", 1e-6, 5e6, [under]))

    assert "Turns: 100 of AWG 44" in ohm_text
    assert "DCR: 9.911 Ω" in ohm_text
    assert "Turns: 14 of AWG 18" in under_text
    assert "(-3.96%)" in under_text


@pytest.mark.parametrize(
    ("formatter", "expected"),
    [
        (
            format_recommendation_block,
            ["  L1 target: 1.00 µH  (design freq 500 MHz)", "  " + "─" * 60, EMPTY_MESSAGE],
        ),
        (format_recommendation_block_compact, ["  L1 target: 1.00 µH @ 500 MHz", EMPTY_MESSAGE]),
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

    assert lines[:3] == [
        "",
        "Screened Toroid Winding Candidates (Iron-Powder T-Series)",
        "-" * 55,
    ]
    assert lines[3] == NOT_ASSESSED_WARNING
    assert lines.count(NOT_ASSESSED_WARNING) == 1
    has_accuracy_note = "(Accuracy: A_L tolerance ±5% per spec; N rounding shown as %)" in lines
    assert has_accuracy_note is not compact
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
    assert assessments["rf_q"]["note"] == "ωL/Rdc is a wire-only diagnostic ceiling, not RF Q."
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
        ((3.0, 3.0), "(Accuracy: A_L tolerance ±3% per spec; N rounding shown as %)"),
        (
            (3.0, 8.0),
            "(Accuracy: A_L tolerance per candidate, shown in each L range; N rounding shown as %)",
        ),
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

    accuracy = [line for line in lines if line.startswith("(Accuracy")]
    assert accuracy == ([note] if note else [])
    assert lines[3] == NOT_ASSESSED_WARNING
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

    assert full[3].endswith("(+0.00%)")
    assert "(+0.00%)" in compact[1]
    assert columns[CSV_TOROID_HEADER.index("ToroidErrorPct")] == "0.00"
