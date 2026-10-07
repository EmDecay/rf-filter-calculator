"""Lowpass subcommand handler."""

from argparse import ArgumentParser, Namespace

from ..shared.cli_aliases import FILTER_EXPLANATIONS
from ..shared.cli_helpers import (
    add_build_analysis_args,
    add_common_filter_args,
    add_eseries_args,
    add_filter_type_args,
    add_output_args,
    add_plot_args,
    add_sim_matched_arg,
)
from .ladder_command import run_ladder
from .toroid_flags import add_toroid_flags


def setup_parser(parser: ArgumentParser) -> None:
    """Add arguments to the lowpass subparser."""
    add_filter_type_args(parser, "lowpass")
    add_common_filter_args(parser)
    add_output_args(parser)
    add_eseries_args(parser)
    add_sim_matched_arg(parser)
    add_build_analysis_args(parser)
    add_plot_args(parser)
    add_toroid_flags(parser)
    # Make the subparser reachable from run() so missing-argument problems
    # exit with a usage line (argparse error) instead of a raw traceback.
    parser.set_defaults(_parser=parser)


def run(args: Namespace) -> None:
    """Execute lowpass command.

    Args:
        args: Parsed Namespace from setup_parser()

    Raises:
        ValueError: For invalid numeric input; cli.main() converts this to a
            clean stderr message. Usage-level problems (missing filter type,
            frequency, or topology) exit via argparse's usage error instead.
    """
    run_ladder(args, "lowpass", FILTER_EXPLANATIONS, "lp bw pi 10MHz")
