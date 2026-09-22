"""Subcommand parser wiring: alternative option spellings land on the fields ``run()`` reads."""

import argparse

import pytest

from filter_lib.cli import bandpass_cmd, highpass_cmd, lowpass_cmd
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
        (lowpass_cmd.setup_parser, ["elliptic", "pi", "10MHz"], "argument filter_type"),
        (highpass_cmd.setup_parser, ["bw", "L", "10MHz"], "argument topology_pos"),
        (bandpass_cmd.setup_parser, ["bw", "shunt"], "argument coupling_pos"),
        (bandpass_cmd.setup_parser, ["bw", "top", "-n", "10"], "argument -n/--resonators"),
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
