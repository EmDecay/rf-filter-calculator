"""Text, JSON, and CSV rendering of inductor suggestions and the toroid winding's own pieces.

The reference candidate is T68-2 wound for 0.8208 µH at 5 MHz: 12 turns of
AWG 14 (A_L 5.7 nH/turn² × 144), 276.7 mm of 1.600 mm wire, and 2.4 mΩ from the
datasheet's single-layer row, giving a wire-only ωL/DCR of 10,744.
"""

import dataclasses
import json
import re

import pytest

from filter_lib.shared import toroid_selection
from filter_lib.shared.inductor_display import (
    CSV_INDUCTOR_HEADER,
    SECTION_NAME,
    format_error_budget,
    has_suggestion,
    inductor_csv_columns,
    inductor_note_line,
    inductor_suggestions_payload,
    suggestion_payload,
    suggestion_section_lines,
)
from filter_lib.shared.inductor_suggestion import ErrorBudget, KindSuggestions
from filter_lib.shared.toroid_core_data import get_core
from filter_lib.shared.toroid_display import (
    CSV_TOROID_HEADER,
    toroid_build_payload,
    toroid_compact_text,
    toroid_csv_columns,
    toroid_detail_lines,
    toroid_preamble_lines,
    toroid_title,
)
from filter_lib.shared.toroid_selection import suggest_toroids
from tests.parts_helpers import parts_for

T68_DATASHEET = "https://datasheets.micrometals.com/T68-2-DataSheet.pdf"
MIX_2_GUIDANCE = "https://www.amidoncorp.com/2ipt/"
NOT_ASSESSED_WARNING = (
    "Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use."
)
CHECKED_LINE = (
    "Checked: rated frequency range, whole-turn inductance within A_L tolerance, wire fit."
)
TOROID_HEADING = "Toroid windings (iron-powder T-series):"
TURN_ERROR_NOTE = "% vs target: error from rounding to whole turns."
COMPACT_TURN_ERROR_NOTE = "% in parentheses: error vs target from rounding to whole turns."
# Names all three rejection reasons: frequency rating, whole-turn accuracy, winding fit.
NO_SUITABLE_CORE = [
    "  - No suitable toroid core in the built-in list. A core must be rated for this",
    "    frequency, reach this inductance within its A_L tolerance using whole turns, and fit",
    "    the winding. Choose a core manually.",
]
NO_RATED_CORE = [
    "  - No built-in toroid core is rated for 500 MHz. VHF toroids are not offered: the core",
    "    maker publishes no self-resonance or winding-capacitance data, so the inductance",
    "    near the band cannot be checked.",
]
OTHER_KINDS_NONE = [
    "  - Air-core coils are not offered: no published self-capacitance model is validated for",
    "    coils of a few spaced turns, so their self-resonance cannot be checked.",
    "  - Chip inductor suggestions are not available in this version.",
]
SECTION_RULE = "─" * 50
SUB_RULE = "  " + "─" * 48
T68_DETAIL_LINES = [
    "     12 turns of AWG 14   L: 820.80 nH (+0.00% vs target)",
    "     L range (A_L ±5%): 779.76 nH – 861.84 nH",
    "     Wire: 277 mm of AWG 14 (1.600 mm dia.)   DCR: 2.4 mΩ   Fit: single layer (datasheet)",
    "     Q limit from wire DCR alone (ωL/DCR): 10,744 at 5 MHz. Real Q is lower.",
    "     Size: 17.50 × 9.40 × 4.83 mm (OD × ID × H)   Source: Micrometals, Inc. datasheet",
]


def _inductor(target_h: float, freq_hz: float, detail: str = "best"):
    """The suggestions ``design()`` resolves for one inductor of a design at ``freq_hz``."""
    result = {
        "filter_type": "butterworth",
        "freq_hz": freq_hz,
        "impedance": 50.0,
        "capacitors": [],
        "inductors": [target_h],
        "order": 1,
        "topology": "t",
    }
    return parts_for(result, "lowpass", eseries=None, inductor_detail=detail).inductor("L1")


def _block(lines: list[str], label: str) -> list[str]:
    """One inductor's block of a section: from its target line to the next blank line."""
    start = next(i for i, line in enumerate(lines) if line.startswith(f"  {label} target:"))
    return lines[start : lines.index("", start)]


@pytest.fixture(scope="module")
def t68_suggestion():
    return suggest_toroids(0.8208e-6, 5e6).suggestions[0]


@pytest.fixture(scope="module")
def t68_candidate(t68_suggestion):
    return t68_suggestion.build


def test_toroid_title_and_detail_lines_report_hand_computed_winding_values(t68_candidate):
    assert toroid_title(t68_candidate) == "T68-2  (mix 2, red/clear, 95 ppm/°C)"
    assert toroid_detail_lines(t68_candidate) == T68_DETAIL_LINES


def test_full_block_reports_hand_computed_winding_values():
    lines = suggestion_section_lines([("L1", _inductor(0.8208e-6, 5e6))], 5e6, "best")

    assert _block(lines, "L1") == [
        "  L1 target: 820.80 nH at 5 MHz",
        SUB_RULE,
        "  1. Toroid winding T68-2  (mix 2, red/clear, 95 ppm/°C)",
        *T68_DETAIL_LINES,
        "     Error budget: +0.00% nominal, ±5% tolerance, SRF drift not checked",
    ]


def test_compact_line_reports_the_same_candidate_on_one_line(t68_candidate):
    lines = suggestion_section_lines([("L1", _inductor(0.8208e-6, 5e6))], 5e6, "compact")

    assert toroid_compact_text(t68_candidate) == (
        "T68-2    12 turns AWG 14   820.80 nH (+0.00%)   DCR 2.4 mΩ   Q limit (wire DCR): 10,744"
    )
    # Same target line, inductance unit, and DCR text as the full block; the
    # not-checked caveat is stated once in the section header, not per line.
    assert _block(lines, "L1") == [
        "  L1 target: 820.80 nH at 5 MHz",
        f"  1. Toroid {toroid_compact_text(t68_candidate)}",
    ]


def test_detail_lines_show_negative_error_and_ohm_scale_dcr():
    """T25-6 at 27 µH/40 MHz: 100 single-layer AWG 44 turns, 11.1 Ω × 100/112 = 9.911 Ω.

    T50-2 at 1 µH/5 MHz: 14 turns, 0.9604 µH (-3.96%).
    """
    [thin_wire] = suggest_toroids(27e-6, 40e6).suggestions
    ohm_text = "\n".join(toroid_detail_lines(thin_wire.build))
    under = suggest_toroids(1e-6, 5e6).suggestions[1].build
    under_text = "\n".join(toroid_detail_lines(under))

    assert "100 turns of AWG 44" in ohm_text
    assert "DCR: 9.911 Ω" in ohm_text
    assert "14 turns of AWG 18" in under_text
    assert "(-3.96% vs target)" in under_text


@pytest.mark.parametrize(
    ("target_h", "freq_hz", "target", "toroid_reason"),
    [
        (10e-9, 10e6, "  L1 target: 10.00 nH at 10 MHz", NO_SUITABLE_CORE),
        (1e-6, 500e6, "  L1 target: 1.00 µH at 500 MHz", NO_RATED_CORE),
    ],
    ids=["no-suitable-core", "no-rated-core"],
)
@pytest.mark.parametrize("detail", ["best", "compact"])
def test_blocks_without_suggestions_explain_every_kind(
    target_h, freq_hz, target, toroid_reason, detail
):
    lines = suggestion_section_lines([("L1", _inductor(target_h, freq_hz))], freq_hz, detail)

    rule = [SUB_RULE] if detail == "best" else []
    assert _block(lines, "L1") == [
        target,
        *rule,
        "  No inductor suggestion qualifies:",
        *toroid_reason,
        *OTHER_KINDS_NONE,
    ]
    # No toroid is shown, so no toroid caveats precede the blocks.
    assert TOROID_HEADING not in lines
    assert NOT_ASSESSED_WARNING not in lines


@pytest.mark.parametrize(
    ("detail", "shown"), [("best", 1), ("full", 3), ("compact", 1)], ids=["best", "full", "compact"]
)
def test_section_lists_up_to_three_ranked_suggestions_per_target(detail, shown):
    """1.3 µH at 10 MHz qualifies T25-6, T68-2, and T50-2 in that order."""
    inductor = _inductor(1.3e-6, 10e6, detail)
    lines = suggestion_section_lines([("L1", inductor), ("L2", inductor)], 10e6, detail)

    compact = detail == "compact"
    assert lines[:6] == [
        "",
        SECTION_NAME,
        SECTION_RULE,
        TOROID_HEADING,
        CHECKED_LINE,
        NOT_ASSESSED_WARNING,
    ]
    assert lines.count(NOT_ASSESSED_WARNING) == 1
    has_accuracy_note = "L range: the same turns across the core's ±5% A_L tolerance." in lines
    assert has_accuracy_note is not compact
    assert (TURN_ERROR_NOTE in lines) is not compact
    assert (COMPACT_TURN_ERROR_NOTE in lines) is compact
    ranked = ["T25-6", "T68-2", "T50-2"][:shown]
    for label in ("L1", "L2"):
        block = _block(lines, label)
        title = "Toroid " if compact else "Toroid winding "
        numbered = [line for line in block if re.match(r"  \d\. ", line)]
        assert [line.split(title)[1].split()[0] for line in numbered] == ranked
        assert all(
            line.startswith(f"  {rank}. {title}") for rank, line in enumerate(numbered, start=1)
        )
        # Full lists why the other kinds have no part; best and compact show only the pick.
        assert (block[-len(OTHER_KINDS_NONE) :] == OTHER_KINDS_NONE) is (detail == "full")
    assert lines[-1] == ""


def test_suggestion_json_carries_values_provenance_and_assessments(t68_suggestion):
    record = suggestion_payload(t68_suggestion)

    assert json.loads(json.dumps(record, allow_nan=False)) == record
    assert (record["kind"], record["rank"], record["part_name"]) == ("toroid", 1, "T68-2")
    assert record["status"] == "screened_candidate"
    assert record["target_henries"] == 0.8208e-6
    assert record["achieved_henries"] == pytest.approx(0.8208e-6)
    assert record["tolerance_pct"] == 5.0
    assert (record["srf_basis"], record["srf_accuracy"]) == ("not_checked", None)
    budget = record["error_budget"]
    assert budget["nominal_mismatch_pct"] == pytest.approx(0.0, abs=1e-9)
    assert (budget["tolerance_pct"], budget["srf_drift_pct"]) == (5.0, None)
    assert record["source"]["url"] == T68_DATASHEET
    assert record["warnings"] == [NOT_ASSESSED_WARNING]
    build = record["build"]
    assert build == toroid_build_payload(t68_suggestion.build)
    # The rank and status are the suggestion's; the deprecated Q alias is gone.
    assert not {"rank", "candidate_status", "q_dc_upper_bound"} & build.keys()
    core = build["core"]
    assert (core["name"], core["manufacturer_part_number"], core["mix"]) == ("T68-2", "T68-2", "2")
    assert core["provenance_status"] == "primary_verified"
    assert core["core_source"]["url"] == T68_DATASHEET
    assert core["frequency_source"]["url"] == MIX_2_GUIDANCE
    assert (core["freq_min_hz"], core["freq_max_hz"]) == (2e6, 30e6)
    winding = build["winding"]
    assert winding["turns"] == 12
    assert winding["l_target_henries"] == 0.8208e-6
    assert winding["l_actual_henries"] == pytest.approx(0.8208e-6)
    assert winding["error_pct"] == pytest.approx(0.0, abs=1e-9)
    assert (winding["l_min_henries"], winding["l_max_henries"]) == pytest.approx(
        (0.77976e-6, 0.86184e-6)
    )
    assert [option["turns"] for option in winding["turn_options"]] == [11, 12]
    assert winding["turn_options"][0]["error_pct"] == pytest.approx(-15.9722, abs=1e-4)
    wire = build["wire"]
    assert (wire["awg"], wire["diameter_mm"], wire["n_max"], wire["fits"]) == (14, 1.6, 12, True)
    assert wire["length_mm"] == pytest.approx(276.684, abs=0.01)
    assert wire["dc_resistance_ohm"] == pytest.approx(0.0024)
    assert wire["capacity_status"] == "manufacturer_single_layer"
    assert wire["capacity_source"]["url"] == T68_DATASHEET
    assert build["wire_dcr_reactance_ratio_ceiling"] == pytest.approx(10744.25, abs=0.01)
    assert build["design_freq_hz"] == 5e6
    assessments = build["assessments"]
    assert assessments["frequency_guidance"]["status"] == "within_published_guidance"
    assert assessments["mechanical_capacity"]["status"] == "manufacturer_single_layer"
    for name in ("rf_q", "srf", "power"):
        assert assessments[name]["status"] == "not_assessed"
    assert (
        assessments["rf_q"]["note"]
        == "ωL/DCR uses the wire's DC resistance only; it is an upper limit, not RF Q."
    )


def test_json_ranks_follow_candidate_order_and_every_kind_is_listed():
    payload = inductor_suggestions_payload(_inductor(1.3e-6, 10e6))

    toroids, air_coils, chips = payload["kinds"]
    assert [(s["rank"], s["part_name"]) for s in toroids["suggestions"]] == [
        (1, "T25-6"),
        (2, "T68-2"),
        (3, "T50-2"),
    ]
    assert payload["best"] == {"kind": "toroid", "rank": 1}
    assert toroids["reason_none"] is None
    for group, kind in ((air_coils, "air-coil"), (chips, "chip")):
        assert group["kind"] == kind
        assert group["suggestions"] == []
        assert group["reason_none"]

    empty = inductor_suggestions_payload(_inductor(1e-6, 500e6))
    assert empty["best"] is None
    assert empty["kinds"][0]["suggestions"] == []
    assert empty["kinds"][0]["reason_none"].startswith("No built-in toroid core is rated")


def test_csv_columns_align_with_header_for_best_candidate(t68_candidate):
    row = dict(zip(CSV_TOROID_HEADER, toroid_csv_columns(t68_candidate)))

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
    # The inductor row leads with its best suggestion's kind, then that kind's columns.
    assert CSV_INDUCTOR_HEADER == ["InductorKind", *CSV_TOROID_HEADER]
    assert inductor_csv_columns(_inductor(0.8208e-6, 5e6)) == [
        "toroid",
        *toroid_csv_columns(t68_candidate),
    ]


def test_csv_columns_are_blank_without_a_candidate():
    assert toroid_csv_columns(None) == [""] * len(CSV_TOROID_HEADER)
    assert inductor_csv_columns(None) == [""] * len(CSV_INDUCTOR_HEADER)
    assert inductor_csv_columns(_inductor(1e-6, 500e6)) == [""] * len(CSV_INDUCTOR_HEADER)


def test_estimated_capacity_is_reported_without_a_source(monkeypatch):
    estimated = dataclasses.replace(
        toroid_selection.fit_wire(get_core("T50-2"), 10, awg=36),
        capacity_status="estimated",
        capacity_source_id=None,
    )
    monkeypatch.setattr(toroid_selection, "fit_wire", lambda *_args, **_kwargs: estimated)
    candidate = suggest_toroids(1e-6, 10e6).suggestions[0].build

    record = toroid_build_payload(candidate)
    row = dict(zip(CSV_TOROID_HEADER, toroid_csv_columns(candidate)))

    assert record["wire"]["capacity_status"] == "estimated"
    assert record["wire"]["capacity_source"] is None
    assert row["ToroidMechanicalStatus"] == "estimated"
    assert row["ToroidMechanicalSourceURL"] == ""
    assert "geometry estimate" in row["ToroidWarnings"]


def _with_tolerances(suggestion, tolerances):
    """Copies of ``suggestion`` ranked 1, 2, ... whose cores have the given A_L tolerances."""
    return tuple(
        dataclasses.replace(
            suggestion,
            rank=rank,
            build=dataclasses.replace(
                suggestion.build,
                core=dataclasses.replace(suggestion.build.core, al_tolerance_pct=tolerance),
            ),
        )
        for rank, tolerance in enumerate(tolerances, start=1)
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
def test_accuracy_note_is_derived_from_the_candidates_shown(t68_suggestion, tolerances, note):
    base = _inductor(0.8208e-6, 5e6, "full")
    shown = _with_tolerances(t68_suggestion, tolerances)
    toroids = (
        KindSuggestions("toroid", shown)
        if shown
        else KindSuggestions("toroid", reason_none=toroid_selection.NO_SUITABLE_CORE_REASON)
    )
    inductor = dataclasses.replace(base, kinds=(toroids, *base.kinds[1:]), build_pick=None)

    lines = suggestion_section_lines([("L1", inductor)], 5e6, "full")

    accuracy = [line for line in lines if line.startswith(("% vs target", "L range:"))]
    assert accuracy == ([TURN_ERROR_NOTE, note] if note else [])
    if shown:
        assert lines[3:6] == [TOROID_HEADING, CHECKED_LINE, NOT_ASSESSED_WARNING]
        assert toroid_preamble_lines([item.build for item in shown], compact=False) == [
            TOROID_HEADING,
            CHECKED_LINE,
            NOT_ASSESSED_WARNING,
            *accuracy,
        ]
    else:
        assert NOT_ASSESSED_WARNING not in lines
    # Each candidate's own tolerance stays visible in its L range line.
    l_ranges = [line for line in lines if line.startswith("     L range (A_L ±")]
    assert [line.split("±")[1].split("%")[0] for line in l_ranges] == [
        f"{value:g}" for value in tolerances
    ]


def test_near_zero_negative_turn_error_prints_unsigned_zero(t68_candidate):
    winding = dataclasses.replace(t68_candidate.winding, error_pct=-0.001)
    candidate = dataclasses.replace(t68_candidate, winding=winding)

    full = toroid_detail_lines(candidate)
    compact = toroid_compact_text(candidate)
    columns = toroid_csv_columns(candidate)

    assert full[0].endswith("(+0.00% vs target)")
    assert "(+0.00%)" in compact
    assert columns[CSV_TOROID_HEADER.index("ToroidErrorPct")] == "0.00"
    assert format_error_budget(ErrorBudget(-0.001, 5.0)) == (
        "Error budget: +0.00% nominal, ±5% tolerance, SRF drift not checked"
    )


def test_error_budget_states_each_term_and_a_checked_srf_drift():
    assert format_error_budget(ErrorBudget(-0.4, 5.0)) == (
        "Error budget: -0.40% nominal, ±5% tolerance, SRF drift not checked"
    )
    assert format_error_budget(ErrorBudget(1.234, 2.0, (0.1, 1.5))) == (
        "Error budget: +1.23% nominal, ±2% tolerance, SRF drift +0.10% to +1.50%"
    )


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

    wire_line = toroid_detail_lines(candidate)[2]

    assert wire_line.endswith(label)
    assert "_" not in wire_line


def test_size_line_says_when_the_core_source_is_unavailable(t68_candidate):
    core = dataclasses.replace(t68_candidate.core, core_source_id=None)
    candidate = dataclasses.replace(t68_candidate, core=core)

    size_line = toroid_detail_lines(candidate)[4]

    assert size_line.endswith("Source: unavailable")


def test_inductor_note_points_at_the_section_only_when_it_has_suggestions():
    assert inductor_note_line(True) == "Inductors: no standard values; see Inductor Suggestions."
    assert inductor_note_line(False) == "Inductors: no standard values; use the calculated value."
    assert has_suggestion([_inductor(0.8208e-6, 5e6)])
    assert not has_suggestion([_inductor(1e-6, 500e6)])


def test_compact_legend_only_when_a_candidate_is_shown():
    """500 MHz qualifies no core, so there is no percentage to explain."""
    lines = suggestion_section_lines([("L1", _inductor(1e-6, 500e6, "compact"))], 500e6, "compact")

    assert not any(line.startswith("% in parentheses") for line in lines)
