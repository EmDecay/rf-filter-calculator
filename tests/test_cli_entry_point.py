"""Top-level ``filter-calc`` entry point: dispatch, version reporting, and error translation."""

import io
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from unittest.mock import patch

import pytest

from filter_lib import __version__, cli

# Textbook quiet listings (Butterworth n=3, g = 1, 2, 1; 50 ohm; 10 MHz):
# LP Pi: C = g/(Z*w) = 318.31 pF, L = g*Z/w = 1.59 uH.
# HP T:  C = 1/(g*Z*w) = 318.31 pF, L = Z/(g*w) = 397.89 nH.
_LP_QUIET = "C1: 318.31 pF\nC2: 318.31 pF\nL1: 1.59 µH\n"
_HP_QUIET = "C1: 318.31 pF\nC2: 318.31 pF\nL1: 397.89 nH\n"
_QUIET_FLAGS = ("-q", "--no-match", "--no-toroids")


def _main(monkeypatch, *arguments: str) -> None:
    monkeypatch.setattr("sys.argv", ["filter-calc", *arguments])
    cli.main()


@pytest.mark.parametrize(
    ("command", "arguments", "expected"),
    [
        ("lowpass", ("bw", "pi", "10MHz", "-n", "3"), _LP_QUIET),
        ("lp", ("bw", "pi", "10MHz", "-n", "3"), _LP_QUIET),
        ("highpass", ("bw", "t", "10MHz", "-n", "3"), _HP_QUIET),
        ("hp", ("bw", "t", "10MHz", "-n", "3"), _HP_QUIET),
    ],
)
def test_ladder_commands_and_aliases_dispatch_to_their_category(
    monkeypatch, capsys, command, arguments, expected
):
    _main(monkeypatch, command, *arguments, *_QUIET_FLAGS)

    captured = capsys.readouterr()
    assert captured.out == expected
    assert captured.err == ""


def test_bandpass_command_and_alias_produce_identical_designs(monkeypatch, capsys):
    arguments = ("bw", "top", "-f", "14.175MHz", "-b", "350kHz", *_QUIET_FLAGS)
    _main(monkeypatch, "bandpass", *arguments)
    full_name = capsys.readouterr().out
    _main(monkeypatch, "bp", *arguments)
    alias = capsys.readouterr().out

    assert alias == full_name
    assert [line.split(":")[0] for line in full_name.splitlines()] == [
        "Cp1",
        "Cp2",
        "Cp3",
        "L1",
        "L2",
        "L3",
        "Cs12",
        "Cs23",
        "Ce_in",
        "Ce_out",
    ]


def test_no_subcommand_starts_the_wizard(monkeypatch):
    with patch("filter_lib.wizard.run_wizard") as run_wizard:
        _main(monkeypatch)

    run_wizard.assert_called_once_with()


@pytest.mark.parametrize("command", ["wizard", "w"])
def test_wizard_subcommand_and_alias_start_the_wizard(monkeypatch, command):
    with patch("filter_lib.cli.wizard_cmd.run_wizard") as run_wizard:
        _main(monkeypatch, command)

    run_wizard.assert_called_once_with()


def test_wizard_subcommand_accepts_no_options(monkeypatch, capsys):
    with patch("filter_lib.cli.wizard_cmd.run_wizard") as run_wizard:
        with pytest.raises(SystemExit) as exc_info:
            _main(monkeypatch, "wizard", "--format", "json")

    assert exc_info.value.code == 2
    assert "unrecognized arguments: --format json" in capsys.readouterr().err
    run_wizard.assert_not_called()


def test_version_reports_installed_distribution(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc_info:
        _main(monkeypatch, "--version")

    assert exc_info.value.code == 0
    assert capsys.readouterr().out == f"filter-calc {version('rf-filter-calculator')}\n"


def test_version_falls_back_to_package_literal_in_source_checkout(monkeypatch, capsys):
    missing = PackageNotFoundError("rf-filter-calculator")
    with patch("filter_lib.cli.metadata_version", side_effect=missing):
        with pytest.raises(SystemExit) as exc_info:
            _main(monkeypatch, "--version")

    assert exc_info.value.code == 0
    assert capsys.readouterr().out == f"filter-calc {__version__}\n"


def test_invalid_design_value_exits_1_with_clean_error(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc_info:
        _main(monkeypatch, "lp", "bw", "pi", "10MHz", "-n", "12", *_QUIET_FLAGS)

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.out == ""
    assert captured.err == "Error: Components must be 2-9\n"


def test_closed_stdout_pipe_exits_1_without_traceback(monkeypatch, capsys):
    class ClosedPipe(io.StringIO):
        def write(self, text):
            raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr("sys.argv", ["filter-calc", "lp", "bw", "pi", "10MHz", "--format", "json"])
    monkeypatch.setattr("sys.stdout", ClosedPipe())
    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1
    assert capsys.readouterr().err == ""


def test_closed_pipe_descriptor_is_redirected_so_the_exit_flush_cannot_fail(monkeypatch, capsys):
    read_end, write_end = os.pipe()
    os.close(read_end)
    stdout = open(write_end, "w", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["filter-calc", "lp", "bw", "pi", "10MHz", "--format", "json"])
    monkeypatch.setattr("sys.stdout", stdout)
    try:
        with pytest.raises(SystemExit) as exc_info:
            cli.main()
        # The descriptor now points at devnull, so output still buffered for the closed
        # pipe (what Python flushes at exit) is discarded instead of raising again.
        stdout.write("discarded")
        stdout.flush()
    finally:
        stdout.close()

    assert exc_info.value.code == 1
    assert capsys.readouterr().err == ""


def test_reader_closing_a_real_pipe_early_leaves_no_traceback():
    """``filter-calc ... | head`` must not print a BrokenPipeError traceback."""
    # Closing the read end before the child writes makes the broken pipe deterministic. Without
    # handling it, Python reports it while flushing stdout at exit and exits 120.
    command = [sys.executable, "-c", "from filter_lib.cli import main; main()"]
    command += ["bp", "bw", "top", "-f", "14.175MHz", "-b", "350kHz", "--plot-data", "csv"]
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child.stdout.close()
    _, stderr = child.communicate(timeout=60)

    assert child.returncode == 1
    assert stderr == b""


def test_keyboard_interrupt_exits_1_with_cancel_message(monkeypatch, capsys):
    with patch("filter_lib.wizard.run_wizard", side_effect=KeyboardInterrupt):
        with pytest.raises(SystemExit) as exc_info:
            _main(monkeypatch)

    assert exc_info.value.code == 1
    assert capsys.readouterr().err == "\nCancelled.\n"
