"""Map parsed CLI output flags onto the shared design dispatcher's options."""

import sys
from argparse import Namespace
from collections.abc import Callable
from typing import Any

from ..design import RenderOptions
from ..shared.cli_helpers import SIM_MATCHED_DEPRECATION_WARNING


def render_options_from_args(args: Namespace) -> RenderOptions:
    """Return the CLI's render options; ``--quiet`` selects the quiet format."""
    return RenderOptions(
        output_format="quiet" if args.quiet else args.format,
        raw=args.raw,
        eseries=None if args.no_match else args.eseries,
        show_plot=args.plot,
        include_toroids=not args.no_toroids,
        toroid_compact=args.toroid_compact,
        toroid_full=args.toroid_full,
    )


def spice_realization_from_args(args: Namespace) -> str:
    """Return the SPICE realization id; nominal-build is the CLI default."""
    return (getattr(args, "spice_realization", None) or "nominal-build").replace("-", "_")


def run_deprecated_matched_simulation(
    args: Namespace,
    category: str,
    result: dict,
    display_results: Callable[..., None],
    **match_kwargs: Any,
) -> None:
    """Print the deprecated ``--sim-matched`` output, kept apart from the dispatchers.

    ``match_kwargs`` carries the category's E-series display arguments.
    """
    from ..shared.matched_simulation import (
        format_matched_sim_block,
        matched_sim_json_payload,
        run_matched_simulation,
    )

    print(SIM_MATCHED_DEPRECATION_WARNING, file=sys.stderr)
    summary = run_matched_simulation(
        result, category, args.eseries, use_toroid_candidates=not args.no_toroids
    )
    display_results(
        result,
        raw=args.raw,
        output_format=args.format,
        quiet=args.quiet,
        **match_kwargs,
        show_plot=args.plot,
        include_toroids=not args.no_toroids,
        toroid_compact=args.toroid_compact,
        toroid_full=args.toroid_full,
        matched_sim=matched_sim_json_payload(summary) if args.format == "json" else None,
    )
    if args.format == "table" and not args.quiet:
        print("\n".join(format_matched_sim_block(summary)))
