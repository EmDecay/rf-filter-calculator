"""The capacitor grade, tolerance and stray inputs as the wizard and the web show them.

Both interfaces use these labels, choices, help texts and parsers, so a value either one
refuses gets the CLI's message (``--capacitor-grade``, ``--capacitor-tolerance``,
``--stray-capacitance``). A blank text field means the CLI flag left out.
"""

from __future__ import annotations

from ..shared.capacitor_grades import GRADE_NAMES, SERIES
from ..shared.eseries import (
    CAPACITOR_GRADE_LABEL,
    CAPACITOR_TOLERANCE_LABEL,
    DEFAULT_STRAY_CAPACITANCE_F,
    require_capacitor_tolerance_pct,
)
from ..shared.parsing import parse_stray_capacitance

GRADE_CHOICES = (("standard", "Standard"), ("tight", "Tight"))
GRADE_HELP = (
    f"Tolerance grade of the sourced C0G series ({SERIES.title}): Standard is the "
    "manufacturer's standard tolerance, Tight one step tighter. Each capacitor is chosen "
    "by its worst case within tolerance."
)
TOLERANCE_FIELD_LABEL = f"{CAPACITOR_TOLERANCE_LABEL} (±%)"
TOLERANCE_FIELD_HELP = (
    "Blank = the grade's tolerance. A value can only loosen it: each capacitor uses the "
    "larger of the two. A value the series does not make uses it instead of the assumed 5%."
)
STRAY_FIELD_LABEL = "Stray capacitance per extra part"
STRAY_FIELD_HELP = (
    "Assumed layout capacitance across the second part of a parallel pair, e.g. 0.2pF; "
    "0 to 10 pF. Blank = 0.2 pF. An assumption, not a sourced value."
)

assert tuple(value for value, _label in GRADE_CHOICES) == GRADE_NAMES


def parse_tolerance_field(text: str) -> float | None:
    """The tolerance override typed in the field, or ``None`` when it is blank."""
    text = text.strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError as error:
        raise ValueError(f"{CAPACITOR_TOLERANCE_LABEL} must be a number") from error
    return require_capacitor_tolerance_pct(value)


def parse_stray_field(text: str) -> float:
    """The stray capacitance typed in the field, or the default when it is blank."""
    text = text.strip()
    return parse_stray_capacitance(text) if text else DEFAULT_STRAY_CAPACITANCE_F


__all__ = [
    "CAPACITOR_GRADE_LABEL",
    "GRADE_CHOICES",
    "GRADE_HELP",
    "STRAY_FIELD_HELP",
    "STRAY_FIELD_LABEL",
    "TOLERANCE_FIELD_HELP",
    "TOLERANCE_FIELD_LABEL",
    "parse_stray_field",
    "parse_tolerance_field",
]
