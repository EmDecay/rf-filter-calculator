"""Bandpass filter wizard.

Interactive prompts for bandpass filter design with coupled resonators.
"""
from ..shared.parsing import parse_frequency, parse_impedance
from ..bandpass import calculate_bandpass_filter, display_results
from .prompts import (prompt_input, prompt_choice, prompt_filter_type,
                      show_summary, validate_order, validate_ripple, prompt_show_plot)

# Default values
DEFAULT_IMPEDANCE = "50"
DEFAULT_RESONATORS = "5"
DEFAULT_RIPPLE = "0.5"


def prompt_coupling() -> str:
    """Prompt for bandpass coupling topology."""
    choice = prompt_choice(
        "Select coupling topology:",
        [
            ('1', 'Top-C (Series) - Better for wider bandwidth'),
            ('2', 'Shunt-C (Parallel) - Better for narrow bandwidth < 10%'),
        ],
        default='1'
    )
    return 'top' if choice == '1' else 'shunt'


def run_bandpass_wizard() -> None:
    """Run bandpass filter wizard."""
    print("\n--- Bandpass Filter Design ---\n")

    while True:
        # Filter type
        filter_type = prompt_filter_type()

        # Coupling
        coupling = prompt_coupling()

        # Center frequency
        print("\nEnter the center frequency of the passband.")
        print("Examples: 14.2MHz, 7.1MHz, 455kHz")
        f0 = prompt_input("Center frequency", validator=parse_frequency)

        # Bandwidth
        print("\nEnter the 3dB bandwidth.")
        print("Examples: 500kHz, 100kHz, 30kHz")
        bw = prompt_input("Bandwidth", validator=parse_frequency)

        # Validate FBW
        fbw = bw / f0
        if fbw > 0.40:
            print(f"\n  Warning: Fractional BW {fbw*100:.1f}% is very wide.")
            print("  Results may be inaccurate above 40%.")
        if coupling == 'shunt' and fbw > 0.10:
            print(f"\n  Warning: Shunt-C limited to ~10% FBW.")
            print("  Consider Top-C for this bandwidth.")

        # Impedance
        print("\nEnter the system impedance (typically 50 ohms).")
        impedance = prompt_input("Impedance", default=DEFAULT_IMPEDANCE,
                                 validator=parse_impedance)

        # Resonators
        print("\nEnter number of resonators (LC tanks).")
        print("More = sharper skirts, more complex (2-9)")
        n = prompt_input("Resonators", default=DEFAULT_RESONATORS,
                         validator=validate_order)

        # Chebyshev odd check
        if filter_type == 'chebyshev' and n % 2 == 0:
            print("\n  Chebyshev requires ODD resonator count for equal terminations.")
            print(f"  Changing to {n + 1}")
            n = n + 1

        # Ripple
        ripple = 0.5
        if filter_type == 'chebyshev':
            print("\nEnter passband ripple in dB (0.1, 0.5, or 1.0)")
            ripple = prompt_input("Ripple dB", default=DEFAULT_RIPPLE,
                                  validator=validate_ripple)

        # Summary
        params = {
            'Response': filter_type.title(),
            'Topology': 'Top-C (Series)' if coupling == 'top' else 'Shunt-C (Parallel)',
            'Center freq': f"{f0/1e6:.4g} MHz",
            'Bandwidth': f"{bw/1e3:.4g} kHz",
            'FBW': f"{fbw*100:.2f}%",
            'Impedance': f"{impedance} Ohm",
            'Resonators': n,
        }
        if filter_type == 'chebyshev':
            params['Ripple'] = f"{ripple} dB"

        if not show_summary('bandpass', params):
            continue  # Start over

        # Calculate
        print("\n  Calculating...")

        try:
            result = calculate_bandpass_filter(
                f0=f0, bw=bw, z0=impedance, n_resonators=n,
                filter_type=filter_type, coupling=coupling,
                ripple_db=ripple if filter_type == 'chebyshev' else 0.5,
            )
            show_plot = prompt_show_plot()
            display_results(result, show_plot=show_plot)
            break  # Exit loop after successful calculation
        except ValueError as e:
            print(f"\n  Error: {e}")
            print("  Try reducing bandwidth or number of resonators.")
            # Continue loop to let user try again
