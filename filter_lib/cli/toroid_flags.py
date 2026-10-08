"""Shared --no-toroids, --toroid-compact, and --toroid-full flags for LP/HP/BP parsers."""

from argparse import ArgumentParser


def add_toroid_flags(parser: ArgumentParser) -> None:
    """Attach --no-toroids, --toroid-compact, and --toroid-full to a subcommand parser."""
    parser.add_argument(
        "--no-toroids",
        dest="no_toroids",
        action="store_true",
        help="Leave out the suggested toroid windings from all outputs; --sim-build and "
        "SPICE then use the calculated inductances",
    )
    parser.add_argument(
        "--toroid-compact",
        dest="toroid_compact",
        action="store_true",
        help="In table output, show the best toroid suggestion for each inductor on one line",
    )
    parser.add_argument(
        "--toroid-full",
        dest="toroid_full",
        action="store_true",
        help="In table output, show up to three toroid suggestions per inductor instead of "
        "one. JSON always lists up to three; CSV lists the best",
    )
