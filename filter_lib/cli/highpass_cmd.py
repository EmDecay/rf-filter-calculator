"""Highpass subcommand handler."""
from argparse import ArgumentParser, Namespace

from ..shared.parsing import parse_frequency, parse_impedance
from ..shared.cli_aliases import (
    FILTER_EXPLANATIONS_HIGHPASS, DEFAULT_RIPPLE_DB, resolve_filter_type,
)
from ..shared.cli_helpers import (
    add_filter_type_args, add_common_filter_args, add_output_args,
    add_eseries_args, add_plot_args, validate_filter_args, export_plot_data,
)
from ..highpass import (
    calculate_butterworth, calculate_chebyshev, calculate_bessel,
    display_results, generate_frequency_points, frequency_response,
    export_response_json, export_response_csv,
)


def setup_parser(parser: ArgumentParser) -> None:
    """Add arguments to the highpass subparser."""
    add_filter_type_args(parser, 'highpass')
    add_common_filter_args(parser)
    add_output_args(parser)
    add_eseries_args(parser)
    add_plot_args(parser)


def run(args: Namespace) -> None:
    """Execute highpass command."""
    filter_type = args.filter_type or args.type_flag
    freq_input = args.frequency or args.freq_flag

    if args.explain:
        if not filter_type:
            raise ValueError('Filter type required for --explain')
        resolved = resolve_filter_type(filter_type)
        print(FILTER_EXPLANATIONS_HIGHPASS[resolved])
        return

    if not filter_type:
        raise ValueError('Filter type required (butterworth/chebyshev/bessel)')
    if not freq_input:
        raise ValueError('Frequency required')

    filter_type = resolve_filter_type(filter_type)
    freq_hz = parse_frequency(freq_input)
    impedance = parse_impedance(args.impedance)

    validate_filter_args(freq_hz, impedance, args.components)

    if filter_type == 'butterworth':
        inds, caps, order = calculate_butterworth(freq_hz, impedance, args.components)
        ripple = None
    elif filter_type == 'chebyshev':
        if args.ripple <= 0:
            raise ValueError("Ripple must be positive")
        inds, caps, order = calculate_chebyshev(freq_hz, impedance, args.ripple,
                                                 args.components)
        ripple = args.ripple
    else:  # bessel
        inds, caps, order = calculate_bessel(freq_hz, impedance, args.components)
        ripple = None

    result = {
        'filter_type': filter_type,
        'freq_hz': freq_hz,
        'impedance': impedance,
        'inductors': inds,
        'capacitors': caps,
        'order': order,
        'ripple': ripple,
    }

    if args.plot_data:
        freqs = generate_frequency_points(freq_hz)
        r = args.ripple if filter_type == 'chebyshev' else DEFAULT_RIPPLE_DB
        response = frequency_response(filter_type, freqs, freq_hz, order, r)
        export_plot_data(args, freqs, response, result,
                         export_response_json, export_response_csv)
        return

    display_results(result, raw=args.raw, output_format=args.format,
                    quiet=args.quiet, eseries=args.eseries,
                    show_match=not args.no_match, show_plot=args.plot)
