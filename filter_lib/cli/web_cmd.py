"""Web subcommand handler: serve the local browser UI.

The web dependencies are an optional extra, so FastAPI and uvicorn are imported only
inside ``run``; the rest of the CLI never needs them.
"""

import sys
from argparse import ArgumentParser, Namespace

from ..web.settings import DEFAULT_HOST, DEFAULT_PORT, WebSettings

INSTALL_HINT = (
    "The web UI needs the optional web dependencies. From a source checkout run: "
    'uv sync --extra web. For an installed package: pip install "rf-filter-calculator[web]".'
)


def setup_parser(parser: ArgumentParser) -> None:
    """Add the bind address arguments."""
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Address to bind (default: {DEFAULT_HOST}, this computer only)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )


def run(args: Namespace) -> None:
    """Serve the web UI until interrupted.

    Raises:
        ValueError: When the optional web dependencies are not installed, or the
            port is out of range; cli.main() prints it as ``Error: ...``.
    """
    try:
        # Jinja2 and python-multipart are imported lazily by Starlette, so check them
        # here rather than failing on the first page or form submission.
        import jinja2  # noqa: F401
        import python_multipart  # noqa: F401
        import uvicorn

        from ..web.app import create_app
    except ImportError:
        raise ValueError(INSTALL_HINT) from None

    settings = WebSettings(host=args.host, port=args.port)
    if not settings.is_loopback:
        print(
            f"Warning: binding to {args.host} lets other machines reach the calculator. "
            "It has no login and is meant for local use.",
            file=sys.stderr,
        )
    host = f"[{args.host}]" if ":" in args.host else args.host
    print(f"RF Filter Calculator web UI: http://{host}:{args.port}/ (Ctrl+C to stop)")
    sys.stdout.flush()
    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="info")
