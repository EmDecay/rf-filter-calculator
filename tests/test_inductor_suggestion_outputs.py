"""Inductor suggestions in LP/HP/BP table, JSON, and CSV output and the CLI option.

Reference designs (toroid suggestions hand-checked against A_L·N²):
- LP Butterworth pi 10 MHz, n=5: L1 = L2 = 1.2876 µH -> T68-2 15 turns (-0.40%),
  T50-2 16 turns (-2.58%), T25-6 22 turns (+1.49%).
- HP Butterworth T 14 MHz, n=5: L1 = L2 = 0.3513 µH -> only T68-2 8 turns (+3.84%).
- BP Butterworth 14.175 MHz, 350 kHz, 3 resonators: L1–L3 = 0.5615 µH ->
  only T68-2 10 turns (+1.52%).
"""

import csv
import io
import json
import re
import sys

import pytest

from filter_lib.cli import main
from filter_lib.design import DesignRequest, RenderOptions, design, render_lines
from filter_lib.shared.inductor_suggestion import FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE

SECTION_TITLE = "Inductor Suggestions"
LP_RANKED = ["T68-2", "T50-2", "T25-6"]
NOT_ASSESSED_WARNING = (
    "Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use."
)
INDUCTOR_NOTE = "Inductors: no standard values; use the calculated value."
INDUCTOR_NOTE_WITH_POINTER = "Inductors: no standard values; see Inductor Suggestions."
COMPACT_Q_LIMIT = "Q limit (wire DCR):"


def _lp_request(frequency_hz: float = 10e6, **fields) -> DesignRequest:
    return DesignRequest("lowpass", "butterworth", "pi", frequency_hz, 50.0, 5, **fields)


def _hp_request(**fields) -> DesignRequest:
    return DesignRequest("highpass", "butterworth", "t", 14e6, 50.0, 5, **fields)


def _bp_request(frequency_hz: float = 14.175e6, bandwidth_hz: float = 350e3, **fields):
    return DesignRequest(
        "bandpass", "butterworth", "top", frequency_hz, 50.0, 3, bandwidth_hz=bandwidth_hz, **fields
    )


REQUESTS = {"lp": _lp_request, "bp": _bp_request}


def _render(request: DesignRequest, output_format: str = "table") -> str:
    """The document ``filter-calc`` prints for ``request`` (without its final newline)."""
    return "\n".join(render_lines(design(request), RenderOptions(output_format=output_format)))


BP_FIXED_TANK = ("bp", "bw", "top", "-f", "10MHz", "-b", "500kHz", "--tank-inductance", "1.3uH")


def _candidate_cores(text: str) -> list[str]:
    """Core names of numbered toroid suggestion lines, in display order (full or compact)."""
    return re.findall(r"^  \d\. Toroid (?:winding )?(T\d+-\d+)\b", text, flags=re.MULTILINE)


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def _toroid_suggestions(inductor: dict) -> list[dict]:
    kinds = {group["kind"]: group for group in inductor["inductor_suggestions"]["kinds"]}
    return kinds["toroid"]["suggestions"]


@pytest.mark.parametrize(
    ("detail", "expected"),
    [("best", LP_RANKED[:1] * 2), ("full", LP_RANKED * 2), ("compact", LP_RANKED[:1] * 2)],
    ids=["default-best", "full-three", "compact-best"],
)
def test_lp_table_shows_ranked_suggestions_per_inductor(detail, expected):
    out = _render(_lp_request(eseries=None, inductor_suggestions=detail))

    assert SECTION_TITLE in out
    assert "L1 target:" in out and "L2 target:" in out
    assert _candidate_cores(out) == expected
    if detail == "compact":
        assert COMPACT_Q_LIMIT in out
    else:
        assert "Q limit from wire DCR alone (ωL/DCR):" in out
    # The not-checked caveat is stated once, in the toroid preamble, not per suggestion.
    assert out.count("Not checked:") == 1
    assert "not assessed" not in out
    assert INDUCTOR_NOTE_WITH_POINTER in out


def test_hp_table_shows_single_qualified_suggestion_even_in_full_mode():
    out = _render(_hp_request(eseries=None, inductor_suggestions="full"))

    assert _candidate_cores(out) == ["T68-2", "T68-2"]
    assert "8 turns of AWG" in out


@pytest.mark.parametrize("detail", ["best", "full", "compact"])
def test_bp_table_shows_one_shared_block_with_only_qualified_suggestions(detail):
    """Full mode does not pad the list with poor matches to reach three."""
    out = _render(_bp_request(eseries=None, inductor_suggestions=detail))

    assert out.count("L1–L3 (all equal) target:") == 1
    assert _candidate_cores(out) == ["T68-2"]


@pytest.mark.parametrize("design_kind", ["lp", "bp"])
def test_no_suggestions_omits_section_and_dangling_reference(design_kind):
    out = _render(REQUESTS[design_kind](eseries=None, inductor_suggestions="none"))

    assert SECTION_TITLE not in out
    assert "Toroid" not in out
    assert INDUCTOR_NOTE in out


@pytest.mark.parametrize("build_inductors", ["toroid", "air-coil", "chip"])
def test_no_suggestions_cannot_be_combined_with_building_a_suggested_kind(build_inductors):
    """One option sets the detail, so only "none" with a forced build kind can conflict."""
    with pytest.raises(ValueError, match=f"^{re.escape(FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE)}$"):
        _lp_request(inductor_suggestions="none", build_inductors=build_inductors)


@pytest.mark.parametrize("build_inductors", ["auto", "calculated"])
def test_no_suggestions_keeps_omitting_them_whatever_the_build_uses(build_inductors):
    request = _lp_request(
        eseries=None, inductor_suggestions="none", build_inductors=build_inductors
    )

    assert "Toroid" not in _render(request)


def test_quiet_output_omits_suggestion_section():
    assert SECTION_TITLE not in _render(_lp_request(eseries=None), "quiet")


def test_out_of_range_frequency_explains_why_no_kind_qualifies():
    # At 3 GHz no toroid is rated and every chip inductor drifts too far below its SRF.
    out = _render(_lp_request(3e9, eseries=None))

    assert "No inductor suggestion qualifies:" in out
    assert "No built-in toroid core is rated for 3 GHz." in out
    assert "No chip inductor qualifies:" in out
    # The note does not point at a section that holds no suggestion.
    assert INDUCTOR_NOTE in out
    assert INDUCTOR_NOTE_WITH_POINTER not in out


def test_lp_json_attaches_up_to_three_suggestions_to_each_inductor():
    inductors = json.loads(_render(_lp_request(eseries=None), "json"))["components"]["inductors"]

    assert len(inductors) == 2
    for inductor in inductors:
        suggestions = _toroid_suggestions(inductor)
        assert [s["part_name"] for s in suggestions] == LP_RANKED
        assert [s["build"]["core"]["name"] for s in suggestions] == LP_RANKED
        assert [s["rank"] for s in suggestions] == [1, 2, 3]
        assert all(s["warnings"] == [NOT_ASSESSED_WARNING] for s in suggestions)
        assert inductor["inductor_suggestions"]["best"] == {"kind": "toroid", "rank": 1}


def test_hp_json_attaches_suggestions_to_each_inductor():
    inductors = json.loads(_render(_hp_request(eseries=None), "json"))["components"]["inductors"]

    assert [[s["part_name"] for s in _toroid_suggestions(i)] for i in inductors] == [
        ["T68-2"],
        ["T68-2"],
    ]


def test_bp_json_attaches_the_shared_suggestion_to_every_resonator_inductor():
    data = json.loads(_render(_bp_request(eseries=None), "json"))
    inductors = data["components"]["inductors"]

    assert [inductor["name"] for inductor in inductors] == ["L1", "L2", "L3"]
    for inductor in inductors:
        [suggestion] = _toroid_suggestions(inductor)
        assert suggestion["part_name"] == "T68-2"
        assert suggestion["build"]["winding"]["turns"] == 10
    assert "resonator_toroid_candidates" not in data
    assert "resonator_toroid_recommendations" not in data


@pytest.mark.parametrize("design_kind", ["lp", "bp"])
def test_json_no_suggestions_omits_suggestion_keys(design_kind):
    request = REQUESTS[design_kind](eseries=None, inductor_suggestions="none")
    data = json.loads(_render(request, "json"))

    assert all("inductor_suggestions" not in i for i in data["components"]["inductors"])
    assert "toroid" not in json.dumps(data).lower()


def test_lp_csv_carries_best_suggestion_on_inductor_rows_only():
    rows = _csv_rows(_render(_lp_request(eseries=None), "csv"))

    by_kind = {prefix: [r for r in rows if r["Component"].startswith(prefix)] for prefix in "LC"}
    assert [(r["ToroidCore"], r["ToroidTurns"]) for r in by_kind["L"]] == [("T68-2", "15")] * 2
    assert all(r["InductorKind"] == "toroid" for r in by_kind["L"])
    assert all(r["ToroidErrorPct"] == "-0.40" for r in by_kind["L"])
    assert all(r["ToroidWarnings"] == NOT_ASSESSED_WARNING for r in by_kind["L"])
    assert by_kind["C"]
    assert all(r["ToroidCore"] == r["InductorKind"] == "" for r in by_kind["C"])


def test_bp_csv_repeats_shared_suggestion_on_every_resonator_row():
    rows = _csv_rows(_render(_bp_request(eseries=None), "csv"))

    inductor_rows = [r for r in rows if r["Component"].startswith("L")]
    assert [r["Component"] for r in inductor_rows] == ["L1", "L2", "L3"]
    assert {(r["InductorKind"], r["ToroidCore"], r["ToroidTurns"]) for r in inductor_rows} == {
        ("toroid", "T68-2", "10")
    }
    assert all(r["ToroidCore"] == "" for r in rows if not r["Component"].startswith("L"))


@pytest.mark.parametrize("design_kind", ["lp", "bp"])
def test_csv_no_suggestions_drops_inductor_columns(design_kind):
    request = REQUESTS[design_kind](eseries=None, inductor_suggestions="none")
    header = next(csv.reader(io.StringIO(_render(request, "csv"))))

    assert not any(column.startswith(("Toroid", "Inductor")) for column in header)


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (("lp", "bw", "pi", "10MHz", "-n", "5"), LP_RANKED[:1] * 2),
        (("lp", "bw", "pi", "10MHz", "-n", "5", "--inductor-suggestions", "full"), LP_RANKED * 2),
        (
            ("lp", "bw", "pi", "10MHz", "-n", "5", "--inductor-suggestions", "compact"),
            LP_RANKED[:1] * 2,
        ),
        # HP pi 10 MHz, n=3: L1 = L2 = 0.796 µH, which all three parts realize.
        (("hp", "bw", "pi", "10MHz", "-n", "3"), ["T68-2"] * 2),
        (
            ("hp", "bw", "pi", "10MHz", "-n", "3", "--inductor-suggestions", "full"),
            ["T68-2", "T50-2", "T25-6"] * 2,
        ),
        # A fixed 1.3 µH tank at 10 MHz qualifies T25-6, T68-2, and T50-2 in that order.
        (BP_FIXED_TANK, ["T25-6"]),
        ((*BP_FIXED_TANK, "--inductor-suggestions", "full"), ["T25-6", "T68-2", "T50-2"]),
    ],
    ids=["lp-default", "lp-full", "lp-compact", "hp-default", "hp-full", "bp-default", "bp-full"],
)
def test_cli_inductor_suggestions_select_table_detail(monkeypatch, capsys, arguments, expected):
    monkeypatch.setattr(sys, "argv", ["filter-calc", *arguments, "--no-match"])

    main()
    out = capsys.readouterr().out

    assert _candidate_cores(out) == expected
    assert (COMPACT_Q_LIMIT in out) is ("compact" in arguments)


def test_cli_no_suggestions_removes_them_from_every_format(monkeypatch, capsys):
    for output_format in ("table", "json", "csv"):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                *("filter-calc", "lp", "bw", "pi", "10MHz"),
                *("--inductor-suggestions", "none", "--format", output_format),
            ],
        )
        main()
        assert "toroid" not in capsys.readouterr().out.lower(), output_format


@pytest.mark.parametrize("detail", ["full", "compact"])
def test_cli_table_section_states_every_not_assessed_quantity(monkeypatch, capsys, detail):
    argv = ["filter-calc", "lp", "bw", "pi", "10MHz", "--inductor-suggestions", detail]
    monkeypatch.setattr(sys, "argv", argv)

    main()
    out = capsys.readouterr().out

    assert out.count(NOT_ASSESSED_WARNING) == 1
    section = out[out.index(f"\n{SECTION_TITLE}\n") + 1 :]
    assert section.splitlines()[2:5] == [
        "Toroid windings (iron-powder T-series):",
        "Checked: rated frequency range, whole-turn inductance within A_L tolerance, wire fit.",
        NOT_ASSESSED_WARNING,
    ]
    for quantity in ("RF Q", "core loss", "SRF", "saturation", "heating", "power handling"):
        assert quantity in section


def test_cli_json_and_csv_keep_the_not_assessed_warning_per_suggestion(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["filter-calc", "lp", "bw", "pi", "10MHz", "--format", "json"])
    main()
    inductors = json.loads(capsys.readouterr().out)["components"]["inductors"]
    suggestions = [s for item in inductors for s in _toroid_suggestions(item)]
    assert suggestions
    assert all(s["warnings"] == [NOT_ASSESSED_WARNING] for s in suggestions)

    monkeypatch.setattr(sys, "argv", ["filter-calc", "lp", "bw", "pi", "10MHz", "--format", "csv"])
    main()
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    warnings = {row["ToroidWarnings"] for row in rows if row["ToroidCore"]}
    assert warnings == {NOT_ASSESSED_WARNING}


def test_bp_inductor_note_drops_the_pointer_when_no_core_suits():
    """At 3 GHz no part of any kind qualifies, so the note must not point at an empty section."""
    out = _render(_bp_request(3e9, 150e6, eseries=None))

    assert "No built-in toroid core is rated for 3 GHz." in out
    assert "No chip inductor qualifies:" in out
    assert INDUCTOR_NOTE in out
    assert INDUCTOR_NOTE_WITH_POINTER not in out
