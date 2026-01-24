"""Bandpass subcommand handler."""
import math
import sys
from argparse import ArgumentParser, Namespace

from ..shared.parsing import parse_frequency, parse_impedance
from ..shared.cli_aliases import (
    FILTER_EXPLANATIONS_BANDPASS,
    DEFAULT_IMPEDANCE, DEFAULT_RIPPLE_DB, DEFAULT_RESONATORS,
    DEFAULT_Q_SAFETY, DEFAULT_ESERIES,
    resolve_filter_type, resolve_coupling,
)
from ..bandpass import calculate_bandpass_filter, display_results


def setup_parser(parser: ArgumentParser) -> None:
    """Add arguments to the bandpass subparser."""
    parser.add_argument('filter_type', nargs='?',
                        choices=['butterworth', 'chebyshev', 'bessel',
                                 'bw', 'ch', 'bs', 'b', 'c'],
                        help='Filter type')
    parser.add_argument('coupling_pos', nargs='?',
                        choices=['top', 'shunt', 't', 's'],
                        help='Coupling topology (top=series, shunt=parallel)')

    parser.add_argument('-t', '--type', dest='type_flag',
                        choices=['butterworth', 'chebyshev', 'bessel',
                                 'bw', 'ch', 'bs', 'b', 'c'],
                        help='Filter type (alternative)')
    parser.add_argument('-c', '--coupling', dest='coupling_flag',
                        choices=['top', 'shunt', 't', 's'],
                        help='Coupling topology (alternative)')

    # Frequency method 1: center + bandwidth
    parser.add_argument('-f', '--frequency', help='Center frequency')
    parser.add_argument('-b', '--bandwidth', help='3dB bandwidth')

    # Frequency method 2: low/high cutoff
    parser.add_argument('--fl', dest='f_low', help='Lower cutoff frequency')
    parser.add_argument('--fh', dest='f_high', help='Upper cutoff frequency')

    parser.add_argument('-z', '--impedance', default=DEFAULT_IMPEDANCE,
                        help=f'System impedance (default: {DEFAULT_IMPEDANCE})')
    parser.add_argument('-n', '--resonators', type=int, default=DEFAULT_RESONATORS,
                        choices=range(2, 10), metavar='N',
                        help=f'Number of resonators: 2-9 (default: {DEFAULT_RESONATORS})')
    parser.add_argument('-r', '--ripple', type=float, default=DEFAULT_RIPPLE_DB,
                        help=f'Chebyshev ripple in dB (default: {DEFAULT_RIPPLE_DB})')
    parser.add_argument('--q-safety', type=float, default=DEFAULT_Q_SAFETY,
                        help=f'Q safety factor (default: {DEFAULT_Q_SAFETY})')

    parser.add_argument('--raw', action='store_true',
                        help='Output raw values in scientific notation')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Minimal output')
    parser.add_argument('--format', choices=['table', 'json', 'csv'],
                        default='table', help='Output format')
    parser.add_argument('--explain', action='store_true',
                        help='Explain filter type')
    parser.add_argument('--verify', action='store_true',
                        help='Run self-verification tests')

    parser.add_argument('-e', '--eseries', choices=['E12', 'E24', 'E96'],
                        default=DEFAULT_ESERIES, help=f'E-series (default: {DEFAULT_ESERIES})')
    parser.add_argument('--no-match', action='store_true',
                        help='Disable E-series matching')

    parser.add_argument('--plot', action='store_true',
                        help='Show ASCII frequency response')
    parser.add_argument('--plot-data', choices=['json', 'csv'],
                        help='Export frequency response data')


def run(args: Namespace) -> None:
    """Execute bandpass command."""
    if args.verify:
        _run_verification()
        return

    filter_type = args.filter_type or args.type_flag
    coupling = args.coupling_pos or args.coupling_flag

    if args.explain:
        if not filter_type:
            raise ValueError('Filter type required for --explain')
        resolved = resolve_filter_type(filter_type)
        print(FILTER_EXPLANATIONS_BANDPASS[resolved])
        return

    if not filter_type:
        raise ValueError('Filter type required (butterworth/chebyshev/bessel)')
    if not coupling:
        raise ValueError('Coupling topology required (top/shunt)')

    filter_type = resolve_filter_type(filter_type)
    coupling = resolve_coupling(coupling)

    f0, bw, f_low, f_high = _validate_frequencies(args)
    z0 = parse_impedance(args.impedance)

    if args.q_safety <= 0:
        raise ValueError("Q safety factor must be positive")
    if filter_type == 'chebyshev' and args.resonators % 2 == 0:
        raise ValueError("Chebyshev requires odd resonator count")

    result = calculate_bandpass_filter(
        f0=f0, bw=bw, z0=z0, n_resonators=args.resonators,
        filter_type=filter_type, coupling=coupling,
        ripple_db=args.ripple if filter_type == 'chebyshev' else DEFAULT_RIPPLE_DB,
        q_safety=args.q_safety
    )
    result['f_low'] = f_low
    result['f_high'] = f_high

    for w in result.get('warnings', []):
        print(f"Warning: {w}", file=sys.stderr)

    display_results(result, raw=args.raw, output_format=args.format,
                    quiet=args.quiet,
                    eseries=None if args.no_match else args.eseries,
                    show_plot=args.plot, plot_data=args.plot_data)


def _validate_frequencies(args: Namespace) -> tuple[float, float, float, float]:
    """Validate and compute f0, bw from input method."""
    has_center_bw = args.frequency and args.bandwidth
    has_low_high = args.f_low and args.f_high

    if has_center_bw and has_low_high:
        raise ValueError("Use (-f + -b) OR (--fl + --fh), not both")
    if not has_center_bw and not has_low_high:
        raise ValueError("Specify frequency as (-f + -b) or (--fl + --fh)")

    if has_center_bw:
        f0 = parse_frequency(args.frequency)
        bw = parse_frequency(args.bandwidth)
        f_low = f0 - bw / 2
        f_high = f0 + bw / 2
    else:
        f_low = parse_frequency(args.f_low)
        f_high = parse_frequency(args.f_high)
        if f_low >= f_high:
            raise ValueError("Lower frequency must be less than upper")
        f0 = math.sqrt(f_low * f_high)
        bw = f_high - f_low

    return f0, bw, f_low, f_high


def _run_verification() -> None:
    """Run self-verification tests."""
    from ..bandpass.g_values import (
        calculate_butterworth_g_values, get_chebyshev_g_values,
    )
    from ..bandpass.calculations import calculate_resonator_components

    print("Running verification tests...")

    # Test g-value calculations
    g3 = calculate_butterworth_g_values(3)
    assert len(g3) == 3, f"Expected 3 g-values, got {len(g3)}"
    assert abs(g3[0] - 1.0) < 0.01, f"g1 should be ~1.0, got {g3[0]}"

    # Test Chebyshev
    gc3 = get_chebyshev_g_values(3, 0.5)
    assert len(gc3) == 3, f"Expected 3 Chebyshev g-values"

    # Test resonator components
    L, C = calculate_resonator_components(10e6, 50)
    assert L > 0 and C > 0, "L and C must be positive"

    print("Verification passed")
