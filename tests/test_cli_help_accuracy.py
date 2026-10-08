"""User-facing CLI help, examples, and explanations must agree with actual behavior."""

import argparse
import json
import re
import shlex
from unittest.mock import patch

import pytest

from filter_lib import cli
from filter_lib.cli import bandpass_cmd, highpass_cmd, lowpass_cmd
from filter_lib.highpass.calculations import calculate_chebyshev as hp_chebyshev
from filter_lib.lowpass.calculations import calculate_chebyshev as lp_chebyshev
from filter_lib.shared.cli_aliases import (
    FILTER_EXPLANATIONS,
    FILTER_EXPLANATIONS_BANDPASS,
    FILTER_EXPLANATIONS_HIGHPASS,
)


def _main(*arguments: str) -> None:
    with patch("sys.argv", ["filter-calc", *arguments]):
        cli.main()


def _help(*arguments: str, capsys) -> str:
    with pytest.raises(SystemExit) as exc_info:
        _main(*arguments, "--help")
    assert exc_info.value.code == 0
    return capsys.readouterr().out


@pytest.mark.parametrize("command", ["lp", "hp"])
def test_ladder_help_pi_and_t_forms_match_rendered_topology(command: str, capsys) -> None:
    output = _help(command, capsys=capsys).lower()
    assert "pi=shunt-first" in output
    assert "t=series-first" in output

    for topology, first_element in (("pi", "  IN ───┬"), ("t", "  IN ───┤")):
        _main(command, "bw", topology, "10MHz", "--no-match", "--no-toroids")
        lines = capsys.readouterr().out.splitlines()
        diagram_first_line = lines[lines.index("Topology:") + 1]
        assert diagram_first_line.startswith(first_element)


@pytest.mark.parametrize(
    ("command", "design"),
    [
        ("lp", ("bw", "pi", "10MHz")),
        ("hp", ("bw", "t", "10MHz")),
        ("bp", ("bw", "top", "-f", "14.175MHz", "-b", "350kHz")),
    ],
)
def test_eseries_help_and_table_both_disclaim_part_tolerance(command, design, capsys) -> None:
    # Help wraps to the terminal width, so compare with the line breaks folded.
    output = " ".join(_help(command, capsys=capsys).lower().split())
    # The help must say E-series means values per decade, not part tolerance.
    assert "e12, e24, or e96 (12, 24, or 96 values per decade)" in output
    assert "not part tolerance" in output

    _main(command, *design, "--no-toroids")
    assert "E24 = 24 standard values per decade; it does not set the part tolerance." in (
        capsys.readouterr().out
    )


_DEFAULT_PATTERN = re.compile(r"\(default: ([^;)]+)")


def _help_defaults(setup) -> dict[str, str]:
    """Map option dest to the default value its help text advertises."""
    parser = argparse.ArgumentParser()
    setup(parser)
    defaults = {}
    for action in parser._actions:
        match = _DEFAULT_PATTERN.search(action.help or "")
        if match:
            defaults[action.dest] = match.group(1)
    return defaults


@pytest.mark.parametrize(
    ("setup", "design", "order_field", "order_dest", "capacitor_group"),
    [
        (
            lowpass_cmd.setup_parser,
            ("lp", "ch", "pi", "10MHz"),
            "order",
            "components",
            "capacitors",
        ),
        (
            highpass_cmd.setup_parser,
            ("hp", "ch", "t", "10MHz"),
            "order",
            "components",
            "capacitors",
        ),
        (
            bandpass_cmd.setup_parser,
            ("bp", "ch", "top", "-f", "14.175MHz", "-b", "350kHz"),
            "n_resonators",
            "resonators",
            "tank_capacitors",
        ),
    ],
    ids=["lowpass", "highpass", "bandpass"],
)
def test_advertised_defaults_are_the_defaults_used(
    setup, design, order_field, order_dest, capacitor_group, capsys
):
    advertised = _help_defaults(setup)

    _main(*design, "--format", "json", "--no-toroids")
    payload = json.loads(capsys.readouterr().out)

    assert payload["impedance_ohms"] == float(advertised["impedance"])
    assert payload["ripple_db"] == float(advertised["ripple"])
    assert payload[order_field] == int(advertised[order_dest])
    first_capacitor = payload["components"][capacitor_group][0]
    assert first_capacitor["standard_match"]["series"] == advertised["eseries"]

    assert advertised["spice_realization"] == "nominal-build"
    _main(*design, "--format", "spice")
    assert "* values: chosen parts (nominal-build)" in capsys.readouterr().out


def test_every_top_level_help_example_runs_cleanly(capsys) -> None:
    help_text = _help(capsys=capsys)
    examples = [
        shlex.split(match.group(1))
        for match in re.finditer(r"^  filter-calc (\S[^#\n]*?)\s*(?:#.*)?$", help_text, re.M)
    ]
    runnable = [example for example in examples if example[0] not in {"wizard", "w"}]
    assert len(runnable) == 7

    for example in runnable:
        _main(*example)
        captured = capsys.readouterr()
        assert captured.err == "", example
        if "--format" in example and example[example.index("--format") + 1] == "json":
            assert json.loads(captured.out)["components"], example
        else:
            assert re.search(r"^\w+ .*Filter$", captured.out, re.M), example


@pytest.mark.parametrize("command", ["lp", "hp", "bp"])
def test_explain_rejects_machine_output_mode_instead_of_ignoring_it(command: str, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _main(command, "bw", "--explain", "--format", "json")

    assert exc_info.value.code == 2
    assert (
        "--explain prints only a description of the filter type; remove --format json"
        in capsys.readouterr().err
    )


@pytest.mark.parametrize("command", ["lp", "hp"])
def test_explain_still_rejects_conflicting_topology_forms(command: str, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _main(command, "bw", "pi", "--topology", "t", "--explain")

    assert exc_info.value.code == 2
    assert "topology supplied both positionally and by flag" in capsys.readouterr().err


@pytest.mark.parametrize(
    "explanation",
    [FILTER_EXPLANATIONS_HIGHPASS["bessel"], FILTER_EXPLANATIONS_BANDPASS["bessel"]],
    ids=["highpass", "bandpass"],
)
def test_transformed_bessel_explanations_do_not_claim_flat_delay(explanation):
    """LP-to-HP/BP transformations do not preserve the prototype's flat group delay."""
    normalized = " ".join(explanation.lower().split())
    assert "flat group delay" in normalized
    assert "not preserved" in normalized
    assert "linear phase" not in normalized


@pytest.mark.parametrize(("command", "calculate"), [("lp", lp_chebyshev), ("hp", hp_chebyshev)])
def test_ladder_chebyshev_explanation_states_cutoff_and_odd_order(command, calculate, capsys):
    """Both facts are enforced: the cutoff is the ripple edge and even orders are rejected."""
    _main(command, "ch", "--explain")
    text = capsys.readouterr().out

    assert "- Cutoff is the ripple-band edge; the -3 dB point lies beyond it" in text
    assert "- Odd order only (3, 5, 7, 9) for equal source and load impedance" in text
    with pytest.raises(ValueError, match="odd number of components"):
        calculate(10e6, 50.0, 0.5, 4, "pi")


def test_lowpass_and_highpass_explanations_list_the_same_points():
    """Apart from the transformed-Bessel delay note, LP and HP describe each type alike."""
    for filter_type in ("butterworth", "chebyshev"):
        lowpass = FILTER_EXPLANATIONS[filter_type].splitlines()
        highpass = FILTER_EXPLANATIONS_HIGHPASS[filter_type].splitlines()
        assert lowpass[0].replace("Low-Pass", "High-Pass") == highpass[0]
        assert lowpass[1:] == highpass[1:]


def test_top_level_help_describes_the_tool_and_lists_subcommands_once(capsys) -> None:
    help_text = _help(capsys=capsys)

    assert "Calculate LC low-pass, high-pass, and band-pass filter component values." in help_text
    assert "Subcommands:" not in help_text
    assert help_text.count("Coupled-resonator band-pass filter") == 1


def test_wizard_help_says_what_the_subcommand_starts(capsys) -> None:
    help_text = " ".join(_help("wizard", capsys=capsys).split())

    assert (
        "Start the interactive terminal wizard (same as running filter-calc with no arguments)."
        in help_text
    )


@pytest.mark.parametrize("command", ["lp", "bp"])
def test_help_does_not_split_hyphenated_option_names(command, capsys) -> None:
    help_text = _help(command, capsys=capsys)

    assert "--spice-\n" not in help_text
    assert "nominal-\n" not in help_text
