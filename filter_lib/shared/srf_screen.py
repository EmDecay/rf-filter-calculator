"""Self-resonance (SRF) screen, error budget and part model for inductors with a sourced SRF.

**Part model.** A part with catalog inductance ``L_m`` measured at ``f_m`` and guaranteed
minimum SRF is ``L0`` in parallel with ``C_self``::

    L0 = L_m (1 - (f_m/SRF)^2)        C_self = 1 / ((2 pi SRF)^2 L0)
    L(f) = L0 / (1 - (f/SRF)^2)       (which gives L_m at f_m)

The drift ``L(f)/L_m - 1`` is the change of inductance from self-resonance; it is negative
below ``f_m`` and positive above. A real part's SRF is at or above the minimum, so its
drift lies between zero and the drift at the minimum SRF.

**Screen.** Over the check window (low-pass: DC to the cutoff; band-pass: DC to the upper
-3 dB edge; high-pass: the cutoff to twice the cutoff) a part qualifies when

- its drift at the minimum SRF stays within ``DRIFT_ALLOWANCE_PCT`` everywhere, and
- at both tolerance endpoints, both window ends and both SRF limits (the minimum, and no
  drift), its inductance stays within ``DESIGN_ALLOWANCE_PCT`` of the target. Tolerance
  and drift are combined in henries, so 5% tolerance and 5% drift is 10.25% and fails.

Qualification always uses the manufacturer's guaranteed tolerance. The figures are
conditional on this parallel-LC model and on the manufacturer's fixture measurements:
board mounting changes the SRF (``docs/component-data-sources.md``, Coverage).
"""

from __future__ import annotations

import math
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from fractions import Fraction

from .formatting import format_frequency
from .numeric import is_finite_real, require_positive_finite

# Named design allowances, shown in the output.
DRIFT_ALLOWANCE_PCT = 5.0
DESIGN_ALLOWANCE_PCT = 10.0
# A high-pass design is checked from its cutoff to this multiple of it.
HIGHPASS_CHECK_MULTIPLE = 2.0

# The limits a part can fail, named in the reason a kind has no part.
LIMIT_DRIFT = "drift"
LIMIT_ALLOWANCE = "allowance"


@dataclass(frozen=True)
class CheckWindow:
    """The frequencies a part is checked over, from ``low_hz`` (0 for DC) to ``high_hz``."""

    low_hz: float
    high_hz: float

    def __post_init__(self) -> None:
        if (
            not is_finite_real(self.low_hz)
            or not is_finite_real(self.high_hz)
            or not 0 <= self.low_hz <= self.high_hz
            or self.high_hz == 0
        ):
            raise ValueError("A check window needs finite frequencies from 0, low not above high")

    def describe(self) -> str:
        """``DC to 146 MHz`` or ``125 MHz to 250 MHz``."""
        low = "DC" if self.low_hz == 0 else format_frequency(self.low_hz)
        return f"{low} to {format_frequency(self.high_hz)}"


def _frequency(result: Mapping, key: str, label: str) -> float:
    value = result.get(key)
    if not is_finite_real(value) or value <= 0:
        raise ValueError(f"The design's {label} ({key}) must be positive and finite")
    return value


def check_window(result: Mapping, category: str) -> CheckWindow:
    """The check window of a synthesized design (see the module docstring).

    A high-pass window whose top would pass the largest float stops there, so an extreme
    design is checked (and its parts fail) instead of aborting.
    """
    if category == "bandpass":
        return CheckWindow(0.0, _frequency(result, "f_high", "upper -3 dB edge"))
    if category not in ("lowpass", "highpass"):
        raise ValueError("category must be 'lowpass', 'highpass', or 'bandpass'")
    cutoff = _frequency(result, "freq_hz", "cutoff")
    if category == "lowpass":
        return CheckWindow(0.0, cutoff)
    return CheckWindow(cutoff, min(HIGHPASS_CHECK_MULTIPLE * cutoff, sys.float_info.max))


@dataclass(frozen=True)
class PartModel:
    """A part as ``L0`` in parallel with ``C_self``, from its catalog value and minimum SRF."""

    catalog_inductance_h: float
    test_frequency_hz: float
    srf_hz: float

    def __post_init__(self) -> None:
        for value in (self.catalog_inductance_h, self.test_frequency_hz, self.srf_hz):
            if not is_finite_real(value) or value <= 0:
                raise ValueError("A part model needs positive finite values")
        if self.test_frequency_hz >= self.srf_hz:
            raise ValueError("A part's test frequency must be below its SRF")

    @property
    def _test_ratio(self) -> float:
        return (self.test_frequency_hz / self.srf_hz) ** 2

    @property
    def l0_h(self) -> float:
        """The inductance without self-capacitance, ``L_m (1 - (f_m/SRF)^2)``."""
        return self.catalog_inductance_h * (1.0 - self._test_ratio)

    @property
    def self_capacitance_f(self) -> float:
        """``1 / ((2 pi SRF)^2 L0)``: an upper bound, because the SRF is a minimum."""
        return 1.0 / ((2.0 * math.pi * self.srf_hz) ** 2 * self.l0_h)

    def drift(self, frequency_hz: float) -> float:
        """``L(f)/L_m - 1`` at the minimum SRF (a fraction); ``f`` must be below the SRF."""
        ratio = (frequency_hz / self.srf_hz) ** 2
        if ratio >= 1:
            raise ValueError("The drift is unbounded at and above the SRF")
        return (ratio - self._test_ratio) / (1.0 - ratio)

    def inductance_at(self, frequency_hz: float) -> float:
        """The effective inductance ``L(f)`` at the minimum SRF."""
        return self.catalog_inductance_h * (1.0 + self.drift(frequency_hz))


@dataclass(frozen=True)
class ScreenResult:
    """One part screened against one target over one window.

    ``drift_range`` is the drift (fraction of the catalog value) over the window between
    the minimum SRF and no drift, so it always includes zero. ``budget_pct`` gives the
    error budget's terms in percent of the target: the nominal mismatch, the ±tolerance,
    and the (lowest, highest) drift contribution at the tolerance endpoint it adds to;
    ``worst_case_pct`` is their (lowest, highest) total. ``achieved_h`` is the nominal
    part's inductance at the top of the window at the minimum SRF. ``allowance_range_hz``
    is every frequency at which the part stays within both allowances. The figures are
    ``None`` when the window reaches the minimum SRF.
    """

    failed_limits: frozenset[str]
    drift_range: tuple[float, float] | None
    budget_pct: tuple[float, float, tuple[float, float]] | None
    worst_case_pct: tuple[float, float] | None
    achieved_h: float | None
    allowance_range_hz: tuple[float, float] | None

    @property
    def passed(self) -> bool:
        return not self.failed_limits

    @property
    def worst_abs_pct(self) -> float:
        """The larger distance of the worst case from the target, for ranking."""
        if self.worst_case_pct is None:
            return math.inf
        return max(abs(value) for value in self.worst_case_pct)


def _exact(value: float) -> Fraction:
    """The decimal a value reads as (``2.1e-08`` is exactly 21/10^9), for exact limits."""
    return Fraction(repr(float(value)))


_DRIFT_LIMIT = _exact(DRIFT_ALLOWANCE_PCT) / 100
_DESIGN_LIMIT = _exact(DESIGN_ALLOWANCE_PCT) / 100


class _ExactModel:
    """The part model in exact arithmetic, so a part exactly at a limit is within it."""

    def __init__(self, model: PartModel) -> None:
        self.srf = _exact(model.srf_hz)
        self.catalog = _exact(model.catalog_inductance_h)
        self.test_ratio = (_exact(model.test_frequency_hz) / self.srf) ** 2

    def drift(self, frequency_hz: float) -> Fraction:
        ratio = (_exact(frequency_hz) / self.srf) ** 2
        return (ratio - self.test_ratio) / (1 - ratio)

    def frequency_at_drift(self, drift: Fraction) -> float:
        ratio = (self.test_ratio + drift) / (1 + drift)
        return float(self.srf) * math.sqrt(ratio) if ratio > 0 else 0.0


def _allowance_range(
    target: Fraction, exact: _ExactModel, tolerance: Fraction
) -> tuple[float, float] | None:
    high_drift = min(
        _DRIFT_LIMIT, (1 + _DESIGN_LIMIT) * target / (exact.catalog * (1 + tolerance)) - 1
    )
    low_drift = max(
        -_DRIFT_LIMIT, (1 - _DESIGN_LIMIT) * target / (exact.catalog * (1 - tolerance)) - 1
    )
    if high_drift < 0 or low_drift > 0:
        return None
    # Each end is rounded inward until the exact drift keeps its limit, so every
    # frequency in the returned range passes the exact screen.
    low = exact.frequency_at_drift(low_drift)
    while low > 0 and exact.drift(low) < low_drift:
        low = math.nextafter(low, math.inf)
    high = exact.frequency_at_drift(high_drift)
    while exact.drift(high) > high_drift:
        high = math.nextafter(high, 0.0)
    return low, high


def _require_screen_inputs(target_h: float, tolerance_pct: float) -> None:
    require_positive_finite(target_h, "target inductance")
    if not is_finite_real(tolerance_pct) or not 0 <= tolerance_pct < 100:
        raise ValueError("A part's tolerance must be at least 0% and below 100%")


def allowance_range(
    target_h: float, model: PartModel, tolerance_pct: float
) -> tuple[float, float] | None:
    """Every frequency at which the part stays within both allowances, or ``None``.

    At one frequency the part lies between its low tolerance endpoint (with the drift
    when negative) and its high endpoint (with the drift when positive). Its drift rises
    with frequency, so the frequencies that keep both limits form one range around the
    test frequency; ``None`` when even no drift misses the design allowance.
    """
    _require_screen_inputs(target_h, tolerance_pct)
    return _allowance_range(_exact(target_h), _ExactModel(model), _exact(tolerance_pct) / 100)


def screen_part(
    target_h: float, window: CheckWindow, model: PartModel, tolerance_pct: float
) -> ScreenResult:
    """Screen one part (see the module docstring); a part exactly at a limit is within it."""
    _require_screen_inputs(target_h, tolerance_pct)
    if window.high_hz >= model.srf_hz:
        return ScreenResult(frozenset({LIMIT_DRIFT}), None, None, None, None, None)
    exact = _ExactModel(model)
    target = _exact(target_h)
    tolerance = _exact(tolerance_pct) / 100
    drift_low_end = exact.drift(window.low_hz)
    drift_high_end = exact.drift(window.high_hz)
    drift_min = min(Fraction(0), drift_low_end)
    drift_max = max(Fraction(0), drift_high_end)
    failed = set()
    if max(abs(drift_low_end), abs(drift_high_end)) > _DRIFT_LIMIT:
        failed.add(LIMIT_DRIFT)
    catalog = exact.catalog
    upper = catalog * (1 + tolerance) * (1 + drift_max)
    lower = catalog * (1 - tolerance) * (1 + drift_min)
    if upper > target * (1 + _DESIGN_LIMIT) or lower < target * (1 - _DESIGN_LIMIT):
        failed.add(LIMIT_ALLOWANCE)

    def pct(value: Fraction) -> float:
        return float(value / target * 100)

    try:
        budget = (
            pct(catalog - target),
            pct(tolerance * catalog),
            (
                pct(drift_min * catalog * (1 - tolerance)),
                pct(drift_max * catalog * (1 + tolerance)),
            ),
        )
        worst = (pct(lower - target), pct(upper - target))
    except OverflowError:
        # A target so far below the part that its error passes the largest float: the
        # part fails the allowance, and its percentages cannot be stated.
        assert LIMIT_ALLOWANCE in failed
        budget, worst = None, None
    return ScreenResult(
        failed_limits=frozenset(failed),
        drift_range=(float(drift_min), float(drift_max)),
        budget_pct=budget,
        worst_case_pct=worst,
        achieved_h=model.inductance_at(window.high_hz),
        allowance_range_hz=_allowance_range(target, exact, tolerance),
    )


def common_range(ranges: Iterable[tuple[float, float]]) -> tuple[float, float] | None:
    """The frequencies inside every range, or ``None`` when there is no range."""
    ranges = list(ranges)
    if not ranges:
        return None
    return max(low for low, _high in ranges), min(high for _low, high in ranges)


def _inward(value: float, rounding: str) -> float:
    """``value`` rounded to the four significant digits the output prints, toward the
    inside of a range (``ROUND_FLOOR`` for its top, ``ROUND_CEILING`` for its bottom)."""
    decimal = Decimal(repr(value))
    step = Decimal(1).scaleb(decimal.adjusted() - 3)
    return float(decimal.quantize(step, rounding=rounding))


def describe_range(frequency_range: tuple[float, float]) -> str:
    """``DC to 532.7 MHz`` or ``118 MHz to 1.2 GHz``, each end rounded inward.

    A part is within its allowances everywhere in the printed range, which never claims
    a frequency the exact range leaves out.
    """
    low, high = frequency_range
    start = "DC" if low == 0 else format_frequency(_inward(low, ROUND_CEILING))
    return f"{start} to {format_frequency(_inward(high, ROUND_FLOOR))}"
