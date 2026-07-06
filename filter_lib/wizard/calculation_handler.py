"""Calculation orchestration for wizard results.

Main entry point that routes to filter-specific calculators.
The actual calculation logic is in filter_type_calculators.py.
Formatting helpers are in formatting_helpers.py.
"""

from .state import FilterState


def calculate_and_format(state: FilterState) -> str:
    """Perform filter calculation and return formatted output text.

    Args:
        state: FilterState with all parameters configured

    Returns:
        Formatted output string for display
    """
    # Deferred so the wizard UI can start without loading the calculation
    # stack; it's only paid when the user actually reaches the results screen.
    from .filter_type_calculators import calculate_bandpass, calculate_highpass, calculate_lowpass

    # Broad catch is deliberate: this runs inside a Textual worker thread, and
    # any escaping exception would leave the results screen stuck on
    # "Calculating...". Errors become display text instead.
    try:
        if state.category == "lowpass":
            lines = calculate_lowpass(state)
        elif state.category == "highpass":
            lines = calculate_highpass(state)
        elif state.category == "bandpass":
            lines = calculate_bandpass(state)
        else:
            lines = ["Unknown filter category"]
    except Exception as e:
        lines = [f"Calculation error: {e}"]

    return "\n".join(lines)
