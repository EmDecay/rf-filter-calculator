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

# The table prints this one only when extra random tolerance cases were run.
RANDOM_CASES_LIMITATION = (
    "The extra random tolerance cases repeat for the same seed; their spread is not a "
    "production-yield estimate."
)


def _cases(count: int) -> str:
    return f"{count} tolerance case is" if count == 1 else f"{count} tolerance cases are"


def _analysis_limitations(
    nominal_limitations: tuple[str, ...],
    category: str,
    source: float,
    load: float,
    grid_censored_cases: int,
    unresolved_cases: int,
    disconnected_cases: int,
) -> tuple[str, ...]:
    limitations = list(nominal_limitations)
    limitations.extend(
        (
            "The tolerance cases do not guarantee the true worst case.",
            RANDOM_CASES_LIMITATION,
            "The simulation leaves out layout and wiring, self-resonance (SRF), temperature "
            "drift, nonlinear effects, and power handling.",
        )
    )
    if source != load:
        limitations.append(
            "The parts are still designed for equal source and load impedance; the different "
            "source and load resistances apply only to this simulation."
        )
    is_bandpass = category == "bandpass"
    if grid_censored_cases:
        figures = "edge, center, and bandwidth figures" if is_bandpass else "cutoff figures"
        point = "a -3 dB edge" if is_bandpass else "the -3 dB point"
        limitations.append(
            f"{_cases(grid_censored_cases)} left out of the {figures} because "
            f"{point} fell outside the simulated frequency range; JSON output lists each case."
        )
    if unresolved_cases:
        limitations.append(
            f"{_cases(unresolved_cases)} left out of the figures because the measurement "
            "did not converge."
        )
    if disconnected_cases:
        their = "its" if disconnected_cases == 1 else "their"
        taken = (
            f"{their} edges and bandwidth come from the range around the peak nearest the center"
            if is_bandpass
            else f"{their} cutoff comes from the range that holds the peak"
        )
        limitations.append(
            f"In {disconnected_cases} tolerance case{'' if disconnected_cases == 1 else 's'} "
            f"the response is above -3 dB in separate frequency ranges; {taken}."
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
            category,
            source,
            load,
            censored,
            sum(not case.measurement.measurement_converged for case in cases),
            sum(len(case.measurement.threshold_regions) > 1 for case in cases),
        ),
    )
