"""Run ``filter-calc`` in-process and capture what it prints.

Parity tests compare another surface (the shared dispatcher, the wizard, the web UI)
with live CLI output rather than stored fixtures, so a formatter change is checked
everywhere at once.
"""

from __future__ import annotations

import pytest

from filter_lib import cli


def cli_stdout(monkeypatch, capsys, *argv: str) -> str:
    """Run ``filter-calc *argv`` and return its standard output."""
    monkeypatch.setattr("sys.argv", ["filter-calc", *argv])
    capsys.readouterr()
    cli.main()
    return capsys.readouterr().out


def cli_stderr(monkeypatch, capsys, *argv: str) -> str:
    """Run a failing ``filter-calc *argv`` and return its standard error."""
    monkeypatch.setattr("sys.argv", ["filter-calc", *argv])
    capsys.readouterr()
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code != 0
    return capsys.readouterr().err


def cli_error_message(monkeypatch, capsys, *argv: str) -> str:
    """Return the message of the ``Error: ...`` line a failing command prints."""
    lines = [line for line in cli_stderr(monkeypatch, capsys, *argv).splitlines() if line.strip()]
    assert lines and lines[-1].startswith("Error: "), lines
    return lines[-1].removeprefix("Error: ")
