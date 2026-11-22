"""Shared display formatting helpers for filter results.

Provides E-series matching display, component formatting, and output formatters.
"""

import re
import textwrap
from collections.abc import Callable

from .capacitor_choice import assumed_tolerance_pct
from .capacitor_grades import SERIES, require_grade, tolerance_rule_text
from .eseries import DEFAULT_MATCH_POLICY, TOLERANCE_NOT_SOURCED, ESeriesMatch, MatchPolicy
from .formatting import format_fixed


def _signed_error_pct(error_pct: float) -> str:
    """One-decimal error with "+" on positive values; an error that rounds to zero is unsigned."""
    rendered = format_fixed(error_pct, 1)
    return f"+{rendered}" if float(rendered) > 0 else rendered


# Rule under every table-output section heading (E-series, inductor suggestions). One width and
# one character keep the sections visually consistent across LP/HP and bandpass.
SECTION_RULE = "\u2500" * 50

# Label column for the E-series rows; both labels pad to the same width so values align.
_USE_LABEL = "  Use:            "
_NEAREST_LABEL = "  Nearest single: "
# Row warnings wrap to an 80-column terminal; CSV, JSON, and SPICE keep one line.
_WARNING_WIDTH = 80
# The section's rule lines, as wide as its longest fixed line.
_RULE_WIDTH = 88


def not_sourced_note(policy: MatchPolicy) -> str:
    """The table note under a choice whose part values the sourced table does not list."""
    return (
        "  Tolerance not sourced (a part is not in the sourced table): chosen by nominal "
        f"value, ±{assumed_tolerance_pct(policy):g}% assumed for it."
    )


def eseries_section_lines(
    series: str, component_name: str = "Capacitor", policy: MatchPolicy | None = None
) -> list[str]:
    """Heading, rule, and selection-rule note for the E-series section.

    Shared by the LP/HP and bandpass renderers so both print the same explanation.
    The series name encodes its density (E24 has 24 values per decade); the grade,
    its tolerances, the override and the stray come from the match policy that selects
    the rows below (the default policy when ``policy`` is None).
    """
    policy = policy or DEFAULT_MATCH_POLICY
    values_per_decade = int(series.upper().removeprefix("E"))
    name = component_name.lower()
    return [
        f"\n{series} Standard {component_name} Values",
        SECTION_RULE,
        f"{series} = {values_per_decade} standard values per decade; "
        "it does not set the part tolerance.",
        f"Each {name} gets the single part or parallel pair whose worst case (each part at",
        "either end of its tolerance, plus the assumed stray across a pair) is closest to",
        "the calculated value; a pair only if it is at least "
        f"{policy.min_parallel_improvement_pct_points:g} percentage points closer.",
        *_policy_lines(policy),
        "",
    ]


def _policy_lines(policy: MatchPolicy) -> list[str]:
    """The grade, its tolerances, any override and the stray, wrapped for the table."""
    grade = require_grade(policy.grade).label.lower()
    if policy.tolerance_override_pct is None:
        tolerance = f"Tolerance ({grade} grade, {SERIES.title}): "
    else:
        tolerance = (
            f"Tolerance: the larger of ±{policy.tolerance_override_pct:g}% and the "
            f"{grade} grade ({SERIES.title}): "
        )
    stray_pf = policy.stray_capacitance_f * 1e12
    return [
        *_wrap_pieces(tolerance, tolerance_rule_text(policy.grade).split(", ")),
        f"Stray: {stray_pf:g} pF across the second part of a pair (an assumption).",
    ]


def _wrap_pieces(lead: str, pieces: list[str]) -> list[str]:
    """``lead`` then ``pieces`` joined by ", ", wrapped only between pieces, ending with "."."""
    lines = [lead.rstrip()]
    for index, piece in enumerate(pieces):
        piece += "." if index == len(pieces) - 1 else ","
        if len(lines[-1]) + 1 + len(piece) <= _RULE_WIDTH:
            lines[-1] += " " + piece
        else:
            lines.append(piece)
    return lines


def format_eseries_match(match: ESeriesMatch, unit_formatter: Callable[[float], str]) -> list[str]:
    """Format the standard-value choice ``design()`` resolved for one capacitor.

    ``Use:`` names the chosen option. ``Nearest single:`` appears only when the
    choice is a parallel pair, or as a reference value when no part is chosen
    (targets below the automatic-selection floor).

    Args:
        match: The resolved choice (``ResolvedParts.capacitor``)
        unit_formatter: Function to format value with units (e.g., format_capacitance)

    Returns:
        List of indented lines: the chosen option, then any reference or warning lines
    """
    single = f"{unit_formatter(match.single_value)} ({_signed_error_pct(match.single_error_pct)}%)"
    nearest = (
        f"{unit_formatter(match.nearest_value)} ({_signed_error_pct(match.nearest_error_pct)}%)"
    )
    notes = (
        textwrap.wrap(
            not_sourced_note(match.policy),
            width=_WARNING_WIDTH,
            subsequent_indent="    ",
        )
        if match.status == TOLERANCE_NOT_SOURCED
        else []
    )

    if match.selected_value is None:
        floor_pf = match.policy.minimum_capacitance_f * 1e12
        lines = [
            f"{_USE_LABEL}none (below {floor_pf:g} pF; see warning)",
            f"{_NEAREST_LABEL}{nearest}, for reference only",
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
        return [f"{_USE_LABEL}{pair}", f"{_NEAREST_LABEL}{nearest}", *notes]
    return [f"{_USE_LABEL}{single}", *notes]


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


# A number and its unit (``3.09 pF``, ``145.974 MHz``) never wrap apart.
_VALUE_UNIT = re.compile(r"(\d) (?=[fpnuµm]?(?:F|H|Hz)\b|[kMG]Hz\b)")


def wrap_keeping_units(
    text: str, width: int, *, initial_indent: str = "", subsequent_indent: str = ""
) -> list[str]:
    """Wrap ``text`` at ``width`` without separating a number from its unit."""
    joined = _VALUE_UNIT.sub("\\1\u00a0", text)
    return [
        line.replace("\u00a0", " ")
        for line in textwrap.wrap(
            joined,
            width=width,
            initial_indent=initial_indent,
            subsequent_indent=subsequent_indent,
            break_on_hyphens=False,
        )
    ]
