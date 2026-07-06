"""Wizard subcommand handler.

Interactive mode for guided filter design.
"""

from argparse import ArgumentParser, Namespace

from ..wizard import run_wizard


def setup_parser(parser: ArgumentParser) -> None:
    """Add arguments to wizard subparser.

    No additional arguments - wizard is fully interactive.
    """
    pass


def run(args: Namespace) -> None:
    """Execute wizard command.

    ``args`` is unused (the wizard takes no flags) but the signature must
    match the subcommand dispatch contract used by cli.main().
    """
    run_wizard()
