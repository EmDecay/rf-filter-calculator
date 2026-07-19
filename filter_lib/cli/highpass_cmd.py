"""Highpass subcommand handler."""

import sys
from argparse import ArgumentParser, Namespace

from ..highpass import (
    calculate_bessel,
    calculate_butterworth,
    calculate_chebyshev,
    display_results,
    frequency_response,
    generate_frequency_points,
)
from ..shared.cli_aliases import (
    FILTER_EXPLANATIONS_HIGHPASS,
    resolve_filter_type,
)
from ..shared.cli_helpers import (
    add_build_analysis_args,
    add_common_filter_args,
    add_eseries_args,
    add_filter_type_args,
    add_output_args,
    add_plot_args,
    add_sim_matched_arg,
    export_plot_data,
    get_filter_type_arg,
    make_build_config,
    resolve_alternative_arg,
    resolve_ripple_arg,
    usage_error,
    validate_filter_args,
    validate_output_mode_args,
)
from ..shared.parsing import parse_frequency, parse_impedance
from ..shared.response_export import response_meta
from .toroid_flags import add_toroid_flags


def setup_parser(parser: ArgumentParser) -> None:
    """Add arguments to the highpass subparser."""
    add_filter_type_args(parser, "highpass")
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
    """Execute highpass command.

    Args:
        args: Parsed Namespace from setup_parser()

    Raises:
        ValueError: For invalid numeric input; cli.main() converts this to a
            clean stderr message. Usage-level problems (missing filter type,
            frequency, or topology) exit via argparse's usage error instead.
    """
    filter_type = get_filter_type_arg(args)
    freq_input = resolve_alternative_arg(args, "frequency", "freq_flag", "frequency")
    topology = resolve_alternative_arg(args, "topology_pos", "topology_flag", "topology")

    if args.explain:
        if not filter_type:
            usage_error(
                args, "filter type required for --explain (try: filter-calc hp bw --explain)"
            )
        validate_output_mode_args(args)
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

    validate_output_mode_args(args)

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
        # The 3.0 dB ripple ceiling was already enforced by resolve_ripple_arg;
        # this guards non-positive values, while NaN falls through to the
        # shared calculation layer's isfinite check.
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

    build_config = None
    build_analysis = None
    matched_summary = None
    matched_payload = None
    if args.format == "spice":
        from ..shared.spice_export import export_spice_deck

        build_config = make_build_config(args)
        realization = (getattr(args, "spice_realization", None) or "nominal-build").replace(
            "-", "_"
        )
        print(
            export_spice_deck(
                result,
                "highpass",
                realization=realization,
                config=build_config,
            ),
            end="",
        )
        return

    if getattr(args, "sim_build", False):
        from ..shared.build_simulation import analyze_build

        build_config = make_build_config(args)
        build_analysis = analyze_build(result, "highpass", build_config)
    elif getattr(args, "sim_matched", False):
        from ..shared.matched_simulation import matched_sim_json_payload, run_matched_simulation

        print("Warning: --sim-matched is deprecated; use --sim-build", file=sys.stderr)
        matched_summary = run_matched_simulation(
            result,
            "highpass",
            args.eseries,
            use_toroid_candidates=not args.no_toroids,
        )
        if args.format == "json":
            matched_payload = matched_sim_json_payload(matched_summary)

    if args.plot_data:
        freqs = generate_frequency_points(freq_hz)
        response = frequency_response(filter_type, freqs, freq_hz, order, ripple_db)
        export_plot_data(args, freqs, response, response_meta("highpass", result))
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
        matched_sim=matched_payload,
        build_analysis=build_analysis,
    )

    if build_analysis is not None and args.format == "table" and not args.quiet:
        from ..shared.build_output import format_build_analysis_block

        print("\n".join(format_build_analysis_block(build_analysis)))
    elif matched_summary is not None and args.format == "table" and not args.quiet:
        from ..shared.matched_simulation import format_matched_sim_block

        print("\n".join(format_matched_sim_block(matched_summary)))
