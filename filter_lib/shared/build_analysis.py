"""Orchestration for calculated, nominal, and bounded build analysis."""

from dataclasses import dataclass

from .build_response import build_frequency_grid, evaluation_ports, measure_circuit
from .build_types import (
    BuildAnalysisResult,
    BuildConfig,
    CancellationCheck,
    CircuitMeasurement,
    NominalRealization,
    raise_if_cancelled,
    resolve_build_config,
)
from .circuit_builders import build_named_circuit
from .nominal_realization import realize_nominal_build
from .tolerance_screening import run_screening_cases, summarize_cases


def _analysis_limitations(
    nominal_limitations: tuple[str, ...],
    source: float,
    load: float,
    grid_censored_cases: int,
    unresolved_cases: int,
    disconnected_cases: int,
) -> tuple[str, ...]:
    limitations = list(nominal_limitations)
    limitations.extend(
        (
            "Deterministic tolerance corners and bounded samples are not a guaranteed worst case.",
            "Seeded uniform samples are a repeatable screening set, not a probability or yield model.",
            "The circuit model omits layout, interconnect and package parasitics, SRF, "
            "temperature dependence, nonlinear voltage/current effects, and power behavior.",
        )
    )
    if source != load:
        limitations.append(
            "Separate source/load resistances evaluate transducer power gain; this does not "
            "imply unequal-termination synthesis."
        )
    if grid_censored_cases:
        limitations.append(
            f"Edge/cutoff summaries omit {grid_censored_cases} grid-boundary-censored "
            "screening cases; inspect their case records before extending the sweep."
        )
    if unresolved_cases:
        limitations.append(
            f"Metric summaries omit {unresolved_cases} unresolved screening cases; "
            "their response measurements did not converge within the refinement budget."
        )
    if disconnected_cases:
        limitations.append(
            f"{disconnected_cases} screening cases have disconnected half-power regions; "
            "bandwidth describes the selected local-peak region, not the outer envelope."
        )
    return tuple(limitations)


@dataclass(frozen=True)
class CalculatedAndNominalMeasurement:
    """Calculated and nominal-build measurements without tolerance screening."""

    config: BuildConfig
    source_resistance_ohm: float
    load_resistance_ohm: float
    calculated: CircuitMeasurement
    nominal_realization: NominalRealization
    nominal_build: CircuitMeasurement


@dataclass(frozen=True)
class _PreparedAnalysis:
    config: BuildConfig
    nominal: NominalRealization
    freqs: list[float]
    source: float
    load: float
    calculated: CircuitMeasurement


def _prepare_analysis(
    result: dict,
    category: str,
    config: BuildConfig | None,
    should_cancel: CancellationCheck | None = None,
) -> _PreparedAnalysis:
    """Resolve the config, realize the nominal build, and measure the calculated circuit."""
    active_config = resolve_build_config(config)
    exact_circuit = build_named_circuit(result, category)
    nominal = realize_nominal_build(result, category, active_config)
    freqs = build_frequency_grid(result, category, active_config.grid_points)
    source, load = evaluation_ports(result, category, active_config)
    raise_if_cancelled(should_cancel)
    calculated_measurement = measure_circuit(exact_circuit, result, category, freqs, source, load)
    return _PreparedAnalysis(active_config, nominal, freqs, source, load, calculated_measurement)


def measure_calculated_and_nominal(
    result: dict, category: str, config: BuildConfig | None = None
) -> CalculatedAndNominalMeasurement:
    """Measure only the calculated and nominal-build circuits.

    The nominal measurement equals ``analyze_build(...).nominal_build``; the
    deterministic corners and seeded samples are skipped.
    """
    prepared = _prepare_analysis(result, category, config)
    return CalculatedAndNominalMeasurement(
        config=prepared.config,
        source_resistance_ohm=prepared.source,
        load_resistance_ohm=prepared.load,
        calculated=prepared.calculated,
        nominal_realization=prepared.nominal,
        nominal_build=measure_circuit(
            prepared.nominal.circuit,
            result,
            category,
            prepared.freqs,
            prepared.source,
            prepared.load,
        ),
    )


def analyze_build(
    result: dict,
    category: str,
    config: BuildConfig | None = None,
    *,
    should_cancel: CancellationCheck | None = None,
) -> BuildAnalysisResult:
    """Analyze calculated, nominal-build, corners, and seeded uniform cases.

    A large sample count times a dense grid can run for minutes. An interactive
    caller passes ``should_cancel``, a zero-argument callable polled before the
    calculated measurement and before each screening case (the nominal build is the
    first case); when it returns true the analysis stops by raising
    ``BuildAnalysisCancelled``. ``None`` runs to completion.
    """
    if should_cancel is not None and not callable(should_cancel):
        raise ValueError("should_cancel must be a zero-argument callable or None")
    prepared = _prepare_analysis(result, category, config, should_cancel)
    active_config, nominal = prepared.config, prepared.nominal
    source, load = prepared.source, prepared.load
    cases = run_screening_cases(
        nominal.circuit,
        result,
        category,
        prepared.freqs,
        source,
        load,
        active_config,
        should_cancel,
    )
    censored = sum(case.measurement.at_grid_edge for case in cases)
    return BuildAnalysisResult(
        category=category,
        config=active_config,
        source_resistance_ohm=source,
        load_resistance_ohm=load,
        gain_metric="transducer_power_gain_db",
        calculated=prepared.calculated,
        nominal_build=cases[0].measurement,
        nominal_realization=nominal,
        cases=cases,
        metric_summaries=summarize_cases(cases, category),
        limitations=_analysis_limitations(
            nominal.limitations,
            source,
            load,
            censored,
            sum(not case.measurement.measurement_converged for case in cases),
            sum(len(case.measurement.threshold_regions) > 1 for case in cases),
        ),
    )
