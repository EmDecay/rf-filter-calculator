"""Regression tests for user-facing CLI terminology."""

from unittest.mock import patch

import pytest

from filter_lib import cli


@pytest.mark.parametrize("command", ["lp", "hp"])
def test_ladder_help_explains_pi_and_t_forms(command: str, capsys) -> None:
    with patch("sys.argv", ["filter-calc", command, "--help"]), pytest.raises(SystemExit):
        cli.main()

    output = capsys.readouterr().out.lower()
    assert "pi=shunt-first" in output
    assert "t=series-first" in output


@pytest.mark.parametrize("command", ["lp", "hp", "bp"])
def test_eseries_help_does_not_imply_part_tolerance(command: str, capsys) -> None:
    with patch("sys.argv", ["filter-calc", command, "--help"]), pytest.raises(SystemExit):
        cli.main()

    output = capsys.readouterr().out.lower()
    assert "preferred-value density" in output
    assert "not part tolerance" in output


@pytest.mark.parametrize("command", ["lp", "hp", "bp"])
def test_explain_rejects_machine_output_mode_instead_of_ignoring_it(command: str, capsys) -> None:
    with (
        patch("sys.argv", ["filter-calc", command, "bw", "--explain", "--format", "json"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli.main()

    assert exc_info.value.code == 2
    assert "--explain is standalone" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["lp", "hp"])
def test_explain_still_rejects_conflicting_topology_forms(command: str, capsys) -> None:
    with (
        patch("sys.argv", ["filter-calc", command, "bw", "pi", "--topology", "t", "--explain"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        cli.main()

    assert exc_info.value.code == 2
    assert "topology supplied both" in capsys.readouterr().err
