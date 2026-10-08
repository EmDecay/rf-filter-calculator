"""Shared ``run`` body for the lowpass and highpass subcommands.

The two handlers differ only in their category, their explanation table, and the
example shown in usage errors; everything after argument resolution lives here.
"""

import sys
from argparse import Namespace

from ..design import (
    DesignRequest,
    design,
    export_response_data,
    export_spice,
    render_lines,
    with_build_analysis,
)
from ..shared.cli_aliases import resolve_filter_type
from ..shared.cli_helpers import (
    SIM_MATCHED_DEPRECATION_WARNING,
    get_filter_type_arg,
    make_build_config,
    resolve_alternative_arg,
    resolve_ripple_arg,
    usage_error,
    validate_filter_args,
    validate_output_mode_args,
)
from ..shared.parsing import parse_frequency, parse_impedance
from .design_output_args import render_options_from_args, spice_realization_from_args


def run_ladder(args: Namespace, category: str, explanations: dict, example: str) -> None:
    """Execute a lowpass or highpass command.

    Args:
        args: Parsed Namespace from the category's ``setup_parser()``
        category: ``"lowpass"`` or ``"highpass"``
        explanations: Filter-type explanation table printed by ``--explain``
        example: Subcommand alias used in usage hints (``lp`` or ``hp``) followed
            by a valid design, e.g. ``"lp bw pi 10MHz"``

    Raises:
        ValueError: For invalid numeric input; cli.main() converts this to a
            clean stderr message. Usage-level problems (missing filter type,
            frequency, or topology) exit via argparse's usage error instead.
    """
    alias = example.split()[0]
    filter_type = get_filter_type_arg(args)
    freq_input = resolve_alternative_arg(args, "frequency", "freq_flag", "frequency")
    topology = resolve_alternative_arg(args, "topology_pos", "topology_flag", "topology")

    if args.explain:
        if not filter_type:
            usage_error(
                args,
                f"filter type required for --explain (try: filter-calc {alias} bw --explain)",
            )
        validate_output_mode_args(args)
        print(explanations[resolve_filter_type(filter_type)])
        return

    if not filter_type:
        usage_error(
            args,
            f"filter type required: butterworth/chebyshev/bessel (try: filter-calc {example})",
        )
    if not freq_input:
        usage_error(args, f"frequency required (try: filter-calc {example})")

    validate_output_mode_args(args)

    if not topology:
        usage_error(
            args, f"topology required: pi or t, positional or -T (try: filter-calc {example})"
        )

    filter_type = resolve_filter_type(filter_type)
    ripple_db = resolve_ripple_arg(args, filter_type)
    freq_hz = parse_frequency(freq_input)
    impedance = parse_impedance(args.impedance)
    validate_filter_args(freq_hz, impedance, args.components)

    request = DesignRequest(
        category=category,
        filter_type=filter_type,
        topology=topology,
        frequency_hz=freq_hz,
        impedance=impedance,
        order=args.components,
        ripple_db=ripple_db,
        allow_sub_pf=bool(getattr(args, "allow_sub_pf", False)),
    )
    outcome = design(request)

    if args.format == "spice":
        config = make_build_config(args)
        print(export_spice(outcome, spice_realization_from_args(args), config), end="")
        return

    if getattr(args, "sim_build", False):
        outcome = with_build_analysis(outcome, make_build_config(args))
    elif getattr(args, "sim_matched", False):
        _run_deprecated_matched_simulation(args, category, outcome.result)
        return

    if args.plot_data:
        print(export_response_data(outcome, args.plot_data))
        return

    print("\n".join(render_lines(outcome, render_options_from_args(args))))


def _run_deprecated_matched_simulation(args: Namespace, category: str, result: dict) -> None:
    """Print the deprecated ``--sim-matched`` output, kept apart from the dispatcher."""
    from ..shared.matched_simulation import (
        format_matched_sim_block,
        matched_sim_json_payload,
        run_matched_simulation,
    )

    if category == "lowpass":
        from ..lowpass import display_results
    else:
        from ..highpass import display_results

    print(SIM_MATCHED_DEPRECATION_WARNING, file=sys.stderr)
    summary = run_matched_simulation(
        result, category, args.eseries, use_toroid_candidates=not args.no_toroids
    )
    display_results(
        result,
        raw=args.raw,
        output_format=args.format,
        quiet=args.quiet,
        eseries=args.eseries,
        show_match=not args.no_match,
        show_plot=args.plot,
        include_toroids=not args.no_toroids,
        toroid_compact=args.toroid_compact,
        toroid_full=args.toroid_full,
        matched_sim=matched_sim_json_payload(summary) if args.format == "json" else None,
    )
    if args.format == "table" and not args.quiet:
        print("\n".join(format_matched_sim_block(summary)))
