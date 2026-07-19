"""Shared --no-toroids, --toroid-compact, and --toroid-full flags for LP/HP/BP parsers."""

from argparse import ArgumentParser


def add_toroid_flags(parser: ArgumentParser) -> None:
    """Attach --no-toroids, --toroid-compact, and --toroid-full to a subcommand parser."""
    parser.add_argument(
        "--no-toroids",
        dest="no_toroids",
        action="store_true",
        help="Skip screened toroid winding candidates in all output formats.",
    )
    parser.add_argument(
        "--toroid-compact",
        dest="toroid_compact",
        action="store_true",
        help="Compact one-line-per-candidate table output.",
    )
    parser.add_argument(
        "--toroid-full",
        dest="toroid_full",
        action="store_true",
        help="Show up to 3 qualified cores per inductor in table output "
        "(default is top-1; JSON includes up to 3 and CSV the best available).",
    )
