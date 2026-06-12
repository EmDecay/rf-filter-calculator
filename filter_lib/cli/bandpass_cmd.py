"""Bandpass subcommand handler."""

import math
import sys
from argparse import ArgumentParser, Namespace

from ..bandpass import calculate_bandpass_filter, display_results
from ..shared.cli_aliases import (
    DEFAULT_ESERIES,
    DEFAULT_IMPEDANCE,
    DEFAULT_Q_SAFETY,
    DEFAULT_RESONATORS,
    DEFAULT_RIPPLE_DB,
    FILTER_EXPLANATIONS_BANDPASS,
    resolve_coupling,
    resolve_filter_type,
)
from ..shared.cli_helpers import (
    FREQ_SUFFIX_HELP,
    get_filter_type_arg,
    resolve_ripple_arg,
    usage_error,
)
from ..shared.parsing import parse_frequency, parse_impedance
from .toroid_flags import add_toroid_flags

BP_EXAMPLE = "try: filter-calc bp bw top -f 14.2MHz -b 500kHz"


def setup_parser(parser: ArgumentParser) -> None:
    """Add arguments to the bandpass subparser."""
    parser.add_argument(
        "filter_type",
        nargs="?",
        choices=["butterworth", "chebyshev", "bessel", "bw", "ch", "bs", "b", "c"],
        help="Filter type",
    )
    parser.add_argument(
        "coupling_pos",
        nargs="?",
        choices=["top", "t"],
        help="Coupling topology (top=series capacitive coupling)",
    )

    parser.add_argument(
        "--type",
        dest="type_flag",
        choices=["butterworth", "chebyshev", "bessel", "bw", "ch", "bs", "b", "c"],
        help="Filter type (alternative)",
    )
    parser.add_argument(
        "-c",
        "--coupling",
        dest="coupling_flag",
        choices=["top", "t"],
        help="Coupling topology (alternative)",
    )

    # Frequency method 1: center + bandwidth
    parser.add_argument("-f", "--frequency", help=f"Center frequency; {FREQ_SUFFIX_HELP}")
    parser.add_argument(
        "-b",
        "--bandwidth",
        help="True -3 dB bandwidth for all response types (incl. Chebyshev)",
    )

    # Frequency method 2: low/high cutoff
    parser.add_argument("--fl", dest="f_low", help=f"Lower cutoff frequency; {FREQ_SUFFIX_HELP}")
    parser.add_argument("--fh", dest="f_high", help=f"Upper cutoff frequency; {FREQ_SUFFIX_HELP}")

    parser.add_argument(
        "-z",
        "--impedance",
        default=DEFAULT_IMPEDANCE,
        help=f"System impedance (default: {DEFAULT_IMPEDANCE})",
    )
    parser.add_argument(
        "-n",
        "--resonators",
        type=int,
        default=DEFAULT_RESONATORS,
        choices=range(2, 10),
        metavar="N",
        help=f"Number of resonators: 2-9 (default: {DEFAULT_RESONATORS})",
    )
    # default=None is a sentinel: "ripple was explicitly supplied" drives the
    # only-used-by-Chebyshev warning; DEFAULT_RIPPLE_DB is applied afterwards.
    parser.add_argument(
        "-r",
        "--ripple",
        type=float,
        default=None,
        help=f"Chebyshev ripple in dB, 0 < r <= 3.0 (default: {DEFAULT_RIPPLE_DB})",
    )
    parser.add_argument(
        "--q-safety",
        type=float,
        default=DEFAULT_Q_SAFETY,
        help=f"Q safety factor (default: {DEFAULT_Q_SAFETY})",
    )

    parser.add_argument(
        "--raw", action="store_true", help="Output raw values in scientific notation"
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    parser.add_argument(
        "--format", choices=["table", "json", "csv"], default="table", help="Output format"
    )
    parser.add_argument("--explain", action="store_true", help="Explain filter type")

    parser.add_argument(
        "-e",
        "--eseries",
        choices=["E12", "E24", "E96"],
        default=DEFAULT_ESERIES,
        help=f"E-series (default: {DEFAULT_ESERIES})",
    )
    parser.add_argument("--no-match", action="store_true", help="Disable E-series matching")

    parser.add_argument("--plot", action="store_true", help="Show ASCII frequency response")
    parser.add_argument(
        "--plot-data", choices=["json", "csv"], help="Export frequency response data"
    )
    add_toroid_flags(parser)
    parser.epilog = "Note: the bandwidth must be less than the center frequency (bw < f0)."
    # Make the subparser reachable from run() so missing-argument problems
    # exit with a usage line (argparse error) instead of a raw traceback.
    parser.set_defaults(_parser=parser)


def run(args: Namespace) -> None:
    """Execute bandpass command."""
    filter_type = get_filter_type_arg(args)
    coupling = args.coupling_pos or args.coupling_flag

    if args.explain:
        if not filter_type:
            usage_error(
                args, "filter type required for --explain (try: filter-calc bp bw --explain)"
            )
        resolved = resolve_filter_type(filter_type)
        print(FILTER_EXPLANATIONS_BANDPASS[resolved])
        return

    if not filter_type:
        usage_error(args, f"filter type required: butterworth/chebyshev/bessel ({BP_EXAMPLE})")
    if not coupling:
        usage_error(args, f"coupling topology required: top ({BP_EXAMPLE})")

    filter_type = resolve_filter_type(filter_type)
    coupling = resolve_coupling(coupling)
    ripple_db = resolve_ripple_arg(args, filter_type)

    f0, bw = _validate_frequencies(args)
    z0 = parse_impedance(args.impedance)

    if args.q_safety <= 0:
        raise ValueError("Q safety factor must be positive")
    if filter_type == "chebyshev":
        if args.resonators % 2 == 0:
            raise ValueError("Chebyshev requires odd resonator count")
        if not math.isfinite(ripple_db) or ripple_db <= 0:
            raise ValueError("Ripple must be positive and finite")
        if ripple_db > 3.0:
            raise ValueError("Ripple must be at most 3.0 dB")

    result = calculate_bandpass_filter(
        f0=f0,
        bw=bw,
        z0=z0,
        n_resonators=args.resonators,
        filter_type=filter_type,
        coupling=coupling,
        ripple_db=ripple_db if filter_type == "chebyshev" else DEFAULT_RIPPLE_DB,
        q_safety=args.q_safety,
    )

    for w in result.get("warnings", []):
        print(f"Warning: {w}", file=sys.stderr)

    display_results(
        result,
        raw=args.raw,
        output_format=args.format,
        quiet=args.quiet,
        eseries=None if args.no_match else args.eseries,
        show_plot=args.plot,
        plot_data=args.plot_data,
        include_toroids=not args.no_toroids,
        toroid_compact=args.toroid_compact,
        toroid_full=args.toroid_full,
    )


def _validate_frequencies(args: Namespace) -> tuple[float, float]:
    """Validate and compute f0, bw from input method.

    Returns f0 (geometric center) and bw (passband width). The true -3 dB
    edges are computed downstream by compute_bandpass_3db_edges.
    """
    has_center_bw = args.frequency and args.bandwidth
    has_low_high = args.f_low and args.f_high

    if has_center_bw and has_low_high:
        usage_error(args, "use (-f + -b) OR (--fl + --fh), not both")
    if not has_center_bw and not has_low_high:
        usage_error(args, f"frequency required: (-f + -b) or (--fl + --fh) ({BP_EXAMPLE})")

    if has_center_bw:
        f0 = parse_frequency(args.frequency)
        bw = parse_frequency(args.bandwidth)
    else:
        f_low = parse_frequency(args.f_low)
        f_high = parse_frequency(args.f_high)
        if f_low >= f_high:
            raise ValueError("Lower frequency must be less than upper")
        f0 = math.sqrt(f_low * f_high)
        bw = f_high - f_low

    return f0, bw
