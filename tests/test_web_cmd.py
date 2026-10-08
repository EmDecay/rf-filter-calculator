"""``filter-calc web``: parser wiring, uvicorn handoff, warnings, and the install hint."""

from __future__ import annotations

import argparse
import sys

import pytest

from filter_lib.cli import web_cmd
from filter_lib.web.settings import DEFAULT_HOST, DEFAULT_PORT

INSTALL_HINT = (
    "The web UI needs the optional web dependencies. From a source checkout run: "
    'uv sync --extra web. For an installed package: pip install "rf-filter-calculator[web]".'
)


def _parse(*argv: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    web_cmd.setup_parser(parser)
    return parser.parse_args(list(argv))


def test_parser_defaults_bind_to_loopback_port_8765():
    args = _parse()

    assert (args.host, args.port) == (DEFAULT_HOST, DEFAULT_PORT) == ("127.0.0.1", 8765)


def test_parser_accepts_host_and_port():
    args = _parse("--host", "0.0.0.0", "--port", "9000")

    assert (args.host, args.port) == ("0.0.0.0", 9000)


@pytest.fixture
def served(monkeypatch):
    """Capture the uvicorn.run call instead of starting a server."""
    pytest.importorskip("fastapi")
    import uvicorn

    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs)))
    return calls


def test_run_hands_the_app_to_uvicorn(served, capsys):
    from fastapi import FastAPI

    web_cmd.run(_parse("--port", "9123"))

    app, kwargs = served[0]
    assert isinstance(app, FastAPI)
    assert app.state.settings.port == 9123
    assert kwargs == {"host": "127.0.0.1", "port": 9123, "log_level": "info"}
    captured = capsys.readouterr()
    assert "http://127.0.0.1:9123/" in captured.out
    assert captured.err == ""


def test_non_loopback_bind_warns(served, capsys):
    web_cmd.run(_parse("--host", "0.0.0.0"))

    assert "lets other machines reach the calculator. It has no login" in capsys.readouterr().err


def test_ipv6_loopback_url_is_bracketed(served, capsys):
    web_cmd.run(_parse("--host", "::1"))

    captured = capsys.readouterr()
    assert "http://[::1]:8765/" in captured.out
    assert captured.err == ""


def test_invalid_port_is_a_clean_cli_error(served, monkeypatch, capsys):
    from filter_lib import cli

    monkeypatch.setattr("sys.argv", ["filter-calc", "web", "--port", "0"])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().err == "Error: Port must be 1-65535\n"
    assert served == []


@pytest.mark.parametrize("module", ["fastapi", "uvicorn", "jinja2", "python_multipart"])
def test_missing_extra_prints_the_install_hint(monkeypatch, capsys, module):
    from filter_lib import cli

    monkeypatch.setitem(sys.modules, module, None)
    monkeypatch.delitem(sys.modules, "filter_lib.web.app", raising=False)
    monkeypatch.setattr("sys.argv", ["filter-calc", "web"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().err == f"Error: {INSTALL_HINT}\n"
