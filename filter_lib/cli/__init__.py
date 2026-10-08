"""CLI subcommand handlers."""

import argparse
import os
import sys
import textwrap
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as metadata_version

from .. import __version__
from . import bandpass_cmd, highpass_cmd, lowpass_cmd, web_cmd, wizard_cmd

__all__ = ["lowpass_cmd", "highpass_cmd", "bandpass_cmd", "wizard_cmd", "web_cmd", "main"]


def _package_version() -> str:
    """Return the installed distribution version, falling back for source checkouts."""
    try:
        return metadata_version("rf-filter-calculator")
    except PackageNotFoundError:
        return __version__


def _discard_further_stdout() -> None:
    """Point stdout's file descriptor at devnull after its reader went away.

    Python flushes stdout again at exit; without this, output still buffered for the
    closed pipe raises a second BrokenPipeError there (the Python ``signal`` docs
    recipe). A stream without a descriptor has nothing left to redirect.
    """
    try:
        descriptor = sys.stdout.fileno()
    except (AttributeError, OSError, ValueError):
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, descriptor)
    os.close(devnull)


class _HelpFormatter(argparse.HelpFormatter):
    """Wrap help text without splitting hyphenated words such as ``--spice-realization``."""

    def _split_lines(self, text: str, width: int) -> list[str]:
        return textwrap.wrap(" ".join(text.split()), width, break_on_hyphens=False)


class _TopLevelHelpFormatter(_HelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Keep the hand-formatted examples epilog of the top-level help."""


def main():
    """Main entry point for the filter calculator CLI."""
    parser = argparse.ArgumentParser(
        description="Calculate LC low-pass, high-pass, and band-pass filter component values.",
        epilog="""Run with no arguments to start the interactive wizard.

Examples:
  %(prog)s                              # Start interactive wizard
  %(prog)s wizard
  %(prog)s lowpass butterworth pi 10MHz -n 5
  %(prog)s lp bw t 10MHz
  %(prog)s lp bw pi 10MHz --format json
  %(prog)s highpass bw t 10MHz -n 5
  %(prog)s hp ch -T pi -f 10MHz -r 0.5
  %(prog)s bandpass bw top -f 14.2MHz -b 500kHz
  %(prog)s bp ch top --fl 14MHz --fh 14.35MHz -n 7""",
        formatter_class=_TopLevelHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
    )

    subparsers = parser.add_subparsers(dest="command")

    lp_parser = subparsers.add_parser(
        "lowpass",
        aliases=["lp"],
        help="LC low-pass filter (Pi or T)",
        formatter_class=_HelpFormatter,
    )
    lowpass_cmd.setup_parser(lp_parser)
    lp_parser.set_defaults(func=lowpass_cmd.run)

    hp_parser = subparsers.add_parser(
        "highpass",
        aliases=["hp"],
        help="LC high-pass filter (Pi or T)",
        formatter_class=_HelpFormatter,
    )
    highpass_cmd.setup_parser(hp_parser)
    hp_parser.set_defaults(func=highpass_cmd.run)

    bp_parser = subparsers.add_parser(
        "bandpass",
        aliases=["bp"],
        help="Coupled-resonator band-pass filter",
        formatter_class=_HelpFormatter,
    )
    bandpass_cmd.setup_parser(bp_parser)
    bp_parser.set_defaults(func=bandpass_cmd.run)

    wizard_parser = subparsers.add_parser(
        "wizard", aliases=["w"], help="Interactive terminal wizard", formatter_class=_HelpFormatter
    )
    wizard_cmd.setup_parser(wizard_parser)
    wizard_parser.set_defaults(func=wizard_cmd.run)

    web_parser = subparsers.add_parser(
        "web",
        help="Browser interface on this computer (needs the optional web dependencies)",
        formatter_class=_HelpFormatter,
    )
    web_cmd.setup_parser(web_parser)
    web_parser.set_defaults(func=web_cmd.run)

    args = parser.parse_args()

    try:
        # Default to wizard when no command given
        if args.command is None:
            from ..wizard import run_wizard

            run_wizard()
        else:
            args.func(args)
        # Flush here so a reader that closed the pipe early (``| head``) is reported
        # below instead of during interpreter shutdown.
        sys.stdout.flush()
    except BrokenPipeError:
        _discard_further_stdout()
        sys.exit(1)
    # ValueError is the library-wide contract for invalid user input (bad
    # frequencies, unsupported orders, unrealizable designs): surface the
    # message cleanly on stderr instead of dumping a traceback.
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(1)
