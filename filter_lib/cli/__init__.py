"""CLI subcommand handlers."""

import argparse
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as metadata_version

from .. import __version__
from . import bandpass_cmd, highpass_cmd, lowpass_cmd, wizard_cmd

__all__ = ["lowpass_cmd", "highpass_cmd", "bandpass_cmd", "wizard_cmd", "main"]


def _package_version() -> str:
    """Return the installed distribution version, falling back for source checkouts."""
    try:
        return metadata_version("rf-filter-calculator")
    except PackageNotFoundError:
        return __version__


def main():
    """Main entry point for the filter calculator CLI."""
    parser = argparse.ArgumentParser(
        description="Unified Filter Calculator",
        epilog="""Subcommands:
  lowpass (lp)   LC low-pass filter (Pi or T topology)
  highpass (hp)  LC high-pass filter (Pi or T topology)
  bandpass (bp)  Coupled resonator bandpass filter
  wizard (w)     Interactive wizard (TUI)

Run with no arguments to start the interactive wizard.

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
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
    )

    subparsers = parser.add_subparsers(dest="command")

    lp_parser = subparsers.add_parser(
        "lowpass", aliases=["lp"], help="LC low-pass filter (Pi or T)"
    )
    lowpass_cmd.setup_parser(lp_parser)
    lp_parser.set_defaults(func=lowpass_cmd.run)

    hp_parser = subparsers.add_parser(
        "highpass", aliases=["hp"], help="LC high-pass filter (Pi or T)"
    )
    highpass_cmd.setup_parser(hp_parser)
    hp_parser.set_defaults(func=highpass_cmd.run)

    bp_parser = subparsers.add_parser(
        "bandpass", aliases=["bp"], help="Coupled resonator bandpass filter"
    )
    bandpass_cmd.setup_parser(bp_parser)
    bp_parser.set_defaults(func=bandpass_cmd.run)

    wizard_parser = subparsers.add_parser("wizard", aliases=["w"], help="Interactive wizard (TUI)")
    wizard_cmd.setup_parser(wizard_parser)
    wizard_parser.set_defaults(func=wizard_cmd.run)

    args = parser.parse_args()

    try:
        # Default to wizard when no command given
        if args.command is None:
            from ..wizard import run_wizard

            run_wizard()
        else:
            args.func(args)
    # ValueError is the library-wide contract for invalid user input (bad
    # frequencies, unsupported orders, unrealizable designs): surface the
    # message cleanly on stderr instead of dumping a traceback.
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(1)
