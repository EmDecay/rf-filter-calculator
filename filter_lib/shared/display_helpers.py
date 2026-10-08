"""Shared display formatting helpers for filter results.

Provides E-series matching display, component formatting, and output formatters.
"""

import textwrap
from collections.abc import Callable

from .eseries import DEFAULT_MATCH_POLICY, MatchPolicy, match_component
from .formatting import format_fixed


def _signed_error_pct(error_pct: float) -> str:
    """One-decimal error with "+" on positive values; an error that rounds to zero is unsigned."""
    rendered = format_fixed(error_pct, 1)
    return f"+{rendered}" if float(rendered) > 0 else rendered


# Rule under every table-output section heading (E-series, toroid). One width and
# one character keep the sections visually consistent across LP/HP and bandpass.
SECTION_RULE = "\u2500" * 50

# Label column for the E-series rows; both labels pad to the same width so values align.
_USE_LABEL = "  Use:            "
_NEAREST_LABEL = "  Nearest single: "
# Row warnings wrap to an 80-column terminal; CSV, JSON, and SPICE keep one line.
_WARNING_WIDTH = 80


def eseries_section_lines(
    series: str, component_name: str = "Capacitor", policy: MatchPolicy | None = None
) -> list[str]:
    """Heading, rule, and selection-rule note for the E-series section.

    Shared by the LP/HP and bandpass renderers so both print the same explanation.
    The series name encodes its density (E24 has 24 values per decade), and the
    thresholds come from the match policy that selects the rows below (the default
    policy when ``policy`` is None).
    """
    policy = policy or DEFAULT_MATCH_POLICY
    values_per_decade = int(series.upper().removeprefix("E"))
    return [
        f"\n{series} Standard {component_name} Values",
        SECTION_RULE,
        f"{series} = {values_per_decade} standard values per decade; "
        "it does not set the part tolerance.",
        f"Each {component_name.lower()} gets one choice: a single part if within "
        f"{policy.prefer_single_within_pct:g}%, otherwise two in",
        f"parallel if that is at least {policy.min_parallel_improvement_pct_points:g} "
        "percentage points closer.",
        "",
    ]


def format_eseries_match(
    value: float,
    series: str,
    unit_formatter: Callable[[float], str],
    parallel_mode: str | None = None,
    policy: MatchPolicy | None = None,
) -> list[str]:
    """Format the E-series choice for one component.

    ``Use:`` names the chosen option. ``Nearest single:`` appears only when the
    choice is a parallel pair, or as a reference value when no part is chosen
    (targets below the automatic-selection floor).

    Args:
        value: Component value to match
        series: E-series name (E12, E24, E96)
        unit_formatter: Function to format value with units (e.g., format_capacitance)
        parallel_mode: 'additive' for capacitors, 'harmonic' for inductors/resistors.
                       Required — must match the component physics.
        policy: Match policy (None selects the default, which chooses no part below 1 pF)

    Returns:
        List of indented lines: the chosen option, then any reference or warning lines
    """
    match = match_component(value, series, parallel_mode=parallel_mode, policy=policy)
    single = f"{unit_formatter(match.single_value)} ({_signed_error_pct(match.single_error_pct)}%)"

    if match.selected_value is None:
        floor_pf = match.policy.minimum_capacitance_f * 1e12
        lines = [
            f"{_USE_LABEL}none (below {floor_pf:g} pF; see warning)",
            f"{_NEAREST_LABEL}{single}, for reference only",
        ]
        for warning in match.warnings:
            lines.extend(
                textwrap.wrap(
                    warning,
                    width=_WARNING_WIDTH,
                    initial_indent="  Warning: ",
                    subsequent_indent="           ",
                )
            )
        return lines

    if match.prefers_parallel:
        p1, p2 = match.parallel
        # Both values keep full units: a pair can span decades
        # (e.g. "910 pF || 8.2 nF"), so a bare first number is ambiguous.
        pair = (
            f"{unit_formatter(p1)} || {unit_formatter(p2)} "
            f"({_signed_error_pct(match.parallel_error_pct)}%)"
        )
        return [f"{_USE_LABEL}{pair}", f"{_NEAREST_LABEL}{single}"]
    return [f"{_USE_LABEL}{single}"]


def format_component_value(
    name: str, value: float, unit_formatter: Callable[[float], str], raw: bool = False
) -> str:
    """Format a component value with optional raw mode.

    Args:
        name: Component name (e.g., 'C1', 'L2')
        value: Component value in base units (F or H)
        unit_formatter: Function to format value (format_capacitance or format_inductance)
        raw: If True, use scientific notation

    Returns:
        Formatted string like "C1: 150 pF" or "C1: 1.50e-10 F"
    """
    if raw:
        # Raw mode bypasses the formatter, so the base unit is inferred from
        # the formatter's name (format_capacitance -> F, else H). Renaming
        # those formatters would silently mislabel raw output.
        unit = "F" if "capacit" in unit_formatter.__name__.lower() else "H"
        return f"{name}: {value:.6e} {unit}"
    return f"{name}: {unit_formatter(value)}"


def split_value_unit(formatted_string: str) -> tuple[str, str]:
    """Split a formatted value string into (value, unit) tuple.

    Relies on the formatting.py invariant that every formatter emits
    exactly one space before the unit suffix ("<number> <unit>").

    Args:
        formatted_string: String like "150 pF" or "1.5 uH"

    Returns:
        Tuple of (value_str, unit_str), e.g., ("150", "pF")
    """
    return tuple(formatted_string.rsplit(" ", 1))
