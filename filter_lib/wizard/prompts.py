"""Prompt utilities for interactive wizard.

Reusable input prompts with validation, defaults, and choices.
Uses questionary for elegant arrow-key navigation interface.
"""
from typing import Callable

import questionary
from questionary import Style

# Custom style for consistent look throughout wizard
WIZARD_STYLE = Style([
    ('qmark', 'fg:cyan bold'),
    ('question', 'bold'),
    ('answer', 'fg:cyan bold'),
    ('pointer', 'fg:cyan bold'),
    ('highlighted', 'fg:cyan bold'),
    ('selected', 'fg:green'),
])


def prompt_input(message: str, default: str | None = None,
                 validator: Callable[[str], str] | None = None) -> str:
    """Prompt user for text input with optional default and validation.

    Args:
        message: Prompt message to display
        default: Default value if user presses Enter
        validator: Optional function to validate/transform input

    Returns:
        Validated user input or default

    Raises:
        KeyboardInterrupt: If user presses Ctrl+C or cancels
    """
    while True:
        try:
            result = questionary.text(
                message,
                default=default or "",
                style=WIZARD_STYLE,
            ).ask()

            if result is None:
                raise KeyboardInterrupt()

            value = result.strip()
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
    """Prompt user to select from choices using arrow keys.

    Args:
        message: Question to ask
        choices: List of (key, description) tuples
        default: Default key if user presses Enter

    Returns:
        Selected key
    """
    # Build questionary choices
    q_choices = []
    default_choice = None
    for key, desc in choices:
        choice = questionary.Choice(desc, value=key)
        q_choices.append(choice)
        if key == default:
            default_choice = desc

    try:
        result = questionary.select(
            message,
            choices=q_choices,
            default=default_choice,
            style=WIZARD_STYLE,
        ).ask()

        if result is None:
            raise KeyboardInterrupt()
        return result
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


def prompt_topology(filter_category: str) -> str:
    """Prompt for filter topology using arrow keys.

    Args:
        filter_category: 'lowpass' or 'highpass' for context-aware ordering
    """
    if filter_category == 'lowpass':
        choices = [
            questionary.Choice("Pi - Shunt C first (C-L-C-L-C)", value="pi"),
            questionary.Choice("T  - Series L first (L-C-L-C-L)", value="t"),
        ]
        default = "pi"
    else:
        choices = [
            questionary.Choice("T  - Series L first (L-C-L-C-L)", value="t"),
            questionary.Choice("Pi - Shunt C first (C-L-C-L-C)", value="pi"),
        ]
        default = "t"

    try:
        result = questionary.select(
            "Select filter topology:",
            choices=choices,
            default=default,
            style=WIZARD_STYLE,
        ).ask()
        if result is None:
            raise KeyboardInterrupt()
        return result
    except EOFError:
        raise KeyboardInterrupt()


def prompt_filter_type() -> str:
    """Prompt for filter response type using arrow keys."""
    try:
        result = questionary.select(
            "Select filter response type:",
            choices=[
                questionary.Choice("Butterworth - Maximally flat passband", value="butterworth"),
                questionary.Choice("Chebyshev - Sharper cutoff, passband ripple", value="chebyshev"),
                questionary.Choice("Bessel - Best transient response", value="bessel"),
            ],
            default="butterworth",
            style=WIZARD_STYLE,
        ).ask()

        if result is None:
            raise KeyboardInterrupt()
        return result
    except EOFError:
        raise KeyboardInterrupt()


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

    try:
        result = questionary.confirm(
            "Proceed with calculation?",
            default=True,
            style=WIZARD_STYLE,
        ).ask()

        if result is None:
            raise KeyboardInterrupt()
        return result
    except EOFError:
        raise KeyboardInterrupt()


def prompt_show_plot() -> bool:
    """Ask user if they want to see the frequency response plot.

    Returns:
        True if user wants to see the plot
    """
    try:
        result = questionary.confirm(
            "Show frequency response plot?",
            default=True,
            style=WIZARD_STYLE,
        ).ask()

        if result is None:
            raise KeyboardInterrupt()
        return result
    except EOFError:
        raise KeyboardInterrupt()


def prompt_output_options() -> dict:
    """Prompt for output formatting options with interactive arrow-key navigation.

    Uses questionary for an elegant checkbox/radio interface with arrow keys
    and space bar selection.

    Returns:
        Dict with keys: eseries, no_match, raw, quiet, format, plot_data
    """
    print("\n" + "-" * 50)
    print("  Output Options")
    print("-" * 50)
    print("Use arrow keys to navigate, Enter to select\n")

    try:
        # E-Series selection (radio buttons - mutually exclusive)
        eseries_choice = questionary.select(
            "E-Series component matching:",
            choices=[
                questionary.Choice("E24 - Standard tolerance (default)", value="E24"),
                questionary.Choice("E12 - Fewer values, looser tolerance", value="E12"),
                questionary.Choice("E96 - More values, tighter tolerance", value="E96"),
                questionary.Choice("None - Show calculated values only", value="none"),
            ],
            default="E24",
            style=WIZARD_STYLE,
        ).ask()

        if eseries_choice is None:
            raise KeyboardInterrupt()

        # Output format (radio buttons - mutually exclusive)
        format_choice = questionary.select(
            "Output format:",
            choices=[
                questionary.Choice("Table - Pretty printed display (default)", value="table"),
                questionary.Choice("JSON - Machine readable", value="json"),
                questionary.Choice("CSV - Spreadsheet compatible", value="csv"),
            ],
            default="table",
            style=WIZARD_STYLE,
        ).ask()

        if format_choice is None:
            raise KeyboardInterrupt()

        # Plot data export (radio buttons - mutually exclusive)
        plot_choice = questionary.select(
            "Export frequency response data:",
            choices=[
                questionary.Choice("No export (default)", value="none"),
                questionary.Choice("JSON file", value="json"),
                questionary.Choice("CSV file", value="csv"),
            ],
            default="none",
            style=WIZARD_STYLE,
        ).ask()

        if plot_choice is None:
            raise KeyboardInterrupt()

        # Additional options (checkboxes - can select multiple)
        print()  # Spacing before checkbox prompt
        additional = questionary.checkbox(
            "Additional options (Space to toggle, Enter to confirm):",
            choices=[
                questionary.Choice("Raw units - Display in Farads/Henries", value="raw"),
                questionary.Choice("Quiet mode - Minimal output", value="quiet"),
            ],
            style=WIZARD_STYLE,
        ).ask()

        if additional is None:
            raise KeyboardInterrupt()

        # Build result dict
        return {
            'eseries': eseries_choice if eseries_choice != "none" else 'E24',
            'no_match': eseries_choice == "none",
            'raw': 'raw' in additional,
            'quiet': 'quiet' in additional,
            'format': format_choice,
            'plot_data': None if plot_choice == "none" else plot_choice,
        }

    except EOFError:
        raise KeyboardInterrupt()
