"""Subcommand parser wiring: alternative option spellings land on the fields ``run()`` reads."""

import argparse
import sys

import pytest

from filter_lib import cli
from filter_lib.bandpass.input_validation import RESONATOR_COUNT_MESSAGE
from filter_lib.cli import bandpass_cmd, highpass_cmd, lowpass_cmd
from filter_lib.shared.cli_aliases import COMPONENT_COUNT_MESSAGE
from filter_lib.shared.cli_helpers import add_filter_type_args


def _parser(setup) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="filter-calc")
    setup(parser)
    return parser


@pytest.mark.parametrize(
    ("setup", "argv", "expected"),
    [
        (
            lowpass_cmd.setup_parser,
            ["--type", "ch", "-T", "t", "-f", "10MHz", "-z", "75", "-n", "5", "-r", "0.25"],
            {
                "filter_type": None,
                "type_flag": "ch",
                "topology_pos": None,
                "topology_flag": "t",
                "frequency": None,
                "freq_flag": "10MHz",
                "impedance": "75",
                "components": 5,
                "ripple": 0.25,
            },
        ),
        (
            highpass_cmd.setup_parser,
            ["--topology", "pi", "--freq", "1MHz", "--type", "bs", "--impedance", "1k"],
            {
                "type_flag": "bs",
                "topology_flag": "pi",
                "freq_flag": "1MHz",
                "impedance": "1k",
            },
        ),
        (
            bandpass_cmd.setup_parser,
            [
                "--type",
                "c",
                "-c",
                "t",
                "--fl",
                "14MHz",
                "--fh",
                "14.35MHz",
                "-n",
                "5",
                "--tank-impedance",
                "100",
                "--q-safety",
                "3",
            ],
            {
                "filter_type": None,
                "type_flag": "c",
                "coupling_pos": None,
                "coupling_flag": "t",
                "f_low": "14MHz",
                "f_high": "14.35MHz",
                "resonators": 5,
                "resonator_impedance": "100",
                "q_safety": 3.0,
            },
        ),
        (
            bandpass_cmd.setup_parser,
            ["bw", "top", "-f", "14MHz", "-b", "500kHz", "--tank-inductance", "1.2uH"],
            {
                "filter_type": "bw",
                "coupling_pos": "top",
                "frequency": "14MHz",
                "bandwidth": "500kHz",
                "resonator_inductance": "1.2uH",
            },
        ),
    ],
    ids=["lowpass-short-flags", "highpass-long-flags", "bandpass-flags", "bandpass-positional"],
)
def test_option_spellings_populate_run_fields(setup, argv, expected):
    parsed = vars(_parser(setup).parse_args(argv))

    assert {key: parsed[key] for key in expected} == expected


@pytest.mark.parametrize("setup", [lowpass_cmd.setup_parser, highpass_cmd.setup_parser])
def test_removed_short_type_flag_is_rejected(setup, capsys):
    with pytest.raises(SystemExit) as exc_info:
        _parser(setup).parse_args(["-t", "bw", "pi", "10MHz"])

    assert exc_info.value.code == 2
    assert "unrecognized arguments: -t" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("setup", "argv", "message"),
    [
        (lowpass_cmd.setup_parser, ["elliptic", "pi", "10MHz"], "argument FILTER_TYPE"),
        (highpass_cmd.setup_parser, ["bw", "L", "10MHz"], "argument TOPOLOGY"),
        (bandpass_cmd.setup_parser, ["bw", "shunt"], "argument COUPLING"),
        (lowpass_cmd.setup_parser, ["bw", "pi", "10MHz", "-e", "E48"], "argument -e/--eseries"),
    ],
)
def test_unsupported_choices_are_rejected_by_the_parser(setup, argv, message, capsys):
    with pytest.raises(SystemExit) as exc_info:
        _parser(setup).parse_args(argv)

    assert exc_info.value.code == 2
    assert f"error: {message}: invalid choice" in capsys.readouterr().err


def test_non_ladder_category_gets_no_topology_argument():
    parser = argparse.ArgumentParser()
    add_filter_type_args(parser, "bandpass")
    args = parser.parse_args(["bessel", "10MHz"])

    assert (args.filter_type, args.frequency) == ("bessel", "10MHz")
    assert not hasattr(args, "topology_pos")
    assert not hasattr(args, "topology_flag")


@pytest.mark.parametrize(
    ("setup", "base", "dest"),
    [
        (lowpass_cmd.setup_parser, ["bw", "pi"], "freq_flag"),
        (highpass_cmd.setup_parser, ["bw", "t"], "freq_flag"),
        (bandpass_cmd.setup_parser, ["bw", "top", "-b", "500kHz"], "frequency"),
    ],
    ids=["lowpass", "highpass", "bandpass"],
)
@pytest.mark.parametrize("flag", ["-f", "--frequency", "--freq"])
def test_every_subcommand_accepts_both_frequency_spellings(setup, base, dest, flag):
    parsed = _parser(setup).parse_args([*base, flag, "14MHz"])

    assert getattr(parsed, dest) == "14MHz"


@pytest.mark.parametrize("setup", [lowpass_cmd.setup_parser, bandpass_cmd.setup_parser])
def test_help_lists_frequency_spellings_in_the_same_order(setup):
    help_text = _parser(setup).format_help()

    assert "-f FREQ, --frequency FREQ, --freq FREQ" in help_text


_COUNT_CASES = [
    (lowpass_cmd.setup_parser, "components"),
    (highpass_cmd.setup_parser, "components"),
    (bandpass_cmd.setup_parser, "resonators"),
]


@pytest.mark.parametrize(("setup", "dest"), _COUNT_CASES)
@pytest.mark.parametrize(
    ("value", "parsed"),
    [("2", 2), ("9", 9), ("+5", 5), (" 7 ", 7), ("12", 12), ("-1", -1), ("3.5", "3.5"), ("x", "x")],
)
def test_count_parses_whole_numbers_and_defers_every_rejection_to_run(setup, dest, value, parsed):
    """Argparse never rejects ``-n``; run() applies one rule with the shared message."""
    assert getattr(_parser(setup).parse_args(["-n", value]), dest) == parsed


@pytest.mark.parametrize(("setup", "dest"), _COUNT_CASES)
def test_count_help_shows_the_range(setup, dest):
    help_text = " ".join(_parser(setup).format_help().split())

    assert f"-n N, --{dest} N Number of {dest}, 2-9; Chebyshev needs an odd number" in help_text


@pytest.mark.parametrize(
    ("command", "message"),
    [
        (["lp", "bw", "pi", "10MHz"], COMPONENT_COUNT_MESSAGE),
        (["hp", "ch", "t", "10MHz"], COMPONENT_COUNT_MESSAGE),
        (["bp", "bw", "top", "-f", "14MHz", "-b", "500kHz"], RESONATOR_COUNT_MESSAGE),
        (["bp", "ch", "top", "--fl", "14MHz", "--fh", "14.35MHz"], RESONATOR_COUNT_MESSAGE),
    ],
)
@pytest.mark.parametrize("value", ["1", "0", "10", "3.5", "x", "", "1e1", "9" * 5000])
def test_every_bad_count_gets_the_shared_message_on_every_subcommand(
    command, message, value, monkeypatch, capsys
):
    monkeypatch.setattr(sys, "argv", ["filter-calc", *command, "-n", value])
    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1
    assert capsys.readouterr().err == f"Error: {message}\n"


@pytest.mark.parametrize(
    ("spelling", "canonical"),
    [
        ("exact", "exact"),
        ("calculated", "exact"),
        ("nominal-build", "nominal-build"),
        ("chosen-parts", "nominal-build"),
    ],
)
@pytest.mark.parametrize(
    "setup", [lowpass_cmd.setup_parser, highpass_cmd.setup_parser, bandpass_cmd.setup_parser]
)
def test_spice_realization_aliases_store_the_canonical_value(setup, spelling, canonical):
    parsed = _parser(setup).parse_args(["--spice-realization", spelling])

    assert parsed.spice_realization == canonical


@pytest.mark.parametrize("command", ["lp", "hp", "bp"])
def test_spice_realization_help_names_both_spellings(command, monkeypatch, capsys):
    # The real CLI formatter keeps hyphenated words such as nominal-build unbroken.
    monkeypatch.setattr(sys, "argv", ["filter-calc", command, "--help"])
    with pytest.raises(SystemExit):
        cli.main()
    help_text = " ".join(capsys.readouterr().out.split())

    assert "{exact,nominal-build,calculated,chosen-parts}" in help_text
    assert "nominal-build (or chosen-parts) uses the chosen parts" in help_text
    assert "exact (or calculated) uses the calculated values" in help_text
    assert "(default: nominal-build)" in help_text
