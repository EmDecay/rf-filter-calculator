"""Interactive wizard for filter design.

Main entry point that delegates to specialized filter wizards.
"""
import sys

from ..lowpass import (calculate_butterworth as lp_butterworth,
                       calculate_chebyshev as lp_chebyshev,
                       calculate_bessel as lp_bessel,
                       display_results as display_lowpass)
from ..highpass import (calculate_butterworth as hp_butterworth,
                        calculate_chebyshev as hp_chebyshev,
                        calculate_bessel as hp_bessel,
                        display_results as display_highpass)
from .prompts import prompt_choice
from .filter_wizard import run_filter_wizard
from .bandpass_wizard import run_bandpass_wizard


def _build_lowpass_result(filter_type: str, freq_hz: float, impedance: float,
                          caps: list, inds: list, order: int,
                          ripple: float | None) -> dict:
    """Build result dict for lowpass filter."""
    return {
        'filter_type': filter_type,
        'freq_hz': freq_hz,
        'impedance': impedance,
        'capacitors': caps,
        'inductors': inds,
        'order': order,
        'ripple': ripple,
    }


def _build_highpass_result(filter_type: str, freq_hz: float, impedance: float,
                           inds: list, caps: list, order: int,
                           ripple: float | None) -> dict:
    """Build result dict for highpass filter."""
    return {
        'filter_type': filter_type,
        'freq_hz': freq_hz,
        'impedance': impedance,
        'inductors': inds,
        'capacitors': caps,
        'order': order,
        'ripple': ripple,
    }


def _prompt_filter_category() -> str:
    """Prompt for filter category."""
    choice = prompt_choice(
        "What type of filter do you need?",
        [
            ('1', 'Low-pass filter (blocks high frequencies)'),
            ('2', 'High-pass filter (blocks low frequencies)'),
            ('3', 'Band-pass filter (passes a frequency range)'),
        ],
        default='1'
    )
    return {'1': 'lowpass', '2': 'highpass', '3': 'bandpass'}[choice]


def run_wizard() -> None:
    """Main wizard entry point.

    Guides user through filter design with interactive prompts.
    Handles Ctrl+C gracefully.
    """
    try:
        print("\n" + "=" * 50)
        print("  Filter Calculator Wizard")
        print("=" * 50)
        print("\nThis wizard guides you through designing an LC filter.")
        print("Press Ctrl+C at any time to cancel.\n")

        category = _prompt_filter_category()

        if category == 'lowpass':
            run_filter_wizard(
                filter_category='lowpass',
                calculate_butterworth=lp_butterworth,
                calculate_chebyshev=lp_chebyshev,
                calculate_bessel=lp_bessel,
                display_results=display_lowpass,
                build_result=_build_lowpass_result,
            )
        elif category == 'highpass':
            run_filter_wizard(
                filter_category='highpass',
                calculate_butterworth=hp_butterworth,
                calculate_chebyshev=hp_chebyshev,
                calculate_bessel=hp_bessel,
                display_results=display_highpass,
                build_result=_build_highpass_result,
            )
        else:
            run_bandpass_wizard()

    except KeyboardInterrupt:
        print("\n\nWizard cancelled.")
        sys.exit(0)
