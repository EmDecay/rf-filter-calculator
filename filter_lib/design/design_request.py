"""Validated design inputs shared by the CLI, the wizard, and the web UI.

Every presentation layer converts its own input (argparse flags, wizard state, form
fields) into one ``DesignRequest``. Construction applies the cross-field rules that
used to live in each handler, with their exact messages, so every surface rejects
the same input with the same text. Numeric range checks that the calculators already
perform (frequency, impedance, order) are not repeated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..shared.cli_aliases import (
    DEFAULT_Q_SAFETY,
    MAX_RIPPLE_DB,
    RIPPLE_RANGE_MESSAGE,
    chebyshev_odd_count_message,
    resolve_coupling,
    resolve_filter_type,
)
from ..shared.cli_bandpass_output_validation import loss_q_not_shown_message
from ..shared.eseries import SUB_PF_OPTION_LABEL
from ..shared.numeric import is_finite_real, positive_geometric_mean, require_positive_finite

if TYPE_CHECKING:
    from ..shared.build_types import BuildConfig

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
    """One filter design: synthesis inputs plus optional realized-build settings.

    ``topology`` is ``pi`` or ``t`` for ladders and the coupling id (``top``) for
    bandpass; ``order`` is the component count for ladders and the resonator count
    for bandpass. ``requested_f_low_hz``/``requested_f_high_hz`` record a band
    specified by its edges so the result metadata can restate them exactly.

    ``allow_sub_pf`` is the one switch for choosing standard capacitor values below
    1 pF (``--allow-sub-pf``; "Allow capacitors below 1 pF" in the wizard and web).
    ``design()`` carries it to every place that picks standard capacitors: the
    E-series table section, CSV/JSON standard matches, the build simulation, and the
    chosen-parts SPICE deck. An explicit ``build.match_policy.allow_sub_pf`` opt-in is
    combined with it (either one allows sub-pF parts), never overwritten.
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
    build: BuildConfig | None = None
    allow_sub_pf: bool = False

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError("Unknown filter category")
        if not isinstance(self.allow_sub_pf, bool):
            raise ValueError(f'"{SUB_PF_OPTION_LABEL}" must be on or off')
        object.__setattr__(self, "filter_type", resolve_filter_type(self.filter_type))
        if self.category == "bandpass":
            object.__setattr__(self, "topology", resolve_coupling(self.topology))
            self._validate_bandpass()
        else:
            self._validate_ladder()

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
            for label, value in (("Qu", self.qu), ("QL", self.ql), ("QC", self.qc))
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
