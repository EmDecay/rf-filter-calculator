"""The suggestion record every inductor kind shares, and the inductor option values.

A suggestion is one buildable part for one inductor: its kind, the target and the
inductance it reaches, its manufacturing tolerance, the basis of its self-resonance
(SRF) check, its build details, its source, and its error budget. Each kind keeps its
own selection rules and detail lines; everything that compares, orders, simulates or
prints suggestions uses this record. Kinds are always listed in the fixed build order
``INDUCTOR_KINDS`` (toroid, air coil, chip), each kind's suggestions in its own rank.

A kind with no qualifying part for an inductor states the limit that failed
(``KindSuggestions.reason_none``). A kind that is never offered states why once, in the
words of ``docs/component-data-sources.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .numeric import is_finite_real

# Fixed build order: ``auto`` builds the first kind in this order that has a part.
INDUCTOR_KINDS = ("toroid", "air-coil", "chip")
KIND_LABELS = {"toroid": "Toroid winding", "air-coil": "Air-core coil", "chip": "Chip inductor"}
KIND_SHORT_LABELS = {"toroid": "Toroid", "air-coil": "Air coil", "chip": "Chip"}

# How much the table shows (CLI --inductor-suggestions; wizard and web "Inductor
# suggestions"). JSON always lists up to MAX_SUGGESTIONS_PER_KIND per kind and CSV the
# best; "none" leaves suggestions out of every output and builds the calculated values.
INDUCTOR_DETAILS = ("best", "full", "compact", "none")
DEFAULT_INDUCTOR_DETAIL = "best"
# The details other than the default that only a table shows: choosing one sets the
# inductor detail option (CLI --inductor-suggestions full or compact).
NON_DEFAULT_TABLE_DETAILS = frozenset({"full", "compact"})
# Details that change only the table; JSON, CSV, SPICE, and the build are the same for each.
TABLE_ONLY_DETAILS = frozenset({DEFAULT_INDUCTOR_DETAIL, *NON_DEFAULT_TABLE_DETAILS})
MAX_SUGGESTIONS_PER_KIND = 3

# What the build simulation and the chosen-parts SPICE deck use for each inductor (CLI
# --build-inductors): the first kind with a part (auto), one kind, or the calculated value.
CALCULATED = "calculated"
AUTO = "auto"
BUILD_INDUCTOR_CHOICES = (AUTO, *INDUCTOR_KINDS, CALCULATED)
DEFAULT_BUILD_INDUCTORS = AUTO
FORCED_KINDS = frozenset(INDUCTOR_KINDS)

# The basis of a suggestion's SRF check.
SRF_GUARANTEED_MINIMUM = "guaranteed_minimum"  # a manufacturer's guaranteed minimum SRF
SRF_MODEL = "model"  # a published model, with its stated accuracy
SRF_NOT_CHECKED = "not_checked"  # legacy HF toroid windings only
SRF_BASES = (SRF_GUARANTEED_MINIMUM, SRF_MODEL, SRF_NOT_CHECKED)

# Why a kind is never offered, worded in docs/component-data-sources.md. Every reason a
# kind has no part names the kind, so a list of reasons reads without labels.
VHF_TOROID_EXCLUSION = (
    "VHF toroids are not offered: the core maker publishes no self-resonance or "
    "winding-capacitance data, so the inductance near the band cannot be checked."
)
AIR_COIL_EXCLUSION = (
    "Air-core coils are not offered: no published self-capacitance model is validated for "
    "coils of a few spaced turns, so their self-resonance cannot be checked."
)
CHIP_NOT_AVAILABLE = "Chip inductor suggestions are not available in this version."

# CLI spellings and help; the wizard and web word their controls from
# ``design/inductor_option_inputs.py``.
INDUCTOR_SUGGESTIONS_FLAG = "--inductor-suggestions"
BUILD_INDUCTORS_FLAG = "--build-inductors"
INDUCTOR_SUGGESTIONS_HELP = (
    "Inductor suggestions in table output: best (default) shows the part the build uses, "
    "else the first in the order toroid, air coil, chip; full shows up to three of each "
    "kind and why a kind has none; compact shows the best on one line; none leaves the "
    "suggestions out of every output, and --sim-build and SPICE then use the calculated "
    "inductances. JSON always lists up to three per kind and CSV the best"
)
BUILD_INDUCTORS_HELP = (
    "What --sim-build and the nominal-build SPICE deck use for each inductor: auto "
    "(default) the first suggestion in the order toroid, air coil, chip; toroid, air-coil, "
    "or chip that kind's best suggestion; calculated the calculated inductance. An "
    "inductor with no suggestion of the chosen kind uses its calculated value, and the "
    "output says why"
)

# A forced kind needs suggestions to build with (CLI --inductor-suggestions none with
# --build-inductors toroid, air-coil or chip; the wizard and web disable the control).
FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE = (
    "There are no inductor suggestions to build with when Inductor suggestions is None; "
    "the build uses the calculated inductances"
)

# Build substitution values (JSON ``method``/``status``) for inductors.
SUGGESTED_INDUCTOR_METHOD = "suggested_inductor"
SUGGESTIONS_NOT_USED = "suggestions_not_used"
NO_QUALIFYING_SUGGESTION = "no_verified_candidate"


def require_inductor_detail(value: object) -> str:
    """Return ``value`` when it is an inductor detail choice, else raise ``ValueError``."""
    if not isinstance(value, str) or value not in INDUCTOR_DETAILS:
        raise ValueError("Inductor suggestions must be best, full, compact, or none")
    return value


def require_build_inductors(value: object) -> str:
    """Return ``value`` when it is a build-inductor choice, else raise ``ValueError``."""
    if not isinstance(value, str) or value not in BUILD_INDUCTOR_CHOICES:
        raise ValueError("Build inductors must be auto, toroid, air-coil, chip, or calculated")
    return value


def require_build_with_suggestions(detail: str, build_inductors: str) -> None:
    """Refuse a forced kind when suggestions are off (``FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE``)."""
    if detail == "none" and build_inductors in FORCED_KINDS:
        raise ValueError(FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE)


@dataclass(frozen=True)
class ErrorBudget:
    """How far a suggested part can be from its target, term by term.

    ``nominal_mismatch_pct`` is the signed difference of the part's nominal inductance
    from the target, ``tolerance_pct`` its ± manufacturing tolerance, both in percent of
    the target. ``srf_drift_pct`` is the (lowest, highest) change of inductance from
    self-resonance over the checked frequency range, or ``None`` when the SRF is not
    checked.
    """

    nominal_mismatch_pct: float
    tolerance_pct: float
    srf_drift_pct: tuple[float, float] | None = None


@dataclass(frozen=True)
class PartSource:
    """The primary source a suggestion's guarantees come from."""

    publisher: str
    title: str
    url: str


@dataclass(frozen=True)
class InductorSuggestion:
    """One buildable part for one inductor (see the module docstring).

    ``build`` holds the kind's own build details (for a toroid, the screened
    ``ToroidRecommendation``); ``part_name`` names the part in one word (a core name or
    a part number); ``status`` is the kind's candidate status.
    """

    kind: str
    rank: int
    part_name: str
    target_h: float
    achieved_h: float
    tolerance_pct: float
    srf_basis: str
    error_budget: ErrorBudget
    source: PartSource | None
    build: Any
    status: str
    srf_accuracy: str | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in INDUCTOR_KINDS:
            raise ValueError(f"Unknown inductor kind: {self.kind}")
        if self.srf_basis not in SRF_BASES:
            raise ValueError(f"Unknown SRF basis: {self.srf_basis}")
        if not isinstance(self.rank, int) or isinstance(self.rank, bool) or self.rank < 1:
            raise ValueError("Suggestion rank must be a whole number from 1")
        for value in (self.target_h, self.achieved_h):
            if not is_finite_real(value) or value <= 0:
                raise ValueError("Suggestion inductances must be positive and finite")


@dataclass(frozen=True)
class KindSuggestions:
    """One kind's ranked suggestions for one inductor, or the limit that failed.

    ``reason_none`` is set exactly when ``suggestions`` is empty.
    """

    kind: str
    suggestions: tuple[InductorSuggestion, ...] = ()
    reason_none: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in INDUCTOR_KINDS:
            raise ValueError(f"Unknown inductor kind: {self.kind}")
        if bool(self.suggestions) == (self.reason_none is not None):
            raise ValueError("A kind has either suggestions or the reason it has none")
        if any(item.kind != self.kind for item in self.suggestions):
            raise ValueError("Every suggestion must be of its group's kind")
