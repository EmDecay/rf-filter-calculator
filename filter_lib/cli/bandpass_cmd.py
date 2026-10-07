"""Bandpass subcommand handler."""

import sys
from argparse import SUPPRESS, ArgumentParser, Namespace

from ..bandpass import display_results
from ..design import (
    DesignRequest,
    band_from_edges,
    design,
    export_response_data,
    export_spice,
    render_lines,
    with_build_analysis,
)
from ..design.design_request import check_q_safety
from ..shared.cli_aliases import (
    DEFAULT_IMPEDANCE,
    DEFAULT_Q_SAFETY,
    DEFAULT_RESONATORS,
    DEFAULT_RIPPLE_DB,
    FILTER_EXPLANATIONS_BANDPASS,
    resolve_coupling,
    resolve_filter_type,
)
from ..shared.cli_bandpass_output_validation import validate_bandpass_output_args
from ..shared.cli_helpers import (
    FREQ_SUFFIX_HELP,
    add_build_analysis_args,
    add_eseries_args,
    add_sim_matched_arg,
    get_filter_type_arg,
    make_build_config,
    resolve_alternative_arg,
    resolve_ripple_arg,
    usage_error,
    validate_output_mode_args,
)
from ..shared.parsing import parse_frequency, parse_impedance, parse_inductance
from .design_output_args import render_options_from_args, spice_realization_from_args
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
        help=SUPPRESS,
    )
    parser.add_argument(
        "--qu",
        type=float,
        default=None,
        help="Unloaded Q of the complete resonator (0.01 to 1e9) for the insertion-loss "
        "estimate (estimates at Qu=100/250 are always shown)",
    )
    parser.add_argument(
        "--ql",
        type=float,
        default=None,
        help="Inductor Q at the center frequency (0.01 to 1e9); combines with --qc as "
        "1/Qu=1/QL+1/QC",
    )
    parser.add_argument(
        "--qc",
        type=float,
        default=None,
        help="Capacitor Q at the center frequency (0.01 to 1e9); combines with --ql as "
        "1/Qu=1/QL+1/QC",
    )
    parser.add_argument(
        "--resonator-impedance",
        "--tank-impedance",
        dest="resonator_impedance",
        default=None,
        help="Tank reactance sqrt(L/C), independent of the equal design terminations",
    )
    parser.add_argument(
        "--resonator-inductance",
        "--tank-inductance",
        dest="resonator_inductance",
        default=None,
        help="Fix the tank inductance (for example 1.2uH); mutually exclusive with tank impedance",
    )

    parser.add_argument(
        "--raw", action="store_true", help="Output raw values in scientific notation"
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv", "spice"],
        default="table",
        help="Output format (SPICE supports calculated or nominal-build decks)",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Print a standalone filter-type explanation and exit",
    )

    add_eseries_args(parser)
    add_sim_matched_arg(parser)
    add_build_analysis_args(parser)

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
    """Execute bandpass command.

    Args:
        args: Parsed Namespace from setup_parser()

    Raises:
        ValueError: For invalid numeric input or unrealizable designs;
            cli.main() converts this to a clean stderr message. Usage-level
            problems (missing filter type, coupling, or frequencies) exit via
            argparse's usage error instead.
    """
    filter_type = get_filter_type_arg(args)
    coupling = resolve_alternative_arg(args, "coupling_pos", "coupling_flag", "coupling")

    if args.explain:
        if not filter_type:
            usage_error(
                args, "filter type required for --explain (try: filter-calc bp bw --explain)"
            )
        validate_output_mode_args(args)
        validate_bandpass_output_args(args)
        resolved = resolve_filter_type(filter_type)
        print(FILTER_EXPLANATIONS_BANDPASS[resolved])
        return

    if not filter_type:
        usage_error(args, f"filter type required: butterworth/chebyshev/bessel ({BP_EXAMPLE})")
    if not coupling:
        usage_error(args, f"coupling topology required: top ({BP_EXAMPLE})")

    validate_output_mode_args(args)

    filter_type = resolve_filter_type(filter_type)
    coupling = resolve_coupling(coupling)
    ripple_db = resolve_ripple_arg(args, filter_type)

    f0, bw, requested_f_low, requested_f_high = _validate_frequencies(args)
    z0 = parse_impedance(args.impedance)

    check_q_safety(args.q_safety)
    if args.q_safety != DEFAULT_Q_SAFETY:
        print(
            "Warning: --q-safety is deprecated and retained only for the legacy Q heuristic",
            file=sys.stderr,
        )
    ql = getattr(args, "ql", None)
    qc = getattr(args, "qc", None)
    resonator_impedance_arg = getattr(args, "resonator_impedance", None)
    resonator_inductance_arg = getattr(args, "resonator_inductance", None)
    resonator_impedance = (
        parse_impedance(resonator_impedance_arg, label="Resonator impedance")
        if resonator_impedance_arg is not None
        else None
    )
    resonator_inductance = (
        parse_inductance(resonator_inductance_arg, label="Resonator inductance")
        if resonator_inductance_arg is not None
        else None
    )
    request = DesignRequest(
        category="bandpass",
        filter_type=filter_type,
        topology=coupling,
        frequency_hz=f0,
        impedance=z0,
        order=args.resonators,
        ripple_db=ripple_db,
        bandwidth_hz=bw,
        requested_f_low_hz=requested_f_low,
        requested_f_high_hz=requested_f_high,
        q_safety=args.q_safety,
        qu=args.qu,
        ql=ql,
        qc=qc,
        resonator_impedance=resonator_impedance,
        resonator_inductance=resonator_inductance,
    )
    outcome = design(request)
    result = outcome.result
    validate_bandpass_output_args(args)

    for w in outcome.warnings:
        print(f"Warning: {w}", file=sys.stderr)

    if args.format == "spice":
        config = make_build_config(args)
        print(export_spice(outcome, spice_realization_from_args(args), config), end="")
        return

    if getattr(args, "sim_build", False):
        outcome = with_build_analysis(outcome, make_build_config(args))
    elif getattr(args, "sim_matched", False):
        _run_deprecated_matched_simulation(args, result)
        return

    if args.plot_data:
        print(export_response_data(outcome, args.plot_data))
        return

    print("\n".join(render_lines(outcome, render_options_from_args(args))))


def _run_deprecated_matched_simulation(args: Namespace, result: dict) -> None:
    """Print the deprecated ``--sim-matched`` output, kept apart from the dispatcher."""
    from ..shared.matched_simulation import (
        format_matched_sim_block,
        matched_sim_json_payload,
        run_matched_simulation,
    )

    print("Warning: --sim-matched is deprecated; use --sim-build", file=sys.stderr)
    summary = run_matched_simulation(
        result, "bandpass", args.eseries, use_toroid_candidates=not args.no_toroids
    )
    display_results(
        result,
        raw=args.raw,
        output_format=args.format,
        quiet=args.quiet,
        eseries=None if args.no_match else args.eseries,
        show_plot=args.plot,
        include_toroids=not args.no_toroids,
        toroid_compact=args.toroid_compact,
        toroid_full=args.toroid_full,
        matched_sim=matched_sim_json_payload(summary) if args.format == "json" else None,
    )
    if args.format == "table" and not args.quiet:
        print("\n".join(format_matched_sim_block(summary)))


def _validate_frequencies(args: Namespace) -> tuple[float, float, float | None, float | None]:
    """Validate inputs and return derived f0/BW plus parsed requested edges.

    Returns f0 (geometric center) and bw (passband width). f0 = sqrt(fl*fh)
    rather than the arithmetic mean because the bandpass transfer function is
    geometrically symmetric about f0. Recomputed realized edges agree with the
    user's ``--fl``/``--fh`` values to floating-point precision; the parsed
    values are also returned so requested-parameter metadata remains exact.
    """
    center_bw = (args.frequency, args.bandwidth)
    low_high = (args.f_low, args.f_high)
    any_center_bw = any(value is not None for value in center_bw)
    any_low_high = any(value is not None for value in low_high)
    has_center_bw = all(value is not None for value in center_bw)
    has_low_high = all(value is not None for value in low_high)

    if any_center_bw and any_low_high:
        usage_error(args, "use (-f + -b) OR (--fl + --fh), not both")
    if not any_center_bw and not any_low_high:
        usage_error(args, f"frequency required: (-f + -b) or (--fl + --fh) ({BP_EXAMPLE})")
    if any_center_bw and not has_center_bw:
        usage_error(args, "-f/--frequency and -b/--bandwidth must be supplied together")
    if any_low_high and not has_low_high:
        usage_error(args, "--fl and --fh must be supplied together")

    if has_center_bw:
        f0 = parse_frequency(args.frequency, label="Center frequency")
        bw = parse_frequency(args.bandwidth, label="Bandwidth")
        f_low = None
        f_high = None
    else:
        f_low = parse_frequency(args.f_low, label="Lower cutoff frequency")
        f_high = parse_frequency(args.f_high, label="Upper cutoff frequency")
        f0, bw = band_from_edges(f_low, f_high)

    return f0, bw, f_low, f_high
