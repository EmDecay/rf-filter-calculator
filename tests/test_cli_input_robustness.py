"""The real ``filter-calc`` entry point never crashes and never emits non-finite output.

A representative grid touches every command-line option at least once for each filter
kind. Valid commands must exit 0 with output that is structurally valid for the selected
format; invalid or extreme input must exit 1 (design value) or 2 (usage) with a one-line
human message on stderr, no stdout, and no Python traceback.
"""

import csv
import io
import json
import re
import shlex
import sys

import pytest

from filter_lib import cli

_NON_FINITE = re.compile(r"(?i)(?<![a-z])(?:nan|[+-]?inf(?:inity)?)(?![a-z])")
_QUIET_LINE = re.compile(r"^(?:C|L|Cp|Cs|Ce_)\w*: -?\d+(?:\.\d+)?(?:e[+-]\d+)? [a-zµ]*[FH]$")
# Fast 51-point build grid; the default 601 is exercised by the documented examples.
_FAST_BUILD = "--sim-build --analysis-points 51"


def _invoke(monkeypatch, capsys, command: str) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "argv", ["filter-calc", *shlex.split(command)])
    try:
        cli.main()
        code = 0
    except SystemExit as exc:
        code = exc.code
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _strict_json(text: str):
    def reject(constant: str):
        raise AssertionError(f"non-standard JSON constant {constant}")

    return json.loads(text, parse_constant=reject)


def _option(argv: list[str], name: str) -> str | None:
    return argv[argv.index(name) + 1] if name in argv else None


def _assert_structurally_valid(command: str, out: str) -> None:
    """Check the output against the contract of the format the command selected."""
    argv = shlex.split(command)
    output_format = _option(argv, "--format") or "table"
    plot_data = _option(argv, "--plot-data")
    assert out.strip(), "valid command printed nothing"
    assert "Traceback" not in out

    if plot_data == "json":
        points = _strict_json(out)["data"]
        frequencies = [point["frequency_hz"] for point in points]
        assert len(points) >= 51
        assert all(low < high for low, high in zip(frequencies, frequencies[1:]))
    elif plot_data == "csv":
        rows = list(csv.reader(io.StringIO(out)))
        assert rows[0] == ["frequency_hz", "magnitude_db"]
        assert all(len(row) == 2 for row in rows)
        assert not _NON_FINITE.search(out)
        assert all(float(frequency) > 0 for frequency, _db in rows[1:])
    elif output_format == "json":
        payload = _strict_json(out)
        assert all(payload["components"].values())
        if "--sim-build" in argv:
            assert {"target", "simulated", "nominal_build", "tolerance_analysis"} <= set(payload)
        if "--sim-matched" in argv:
            assert payload["matched_sim"]["deprecated"] is True
    elif output_format == "csv":
        rows = list(csv.reader(io.StringIO(out)))
        header = rows[0]
        assert header[:3] == ["Component", "Value", "Unit"]
        assert len(rows) > 1
        assert all(len(row) == len(header) for row in rows)
        assert not _NON_FINITE.search(out)
        assert all(float(row[1]) > 0 for row in rows[1:])
    elif output_format == "spice":
        assert out.startswith("* RF Filter Calculator generic AC deck\n")
        assert re.search(r"(?m)^\.ac (?:dec|lin) \d+ \S+ \S+$", out)
        assert re.search(r"\n\.print ac vm\(\d+\)\n\.end\n$", out)
        assert not _NON_FINITE.search(out)
        element_values = [line.split()[-1] for line in out.splitlines() if line[:1].isalpha()]
        assert all(float(value) > 0 for value in element_values[1:])
    elif "-q" in argv or "--quiet" in argv:
        lines = out.splitlines()
        assert lines
        assert all(_QUIET_LINE.match(line) for line in lines), lines
    else:
        assert not _NON_FINITE.search(out), _NON_FINITE.search(out)
        assert re.search(r"(?m)^\w+ .*Filter$", out)
        assert "Component Values" in out
        assert ("dB Threshold Summary" in out) is ("--plot" in argv)
        assert ("Realized-Build Analysis" in out) is ("--sim-build" in argv)
        assert ("legacy --sim-matched" in out) is ("--sim-matched" in argv)
        toroids_shown = "Screened Toroid Winding Candidates" in out or " target: " in out
        assert toroids_shown is ("--no-toroids" not in argv)


# Every ladder spelling, topology form, order bound, output format, and option appears at
# least once per ladder category.
_LADDER_VALID = [
    "{cmd} butterworth pi 10MHz",
    "{cmd} bw t 10MHz -n 2",
    "{cmd} b -T pi -f 7.1M -n 9 -q",
    "{cmd} --type bessel --topology t --freq 455kHz -n 6 --raw",
    "{cmd} bs pi 1.8m -n 9 --raw -q --no-toroids --no-match",
    "{cmd} chebyshev pi 28MHz -n 7 -r 1.0 --plot",
    "{cmd} ch t 3.5MHz -n 9 -r 0.01 --plot --toroid-compact -e E96",
    "{cmd} c pi '10 MHz' -n 3 -r 3.0 --toroid-full -e E12",
    "{cmd} bw pi 2.4GHz -n 5 -z 12.5 --no-match",
    "{cmd} bs t 1kHz -n 4 -z 1k --no-toroids",
    "{cmd} bw pi 10e6 -z 300ohm --format json",
    "{cmd} ch t 14MHz -r 0.5 -n 5 --format json -e E12 --no-toroids",
    "{cmd} bw t 10000000 -n 3 --format json --no-match",
    "{cmd} bs pi 50MHz -n 7 --format csv",
    "{cmd} ch pi 7MHz -n 3 -r 0.1 --format csv --no-match --no-toroids",
    "{cmd} bw pi 10MHz --format csv -e E12",
    "{cmd} bw pi 10MHz --format spice",
    "{cmd} ch t 14MHz -r 0.5 -n 5 --format spice --spice-realization exact --no-match",
    "{cmd} bs pi 10MHz --format spice --spice-realization nominal-build -e E12 "
    "--inductor-q 100 --capacitor-q 500 --source-resistance 25 --load-resistance 100 "
    "--loss-reference-frequency 3MHz --no-toroid-build",
    "{cmd} bw pi 10MHz --plot-data json",
    "{cmd} ch t 10MHz -r 0.5 -n 5 --plot-data csv --no-match --no-toroids",
    f"{{cmd}} bw pi 10MHz {_FAST_BUILD} --no-toroids",
    f"{{cmd}} ch pi 10MHz -r 0.5 {_FAST_BUILD} --format json -e E96 --cap-tolerance 2 "
    "--ind-tolerance 7.5 --inductor-q 50 --capacitor-q 400 --source-resistance 25ohm "
    "--load-resistance 1k --loss-reference-frequency 5MHz --samples 2 --seed 7",
    f"{{cmd}} bw t 10MHz {_FAST_BUILD} --raw -e E12 --no-toroid-build --sample-count 1 --seed 3",
    "{cmd} bw pi 10MHz --sim-matched --no-toroids",
    "{cmd} bs t 10MHz --sim-matched --format json",
    # Extreme but representable magnitudes stay finite in every format.
    "{cmd} bw pi 1e-3 --format csv --no-toroids",
    "{cmd} bw t 1e15 --no-toroids",
    "{cmd} bw pi 10MHz -z 1e-300 --format json",
    "{cmd} bw pi 1e300 --plot --no-toroids",
    "{cmd} ch pi 10MHz -r 1e-320 --format spice --spice-realization exact --no-match",
]

_BANDPASS_VALID = [
    "bp butterworth top -f 14.175MHz -b 350kHz",
    "bp bw t --fl 14MHz --fh 14.35MHz -n 2",
    "bp --type chebyshev -c top -f 7.15MHz -b 200kHz -n 9 -r 0.5 -q",
    "bp c top -f 10MHz -b 500kHz -n 3 -r 3.0 --raw",
    "bp bessel top -f 455kHz -b 10kHz -n 9 --raw -q --no-toroids --no-match",
    "bp bs t -f 100MHz -b 5MHz -n 4 --plot",
    "bp b top -f 14.2MHz -b 500kHz --plot --toroid-compact -e E96 --qu 150",
    "bp ch top -f 14.2MHz -b 500kHz -n 5 --toroid-full -e E12 --ql 180 --qc 500",
    "bp bw top -f 10MHz -b 500kHz -z 75 --no-match --resonator-impedance 100",
    "bp bw top -f 14.2MHz -b 500kHz --tank-impedance 200ohm --format csv --no-toroids",
    "bp bw top -f 14.2MHz -b 500kHz --resonator-inductance 1.2uH --format json --qc 300",
    "bp bw top -f 14.2MHz -b 500kHz --tank-inductance 800nH --plot-data csv",
    "bp ch top --fl 144MHz --fh 148MHz -n 5 -r 0.1 --format json -e E12 --no-toroids",
    "bp bw top -f 14.175MHz -b 350kHz --format json --no-match --q-safety 3",
    "bp bs top -f 7MHz -b 300kHz --format csv -e E96",
    "bp bw top -f 10MHz -b 500kHz --format spice",
    "bp ch top -f 10MHz -b 500kHz -n 5 --format spice --spice-realization exact --no-match",
    "bp bw top -f 10MHz -b 500kHz --format spice --spice-realization nominal-build --qu 200 "
    "-e E12 --source-resistance 25 --load-resistance 100 --loss-reference-frequency 9MHz",
    "bp bw top -f 10MHz -b 500kHz --format spice --inductor-q 100 --capacitor-q 500 "
    "--no-toroid-build",
    "bp bw top -f 10MHz -b 500kHz --plot-data json",
    "bp ch top -f 10MHz -b 500kHz -n 3 --plot-data csv --no-match --no-toroids",
    f"bp bw top -f 10MHz -b 300kHz -n 2 {_FAST_BUILD} --no-toroids",
    f"bp bs top --fl 14MHz --fh 14.35MHz -n 2 {_FAST_BUILD} --format json --qu 120 "
    "--cap-tolerance 2 --ind-tolerance 5 --source-resistance 25 --load-resistance 100 "
    "--loss-reference-frequency 14.1MHz --samples 1 --seed 5",
    f"bp bw top -f 10MHz -b 300kHz -n 2 {_FAST_BUILD} --raw -e E96 --inductor-q 80 "
    "--no-toroid-build",
    "bp bw top -f 10MHz -b 300kHz -n 2 --sim-matched --no-toroids",
    "bp bw top -f 10MHz -b 300kHz -n 2 --sim-matched --format json --no-toroids",
    "bp bw top -f 1e-3 -b 1e-4 --format csv --no-toroids",
    "bp bw top -f 1e300 -b 1e299 --format json",
]

_EXPLAIN_VALID = ["lp bw --explain", "hp ch --explain", "bp bs --explain", "bp c --explain"]

_VALID = (
    [command.format(cmd=cmd) for cmd in ("lp", "hp") for command in _LADDER_VALID]
    + _BANDPASS_VALID
    + _EXPLAIN_VALID
)


@pytest.mark.parametrize("command", _VALID)
def test_valid_command_exits_cleanly_with_well_formed_output(monkeypatch, capsys, command):
    code, out, err = _invoke(monkeypatch, capsys, command)

    assert code == 0, err
    assert "Traceback" not in err
    if "--explain" in command:
        assert out.strip() and not _NON_FINITE.search(out)
    else:
        _assert_structurally_valid(command, out)


# (command, exit code, exact final stderr line). Exit 1 is a rejected design value;
# exit 2 is an argparse usage error for the active subcommand.
_INVALID = [
    (
        "lp bw pi ''",
        2,
        "filter-calc lowpass: error: frequency required (try: filter-calc lp bw pi 10MHz)",
    ),
    ("lp bw pi 10XHz", 1, "Error: Invalid frequency: 10XHz"),
    ("lp bw pi --freq=-5MHz", 1, "Error: Frequency must be positive: -5MHz"),
    ("hp bw t 0", 1, "Error: Frequency must be positive: 0"),
    ("hp bw t 0Hz", 1, "Error: Frequency must be positive: 0Hz"),
    ("lp bw pi nan", 1, "Error: Frequency must be positive: nan"),
    ("lp bw pi inf", 1, "Error: Frequency must be positive: inf"),
    ("lp bw pi 1e400", 1, "Error: Frequency must be positive and finite: 1e400"),
    ("hp bw t 1e-400", 1, "Error: Frequency must be positive and finite: 1e-400"),
    ("lp bw pi 1e99999999999999999999", 1, "Error: Invalid frequency: 1e99999999999999999999"),
    ("lp bw pi 10MHz -z 0", 1, "Error: Impedance must be positive: 0"),
    ("lp bw pi 10MHz --impedance=-50", 1, "Error: Impedance must be positive: -50"),
    ("hp bw t 10MHz -z 1e400", 1, "Error: Impedance must be positive and finite: 1e400"),
    ("hp bw t 10MHz -z nan", 1, "Error: Impedance must be positive: nan"),
    ("hp bw t 10MHz -z 50Ohms", 1, "Error: Invalid impedance: 50ohms"),
    ("lp bw pi 10MHz -n 0", 1, "Error: Components must be 2-9"),
    ("lp bw pi 10MHz --components=-1", 1, "Error: Components must be 2-9"),
    ("hp bw t 10MHz -n 10", 1, "Error: Components must be 2-9"),
    ("hp bw t 10MHz -n 99", 1, "Error: Components must be 2-9"),
    (
        "lp bw pi 10MHz -n 3.5",
        2,
        "filter-calc lowpass: error: argument -n/--components: invalid int value: '3.5'",
    ),
    ("lp ch pi 10MHz -r 0", 1, "Error: Ripple must be positive"),
    ("hp ch t 10MHz --ripple=-0.1", 1, "Error: Ripple must be positive"),
    ("lp ch pi 10MHz -r 3.0001", 1, "Error: Ripple must be at most 3.0 dB"),
    ("hp ch t 10MHz -r inf", 1, "Error: Ripple must be at most 3.0 dB"),
    (
        "lp ch pi 10MHz -r nan",
        1,
        "Error: ripple_db must be positive, finite, and at most 3.0 dB for Chebyshev",
    ),
    (
        "hp ch t 10MHz -n 4",
        1,
        "Error: Chebyshev LP/HP requires odd order for equal source/load terminations "
        "(use 3, 5, 7, or 9)",
    ),
    (
        "lp bw pi 10MHz --sim-build --capacitor-tolerance nan",
        1,
        "Error: capacitor_tolerance_pct must be finite and in [0, 100)",
    ),
    (
        "hp bw t 10MHz --sim-build --inductor-tolerance 100",
        1,
        "Error: inductor_tolerance_pct must be finite and in [0, 100)",
    ),
    (
        "lp bw pi 10MHz --sim-build --inductor-q 0",
        1,
        "Error: inductor_q must be finite and in [0.01, 1e+09]",
    ),
    (
        "lp bw pi 10MHz --format spice --capacitor-q nan",
        1,
        "Error: capacitor_q must be finite and in [0.01, 1e+09]",
    ),
    (
        "hp bw t 10MHz --sim-build --sample-count 10001",
        1,
        "Error: sample_count must be an integer in [0, 10000]",
    ),
    (
        "lp bw pi 10MHz --sim-build --analysis-points 50",
        1,
        "Error: grid_points must be an integer in [51, 5001]",
    ),
    (
        "lp bw pi 10MHz --sim-build --analysis-points 5002",
        1,
        "Error: grid_points must be an integer in [51, 5001]",
    ),
    (
        "lp bw pi 10MHz --sim-build --source-resistance 0",
        1,
        "Error: Source resistance must be positive: 0",
    ),
    (
        "hp bw t 10MHz --sim-build --load-resistance=-50",
        1,
        "Error: Load resistance must be positive: -50",
    ),
    (
        "hp bw t 10MHz --format spice --inductor-q 10 --loss-reference-frequency nan",
        1,
        "Error: Loss reference frequency must be positive: nan",
    ),
    (
        "lp bw pi 10MHz --toroid-compact --toroid-full",
        2,
        "filter-calc lowpass: error: use only one of --toroid-compact or --toroid-full",
    ),
    (
        "hp bw t 10MHz --format json --plot",
        2,
        "filter-calc highpass: error: --plot cannot be used with --format json",
    ),
    (
        "lp bw pi 10MHz -e E12 --no-match",
        2,
        "filter-calc lowpass: error: --eseries cannot be combined with --no-match",
    ),
    (
        "hp bw pi 10MHz -T t",
        2,
        "filter-calc highpass: error: topology supplied both positionally and by flag; "
        "use only one form",
    ),
    ("bp bw top -f 10MHz -b 10MHz", 1, "Error: Bandwidth must be less than center frequency"),
    ("bp bw top -f 10MHz -b 20MHz", 1, "Error: Bandwidth must be less than center frequency"),
    (
        "bp bw top -f 10MHz -b 9.99MHz",
        1,
        "Error: Bandwidth too wide to realize: derived tank capacitances must be positive and "
        "finite",
    ),
    ("bp bw top -f 10MHz -b 0", 1, "Error: Bandwidth must be positive: 0"),
    ("bp bw top -f 10MHz --bandwidth=-1MHz", 1, "Error: Bandwidth must be positive: -1MHz"),
    ("bp bw top -f 10MHz -b 5XHz", 1, "Error: Invalid bandwidth: 5XHz"),
    ("bp bw top -f 0 -b 1MHz", 1, "Error: Center frequency must be positive: 0"),
    ("bp bw top --fl 0 --fh 14MHz", 1, "Error: Lower cutoff frequency must be positive: 0"),
    ("bp bw top --fl 14MHz --fh 14MHz", 1, "Error: Lower frequency must be less than upper"),
    ("bp bw top --fl 15MHz --fh 14MHz", 1, "Error: Lower frequency must be less than upper"),
    ("bp bw top --fl 14MHz --fh nan", 1, "Error: Upper cutoff frequency must be positive: nan"),
    (
        "bp bw top -f 14MHz -b 1MHz --fl 13MHz --fh 15MHz",
        2,
        "filter-calc bandpass: error: use (-f + -b) OR (--fl + --fh), not both",
    ),
    (
        "bp bw top -f 14MHz -b 1MHz -n 1",
        2,
        "filter-calc bandpass: error: argument -n/--resonators: invalid choice: 1 "
        "(choose from 2, 3, 4, 5, 6, 7, 8, 9)",
    ),
    ("bp ch top -f 14MHz -b 1MHz -n 4", 1, "Error: Chebyshev requires odd resonator count"),
    ("bp ch top -f 14MHz -b 1MHz -r nan", 1, "Error: Ripple must be positive and finite"),
    ("bp ch top -f 14MHz -b 1MHz -r 0", 1, "Error: Ripple must be positive and finite"),
    ("bp ch top -f 14MHz -b 1MHz -r 3.0001", 1, "Error: Ripple must be at most 3.0 dB"),
    ("bp bw top -f 14MHz -b 1MHz --qu nan", 1, "Error: Qu must be finite and in [0.01, 1e+09]"),
    ("bp bw top -f 14MHz -b 1MHz --qu inf", 1, "Error: Qu must be finite and in [0.01, 1e+09]"),
    ("bp bw top -f 14MHz -b 1MHz --qu 0", 1, "Error: Qu must be finite and in [0.01, 1e+09]"),
    ("bp bw top -f 14MHz -b 1MHz --qu 2e9", 1, "Error: Qu must be finite and in [0.01, 1e+09]"),
    ("bp bw top -f 14MHz -b 1MHz --ql nan", 1, "Error: QL must be finite and in [0.01, 1e+09]"),
    (
        "bp bw top -f 14MHz -b 1MHz --ql 100 --qc 0",
        1,
        "Error: QC must be finite and in [0.01, 1e+09]",
    ),
    (
        "bp bw top -f 14MHz -b 1MHz --q-safety nan --format json",
        1,
        "Error: q_safety must be positive and finite",
    ),
    (
        "bp bw top -f 14MHz -b 1MHz --q-safety 0 --format json",
        1,
        "Error: Q safety factor must be positive",
    ),
    (
        "bp bw top -f 14MHz -b 1MHz --resonator-impedance 0",
        1,
        "Error: Resonator impedance must be positive: 0",
    ),
    (
        "bp bw top -f 14MHz -b 1MHz --resonator-inductance 0",
        1,
        "Error: Resonator inductance must be positive: 0",
    ),
    (
        "bp bw top -f 14MHz -b 1MHz --resonator-inductance xyz",
        1,
        "Error: Invalid resonator inductance: xyz",
    ),
    (
        "bp bw top -f 14MHz -b 1MHz --resonator-impedance 1e300",
        1,
        "Error: Bandwidth too wide: tank capacitors Cp1, Cp3 would be negative. Reduce "
        "bandwidth, tank impedance, or resonator count.",
    ),
    (
        "bp bw top -f 10MHz -b 500kHz --resonator-impedance 1e-300",
        1,
        "Error: Resonator impedance 1e-300 ohm is too low to realize the input/output "
        "coupling to the 50 ohm terminations at this bandwidth and order; it must exceed "
        "about 2.5 ohm (necessary, not sufficient: a wide enough bandwidth fails at any tank "
        "value)",
    ),
    (
        "bp bw top -f 10MHz -b 1e-9",
        1,
        "Error: Bandwidth 1e-09 Hz is too narrow relative to the 1e+07 Hz center frequency "
        "to synthesize at double precision; use a fractional bandwidth of at least "
        "3.6e-12 (a bandwidth of at least 3.6e-05 Hz)",
    ),
    # Q values no lumped part has are rejected up front; 1e-300 once took 30 s to underflow.
    (
        "lp bw pi 10MHz --sim-build --inductor-q 1e-300",
        1,
        "Error: inductor_q must be finite and in [0.01, 1e+09]",
    ),
    (
        "hp bw t 10MHz --sim-build --capacitor-q 2e9",
        1,
        "Error: capacitor_q must be finite and in [0.01, 1e+09]",
    ),
    # Port resistances are limited to 1e-6..1e6 times the design impedance.
    (
        "lp bw pi 10MHz --sim-build --load-resistance 1e9",
        1,
        "Error: Load resistance 1e+09 ohm is outside the supported range 5e-05 to 5e+07 ohm "
        "(1e-06 to 1e+06 times the 50 ohm design impedance)",
    ),
    (
        "bp bw top -f 10MHz -b 500kHz -z 75 --format spice --source-resistance 1e-5",
        1,
        "Error: Source resistance 1e-05 ohm is outside the supported range 7.5e-05 to "
        "7.5e+07 ohm (1e-06 to 1e+06 times the 75 ohm design impedance)",
    ),
    (
        "bp bw top -f 14MHz -b 1MHz --qu 100 --format csv",
        2,
        "filter-calc bandpass: error: Loss-Q input --qu is not represented by this output "
        "mode; use table, JSON, or nominal-build SPICE",
    ),
    (
        "bp bw top -f 14MHz -b 1MHz --sim-build --analysis-points 0",
        1,
        "Error: grid_points must be an integer in [51, 5001]",
    ),
]


def _without_choice_quotes(line: str) -> str:
    """Drop the quoting that argparse's invalid-choice message varies by Python release.

    3.10 and 3.11 print "invalid choice: 1 (choose from 2, 3)", 3.12 quotes the rejected
    value, and 3.13 also quotes each choice. The option and its choices are the contract.
    """
    head, marker, tail = line.partition("invalid choice: ")
    return head + marker + tail.replace("'", "")


@pytest.mark.parametrize(("command", "code", "message"), _INVALID)
def test_invalid_input_exits_with_one_line_message_and_no_traceback(
    monkeypatch, capsys, command, code, message
):
    exit_code, out, err = _invoke(monkeypatch, capsys, command)

    assert exit_code == code
    assert out == ""
    assert "Traceback" not in err
    assert _without_choice_quotes(err.splitlines()[-1]) == message
    if code == 2:
        subcommand = message.split(":")[0]
        assert err.startswith(f"usage: {subcommand} ")
