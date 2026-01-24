"""Prompt utilities for interactive wizard.

Reusable input prompts with validation, defaults, and choices.
"""
from typing import Callable


def prompt_input(message: str, default: str | None = None,
                 validator: Callable[[str], str] | None = None) -> str:
    """Prompt user with optional default and validation.

    Args:
        message: Prompt message to display
        default: Default value if user presses Enter
        validator: Optional function to validate/transform input

    Returns:
        Validated user input or default

    Raises:
        KeyboardInterrupt: If user presses Ctrl+C or EOF
    """
    prompt_text = f"{message}"
    if default:
        prompt_text += f" [{default}]"
    prompt_text += ": "

    while True:
        try:
            value = input(prompt_text).strip()
            if not value and default:
                value = default

            if validator:
                try:
                    return validator(value)
                except ValueError as e:
                    print(f"  Invalid: {e}. Try again.")
                    continue
            return value
        except EOFError:
            raise KeyboardInterrupt()


def prompt_choice(message: str, choices: list[tuple[str, str]],
                  default: str | None = None) -> str:
    """Prompt user to select from numbered choices.

    Args:
        message: Question to ask
        choices: List of (key, description) tuples
        default: Default key if user presses Enter

    Returns:
        Selected key
    """
    print(f"\n{message}")
    for key, desc in choices:
        marker = " *" if key == default else ""
        print(f"  {key}) {desc}{marker}")

    valid_keys = [k for k, _ in choices]
    prompt = "Enter choice"
    if default:
        prompt += f" [{default}]"

    while True:
        try:
            value = input(f"{prompt}: ").strip().lower()
            if not value and default:
                return default
            if value in valid_keys:
                return value
            print(f"  Invalid choice. Enter one of: {', '.join(valid_keys)}")
        except EOFError:
            raise KeyboardInterrupt()


def validate_order(value: str) -> int:
    """Validate filter order (2-9)."""
    n = int(value)
    if not 2 <= n <= 9:
        raise ValueError("Order must be 2-9")
    return n


def validate_ripple(value: str) -> float:
    """Validate Chebyshev ripple (0.1, 0.5, 1.0)."""
    r = float(value)
    if r not in [0.1, 0.5, 1.0]:
        raise ValueError("Ripple must be 0.1, 0.5, or 1.0 dB")
    return r


def prompt_filter_type() -> str:
    """Prompt for filter response type."""
    choice = prompt_choice(
        "Select filter response type:",
        [
            ('1', 'Butterworth - Maximally flat passband'),
            ('2', 'Chebyshev - Sharper cutoff, passband ripple'),
            ('3', 'Bessel - Best transient response'),
        ],
        default='1'
    )
    return {'1': 'butterworth', '2': 'chebyshev', '3': 'bessel'}[choice]


def show_summary(category: str, params: dict) -> bool:
    """Show parameter summary and confirm.

    Args:
        category: Filter category (lowpass/highpass/bandpass)
        params: Dict of parameter names to values

    Returns:
        True if user confirms, False to start over
    """
    print("\n" + "=" * 50)
    print("  Design Summary")
    print("=" * 50)
    print(f"  Filter type: {category.title()}")
    for name, value in params.items():
        print(f"  {name}: {value}")
    print("=" * 50)

    choice = prompt_choice(
        "Proceed with calculation?",
        [
            ('y', 'Yes, calculate'),
            ('n', 'No, start over'),
        ],
        default='y'
    )
    return choice == 'y'


def prompt_show_plot() -> bool:
    """Ask user if they want to see the frequency response plot.

    Returns:
        True if user wants to see the plot
    """
    choice = prompt_choice(
        "Show frequency response plot?",
        [
            ('y', 'Yes, show ASCII frequency response'),
            ('n', 'No, skip plot'),
        ],
        default='y'
    )
    return choice == 'y'


def prompt_output_options() -> dict:
    """Prompt for output formatting options with checkboxes.

    Returns:
        Dict with keys: eseries, no_match, raw, quiet, format, plot_data
    """
    print("\n" + "-" * 50)
    print("  Output Options")
    print("-" * 50)
    print("Select options (enter numbers separated by spaces, or press Enter for defaults):\n")

    options = [
        ('1', 'E12 series', 'Use E12 component values (fewer choices, looser tolerance)'),
        ('2', 'E96 series', 'Use E96 component values (more choices, tighter tolerance)'),
        ('3', 'No matching', 'Show calculated values only (no E-series matching)'),
        ('4', 'Raw units', 'Display in Farads/Henries instead of pF/nH/µH'),
        ('5', 'Quiet mode', 'Minimal output (component values only)'),
        ('6', 'JSON output', 'Output in JSON format'),
        ('7', 'CSV output', 'Output in CSV format'),
        ('8', 'Export plot JSON', 'Export frequency response data as JSON'),
        ('9', 'Export plot CSV', 'Export frequency response data as CSV'),
    ]

    for num, name, desc in options:
        print(f"  [{num}] {name:15} - {desc}")

    print(f"\n  Default: E24 series with matching, table format")

    while True:
        try:
            raw_input = input("\nSelect options (e.g., '1 4' or Enter for defaults): ").strip()
            if not raw_input:
                # Return defaults
                return {
                    'eseries': 'E24',
                    'no_match': False,
                    'raw': False,
                    'quiet': False,
                    'format': 'table',
                    'plot_data': None,
                }

            selected = set(raw_input.split())
            invalid = selected - {'1', '2', '3', '4', '5', '6', '7', '8', '9'}
            if invalid:
                print(f"  Invalid option(s): {', '.join(invalid)}. Try again.")
                continue

            # Check for conflicts
            if '1' in selected and '2' in selected:
                print("  Cannot select both E12 and E96. Choose one.")
                continue
            if '6' in selected and '7' in selected:
                print("  Cannot select both JSON and CSV format. Choose one.")
                continue
            if '8' in selected and '9' in selected:
                print("  Cannot select both plot JSON and CSV. Choose one.")
                continue

            # Build result
            result = {
                'eseries': 'E12' if '1' in selected else ('E96' if '2' in selected else 'E24'),
                'no_match': '3' in selected,
                'raw': '4' in selected,
                'quiet': '5' in selected,
                'format': 'json' if '6' in selected else ('csv' if '7' in selected else 'table'),
                'plot_data': 'json' if '8' in selected else ('csv' if '9' in selected else None),
            }
            return result

        except EOFError:
            raise KeyboardInterrupt()
