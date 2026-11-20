"""Format inductor suggestions as table text, JSON, and CSV, for every kind.

Every output reads the suggestions ``design()`` resolved (``ResolvedParts``); nothing
here selects a part. The table section prints, for each inductor, the suggestions the
detail asks for: ``best`` the build pick or else the first in the fixed kind order,
``full`` up to three of every kind, ``compact`` the best on one line. A kind with no
part states the limit that failed: always when the inductor has no suggestion at all,
and for every kind in ``full``. Each kind supplies its own title, detail lines and
caveats (``toroid_display`` for toroid windings); the error budget is printed the same
way for every kind.
"""

from __future__ import annotations

import textwrap
from collections.abc import Sequence

from .display_helpers import SECTION_RULE
from .formatting import format_fixed, format_frequency, format_inductance
from .inductor_suggestion import KIND_LABELS, KIND_SHORT_LABELS, ErrorBudget, InductorSuggestion
from .resolved_parts import InductorParts
from .toroid_display import (
    CSV_TOROID_HEADER,
    toroid_build_payload,
    toroid_compact_text,
    toroid_csv_columns,
    toroid_detail_lines,
    toroid_preamble_lines,
    toroid_title,
)

# Section name, also used by the inductor note that points at the section.
SECTION_NAME = "Inductor Suggestions"
NO_SUGGESTION_LINE = "No inductor suggestion qualifies:"
_INDUCTOR_NOTE = "Inductors: no standard values"
# One row per inductor: its best suggestion's kind, then each kind's own columns.
CSV_INDUCTOR_HEADER: list[str] = ["InductorKind", *CSV_TOROID_HEADER]
# Reason lines wrap at the width of the section rule plus the indent.
_WRAP_WIDTH = 88


def inductor_note_line(points_to_suggestions: bool) -> str:
    """Footnote under the component table, shared by LP/HP and bandpass.

    Args:
        points_to_suggestions: True when the suggestion section is shown and holds at
            least one suggestion, so the pointer names a section that has content.
    """
    if points_to_suggestions:
        return f"{_INDUCTOR_NOTE}; see {SECTION_NAME}."
    return f"{_INDUCTOR_NOTE}; use the calculated value."


def has_suggestion(inductors: Sequence[InductorParts]) -> bool:
    """True when at least one of ``inductors`` has a suggestion of some kind."""
    return any(inductor.suggestions for inductor in inductors)


def format_error_budget(budget: ErrorBudget) -> str:
    """The error budget, term by term, in percent of the target."""
    mismatch = f"{format_fixed(budget.nominal_mismatch_pct, 2, explicit_sign=True)}%"
    if budget.srf_drift_pct is None:
        drift = "SRF drift not checked"
    else:
        low, high = budget.srf_drift_pct
        drift = (
            f"SRF drift {format_fixed(low, 2, explicit_sign=True)}% to "
            f"{format_fixed(high, 2, explicit_sign=True)}%"
        )
    return f"Error budget: {mismatch} nominal, ±{budget.tolerance_pct:g}% tolerance, {drift}"


def _title(suggestion: InductorSuggestion) -> str:
    if suggestion.kind == "toroid":
        return toroid_title(suggestion.build)
    return suggestion.part_name


def _detail_lines(suggestion: InductorSuggestion) -> list[str]:
    if suggestion.kind == "toroid":
        return toroid_detail_lines(suggestion.build)
    return []


def _compact_text(suggestion: InductorSuggestion) -> str:
    if suggestion.kind == "toroid":
        return toroid_compact_text(suggestion.build)
    return f"{suggestion.part_name}   {format_inductance(suggestion.achieved_h)}"


def _suggestion_lines(suggestion: InductorSuggestion, compact: bool) -> list[str]:
    if compact:
        short = KIND_SHORT_LABELS[suggestion.kind]
        return [f"  {suggestion.rank}. {short} {_compact_text(suggestion)}"]
    return [
        f"  {suggestion.rank}. {KIND_LABELS[suggestion.kind]} {_title(suggestion)}",
        *_detail_lines(suggestion),
        f"     {format_error_budget(suggestion.error_budget)}",
    ]


def _reason_lines(reason: str) -> list[str]:
    """One kind's reason, as a bullet; every reason names its kind."""
    return textwrap.wrap(
        f"- {reason}",
        width=_WRAP_WIDTH,
        initial_indent="  ",
        subsequent_indent="    ",
        break_on_hyphens=False,
    )


def _shown(inductor: InductorParts, detail: str) -> tuple[InductorSuggestion, ...]:
    """The suggestions ``detail`` shows: every one for ``full``, else the best (if any)."""
    if detail == "full":
        return inductor.suggestions
    best = inductor.best
    return () if best is None else (best,)


def _inductor_block(label: str, inductor: InductorParts, freq_hz: float, detail: str) -> list[str]:
    compact = detail == "compact"
    lines = [
        f"  {label} target: {format_inductance(inductor.target_h)} at {format_frequency(freq_hz)}"
    ]
    if not compact:
        # Indented sub-rule ends in the same column as SECTION_RULE.
        lines.append("  " + SECTION_RULE[2:])
    shown = _shown(inductor, detail)
    if not shown:
        lines.append(f"  {NO_SUGGESTION_LINE}")
    for suggestion in shown:
        lines.extend(_suggestion_lines(suggestion, compact))
    if detail == "full" or not shown:
        for group in inductor.kinds:
            if group.reason_none is not None:
                lines.extend(_reason_lines(group.reason_none))
    return lines


def suggestion_section_lines(
    targets: Sequence[tuple[str, InductorParts]], design_freq_hz: float, detail: str
) -> list[str]:
    """The table's inductor suggestion section, shared by CLI, wizard, and web.

    Args:
        targets: ``(label, inductor)`` per block; band-pass passes one block for its
            equal resonator inductors, LP/HP one per inductor.
        design_freq_hz: The frequency the suggestions were checked at.
        detail: ``best``, ``full``, or ``compact`` (``none`` shows no section).

    Returns:
        Lines starting with a blank separator and ending with a blank line after each
        inductor block.
    """
    compact = detail == "compact"
    lines = ["", SECTION_NAME, SECTION_RULE]
    toroids = [
        suggestion.build
        for _label, inductor in targets
        for suggestion in _shown(inductor, detail)
        if suggestion.kind == "toroid"
    ]
    if toroids:
        lines.extend(toroid_preamble_lines(toroids, compact))
    lines.append("")
    for label, inductor in targets:
        lines.extend(_inductor_block(label, inductor, design_freq_hz, detail))
        lines.append("")
    return lines


def _source_payload(suggestion: InductorSuggestion) -> dict | None:
    source = suggestion.source
    if source is None:
        return None
    return {"publisher": source.publisher, "title": source.title, "url": source.url}


def _build_payload(suggestion: InductorSuggestion) -> dict | None:
    if suggestion.kind == "toroid":
        return toroid_build_payload(suggestion.build)
    return None


def suggestion_payload(suggestion: InductorSuggestion) -> dict:
    """One suggestion as JSON (raw enum values kept)."""
    budget = suggestion.error_budget
    return {
        "kind": suggestion.kind,
        "rank": suggestion.rank,
        "part_name": suggestion.part_name,
        "status": suggestion.status,
        "target_henries": suggestion.target_h,
        "achieved_henries": suggestion.achieved_h,
        "tolerance_pct": suggestion.tolerance_pct,
        "srf_basis": suggestion.srf_basis,
        "srf_accuracy": suggestion.srf_accuracy,
        "error_budget": {
            "nominal_mismatch_pct": budget.nominal_mismatch_pct,
            "tolerance_pct": budget.tolerance_pct,
            "srf_drift_pct": None if budget.srf_drift_pct is None else list(budget.srf_drift_pct),
        },
        "source": _source_payload(suggestion),
        "build": _build_payload(suggestion),
        "warnings": list(suggestion.warnings),
    }


def inductor_suggestions_payload(inductor: InductorParts) -> dict:
    """One inductor's suggestions as JSON: every kind's list (or why it has none) and best."""
    best = inductor.best
    return {
        "best": None if best is None else {"kind": best.kind, "rank": best.rank},
        "kinds": [
            {
                "kind": group.kind,
                "suggestions": [suggestion_payload(item) for item in group.suggestions],
                "reason_none": group.reason_none,
            }
            for group in inductor.kinds
        ],
    }


def inductor_csv_columns(inductor: InductorParts | None) -> list[str]:
    """The inductor CSV columns of one row: the best suggestion's kind and its columns.

    A capacitor row (``None``) and an inductor with no suggestion get blanks.
    """
    best = None if inductor is None else inductor.best
    if best is None:
        return [""] * len(CSV_INDUCTOR_HEADER)
    return [best.kind, *toroid_csv_columns(best.build if best.kind == "toroid" else None)]
