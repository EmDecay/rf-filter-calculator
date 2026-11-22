"""Immutable configuration and result contracts for realized-build analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .cancellation import CancellationCheck, DesignCancelled
from .circuit_model import NamedCircuit
from .eseries import MatchPolicy
from .numeric import is_finite_real, positive_geometric_mean
from .physical_input_limits import require_component_q

# Shared with the web form, where resonator Q is entered in the band-pass tank fields.
RESONATOR_AND_COMPONENT_Q_MESSAGE = (
    "Use either resonator Q or the build simulation's inductor and capacitor Q, not both"
)


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


# The inductor tolerance of a toroid winding or a calculated value when none is entered.
DEFAULT_INDUCTOR_TOLERANCE_PCT = 10.0


@dataclass(frozen=True)
class BuildConfig:
    """Inputs controlling nominal realization and bounded screening.

    The standard capacitor series and match policy are design inputs, not build
    settings: ``design()`` resolves them once and passes them with this config.
    """

    # None: each chip inductor (or other part with a checked SRF) at its own guaranteed
    # tolerance; the toroid windings and calculated values use
    # ``DEFAULT_INDUCTOR_TOLERANCE_PCT``. A value applies to every inductor. Which part
    # each inductor is built as is a design input (``DesignRequest.build_inductors``).
    inductor_tolerance_pct: float | None = None
    inductor_q: float | None = None
    capacitor_q: float | None = None
    resonator_q: float | None = None
    source_resistance_ohm: float | None = None
    load_resistance_ohm: float | None = None
    reference_frequency_hz: float | None = None
    sample_count: int = 0
    seed: int = 0
    grid_points: int = 601

    def __post_init__(self) -> None:
        # Messages use plain labels, not field names: the wizard and web show them as-is.
        value = self.inductor_tolerance_pct
        if value is not None and (not is_finite_real(value) or not 0 <= value < 100):
            raise ValueError("Inductor tolerance must be at least 0% and less than 100%")
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
            if value is not None and (not is_finite_real(value) or value <= 0):
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
            not is_finite_real(self.reference_frequency_hz) or self.reference_frequency_hz <= 0
        ):
            raise ValueError(
                "The frequency at which the Q values apply must be positive and finite"
            )


def resolve_build_config(config: object) -> BuildConfig:
    """Return the supplied build config or the default, rejecting wrong types."""
    if config is None:
        return BuildConfig()
    if not isinstance(config, BuildConfig):
        raise ValueError("config must be a BuildConfig or None")
    return config


class BuildAnalysisCancelled(DesignCancelled):
    """Raised when the caller's cancellation check stops a realized-build analysis.

    A ``DesignCancelled``, so a caller that stops any part of ``design()`` catches one
    exception; never a ``ValueError`` (cancellation is not an input error).
    """


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
    # The suggestion an inductor was built as: its kind (``toroid``, ``air-coil``,
    # ``chip``) and part; None for capacitors and calculated values.
    inductor_kind: str | None = None
    part_name: str | None = None
    core_name: str | None = None
    turns: int | None = None
    # Screened winding wire for toroid substitutions; None for capacitors and
    # exact-value fallbacks.
    wire_awg: int | None = None
    wire_length_mm: float | None = None
    # The assumed stray across a parallel pair, simulated as a fixed capacitor across the
    # same terminals; None when there is no pair or the stray is zero.
    stray_capacitance_f: float | None = None
    # An inductor's self-capacitance from its minimum SRF, simulated as a fixed capacitor
    # across it (the inductance element is then the part model's L0); None otherwise.
    self_capacitance_f: float | None = None
    # The ± percent an inductor's tolerance cases use, and whether it is the part's own
    # guaranteed tolerance (no inductor tolerance entered); None for capacitors.
    tolerance_pct: float | None = None
    own_tolerance: bool = False


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
    # Where ``peak_transducer_gain_db`` was found.
    peak_frequency_hz: float | None = None

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

    def ladder_cutoff(self, category: str) -> float | None:
        """Return the -3 dB cutoff of a ladder: the upper edge for lowpass, else the lower."""
        return self.f_high if category == "lowpass" else self.f_low

    def outside_range(
        self, category: str, qualified_range: tuple[float, float] | None
    ) -> tuple[str, ...]:
        """The reported figures (JSON keys) that rest on frequencies outside the range.

        Every reported frequency is checked: the -3 dB edges or cutoff, the reference peak,
        the frequency of the peak gain, and the ends of any other half-power region. A band-pass
        center and bandwidth come from the edges, so they are outside when an edge is.
        None without a range.
        """
        if qualified_range is None:
            return ()
        low, high = qualified_range

        def outside(value: float | None) -> bool:
            return value is not None and not low <= value <= high

        edges = (
            (("f_low_hz", self.f_low), ("f_high_hz", self.f_high))
            if category == "bandpass"
            else (("cutoff_hz", self.ladder_cutoff(category)),)
        )
        keys = [key for key, value in edges if outside(value)]
        if category == "bandpass" and keys:
            keys += ["f0_hz", "bandwidth_hz"]
        if outside(self.reference_peak_frequency_hz):
            keys.append("reference_peak_frequency_hz")
        if outside(self.peak_frequency_hz):
            keys.append("peak_frequency_hz")
        # The selected region's ends are the edges above; any other region is checked here.
        others = (
            region
            for index, region in enumerate(self.threshold_regions)
            if index != self.selected_region_index
        )
        if any(outside(end) for region in others for end in region):
            keys.append("half_power_regions")
        return tuple(keys)


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
    eseries: str
    match_policy: MatchPolicy
    # What the build used for each inductor (``--build-inductors``).
    build_inductors: str
    source_resistance_ohm: float
    load_resistance_ohm: float
    gain_metric: str
    calculated: CircuitMeasurement
    nominal_build: CircuitMeasurement
    nominal_realization: NominalRealization
    cases: tuple[ScreeningCase, ...]
    metric_summaries: tuple[MetricSummary, ...]
    limitations: tuple[str, ...]
    # The frequencies at which every built part with a checked SRF (a chip inductor) is
    # within its allowances; results outside it are predicted with the parasitic model,
    # not qualified. None when no built part has its SRF checked.
    qualified_range_hz: tuple[float, float] | None = None
    # A high-pass build's passband figures stop here (the qualified range's top, never
    # below twice the cutoff); None when they use the whole sweep.
    passband_top_hz: float | None = None
    # A high-pass build takes its peak, and so its half-power threshold, only here (the
    # qualified range within the sweep); None when the whole sweep is used.
    peak_range_hz: tuple[float, float] | None = None
