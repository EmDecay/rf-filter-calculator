"""End-to-end integration tests: toroid block via LP/HP/BP display_results.

Covers flag matrix (--no-toroids, --toroid-compact) across text/JSON/CSV.
"""

import csv as _csv
import io
import json

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.display import display_results as bp_display
from filter_lib.highpass.calculations import calculate_butterworth as hp_calc
from filter_lib.highpass.display import display_results as hp_display
from filter_lib.lowpass.calculations import calculate_butterworth as lp_calc
from filter_lib.lowpass.display import display_results as lp_display


@pytest.fixture
def lp_result():
    caps, inds, order = lp_calc(10e6, 50.0, 5, topology="pi")
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": caps,
        "inductors": inds,
        "order": order,
        "ripple": None,
        "topology": "pi",
    }


@pytest.fixture
def hp_result():
    inds, caps, order = hp_calc(14e6, 50.0, 5, topology="t")
    return {
        "filter_type": "butterworth",
        "freq_hz": 14e6,
        "impedance": 50.0,
        "inductors": inds,
        "capacitors": caps,
        "order": order,
        "ripple": None,
        "topology": "t",
    }


@pytest.fixture
def bp_result():
    r = calculate_bandpass_filter(
        f0=14.175e6,
        bw=350e3,
        z0=50.0,
        n_resonators=3,
        filter_type="butterworth",
        coupling="top",
        ripple_db=0.5,
        q_safety=2.0,
    )
    r["f_low"] = 14e6
    r["f_high"] = 14.35e6
    return r


def test_lp_table_includes_toroid_block(lp_result, capsys):
    lp_display(lp_result, output_format="table", show_plot=False, show_match=False)
    out = capsys.readouterr().out
    assert "Toroid Winding Recommendations" in out
    assert "L1 target:" in out
    assert "L2 target:" in out
    assert "Q (DC est, upper bound)" in out


def test_lp_table_defaults_to_single_core_per_inductor(lp_result, capsys):
    lp_display(lp_result, output_format="table", show_plot=False, show_match=False)
    out = capsys.readouterr().out
    assert "  1. " in out
    assert "  2. " not in out


def test_lp_table_toroid_full_shows_multiple_cores(lp_result, capsys):
    lp_display(
        lp_result, output_format="table", show_plot=False, show_match=False, toroid_full=True
    )
    out = capsys.readouterr().out
    assert "  1. " in out
    assert "  2. " in out


def test_bp_table_defaults_to_single_core(bp_result, capsys):
    bp_display(bp_result, output_format="table", show_plot=False, eseries=None)
    out = capsys.readouterr().out
    assert "  1. " in out
    assert "  2. " not in out


def test_bp_table_toroid_full_shows_multiple_cores(bp_result, capsys):
    bp_display(bp_result, output_format="table", show_plot=False, eseries=None, toroid_full=True)
    out = capsys.readouterr().out
    assert "  1. " in out
    assert "  2. " in out


def test_lp_table_compact_single_line_per_rec(lp_result, capsys):
    lp_display(lp_result, output_format="table", show_match=False, toroid_compact=True)
    out = capsys.readouterr().out
    assert "Toroid Winding Recommendations" in out
    assert "Q≈" in out  # compact uses shorthand


def test_lp_table_no_toroids_omits_block(lp_result, capsys):
    lp_display(lp_result, output_format="table", show_match=False, include_toroids=False)
    out = capsys.readouterr().out
    assert "Toroid Winding Recommendations" not in out
    assert "see toroid recommendations" not in out
    assert "Inductors: wind to value" in out


def test_lp_json_has_toroid_recommendations(lp_result, capsys):
    lp_display(lp_result, output_format="json", show_match=False)
    data = json.loads(capsys.readouterr().out)
    for ind in data["components"]["inductors"]:
        assert "toroid_recommendations" in ind
        assert len(ind["toroid_recommendations"]) <= 3


def test_lp_json_no_toroids_omits_key(lp_result, capsys):
    lp_display(lp_result, output_format="json", show_match=False, include_toroids=False)
    data = json.loads(capsys.readouterr().out)
    for ind in data["components"]["inductors"]:
        assert "toroid_recommendations" not in ind


def test_lp_csv_includes_toroid_columns(lp_result, capsys):
    lp_display(lp_result, output_format="csv", show_match=False)
    out = capsys.readouterr().out
    header = next(_csv.reader(io.StringIO(out)))
    assert "ToroidCore" in header
    assert "ToroidQ_DC_Upper" in header


def test_lp_csv_no_toroids_matches_pre_feature(lp_result, capsys):
    """--no-toroids restores the pre-feature CSV column count exactly."""
    lp_display(lp_result, output_format="csv", show_match=False, include_toroids=False)
    out = capsys.readouterr().out
    header = next(_csv.reader(io.StringIO(out)))
    assert not any(col.startswith("Toroid") for col in header)


def test_lp_csv_inductor_row_has_toroid_data(lp_result, capsys):
    lp_display(lp_result, output_format="csv", show_match=False)
    out = capsys.readouterr().out
    rows = list(_csv.reader(io.StringIO(out)))
    header = rows[0]
    core_idx = header.index("ToroidCore")
    # Find first inductor row; value should be non-empty
    for row in rows[1:]:
        if row[0].startswith("L"):
            assert row[core_idx] != ""
            return
    pytest.fail("No inductor row found in CSV output")


def test_lp_quiet_suppresses_toroid_text(lp_result, capsys):
    """--quiet skips toroid TEXT block (JSON/CSV unaffected)."""
    lp_display(lp_result, output_format="table", quiet=True, show_match=False)
    out = capsys.readouterr().out
    assert "Toroid Winding Recommendations" not in out


def test_lp_no_toroids_precedence_over_compact(lp_result, capsys):
    """--no-toroids wins when both flags set."""
    lp_display(
        lp_result,
        output_format="table",
        show_match=False,
        include_toroids=False,
        toroid_compact=True,
    )
    out = capsys.readouterr().out
    assert "Toroid" not in out


def test_lp_out_of_range_freq_friendly_message(capsys):
    """500 MHz LP shows friendly message, not crash."""
    caps, inds, order = lp_calc(500e6, 50.0, 5, topology="pi")
    result = {
        "filter_type": "butterworth",
        "freq_hz": 500e6,
        "impedance": 50.0,
        "capacitors": caps,
        "inductors": inds,
        "order": order,
        "ripple": None,
        "topology": "pi",
    }
    lp_display(result, output_format="table", show_match=False)
    out = capsys.readouterr().out
    assert "No iron-powder" in out


def test_hp_table_includes_toroid_block(hp_result, capsys):
    hp_display(hp_result, output_format="table", show_plot=False, show_match=False)
    out = capsys.readouterr().out
    assert "Toroid Winding Recommendations" in out
    assert "L1 target:" in out


def test_hp_json_has_toroid_recommendations(hp_result, capsys):
    hp_display(hp_result, output_format="json", show_match=False)
    data = json.loads(capsys.readouterr().out)
    for ind in data["components"]["inductors"]:
        assert "toroid_recommendations" in ind


def test_bp_table_single_shared_block(bp_result, capsys):
    bp_display(bp_result, output_format="table", eseries=None, show_plot=False)
    out = capsys.readouterr().out
    assert "Toroid Winding Recommendations" in out
    assert "L_resonant (applies to L1…L" in out


def test_bp_json_has_top_level_toroids(bp_result, capsys):
    bp_display(bp_result, output_format="json", eseries=None, show_plot=False)
    data = json.loads(capsys.readouterr().out)
    assert "resonator_toroid_recommendations" in data
    assert len(data["resonator_toroid_recommendations"]) <= 3


def test_bp_json_no_toroids_omits_top_level_key(bp_result, capsys):
    bp_display(bp_result, output_format="json", eseries=None, include_toroids=False)
    data = json.loads(capsys.readouterr().out)
    assert "resonator_toroid_recommendations" not in data


def test_bp_csv_n_duplicate_rows(bp_result, capsys):
    """BP CSV: every inductor row (one per resonator) carries the same toroid cols."""
    bp_display(bp_result, output_format="csv", eseries=None)
    out = capsys.readouterr().out
    rows = list(_csv.reader(io.StringIO(out)))
    header = rows[0]
    core_idx = header.index("ToroidCore")
    l_rows = [r for r in rows[1:] if r[0].startswith("L")]
    assert len(l_rows) == bp_result["n_resonators"]
    # All L rows share the same toroid core value
    cores = {r[core_idx] for r in l_rows}
    assert len(cores) == 1
    assert "" not in cores


def test_bp_csv_no_toroids_drops_columns(bp_result, capsys):
    bp_display(bp_result, output_format="csv", eseries=None, include_toroids=False)
    out = capsys.readouterr().out
    header = next(_csv.reader(io.StringIO(out)))
    assert not any(col.startswith("Toroid") for col in header)


def test_bp_table_no_toroids_omits_dangling_note(bp_result, capsys):
    bp_display(bp_result, output_format="table", eseries=None, include_toroids=False)
    out = capsys.readouterr().out
    assert "Toroid Winding Recommendations" not in out
    assert "see toroid recommendations" not in out
    assert "Inductors: wind to value" in out


def test_bp_compact_block(bp_result, capsys):
    bp_display(bp_result, output_format="table", eseries=None, toroid_compact=True)
    out = capsys.readouterr().out
    assert "L_resonant (applies to L1…L" in out
    assert "Q≈" in out
