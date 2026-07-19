"""Immutable configuration and result contracts for realized-build analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .circuit_model import NamedCircuit
from .eseries import DEFAULT_MATCH_POLICY, E_SERIES, MatchPolicy
from .numeric import is_finite_real, positive_geometric_mean


def _is_finite_number(value: object) -> bool:
    return is_finite_real(value)


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
        if not isinstance(self.eseries, str) or self.eseries not in E_SERIES:
            raise ValueError("eseries must be E12, E24, or E96")
        for name in ("capacitor_tolerance_pct", "inductor_tolerance_pct"):
            value = getattr(self, name)
            if not _is_finite_number(value) or not 0 <= value < 100:
                raise ValueError(f"{name} must be finite and in [0, 100)")
        for name in ("inductor_q", "capacitor_q", "resonator_q"):
            value = getattr(self, name)
            if value is not None and (not _is_finite_number(value) or value <= 0):
                raise ValueError(f"{name} must be positive and finite")
        if self.resonator_q is not None and (
            self.inductor_q is not None or self.capacitor_q is not None
        ):
            raise ValueError("resonator_q and component quality factors are mutually exclusive")
        for name in ("source_resistance_ohm", "load_resistance_ohm"):
            value = getattr(self, name)
            if value is not None and (not _is_finite_number(value) or value <= 0):
                raise ValueError(f"{name} must be positive and finite")
        if (
            not isinstance(self.sample_count, int)
            or isinstance(self.sample_count, bool)
            or not 0 <= self.sample_count <= 10_000
        ):
            raise ValueError("sample_count must be an integer in [0, 10000]")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        if (
            not isinstance(self.grid_points, int)
            or isinstance(self.grid_points, bool)
            or not 51 <= self.grid_points <= 5001
        ):
            raise ValueError("grid_points must be an integer in [51, 5001]")
        if self.reference_frequency_hz is not None and (
            not _is_finite_number(self.reference_frequency_hz) or self.reference_frequency_hz <= 0
        ):
            raise ValueError("reference_frequency_hz must be positive and finite")
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


@dataclass(frozen=True)
class NominalRealization:
    """Named nominal-build circuit plus auditable substitution metadata."""

    circuit: NamedCircuit
    substitutions: tuple[ComponentSubstitution, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class CircuitMeasurement:
    """Finite-grid response summary for one calculated or nominal circuit."""

    f_low: float | None
    f_high: float | None
    worst_passband_db: float
    at_grid_edge: bool
    peak_transducer_gain_db: float = -math.inf

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
