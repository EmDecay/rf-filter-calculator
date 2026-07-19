"""Shared argparse error helper for cross-option validation."""

from argparse import Namespace
from typing import NoReturn


def usage_error(args: Namespace, message: str) -> NoReturn:
    """Exit with the active subcommand's argparse usage error."""
    args._parser.error(message)
    raise SystemExit(2)
