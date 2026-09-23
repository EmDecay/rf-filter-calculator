"""Every ``filter-calc`` command shown in the README and docs runs cleanly as written.

Commands are collected from lines that start with ``uv run filter-calc`` (joining ``\\``
continuations and dropping shell redirections or pipes). Syntax templates with ``<...>``
or ``[...]`` placeholders, shell variables, and the interactive wizard are not runnable
examples and are skipped.
"""

import json
import re
import shlex
import sys
from pathlib import Path

import pytest

from filter_lib import cli

_ROOT = Path(__file__).resolve().parent.parent
_DOCUMENTS = [_ROOT / "README.md", *sorted((_ROOT / "docs").glob("*.md"))]
_COMMAND = re.compile(r"^[ \t]*uv run filter-calc(?P<arguments>[^\n`|>#]*)", re.M)


def _documented_commands() -> list[tuple[str, str]]:
    """Return (first document, arguments) for each distinct documented command."""
    commands: dict[str, str] = {}
    for document in _DOCUMENTS:
        text = re.sub(r"\\\n\s*", " ", document.read_text(encoding="utf-8"))
        for match in _COMMAND.finditer(text):
            arguments = match.group("arguments").strip()
            if not arguments or any(marker in arguments for marker in "<[$"):
                continue
            if shlex.split(arguments)[0] in {"wizard", "w"}:
                continue
            commands.setdefault(arguments, document.name)
    return [(document, arguments) for arguments, document in commands.items()]


_EXAMPLES = _documented_commands()


def test_documentation_still_contains_runnable_examples():
    documents = {document for document, _arguments in _EXAMPLES}
    assert {"README.md", "user-guide.md", "quick-start.md", "sample-output.md"} <= documents
    assert len(_EXAMPLES) >= 30


@pytest.mark.parametrize(("document", "arguments"), _EXAMPLES, ids=[a for _d, a in _EXAMPLES])
def test_documented_example_runs_cleanly(monkeypatch, capsys, document, arguments):
    argv = shlex.split(arguments)
    monkeypatch.setattr(sys, "argv", ["filter-calc", *argv])
    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 0, f"{document}: {capsys.readouterr().err}"
    captured = capsys.readouterr()

    assert captured.out.strip(), document
    assert "Traceback" not in captured.err
    if "--format json" in arguments or "--plot-data json" in arguments:
        json.loads(captured.out, parse_constant=lambda constant: pytest.fail(constant))
