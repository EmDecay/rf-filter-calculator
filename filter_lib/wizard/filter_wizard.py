"""Shared filter wizard flow for lowpass and highpass filters.

Reduces duplication between lowpass/highpass wizards which share identical flow.
"""
from typing import Callable, Any

from ..shared.parsing import parse_frequency, parse_impedance
from .prompts import (prompt_input, prompt_filter_type, show_summary,
                      validate_order, validate_ripple, prompt_show_plot)

# Default values
DEFAULT_IMPEDANCE = "50"
DEFAULT_ORDER = "3"
DEFAULT_RIPPLE = "0.5"


def run_filter_wizard(
    filter_category: str,
    calculate_butterworth: Callable,
    calculate_chebyshev: Callable,
    calculate_bessel: Callable,
    display_results: Callable,
    build_result: Callable[[str, float, float, Any, Any, int, float | None], dict],
) -> None:
    """Run wizard for lowpass or highpass filter.

    Args:
        filter_category: 'lowpass' or 'highpass'
        calculate_butterworth: Butterworth calculation function
        calculate_chebyshev: Chebyshev calculation function
        calculate_bessel: Bessel calculation function
        display_results: Display function for results
        build_result: Function to build result dict from calculated values
    """
    title = filter_category.replace('-', ' ').title()
    print(f"\n--- {title} Filter Design ---\n")

    while True:
        # Filter type
        filter_type = prompt_filter_type()

        # Frequency
        print("\nEnter the cutoff frequency (-3dB point).")
        print("Examples: 10MHz, 1.5GHz, 500kHz")
        freq_hz = prompt_input("Cutoff frequency", validator=parse_frequency)

        # Impedance
        print("\nEnter the system impedance (typically 50 ohms).")
        impedance = prompt_input("Impedance", default=DEFAULT_IMPEDANCE,
                                 validator=parse_impedance)

        # Order
        print("\nEnter filter order (number of components).")
        print("Higher order = sharper cutoff, more components (2-9)")
        n = prompt_input("Order", default=DEFAULT_ORDER, validator=validate_order)

        # Ripple for Chebyshev
        ripple = 0.5
        if filter_type == 'chebyshev':
            print("\nEnter passband ripple in dB (0.1, 0.5, or 1.0)")
            print("Lower = flatter passband, Higher = sharper cutoff")
            ripple = prompt_input("Ripple dB", default=DEFAULT_RIPPLE,
                                  validator=validate_ripple)

        # Summary
        params = {
            'Response': filter_type.title(),
            'Cutoff': f"{freq_hz/1e6:.4g} MHz",
            'Impedance': f"{impedance} Ohm",
            'Order': n,
        }
        if filter_type == 'chebyshev':
            params['Ripple'] = f"{ripple} dB"

        if not show_summary(filter_category, params):
            continue  # Start over

        # Calculate
        print("\n  Calculating...")

        if filter_type == 'butterworth':
            components = calculate_butterworth(freq_hz, impedance, n)
        elif filter_type == 'chebyshev':
            components = calculate_chebyshev(freq_hz, impedance, ripple, n)
        else:
            components = calculate_bessel(freq_hz, impedance, n)

        result = build_result(
            filter_type, freq_hz, impedance,
            components[0], components[1], components[2],
            ripple if filter_type == 'chebyshev' else None
        )

        show_plot = prompt_show_plot()
        display_results(result, show_plot=show_plot)
        break  # Exit loop after successful calculation
