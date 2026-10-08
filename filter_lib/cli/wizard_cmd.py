"""Wizard subcommand handler.

Interactive mode for guided filter design.
"""

from argparse import ArgumentParser, Namespace

from ..wizard import run_wizard


def setup_parser(parser: ArgumentParser) -> None:
    """Describe the wizard subcommand; it takes no arguments (it is fully interactive)."""
    parser.description = (
        "Start the interactive terminal wizard (same as running filter-calc with no arguments)."
    )


def run(args: Namespace) -> None:
    """Execute wizard command.

    ``args`` is unused (the wizard takes no flags) but the signature must
    match the subcommand dispatch contract used by cli.main().
    """
    run_wizard()
