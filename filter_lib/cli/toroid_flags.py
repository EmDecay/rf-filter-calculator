"""Shared --no-toroids, --toroid-compact, and --toroid-full flags for LP/HP/BP parsers."""

from argparse import ArgumentParser


def add_toroid_flags(parser: ArgumentParser) -> None:
    """Attach --no-toroids, --toroid-compact, and --toroid-full to a subcommand parser."""
    parser.add_argument(
        "--no-toroids",
        dest="no_toroids",
        action="store_true",
        help="Skip toroid core recommendations in all output formats.",
    )
    parser.add_argument(
        "--toroid-compact",
        dest="toroid_compact",
        action="store_true",
        help="Compact 1-line-per-rec toroid text output (ignored for --format json/csv).",
    )
    parser.add_argument(
        "--toroid-full",
        dest="toroid_full",
        action="store_true",
        help="Show top-3 toroid cores per inductor in table output "
        "(default is top-1; json/csv always include top-3).",
    )
