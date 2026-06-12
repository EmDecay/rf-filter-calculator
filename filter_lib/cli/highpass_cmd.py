"""Highpass subcommand handler."""

from argparse import ArgumentParser, Namespace

from ..highpass import (
    calculate_bessel,
    calculate_butterworth,
    calculate_chebyshev,
    display_results,
    export_response_csv,
    export_response_json,
    frequency_response,
    generate_frequency_points,
)
from ..shared.cli_aliases import (
    FILTER_EXPLANATIONS_HIGHPASS,
    resolve_filter_type,
)
from ..shared.cli_helpers import (
    add_common_filter_args,
    add_eseries_args,
    add_filter_type_args,
    add_output_args,
    add_plot_args,
    export_plot_data,
    get_filter_type_arg,
    resolve_ripple_arg,
    usage_error,
    validate_filter_args,
)
from ..shared.parsing import parse_frequency, parse_impedance
from .toroid_flags import add_toroid_flags


def setup_parser(parser: ArgumentParser) -> None:
    """Add arguments to the highpass subparser."""
    add_filter_type_args(parser, "highpass")
    add_common_filter_args(parser)
    add_output_args(parser)
    add_eseries_args(parser)
    add_plot_args(parser)
    add_toroid_flags(parser)
    # Make the subparser reachable from run() so missing-argument problems
    # exit with a usage line (argparse error) instead of a raw traceback.
    parser.set_defaults(_parser=parser)


def run(args: Namespace) -> None:
    """Execute highpass command."""
    filter_type = get_filter_type_arg(args)
    freq_input = args.frequency or args.freq_flag

    if args.explain:
        if not filter_type:
            usage_error(
                args, "filter type required for --explain (try: filter-calc hp bw --explain)"
            )
        resolved = resolve_filter_type(filter_type)
        print(FILTER_EXPLANATIONS_HIGHPASS[resolved])
        return

    if not filter_type:
        usage_error(
            args,
            "filter type required: butterworth/chebyshev/bessel (try: filter-calc hp bw t 10MHz)",
        )
    if not freq_input:
        usage_error(args, "frequency required (try: filter-calc hp bw t 10MHz)")

    # Resolve topology from positional or flag
    topology = getattr(args, "topology_pos", None) or getattr(args, "topology_flag", None)
    if not topology:
        usage_error(
            args, "topology required: pi or t, positional or -T (try: filter-calc hp bw t 10MHz)"
        )

    filter_type = resolve_filter_type(filter_type)
    ripple_db = resolve_ripple_arg(args, filter_type)
    freq_hz = parse_frequency(freq_input)
    impedance = parse_impedance(args.impedance)

    validate_filter_args(freq_hz, impedance, args.components)

    if filter_type == "butterworth":
        inds, caps, order = calculate_butterworth(
            freq_hz, impedance, args.components, topology=topology
        )
        ripple = None
    elif filter_type == "chebyshev":
        if ripple_db <= 0:
            raise ValueError("Ripple must be positive")
        inds, caps, order = calculate_chebyshev(
            freq_hz, impedance, ripple_db, args.components, topology=topology
        )
        ripple = ripple_db
    else:  # bessel
        inds, caps, order = calculate_bessel(freq_hz, impedance, args.components, topology=topology)
        ripple = None

    result = {
        "filter_type": filter_type,
        "freq_hz": freq_hz,
        "impedance": impedance,
        "inductors": inds,
        "capacitors": caps,
        "order": order,
        "ripple": ripple,
        "topology": topology,
    }

    if args.plot_data:
        freqs = generate_frequency_points(freq_hz)
        response = frequency_response(filter_type, freqs, freq_hz, order, ripple_db)
        export_plot_data(args, freqs, response, result, export_response_json, export_response_csv)
        return

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
    )
