"""Regression tests for CLI options that must never be silently ignored."""

import argparse
import csv
import io
import json
import re
import sys

import pytest

from filter_lib.cli import bandpass_cmd, highpass_cmd, lowpass_cmd, main


def _run(monkeypatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["filter-calc", *arguments])
    main()


@pytest.mark.parametrize("setup", [lowpass_cmd.setup_parser, highpass_cmd.setup_parser])
def test_ladder_parsers_track_explicit_eseries_even_when_default_is_named(setup) -> None:
    parser = argparse.ArgumentParser()
    setup(parser)

    assert parser.parse_args(["bw", "pi", "10MHz"])._eseries_explicit is False
    assert parser.parse_args(["bw", "pi", "10MHz", "-e", "E24"])._eseries_explicit is True


def test_bandpass_parser_tracks_explicit_eseries() -> None:
    parser = argparse.ArgumentParser()
    bandpass_cmd.setup_parser(parser)

    base = ["bw", "top", "-f", "10MHz", "-b", "500kHz"]
    assert parser.parse_args(base)._eseries_explicit is False
    assert parser.parse_args([*base, "--eseries", "E24"])._eseries_explicit is True


@pytest.mark.parametrize("series", ["E12", "E24", "E96"])
@pytest.mark.parametrize(
    "mode",
    [
        ("--raw",),
        ("--quiet",),
        ("--plot-data", "json"),
        ("--explain",),
        ("--format", "spice", "--spice-realization", "exact"),
    ],
)
def test_eseries_is_rejected_when_output_mode_cannot_represent_it(
    monkeypatch, capsys, series, mode
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, "lp", "bw", "pi", "10MHz", "-e", series, *mode)

    assert exc_info.value.code == 2
    assert "--eseries" in capsys.readouterr().err


def test_raw_build_analysis_can_use_explicit_eseries(monkeypatch, capsys) -> None:
    _run(
        monkeypatch,
        "lp",
        "bw",
        "pi",
        "10MHz",
        "--raw",
        "-e",
        "E12",
        "--sim-build",
        "--no-toroids",
        "--analysis-points",
        "51",
    )

    assert "Realized-Build Analysis" in capsys.readouterr().out


def test_nominal_spice_can_use_explicit_eseries(monkeypatch, capsys) -> None:
    _run(
        monkeypatch,
        "lp",
        "bw",
        "pi",
        "10MHz",
        "-e",
        "E96",
        "--format",
        "spice",
        "--spice-realization",
        "nominal-build",
        "--no-toroids",
    )

    deck = capsys.readouterr().out
    assert "C1 1 0 3.16e-10" in deck
    assert "C1A" not in deck


def test_explicit_eseries_conflicts_with_no_match(monkeypatch, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, "lp", "bw", "pi", "10MHz", "-e", "E96", "--no-match")

    assert exc_info.value.code == 2
    assert "cannot be combined" in capsys.readouterr().err


@pytest.mark.parametrize("detail_flag", ["--toroid-compact", "--toroid-full"])
def test_toroid_table_detail_conflicts_with_quiet(monkeypatch, capsys, detail_flag) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, "lp", "bw", "pi", "10MHz", "--quiet", detail_flag)

    assert exc_info.value.code == 2
    assert "--quiet" in capsys.readouterr().err


@pytest.mark.parametrize(
    "flags",
    [
        ("--toroid-compact", "--toroid-full"),
        ("--no-toroids", "--toroid-full"),
    ],
)
def test_contradictory_toroid_display_controls_are_rejected(monkeypatch, capsys, flags) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, "hp", "bw", "t", "10MHz", *flags)

    assert exc_info.value.code == 2
    assert "toroid" in capsys.readouterr().err.lower()


@pytest.mark.parametrize(
    "command",
    [
        ("lp", "bw", "pi", "10MHz"),
        ("hp", "bw", "t", "10MHz"),
    ],
)
def test_ladder_csv_with_toroid_warning_is_rectangular(monkeypatch, capsys, command) -> None:
    _run(monkeypatch, *command, "--format", "csv")

    rows = list(csv.reader(io.StringIO(capsys.readouterr().out)))
    warning_index = rows[0].index("ToroidWarnings")
    assert all(len(row) == len(rows[0]) for row in rows)
    warnings = [row[warning_index] for row in rows[1:] if row[warning_index]]
    assert warnings
    assert any("RF Q, core loss" in warning for warning in warnings)


@pytest.mark.parametrize(
    "arguments",
    [
        ("1e-300", "1.5e-9"),
        ("1e307", "1.5e-16"),
    ],
)
def test_extreme_finite_csv_values_never_render_as_inf_or_zero(
    monkeypatch, capsys, arguments
) -> None:
    frequency, impedance = arguments
    _run(
        monkeypatch,
        "lp",
        "bw",
        "pi",
        frequency,
        "-z",
        impedance,
        "-n",
        "3",
        "--format",
        "csv",
        "--no-toroids",
        "--no-match",
    )

    output = capsys.readouterr().out
    rows = list(csv.DictReader(io.StringIO(output)))
    assert not re.search(r"(?i)(?<![a-z])(?:nan|[+-]?inf(?:inity)?)(?![a-z])", output)
    assert all(float(row["Value"]) != 0 for row in rows)


def test_infeasible_toroid_screen_does_not_abort_valid_extreme_design(monkeypatch, capsys) -> None:
    _run(monkeypatch, "lp", "bw", "pi", "10MHz", "-z", "1e-316", "--format", "json")

    payload = json.loads(capsys.readouterr().out)
    assert payload["components"]["inductors"][0]["value_henries"] == 5e-324
    assert payload["components"]["inductors"][0]["toroid_recommendations"] == []


def test_subnormal_capacitor_matching_reports_expert_action_in_default_json(
    monkeypatch, capsys
) -> None:
    _run(
        monkeypatch,
        "lp",
        "bw",
        "t",
        "1e307",
        "-z",
        "5e15",
        "--no-toroids",
        "--format",
        "json",
    )

    payload = json.loads(capsys.readouterr().out)
    match = payload["components"]["capacitors"][0]["standard_match"]
    assert match["status"] == "expert_override_required"
    assert match["selected"] is None


def test_subnormal_capacitor_table_does_not_present_nearest_as_recommendation(
    monkeypatch, capsys
) -> None:
    _run(
        monkeypatch,
        "lp",
        "bw",
        "t",
        "1e307",
        "-z",
        "5e15",
        "--no-toroids",
    )

    output = capsys.readouterr().out
    assert "policy selects at most one realization; expert action may be required" in output
    assert "Nearest Std (reference only)" in output
    assert "EXPERT ACTION REQUIRED; no part selected" in output
    assert "below the 1 pF automatic-selection floor" in output


@pytest.mark.parametrize(
    "arguments",
    [
        ("lp", "bw", "pi", "10MHz", "--explain", "-z", "75", "-n", "9"),
        (
            "bp",
            "bw",
            "top",
            "-f",
            "10MHz",
            "-b",
            "1MHz",
            "--explain",
            "--resonator-impedance",
            "200",
            "-n",
            "9",
        ),
    ],
)
def test_explain_rejects_design_controls_it_would_ignore(monkeypatch, capsys, arguments):
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, *arguments)

    assert exc_info.value.code == 2
    assert "--explain is standalone" in capsys.readouterr().err
