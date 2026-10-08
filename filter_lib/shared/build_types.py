"""Immutable configuration and result contracts for realized-build analysis."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from .circuit_model import NamedCircuit
from .eseries import DEFAULT_MATCH_POLICY, E_SERIES, MatchPolicy
from .numeric import is_finite_real, positive_geometric_mean
from .physical_input_limits import require_component_q

# Shared with the web form, where resonator Q is entered in the band-pass tank fields.
RESONATOR_AND_COMPONENT_Q_MESSAGE = "Use either resonator Q or inductor/capacitor Q, not both"


def _is_finite_number(value: object) -> bool:
    return is_finite_real(value)


# The CLI refuses ``--seed`` without ``--sample-count`` ("--seed requires a positive
# --sample-count"); the wizard and web give this, in their labels, for a nonzero seed
# with no extra random cases (their seed field is pre-filled with the default 0).
SEED_NEEDS_SAMPLES_MESSAGE = (
    "Random seed requires a positive number of extra random tolerance cases"
)


def require_seed_with_samples(seed: int, sample_count: int) -> None:
    """Refuse a nonzero random seed when no extra random tolerance case uses it."""
    if seed and not sample_count:
        raise ValueError(SEED_NEEDS_SAMPLES_MESSAGE)


@dataclass(frozen=True)
class BuildConfig:
    """Inputs controlling nominal realization and bounded screening."""

    eseries: str = "E24"
    capacitor_tolerance_pct: float = 5.0
    inductor_tolerance_pct: float = 10.0
    inductor_q: float | None = None
    capacitor_q: float | None = None
    resonator_q: float | None = None
    source_resistance_ohm: float | None = None
    load_resistance_ohm: float | None = None
    reference_frequency_hz: float | None = None
    sample_count: int = 0
    seed: int = 0
    grid_points: int = 601
    use_toroid_candidates: bool = True
    match_policy: MatchPolicy = field(default_factory=lambda: DEFAULT_MATCH_POLICY)

    def __post_init__(self) -> None:
        # Messages use plain labels, not field names: the wizard and web show them as-is.
        if not isinstance(self.eseries, str) or self.eseries not in E_SERIES:
            raise ValueError("E-series must be E12, E24, or E96")
        for name, label in (
            ("capacitor_tolerance_pct", "Capacitor tolerance"),
            ("inductor_tolerance_pct", "Inductor tolerance"),
        ):
            value = getattr(self, name)
            if not _is_finite_number(value) or not 0 <= value < 100:
                raise ValueError(f"{label} must be at least 0% and less than 100%")
        for name, label in (
            ("inductor_q", "Inductor Q"),
            ("capacitor_q", "Capacitor Q"),
            ("resonator_q", "Resonator Q"),
        ):
            value = getattr(self, name)
            if value is not None:
                require_component_q(value, label)
        if self.resonator_q is not None and (
            self.inductor_q is not None or self.capacitor_q is not None
        ):
            raise ValueError(RESONATOR_AND_COMPONENT_Q_MESSAGE)
        for name, label in (
            ("source_resistance_ohm", "Simulation source resistance"),
            ("load_resistance_ohm", "Simulation load resistance"),
        ):
            value = getattr(self, name)
            if value is not None and (not _is_finite_number(value) or value <= 0):
                raise ValueError(f"{label} must be positive and finite")
        if (
            not isinstance(self.sample_count, int)
            or isinstance(self.sample_count, bool)
            or not 0 <= self.sample_count <= 10_000
        ):
            raise ValueError(
                "The number of extra random tolerance cases must be a whole number from 0 to 10000"
            )
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise ValueError("Random seed must be a whole number")
        if (
            not isinstance(self.grid_points, int)
            or isinstance(self.grid_points, bool)
            or not 51 <= self.grid_points <= 5001
        ):
            raise ValueError("Frequency points must be a whole number from 51 to 5001")
        if self.reference_frequency_hz is not None and (
            not _is_finite_number(self.reference_frequency_hz) or self.reference_frequency_hz <= 0
        ):
            raise ValueError(
                "The frequency at which the Q values apply must be positive and finite"
            )
        if not isinstance(self.use_toroid_candidates, bool):
            raise ValueError("use_toroid_candidates must be boolean")
        if not isinstance(self.match_policy, MatchPolicy):
            raise ValueError("match_policy must be a MatchPolicy")


def resolve_build_config(config: object) -> BuildConfig:
    """Return the supplied build config or the default, rejecting wrong types."""
    if config is None:
        return BuildConfig()
    if not isinstance(config, BuildConfig):
        raise ValueError("config must be a BuildConfig or None")
    return config


class BuildAnalysisCancelled(Exception):
    """Raised when the caller's cancellation check stops a realized-build analysis.

    Deliberately not a ``ValueError``: cancellation is not an input error, so a
    caller that reports rejected input never presents it as one.
    """


CancellationCheck = Callable[[], bool]


def raise_if_cancelled(should_cancel: CancellationCheck | None) -> None:
    """Raise ``BuildAnalysisCancelled`` when the optional check reports cancellation.

    Thread workers cannot be interrupted from outside, so long analyses poll this
    between bounded units of work. ``None`` means the caller never cancels.
    """
    if should_cancel is not None and should_cancel():
        raise BuildAnalysisCancelled("Build simulation was cancelled")


@dataclass(frozen=True)
class ComponentSubstitution:
    """Trace from one calculated logical element to its nominal parts."""

    logical_name: str
    kind: str
    calculated_value: float
    nominal_value: float
    physical_parts: tuple[float, ...]
    method: str
    status: str
    warnings: tuple[str, ...] = ()
    core_name: str | None = None
    turns: int | None = None
    # Screened winding wire for toroid substitutions; None for capacitors and
    # exact-value fallbacks.
    wire_awg: int | None = None
    wire_length_mm: float | None = None


@dataclass(frozen=True)
class NominalRealization:
    """Named nominal-build circuit plus auditable substitution metadata."""

    circuit: NamedCircuit
    substitutions: tuple[ComponentSubstitution, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class CircuitMeasurement:
    """Refined response summary on a finite simulation window."""

    f_low: float | None
    f_high: float | None
    worst_passband_db: float
    at_grid_edge: bool
    peak_transducer_gain_db: float = -math.inf
    reference_peak_frequency_hz: float | None = None
    reference_peak_gain_db: float | None = None
    threshold_db: float | None = None
    threshold_regions: tuple[tuple[float | None, float | None], ...] = ()
    selected_region_index: int | None = None
    center_in_selected_region: bool | None = None
    measurement_converged: bool = True
    response_evaluations: int = 0

    @property
    def f0(self) -> float | None:
        if self.f_low is None or self.f_high is None:
            return None
        return positive_geometric_mean(self.f_low, self.f_high)

    @property
    def bw(self) -> float | None:
        if self.f_low is None or self.f_high is None:
            return None
        return self.f_high - self.f_low


@dataclass(frozen=True)
class ScreeningCase:
    """One stable tolerance-screening case and its simulated result."""

    case_id: str
    component_factors: tuple[tuple[str, float], ...]
    measurement: CircuitMeasurement


@dataclass(frozen=True)
class MetricSummary:
    """Compact order-statistic envelope over the generated cases."""

    metric: str
    minimum: float
    p05: float
    p50: float
    p95: float
    maximum: float
    included_cases: int
    omitted_cases: int
    grid_censored_cases: int
    unresolved_cases: int = 0


@dataclass(frozen=True)
class BuildAnalysisResult:
    """Calculated, nominal, and bounded-screening response results."""

    category: str
    config: BuildConfig
    source_resistance_ohm: float
    load_resistance_ohm: float
    gain_metric: str
    calculated: CircuitMeasurement
    nominal_build: CircuitMeasurement
    nominal_realization: NominalRealization
    cases: tuple[ScreeningCase, ...]
    metric_summaries: tuple[MetricSummary, ...]
    limitations: tuple[str, ...]
