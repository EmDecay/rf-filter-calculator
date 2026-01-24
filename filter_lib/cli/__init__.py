"""CLI subcommand handlers."""
import argparse
import sys

from . import lowpass_cmd, highpass_cmd, bandpass_cmd, wizard_cmd

__all__ = ['lowpass_cmd', 'highpass_cmd', 'bandpass_cmd', 'wizard_cmd', 'main']


def main():
    """Main entry point for the filter calculator CLI."""
    parser = argparse.ArgumentParser(
        description='Unified Filter Calculator',
        epilog='''Subcommands:
  lowpass (lp)   Pi LC low-pass filter
  highpass (hp)  T LC high-pass filter
  bandpass (bp)  Coupled resonator bandpass filter
  wizard (w)     Interactive filter design

Examples:
  %(prog)s lowpass butterworth 10MHz -n 5
  %(prog)s lp bw 10MHz --format json
  %(prog)s highpass bw 10MHz -n 5
  %(prog)s hp ch 10MHz -r 0.5
  %(prog)s bandpass bw top -f 14.2MHz -b 500kHz
  %(prog)s bp ch shunt --fl 14MHz --fh 14.35MHz -n 7
  %(prog)s wizard''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    lp_parser = subparsers.add_parser('lowpass', aliases=['lp'],
                                       help='Pi LC low-pass filter')
    lowpass_cmd.setup_parser(lp_parser)
    lp_parser.set_defaults(func=lowpass_cmd.run)

    hp_parser = subparsers.add_parser('highpass', aliases=['hp'],
                                       help='T LC high-pass filter')
    highpass_cmd.setup_parser(hp_parser)
    hp_parser.set_defaults(func=highpass_cmd.run)

    bp_parser = subparsers.add_parser('bandpass', aliases=['bp'],
                                       help='Coupled resonator bandpass filter')
    bandpass_cmd.setup_parser(bp_parser)
    bp_parser.set_defaults(func=bandpass_cmd.run)

    wiz_parser = subparsers.add_parser('wizard', aliases=['w'],
                                        help='Interactive filter design')
    wizard_cmd.setup_parser(wiz_parser)
    wiz_parser.set_defaults(func=wizard_cmd.run)

    args = parser.parse_args()

    try:
        args.func(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(1)
