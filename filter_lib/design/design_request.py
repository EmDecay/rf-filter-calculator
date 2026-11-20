"""Validated design inputs shared by the CLI, the wizard, and the web UI.

Every presentation layer converts its own input (argparse flags, wizard state, form
fields) into one ``DesignRequest``. Construction applies the cross-field rules that
used to live in each handler, with their exact messages, so every surface rejects
the same input with the same text. Numeric range checks that the calculators already
perform (frequency, impedance, order) are not repeated here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..shared.build_types import BuildConfig
from ..shared.capacitor_grades import DEFAULT_GRADE, require_grade
from ..shared.cli_aliases import (
    DEFAULT_ESERIES,
    DEFAULT_Q_SAFETY,
    MAX_RIPPLE_DB,
    RIPPLE_RANGE_MESSAGE,
    chebyshev_odd_count_message,
    resolve_coupling,
    resolve_filter_type,
)
from ..shared.cli_bandpass_output_validation import RESONATOR_Q_LABELS, loss_q_not_shown_message
from ..shared.eseries import (
    CAPACITOR_GRADE_LABEL,
    CAPACITOR_TOLERANCE_LABEL,
    DEFAULT_STRAY_CAPACITANCE_F,
    E_SERIES,
    STRAY_CAPACITANCE_LABEL,
    SUB_PF_OPTION_LABEL,
    require_capacitor_tolerance_pct,
)
from ..shared.inductor_suggestion import (
    DEFAULT_BUILD_INDUCTORS,
    DEFAULT_INDUCTOR_DETAIL,
    TABLE_ONLY_DETAILS,
    require_build_inductors,
    require_build_with_suggestions,
    require_inductor_detail,
)
from ..shared.numeric import is_finite_real, positive_geometric_mean, require_positive_finite
from ..shared.physical_input_limits import require_stray_capacitance
from .render_options import (
    BUILD_NEEDS_ESERIES_MESSAGE,
    SUB_PF_NEEDS_ESERIES_MESSAGE,
    needs_eseries_message,
)

CATEGORIES = ("lowpass", "highpass", "bandpass")


def band_from_edges(f_low_hz: float, f_high_hz: float) -> tuple[float, float]:
    """Return ``(center_hz, bandwidth_hz)`` for a band given by its -3 dB edges.

    The center is the geometric mean because the bandpass response is geometrically
    symmetric about it; recomputed edges then agree with the inputs to rounding.
    """
    require_positive_finite(f_low_hz, "Lower cutoff frequency")
    require_positive_finite(f_high_hz, "Upper cutoff frequency")
    if f_low_hz >= f_high_hz:
        raise ValueError("Lower cutoff frequency must be below the upper cutoff frequency")
    return positive_geometric_mean(f_low_hz, f_high_hz), f_high_hz - f_low_hz


def check_q_safety(q_safety: object) -> None:
    """Reject a non-positive legacy Q safety factor (NaN reaches the calculator)."""
    if _is_real(q_safety) and q_safety <= 0:
        raise ValueError("Q safety factor must be positive")


def _is_real(value: object) -> bool:
    """Return whether ``value`` can be compared as a number (NaN included)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class DesignRequest:
    """One filter design: synthesis inputs, part policy, and build settings.

    ``topology`` is ``pi`` or ``t`` for ladders and the coupling id (``top``) for
    bandpass; ``order`` is the component count for ladders and the resonator count
    for bandpass. ``requested_f_low_hz``/``requested_f_high_hz`` record a band
    specified by its edges so the result metadata can restate them exactly.

    The part policy is resolved once, by ``design()``, and every output reads it from
    the ``DesignResult``: ``eseries`` is the standard capacitor series (``None`` for no
    standard values, CLI ``--no-match``) and ``allow_sub_pf`` the one switch for
    choosing capacitors below 1 pF (``--allow-sub-pf``; "Allow capacitors below 1 pF"
    in the wizard and web). Together they decide the standard capacitors of the table,
    CSV, JSON, the build simulation, and the chosen-parts SPICE deck.
    ``capacitor_grade`` picks the sourced tolerance grade (``standard`` or ``tight``),
    ``capacitor_tolerance_pct`` an optional percentage that can only loosen it (``None``
    for none), and ``stray_capacitance_f`` the assumed capacitance across the second part
    of a parallel pair.

    ``inductor_suggestions`` is how much of the inductor suggestions the table shows
    (``best``, ``full``, ``compact``) or ``none``, which leaves them out of every output
    and builds the calculated inductances; ``build_inductors`` is what the build
    simulation and the chosen-parts SPICE deck use for each inductor (``auto``, one kind,
    or ``calculated``). A forced kind needs suggestions.

    ``realization`` holds what a chosen-parts deck or a build simulation needs (ports,
    Q and its frequency, tolerances, grid); ``None`` uses the CLI's
    defaults. ``run_build_analysis`` runs the build simulation's tolerance cases; a
    SPICE deck uses ``realization`` without running them.
    """

    category: str
    filter_type: str
    topology: str
    frequency_hz: float
    impedance: float
    order: int
    ripple_db: float | None = None
    bandwidth_hz: float | None = None
    requested_f_low_hz: float | None = None
    requested_f_high_hz: float | None = None
    q_safety: float = DEFAULT_Q_SAFETY
    qu: float | None = None
    ql: float | None = None
    qc: float | None = None
    resonator_impedance: float | None = None
    resonator_inductance: float | None = None
    eseries: str | None = DEFAULT_ESERIES
    allow_sub_pf: bool = False
    capacitor_grade: str = DEFAULT_GRADE
    capacitor_tolerance_pct: float | None = None
    stray_capacitance_f: float = DEFAULT_STRAY_CAPACITANCE_F
    inductor_suggestions: str = DEFAULT_INDUCTOR_DETAIL
    build_inductors: str = DEFAULT_BUILD_INDUCTORS
    realization: BuildConfig | None = None
    run_build_analysis: bool = False

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError("Unknown filter category")
        self._validate_part_policy()
        object.__setattr__(self, "filter_type", resolve_filter_type(self.filter_type))
        if self.category == "bandpass":
            object.__setattr__(self, "topology", resolve_coupling(self.topology))
            self._validate_bandpass()
        else:
            self._validate_ladder()

    def _validate_part_policy(self) -> None:
        if self.eseries is not None and (
            not isinstance(self.eseries, str) or self.eseries not in E_SERIES
        ):
            raise ValueError("E-series must be E12, E24, or E96")
        if not isinstance(self.allow_sub_pf, bool):
            raise ValueError(f'"{SUB_PF_OPTION_LABEL}" must be on or off')
        if self.allow_sub_pf and self.eseries is None:
            raise ValueError(SUB_PF_NEEDS_ESERIES_MESSAGE)
        self._validate_capacitor_policy()
        require_inductor_detail(self.inductor_suggestions)
        require_build_inductors(self.build_inductors)
        require_build_with_suggestions(self.inductor_suggestions, self.build_inductors)
        if self.realization is not None and not isinstance(self.realization, BuildConfig):
            raise ValueError("realization must be a BuildConfig or None")
        if not isinstance(self.run_build_analysis, bool):
            raise ValueError("run_build_analysis must be on or off")
        if self.run_build_analysis and self.eseries is None:
            raise ValueError(BUILD_NEEDS_ESERIES_MESSAGE)

    def _validate_capacitor_policy(self) -> None:
        require_grade(self.capacitor_grade)
        require_capacitor_tolerance_pct(self.capacitor_tolerance_pct)
        require_stray_capacitance(self.stray_capacitance_f)
        if self.eseries is not None:
            return
        for chosen, label in (
            (self.capacitor_grade != DEFAULT_GRADE, CAPACITOR_GRADE_LABEL),
            (self.capacitor_tolerance_pct is not None, CAPACITOR_TOLERANCE_LABEL),
            (self.stray_capacitance_f != DEFAULT_STRAY_CAPACITANCE_F, STRAY_CAPACITANCE_LABEL),
        ):
            if chosen:
                raise ValueError(needs_eseries_message(f'"{label}"'))

    def without_table_detail(self) -> DesignRequest:
        """This request with the table-only inductor detail (full, compact) as ``best``.

        Those details change only the table, so two requests equal here give the same
        JSON, CSV, SPICE, and build.
        """
        if self.inductor_suggestions in TABLE_ONLY_DETAILS:
            return replace(self, inductor_suggestions=DEFAULT_INDUCTOR_DETAIL)
        return self

    @property
    def is_chebyshev(self) -> bool:
        return self.filter_type == "chebyshev"

    def reject_loss_q(self) -> None:
        """Refuse resonator-loss Q for an output that cannot show its effect.

        The table, JSON, and nominal-build SPICE carry the loss model; quiet, CSV, exact
        SPICE, and response data do not, so supplying Q there would be silently ignored.
        """
        supplied = [
            label
            for label, value in zip(RESONATOR_Q_LABELS, (self.qu, self.ql, self.qc))
            if value is not None
        ]
        if supplied:
            raise ValueError(loss_q_not_shown_message(supplied))

    def _validate_ladder(self) -> None:
        if not self.is_chebyshev:
            return
        ripple = self.ripple_db
        # NaN compares false here and reaches the calculator's finiteness check, which
        # reports the same message.
        if not _is_real(ripple) or ripple > MAX_RIPPLE_DB or ripple <= 0:
            raise ValueError(RIPPLE_RANGE_MESSAGE)

    def _validate_bandpass(self) -> None:
        if self.bandwidth_hz is None:
            raise ValueError("Bandwidth is required")
        check_q_safety(self.q_safety)
        if (self.requested_f_low_hz is None) != (self.requested_f_high_hz is None):
            raise ValueError("Lower and upper cutoff frequencies must be supplied together")
        if not self.is_chebyshev:
            return
        ripple = self.ripple_db
        if _is_real(ripple) and ripple > MAX_RIPPLE_DB:
            raise ValueError(RIPPLE_RANGE_MESSAGE)
        if isinstance(self.order, int) and not isinstance(self.order, bool) and self.order % 2 == 0:
            raise ValueError(chebyshev_odd_count_message("resonators"))
        if not is_finite_real(ripple) or ripple <= 0:
            raise ValueError(RIPPLE_RANGE_MESSAGE)
