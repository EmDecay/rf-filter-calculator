"""The chip inductor's own lines, JSON build record, and CSV columns.

``inductor_display`` prints every inductor suggestion; this module supplies what only a
chip inductor has (manufacturer, family, package, catalog value, guaranteed tolerance,
minimum SRF and Q, the inductance and self-capacitance the model gives, the frequencies
it stays within its allowances) and the chip caveats. Pure formatters, no I/O.
"""

import math
import textwrap
from collections.abc import Sequence

from .chip_selection import CHIP_NOT_ASSESSED_WARNING, ChipSuggestion
from .formatting import format_capacitance, format_fixed, format_frequency, format_inductance
from .srf_screen import DESIGN_ALLOWANCE_PCT, DRIFT_ALLOWANCE_PCT, describe_range

# Each rating with the frequency it is stated at: the catalog L at its test frequency,
# the minimum Q at its own, and the model's L and self-capacitance at the top of the check
# window (at the minimum SRF), then the frequencies where the part is within its allowances.
CSV_CHIP_HEADER: list[str] = [
    "ChipManufacturer",
    "ChipTolerancePct",
    "ChipLTest_MHz",
    "ChipSRFMin_MHz",
    "ChipQMin",
    "ChipQTest_MHz",
    "ChipAchievedL_nH",
    "ChipAchievedLAt_MHz",
    "ChipSelfCapacitance_fF",
    "ChipAllowanceLow_MHz",
    "ChipAllowanceHigh_MHz",
    "ChipSourceURL",
    "ChipModelBasis",
    "ChipWarnings",
]
# What the chip figures rest on (the table's preamble says the same).
CHIP_MODEL_BASIS = (
    "Inductance, self-capacitance and allowance range come from the parallel-LC part model with "
    "the maker's minimum SRF and catalog values measured in its fixture; board mounting "
    "changes the SRF."
)

# Preamble lines wrap at the width of the section rule plus the indent.
_WRAP_WIDTH = 88
# The chip caveats printed once above the suggestions when a chip inductor is shown.
CHIP_HEADING = "Chip inductors (wirewound; the maker's guaranteed tolerance and minimum SRF):"
CHIP_MODEL_LINE = (
    "L at {top}: the part's inductance there at its minimum SRF. Self-capacitance: the "
    "upper bound from that SRF at the catalog inductance. Both come from the maker's "
    "fixture; board mounting changes the SRF."
)


def checked_line(window_text: str) -> str:
    """What the chip screen checks, over the design's check window."""
    return (
        f"Checked from {window_text}: SRF drift within ±{DRIFT_ALLOWANCE_PCT:g}% of the "
        f"catalog value, and tolerance plus drift within ±{DESIGN_ALLOWANCE_PCT:g}% of the "
        "target."
    )


def chip_title(chip: ChipSuggestion) -> str:
    """The part's title after its rank and kind: part number, maker, family, package."""
    part = chip.part
    family = part.family
    return f"{part.part_number}  {family.manufacturer} {family.name}, {family.package} package"


def _rating_line(chip: ChipSuggestion) -> str:
    part = chip.part
    return (
        f"     {format_inductance(part.inductance_h)} ±{part.tolerance_pct:g}% at "
        f"{format_frequency(part.test_frequency_hz)}   SRF min "
        f"{format_frequency(part.srf_min_hz)}   Q min {part.q_min:g} at "
        f"{format_frequency(part.q_test_frequency_hz)}"
    )


def _model_line(chip: ChipSuggestion) -> str:
    screen = chip.screen
    assert screen.achieved_h is not None
    return (
        f"     L at {format_frequency(chip.window.high_hz)}: "
        f"{format_inductance(screen.achieved_h)}   Self-capacitance: "
        f"{format_capacitance(chip.model.self_capacitance_f)}"
    )


def _allowance_line(chip: ChipSuggestion) -> str:
    allowance = chip.screen.allowance_range_hz
    assert allowance is not None
    return f"     Within its allowances from {describe_range(allowance)}"


def _source_line(chip: ChipSuggestion) -> str:
    part = chip.part
    source = part.family.source
    return f"     Source: {source.publisher} {source.title}, {source.revision}, {part.page}"


def chip_detail_lines(chip: ChipSuggestion) -> list[str]:
    """The part's detail lines under its title: rating, model, allowance range, source."""
    return [_rating_line(chip), _model_line(chip), _allowance_line(chip), _source_line(chip)]


def chip_compact_text(chip: ChipSuggestion) -> str:
    """One part on one line, after its rank and kind."""
    part = chip.part
    screen = chip.screen
    assert screen.achieved_h is not None
    return (
        f"{part.part_number} ({part.family.manufacturer})   "
        f"{format_inductance(screen.achieved_h)} at "
        f"{format_frequency(chip.window.high_hz)}   ±{part.tolerance_pct:g}%   "
        f"SRF min {format_frequency(part.srf_min_hz)}"
    )


def chip_preamble_lines(shown: Sequence[ChipSuggestion]) -> list[str]:
    """The chip caveats, printed once above the suggestions that show ``shown``."""
    window = shown[0].window
    lines = [CHIP_HEADING]
    for text in (
        checked_line(window.describe()),
        CHIP_NOT_ASSESSED_WARNING,
        CHIP_MODEL_LINE.format(top=format_frequency(window.high_hz)),
    ):
        lines.extend(textwrap.wrap(text, width=_WRAP_WIDTH, break_on_hyphens=False))
    return lines


def chip_build_payload(chip: ChipSuggestion) -> dict:
    """The part's JSON build record."""
    part = chip.part
    family = part.family
    source = family.source
    screen = chip.screen
    allowance = screen.allowance_range_hz
    return {
        "manufacturer": family.manufacturer,
        "family": family.name,
        "package": family.package,
        "part_number": part.part_number,
        "catalog_inductance_henries": part.inductance_h,
        "test_frequency_hz": part.test_frequency_hz,
        "tolerance_pct": part.tolerance_pct,
        "srf_min_hz": part.srf_min_hz,
        "q_min": part.q_min,
        "q_test_frequency_hz": part.q_test_frequency_hz,
        "measurement": family.measurement,
        "source": {
            "publisher": source.publisher,
            "title": source.title,
            "revision": source.revision,
            "url": source.url,
            "sha256": source.sha256,
            "page": part.page,
        },
        "model": {
            "l0_henries": chip.model.l0_h,
            "self_capacitance_farads": chip.model.self_capacitance_f,
            "inductance_at_check_top_henries": screen.achieved_h,
        },
        "check_window_hz": [chip.window.low_hz, chip.window.high_hz],
        "drift_allowance_pct": DRIFT_ALLOWANCE_PCT,
        "design_allowance_pct": DESIGN_ALLOWANCE_PCT,
        "drift_at_minimum_srf_pct": None
        if screen.drift_range is None
        else [value * 100.0 for value in screen.drift_range],
        "worst_case_pct": None if screen.worst_case_pct is None else list(screen.worst_case_pct),
        "allowance_range_hz": None if allowance is None else list(allowance),
    }


def chip_csv_columns(chip: ChipSuggestion | None) -> list[str]:
    """The ``Chip*`` CSV columns of one part, or blanks for another kind or none."""
    if chip is None:
        return [""] * len(CSV_CHIP_HEADER)
    part = chip.part
    screen = chip.screen
    assert screen.achieved_h is not None and screen.allowance_range_hz is not None
    low, high = screen.allowance_range_hz
    return [
        part.family.manufacturer,
        f"{part.tolerance_pct:g}",
        f"{part.test_frequency_hz / 1e6:g}",
        f"{part.srf_min_hz / 1e6:g}",
        f"{part.q_min:g}",
        f"{part.q_test_frequency_hz / 1e6:g}",
        format_fixed(screen.achieved_h * 1e9, 3),
        f"{chip.window.high_hz / 1e6:.6g}",
        format_fixed(chip.model.self_capacitance_f * 1e15, 2),
        # Rounded inward, like the table, so the printed range never claims too much.
        f"{math.ceil(low / 1e5) / 10:g}",
        f"{math.floor(high / 1e5) / 10:g}",
        part.family.source.url,
        CHIP_MODEL_BASIS,
        CHIP_NOT_ASSESSED_WARNING,
    ]
