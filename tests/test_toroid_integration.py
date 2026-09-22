"""Toroid candidates in LP/HP/BP table, JSON, and CSV output and the toroid CLI flags.

Reference designs (candidates hand-checked against A_L·N²):
- LP Butterworth pi 10 MHz, n=5: L1 = L2 = 1.2876 µH -> T68-2 15 turns (-0.40%),
  T50-2 16 turns (-2.58%), T25-6 22 turns (+1.49%).
- HP Butterworth T 14 MHz, n=5: L1 = L2 = 0.3513 µH -> only T68-2 8 turns (+3.84%).
- BP Butterworth 14.175 MHz, 350 kHz, 3 resonators: L_resonant = 0.5615 µH ->
  only T68-2 10 turns (+1.52%).
"""

import csv
import io
import json
import re
import sys

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.display import display_results as bp_display
from filter_lib.cli import main
from filter_lib.highpass.calculations import calculate_butterworth as hp_calc
from filter_lib.highpass.display import display_results as hp_display
from filter_lib.lowpass.calculations import calculate_butterworth as lp_calc
from filter_lib.lowpass.display import display_results as lp_display

SECTION_TITLE = "Screened Toroid Winding Candidates"
LP_RANKED = ["T68-2", "T50-2", "T25-6"]
NOT_ASSESSED_WARNING = (
    "RF Q, core loss, SRF, saturation, thermal rise, and power handling are not assessed."
)


def _ladder_result(calc, freq_hz, topology):
    first, second, order = calc(freq_hz, 50.0, 5, topology=topology)
    caps, inds = (first, second) if calc is lp_calc else (second, first)
    return {
        "filter_type": "butterworth",
        "freq_hz": freq_hz,
        "impedance": 50.0,
        "capacitors": caps,
        "inductors": inds,
        "order": order,
        "ripple": None,
        "topology": topology,
    }


@pytest.fixture
def lp_result():
    return _ladder_result(lp_calc, 10e6, "pi")


@pytest.fixture
def hp_result():
    return _ladder_result(hp_calc, 14e6, "t")


@pytest.fixture(scope="module")
def bp_result():
    return calculate_bandpass_filter(
        f0=14.175e6,
        bw=350e3,
        z0=50.0,
        n_resonators=3,
        filter_type="butterworth",
        coupling="top",
        ripple_db=0.5,
        q_safety=2.0,
    )


BP_FIXED_TANK = ("bp", "bw", "top", "-f", "10MHz", "-b", "500kHz", "--tank-inductance", "1.3uH")


def _candidate_cores(text: str) -> list[str]:
    """Core names of numbered candidate lines, in display order (full or compact)."""
    return re.findall(r"^  \d\. (T\d+-\d+)\b", text, flags=re.MULTILINE)


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, LP_RANKED[:1] * 2),
        ({"toroid_full": True}, LP_RANKED * 2),
        ({"toroid_compact": True}, LP_RANKED[:1] * 2),
    ],
    ids=["default-best", "full-three", "compact-best"],
)
def test_lp_table_shows_ranked_candidates_per_inductor(lp_result, capsys, kwargs, expected):
    lp_display(lp_result, output_format="table", show_plot=False, show_match=False, **kwargs)
    out = capsys.readouterr().out

    assert SECTION_TITLE in out
    assert "L1 target:" in out and "L2 target:" in out
    assert _candidate_cores(out) == expected
    if kwargs.get("toroid_compact"):
        assert "ωL/Rdc≤" in out and "[RF Q/SRF/power not assessed]" in out
    else:
        assert "RF Q: not assessed; SRF/power: not assessed/not assessed" in out
    assert "Inductors: wind to value (see toroid recommendations)" in out


def test_hp_table_shows_single_qualified_candidate_even_in_full_mode(hp_result, capsys):
    hp_display(
        hp_result, output_format="table", show_plot=False, show_match=False, toroid_full=True
    )
    out = capsys.readouterr().out

    assert _candidate_cores(out) == ["T68-2", "T68-2"]
    assert "Turns: 8 of AWG" in out


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"toroid_full": True}, {"toroid_compact": True}],
    ids=["default", "full", "compact"],
)
def test_bp_table_shows_one_shared_block_with_only_qualified_candidates(bp_result, capsys, kwargs):
    """Full mode does not pad the list with poor matches to reach three."""
    bp_display(bp_result, output_format="table", show_plot=False, eseries=None, **kwargs)
    out = capsys.readouterr().out

    assert out.count("L_resonant (applies to L1…L3) target:") == 1
    assert _candidate_cores(out) == ["T68-2"]


@pytest.mark.parametrize("display", ["lp", "bp"])
def test_no_toroids_omits_section_and_dangling_reference(lp_result, bp_result, capsys, display):
    if display == "lp":
        lp_display(lp_result, output_format="table", show_match=False, include_toroids=False)
    else:
        bp_display(bp_result, output_format="table", eseries=None, include_toroids=False)
    out = capsys.readouterr().out

    assert "Toroid" not in out
    assert "see toroid recommendations" not in out
    assert "Inductors: wind to value" in out


def test_display_api_include_toroids_false_overrides_detail_level(lp_result, capsys):
    """The CLI rejects this combination; the display API gives omission precedence."""
    lp_display(
        lp_result, output_format="table", show_match=False, include_toroids=False, toroid_full=True
    )

    assert "Toroid" not in capsys.readouterr().out


def test_quiet_table_omits_toroid_section(lp_result, capsys):
    lp_display(lp_result, output_format="table", quiet=True, show_match=False)

    assert SECTION_TITLE not in capsys.readouterr().out


def test_out_of_range_frequency_shows_empty_screen_message(capsys):
    lp_display(_ladder_result(lp_calc, 500e6, "pi"), output_format="table", show_match=False)

    assert "No iron-powder winding candidate with primary-verified core data" in (
        capsys.readouterr().out
    )


def test_lp_json_attaches_up_to_three_candidates_to_each_inductor(lp_result, capsys):
    lp_display(lp_result, output_format="json", show_match=False)
    inductors = json.loads(capsys.readouterr().out)["components"]["inductors"]

    assert len(inductors) == 2
    for inductor in inductors:
        candidates = inductor["toroid_recommendations"]
        assert [c["core"]["name"] for c in candidates] == LP_RANKED
        assert [c["rank"] for c in candidates] == [1, 2, 3]
        assert all(c["warnings"] == [NOT_ASSESSED_WARNING] for c in candidates)


def test_hp_json_attaches_candidates_to_each_inductor(hp_result, capsys):
    hp_display(hp_result, output_format="json", show_match=False)
    inductors = json.loads(capsys.readouterr().out)["components"]["inductors"]

    assert [[c["core"]["name"] for c in i["toroid_recommendations"]] for i in inductors] == [
        ["T68-2"],
        ["T68-2"],
    ]


def test_bp_json_has_top_level_candidates_and_compatibility_alias(bp_result, capsys):
    bp_display(bp_result, output_format="json", eseries=None, show_plot=False)
    data = json.loads(capsys.readouterr().out)

    assert [c["core"]["name"] for c in data["resonator_toroid_candidates"]] == ["T68-2"]
    assert data["resonator_toroid_recommendations"] == data["resonator_toroid_candidates"]
    assert data["resonator_toroid_candidates"][0]["winding"]["turns"] == 10


@pytest.mark.parametrize("display", ["lp", "bp"])
def test_json_no_toroids_omits_candidate_keys(lp_result, bp_result, capsys, display):
    if display == "lp":
        lp_display(lp_result, output_format="json", show_match=False, include_toroids=False)
        data = json.loads(capsys.readouterr().out)
        assert all("toroid_recommendations" not in i for i in data["components"]["inductors"])
    else:
        bp_display(bp_result, output_format="json", eseries=None, include_toroids=False)
        data = json.loads(capsys.readouterr().out)
        assert "resonator_toroid_candidates" not in data
        assert "resonator_toroid_recommendations" not in data


def test_lp_csv_carries_best_candidate_on_inductor_rows_only(lp_result, capsys):
    lp_display(lp_result, output_format="csv", show_match=False)
    rows = _csv_rows(capsys.readouterr().out)

    by_kind = {prefix: [r for r in rows if r["Component"].startswith(prefix)] for prefix in "LC"}
    assert [(r["ToroidCore"], r["ToroidTurns"]) for r in by_kind["L"]] == [("T68-2", "15")] * 2
    assert all(r["ToroidErrorPct"] == "-0.40" for r in by_kind["L"])
    assert all(r["ToroidWarnings"] == NOT_ASSESSED_WARNING for r in by_kind["L"])
    assert by_kind["C"] and all(r["ToroidCore"] == "" for r in by_kind["C"])


def test_bp_csv_repeats_shared_candidate_on_every_resonator_row(bp_result, capsys):
    bp_display(bp_result, output_format="csv", eseries=None)
    rows = _csv_rows(capsys.readouterr().out)

    inductor_rows = [r for r in rows if r["Component"].startswith("L")]
    assert [r["Component"] for r in inductor_rows] == ["L1", "L2", "L3"]
    assert {(r["ToroidCore"], r["ToroidTurns"]) for r in inductor_rows} == {("T68-2", "10")}
    assert all(r["ToroidCore"] == "" for r in rows if not r["Component"].startswith("L"))


@pytest.mark.parametrize("display", ["lp", "bp"])
def test_csv_no_toroids_drops_toroid_columns(lp_result, bp_result, capsys, display):
    if display == "lp":
        lp_display(lp_result, output_format="csv", show_match=False, include_toroids=False)
    else:
        bp_display(bp_result, output_format="csv", eseries=None, include_toroids=False)
    header = next(csv.reader(io.StringIO(capsys.readouterr().out)))

    assert not any(column.startswith("Toroid") for column in header)


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (("lp", "bw", "pi", "10MHz", "-n", "5"), LP_RANKED[:1] * 2),
        (("lp", "bw", "pi", "10MHz", "-n", "5", "--toroid-full"), LP_RANKED * 2),
        (("lp", "bw", "pi", "10MHz", "-n", "5", "--toroid-compact"), LP_RANKED[:1] * 2),
        # HP pi 10 MHz, n=3: L1 = L2 = 0.796 µH, which all three parts realize.
        (("hp", "bw", "pi", "10MHz", "-n", "3"), ["T68-2"] * 2),
        (("hp", "bw", "pi", "10MHz", "-n", "3", "--toroid-full"), ["T68-2", "T50-2", "T25-6"] * 2),
        # A fixed 1.3 µH tank at 10 MHz qualifies T25-6, T68-2, and T50-2 in that order.
        (BP_FIXED_TANK, ["T25-6"]),
        ((*BP_FIXED_TANK, "--toroid-full"), ["T25-6", "T68-2", "T50-2"]),
    ],
    ids=["lp-default", "lp-full", "lp-compact", "hp-default", "hp-full", "bp-default", "bp-full"],
)
def test_cli_toroid_flags_select_table_detail(monkeypatch, capsys, arguments, expected):
    monkeypatch.setattr(sys, "argv", ["filter-calc", *arguments, "--no-match"])

    main()
    out = capsys.readouterr().out

    assert _candidate_cores(out) == expected
    assert ("ωL/Rdc≤" in out) is ("--toroid-compact" in arguments)


def test_cli_no_toroids_removes_candidates_from_every_format(monkeypatch, capsys):
    for output_format in ("table", "json", "csv"):
        monkeypatch.setattr(
            sys,
            "argv",
            ["filter-calc", "lp", "bw", "pi", "10MHz", "--no-toroids", "--format", output_format],
        )
        main()
        assert "toroid" not in capsys.readouterr().out.lower(), output_format


@pytest.mark.parametrize("detail", ["--toroid-full", "--toroid-compact"])
def test_cli_table_section_states_every_not_assessed_quantity(monkeypatch, capsys, detail):
    monkeypatch.setattr(sys, "argv", ["filter-calc", "lp", "bw", "pi", "10MHz", detail])

    main()
    out = capsys.readouterr().out

    assert out.count(NOT_ASSESSED_WARNING) == 1
    section = out[out.index(SECTION_TITLE) :]
    assert section.splitlines()[2] == NOT_ASSESSED_WARNING
    for quantity in ("RF Q", "core loss", "SRF", "saturation", "thermal rise", "power handling"):
        assert quantity in section


def test_cli_json_and_csv_keep_the_not_assessed_warning_per_candidate(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["filter-calc", "lp", "bw", "pi", "10MHz", "--format", "json"])
    main()
    inductors = json.loads(capsys.readouterr().out)["components"]["inductors"]
    candidates = [c for item in inductors for c in item["toroid_recommendations"]]
    assert candidates
    assert all(c["warnings"] == [NOT_ASSESSED_WARNING] for c in candidates)

    monkeypatch.setattr(sys, "argv", ["filter-calc", "lp", "bw", "pi", "10MHz", "--format", "csv"])
    main()
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    warnings = {row["ToroidWarnings"] for row in rows if row["ToroidCore"]}
    assert warnings == {NOT_ASSESSED_WARNING}
