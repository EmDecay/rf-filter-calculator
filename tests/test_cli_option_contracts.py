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
    ("mode", "message"),
    [
        (
            ("--raw",),
            "--eseries has no effect with --raw, which skips standard-value matching; "
            "remove --eseries",
        ),
        (
            ("--quiet",),
            "--eseries has no effect with --quiet, which prints only calculated values; "
            "remove --eseries",
        ),
        (
            ("--plot-data", "json"),
            "--plot-data prints only frequency-response data; remove --eseries",
        ),
        (
            ("--explain",),
            "--explain prints only a description of the filter type; remove --eseries",
        ),
        (
            ("--format", "spice", "--spice-realization", "exact"),
            "--eseries has no effect on an exact SPICE deck, which uses the calculated values "
            "without losses; remove it or use --spice-realization nominal-build",
        ),
    ],
)
def test_eseries_is_rejected_when_output_mode_cannot_represent_it(
    monkeypatch, capsys, series, mode, message
) -> None:
    # --explain takes no design arguments, so it gets the filter type alone.
    design = ("lp", "bw") if mode == ("--explain",) else ("lp", "bw", "pi", "10MHz")
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, *design, "-e", series, *mode)

    assert exc_info.value.code == 2
    assert capsys.readouterr().err.endswith(f"filter-calc lowpass: error: {message}\n")


def test_raw_build_analysis_can_use_explicit_eseries(monkeypatch, capsys) -> None:
    _run(
        monkeypatch,
        "lp",
        "bw",
        "pi",
        "10MHz",
        "--raw",
        "-e",
        "E96",
        "--sim-build",
        "--no-toroids",
        "--analysis-points",
        "51",
    )

    lines = capsys.readouterr().out.splitlines()
    assert "│ C1: 3.183099e-10 F     │ L1: 1.591549e-06 H     │" in lines
    assert "Build Simulation (chosen parts; simulated, not measured)" in lines
    # E96 selects the single 316 pF part; the default E24 would build 47 pF + 270 pF.
    assert "  C1: 316.00 pF (E96)" in lines


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


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (
            ("--quiet", "--toroid-compact"),
            "--toroid-compact/--toroid-full cannot be used with --quiet",
        ),
        (
            ("--quiet", "--toroid-full"),
            "--toroid-compact/--toroid-full cannot be used with --quiet",
        ),
        (
            ("--toroid-compact", "--toroid-full"),
            "use only one of --toroid-compact or --toroid-full",
        ),
        (
            ("--no-toroids", "--toroid-full"),
            "--no-toroids cannot be combined with --toroid-compact or --toroid-full",
        ),
    ],
)
def test_contradictory_toroid_display_controls_are_rejected(
    monkeypatch, capsys, flags, message
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, "hp", "bw", "t", "10MHz", *flags)

    assert exc_info.value.code == 2
    assert f"error: {message}" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("command", "first_capacitor"),
    [
        (("hp", "bw", "t", "10MHz"), "C1"),
        # Two resonators keep the bandpass tolerance analysis cheap.
        (("bp", "bw", "top", "-f", "10MHz", "-b", "300kHz", "-n", "2"), "Cp1"),
    ],
)
def test_sim_build_table_appends_realized_build_block(
    monkeypatch, capsys, command, first_capacitor
) -> None:
    _run(monkeypatch, *command, "--sim-build", "--no-toroids", "--analysis-points", "51")

    output = capsys.readouterr().out
    component_table = output.index(f"│ {first_capacitor}: ")
    build_block = output.index("Build Simulation (chosen parts; simulated, not measured)")
    assert component_table < build_block


@pytest.mark.parametrize(
    "command",
    [
        ("lp", "bw", "pi", "10MHz", "--format", "csv"),
        ("hp", "ch", "t", "10MHz", "--format", "csv", "--no-match", "--no-toroids"),
        ("bp", "bw", "top", "-f", "14.175MHz", "-b", "350kHz", "--format", "csv"),
        ("bp", "bs", "top", "-f", "10MHz", "-b", "1MHz", "--format", "csv", "--no-match"),
        ("lp", "bw", "pi", "10MHz", "--plot-data", "csv"),
        ("hp", "bs", "t", "10MHz", "--plot-data", "csv"),
        ("bp", "bw", "top", "-f", "14.175MHz", "-b", "350kHz", "--plot-data", "csv"),
    ],
    ids=lambda command: " ".join(command),
)
def test_every_csv_output_uses_lf_rows_and_one_final_newline(monkeypatch, capsys, command) -> None:
    _run(monkeypatch, *command)

    output = capsys.readouterr().out
    assert "\r" not in output
    assert output.endswith("\n") and not output.endswith("\n\n")
    rows = list(csv.reader(io.StringIO(output)))
    assert len(rows) > 1 and all(len(row) == len(rows[0]) for row in rows)


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


@pytest.mark.parametrize("output_flags", [(), ("-q",), ("--format", "csv")])
def test_oversized_values_print_scientific_base_units_instead_of_hundreds_of_digits(
    monkeypatch, capsys, output_flags
) -> None:
    _run(monkeypatch, "lp", "bw", "pi", "1e-300", "--no-toroids", "--no-match", *output_flags)

    output = capsys.readouterr().out
    # C = 1/(2*pi*f*Z) and L = 2*Z/(2*pi*f) for 1e-300 Hz and 50 ohms.
    separator = "," if "csv" in output_flags else " "
    assert f"3.183099e+297{separator}F" in output
    assert f"1.591549e+301{separator}H" in output
    assert max(len(line) for line in output.splitlines()) <= 80


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
    assert "Each capacitor gets one choice" in output
    assert "  Use:            none (below 1 pF; see warning)" in output
    assert ", for reference only" in output
    assert (
        "  Warning: Below 1 pF no part is chosen automatically. Choose one manually, or" in output
    )
    assert '           turn on "Allow capacitors below 1 pF" (--allow-sub-pf).' in output


@pytest.mark.parametrize(
    ("arguments", "ignored"),
    [
        (("lp", "bw", "pi", "--explain"), "--topology"),
        (("hp", "bw", "-T", "t", "--explain"), "--topology"),
        (("lp", "bw", "--freq", "10MHz", "--explain"), "--frequency"),
        (("hp", "bw", "-f", "10MHz", "--explain"), "--frequency"),
        (("bp", "bw", "top", "--explain"), "--coupling"),
        (("bp", "bw", "-c", "top", "--explain"), "--coupling"),
        (("bp", "bw", "-f", "10MHz", "--explain"), "--frequency"),
        (("bp", "bw", "--fl", "9MHz", "--explain"), "--fl"),
        (("lp", "bw", "--explain", "-z", "75"), "--impedance"),
        (("bp", "bw", "--explain", "--resonator-inductance", "1uH"), "--resonator-inductance"),
    ],
)
def test_explain_names_each_single_design_control_it_would_ignore(
    monkeypatch, capsys, arguments, ignored
):
    """Each positional or flag spelling of a design control is reported on its own."""
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, *arguments)

    assert exc_info.value.code == 2
    assert capsys.readouterr().err.endswith(
        f"error: --explain prints only a description of the filter type; remove {ignored}\n"
    )


@pytest.mark.parametrize("toroid_flag", ["--toroid-compact", "--toroid-full"])
@pytest.mark.parametrize(
    "command", [("lp", "bw", "pi", "10MHz"), ("bp", "bw", "top", "-f", "10MHz", "-b", "1MHz")]
)
def test_plot_data_rejects_each_toroid_table_detail_flag(monkeypatch, capsys, command, toroid_flag):
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, *command, "--plot-data", "json", toroid_flag)

    assert exc_info.value.code == 2
    assert capsys.readouterr().err.endswith(
        "error: --plot-data prints only frequency-response data; remove --toroid-compact/--toroid-full\n"
    )


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
    assert "--explain prints only a description of the filter type" in capsys.readouterr().err


def _capture_run(monkeypatch, capsys, arguments: list[str]) -> tuple[object, str, str]:
    try:
        _run(monkeypatch, *arguments)
        code = 0
    except SystemExit as exc:
        code = exc.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.parametrize(
    ("alias", "canonical"), [("calculated", "exact"), ("chosen-parts", "nominal-build")]
)
@pytest.mark.parametrize(
    "arguments",
    [
        ["lp", "bw", "pi", "10MHz", "--format", "spice"],
        ["hp", "ch", "t", "10MHz", "--format", "spice", "--inductor-q", "100"],
        ["bp", "ch", "top", "-f", "14.175MHz", "-b", "350kHz", "--format", "spice", "--qu", "200"],
        ["bp", "bw", "top", "-f", "14.175MHz", "-b", "350kHz", "--format", "spice", "--no-match"],
        ["lp", "bw", "pi", "10MHz"],
    ],
    ids=["lp-lossless", "hp-inductor-q", "bp-qu", "bp-no-match", "not-spice"],
)
def test_spice_realization_alias_output_is_byte_identical_to_canonical(
    monkeypatch, capsys, alias, canonical, arguments
) -> None:
    """Output, stderr, and exit code match, including validation messages that name the value."""
    expected = _capture_run(monkeypatch, capsys, [*arguments, "--spice-realization", canonical])
    actual = _capture_run(monkeypatch, capsys, [*arguments, "--spice-realization", alias])

    assert actual == expected
    assert expected[1] or expected[2]
