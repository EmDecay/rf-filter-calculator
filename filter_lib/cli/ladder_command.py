"""Shared ``run`` body for the lowpass and highpass subcommands.

The two handlers differ only in their category, their explanation table, and the
example shown in usage errors; everything after argument resolution lives here.
"""

from argparse import Namespace

from ..design import DesignRequest, design, export_response_data, export_spice, render_lines
from ..shared.cli_aliases import resolve_filter_type
from ..shared.cli_helpers import (
    get_filter_type_arg,
    resolve_alternative_arg,
    resolve_ripple_arg,
    usage_error,
    validate_filter_args,
    validate_output_mode_args,
)
from ..shared.parsing import parse_frequency, parse_impedance
from .design_output_args import (
    part_policy_args,
    render_options_from_args,
    spice_realization_from_args,
)


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
            clean stderr message. Usage-level problems (missing response type,
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
                f"response type required for --explain (try: filter-calc {alias} bw --explain)",
            )
        validate_output_mode_args(args)
        print(explanations[resolve_filter_type(filter_type)])
        return

    if not filter_type:
        usage_error(
            args,
            f"response type required: butterworth/chebyshev/bessel (try: filter-calc {example})",
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
        **part_policy_args(args),
    )
    outcome = design(request)

    if args.format == "spice":
        print(export_spice(outcome, spice_realization_from_args(args)), end="")
        return

    if args.plot_data:
        print(export_response_data(outcome, args.plot_data))
        return

    print("\n".join(render_lines(outcome, render_options_from_args(args))))
