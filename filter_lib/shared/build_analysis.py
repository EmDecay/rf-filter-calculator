"""Orchestration for calculated, nominal, and bounded build analysis."""

from dataclasses import dataclass

from .build_response import (
    build_frequency_grid,
    evaluation_ports,
    highpass_passband_top,
    highpass_peak_range,
    measure_circuit,
)
from .build_types import (
    BuildAnalysisResult,
    BuildConfig,
    CancellationCheck,
    CircuitMeasurement,
    NominalRealization,
    raise_if_cancelled,
    resolve_build_config,
)
from .cancellation import require_cancellation_check
from .circuit_builders import build_named_circuit
from .nominal_realization import realize_nominal_build
from .resolved_parts import ResolvedParts
from .tolerance_screening import run_screening_cases, summarize_cases, tuned_cases

# With a chip inductor's self-capacitance fixed, a tolerance case moves only its inductance.
STRESS_CASE_LIMITATION = (
    "The tolerance cases move each chip inductor's inductance with its self-capacitance "
    "fixed, so a case can fall slightly outside the part's guaranteed range; treat those "
    "cases as stress cases of the model, not qualified values."
)
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
    has_pair_stray: bool = False,
    has_self_capacitance: bool = False,
    has_trimmers: bool = False,
) -> tuple[str, ...]:
    limitations = list(nominal_limitations)
    layout = (
        "layout and wiring (other than the assumed stray)"
        if has_pair_stray
        else ("layout and wiring")
    )
    # With a chip inductor's self-capacitance or a trimmer's series inductance modelled,
    # say what still is not.
    modelled = [
        name
        for name, present in (
            ("the chip inductors", has_self_capacitance),
            ("the trimmers (their assumed series inductance)", has_trimmers),
        )
        if present
    ]
    resonance = (
        "capacitor ESL and package parasitics, the self-resonance (SRF) of every part but "
        + " and ".join(modelled)
        if modelled
        else "self-resonance (SRF)"
    )
    if has_self_capacitance:
        limitations.append(STRESS_CASE_LIMITATION)
    limitations.extend(
        (
            "The tolerance cases do not guarantee the true worst case.",
            RANDOM_CASES_LIMITATION,
            f"The simulation leaves out {layout}, {resonance}, temperature "
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
    parts: ResolvedParts
    nominal: NominalRealization
    freqs: list[float]
    source: float
    load: float
    calculated: CircuitMeasurement
    qualified_range: tuple[float, float] | None
    passband_top: float | None
    peak_range: tuple[float, float] | None


def _prepare_analysis(
    result: dict,
    category: str,
    config: BuildConfig | None,
    parts: ResolvedParts,
    should_cancel: CancellationCheck | None = None,
) -> _PreparedAnalysis:
    """Resolve the config, realize the nominal build, and measure the calculated circuit."""
    active_config = resolve_build_config(config)
    exact_circuit = build_named_circuit(result, category)
    nominal = realize_nominal_build(result, category, active_config, parts=parts)
    freqs = build_frequency_grid(result, category, active_config.grid_points)
    source, load = evaluation_ports(result, category, active_config)
    qualified_range = parts.qualified_range_hz()
    passband_top = highpass_passband_top(result, category, freqs, qualified_range)
    peak_range = highpass_peak_range(result, category, freqs, qualified_range)
    raise_if_cancelled(should_cancel)
    calculated_measurement = measure_circuit(
        exact_circuit, result, category, freqs, source, load, passband_top, peak_range
    )
    return _PreparedAnalysis(
        active_config,
        parts,
        nominal,
        freqs,
        source,
        load,
        calculated_measurement,
        qualified_range,
        passband_top,
        peak_range,
    )


def measure_calculated_and_nominal(
    result: dict,
    category: str,
    config: BuildConfig | None = None,
    *,
    parts: ResolvedParts,
) -> CalculatedAndNominalMeasurement:
    """Measure only the calculated and nominal-build circuits.

    The nominal measurement equals ``analyze_build(...).nominal_build``; the
    deterministic corners and seeded samples are skipped.
    """
    prepared = _prepare_analysis(result, category, config, parts)
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
            prepared.passband_top,
            prepared.peak_range,
        ),
    )


def analyze_build(
    result: dict,
    category: str,
    config: BuildConfig | None = None,
    *,
    parts: ResolvedParts,
    should_cancel: CancellationCheck | None = None,
) -> BuildAnalysisResult:
    """Analyze calculated, nominal-build, corners, and seeded uniform cases.

    The build uses the parts ``design()`` resolved (``parts``), so it simulates the
    parts every output shows.

    A large sample count times a dense grid can run for minutes. An interactive
    caller passes ``should_cancel``, a zero-argument callable polled before the
    calculated measurement and before each screening case (the nominal build is the
    first case); when it returns true the analysis stops by raising
    ``BuildAnalysisCancelled``. ``None`` runs to completion.
    """
    require_cancellation_check(should_cancel)
    prepared = _prepare_analysis(result, category, config, parts, should_cancel)
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
        prepared.passband_top,
        prepared.peak_range,
        nominal.tuning,
        nominal.trimmer_settings,
    )
    censored = sum(case.measurement.at_grid_edge for case in cases)
    return BuildAnalysisResult(
        category=category,
        config=active_config,
        eseries=prepared.parts.eseries,
        match_policy=prepared.parts.match_policy,
        build_inductors=prepared.parts.build_inductors,
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
            any(item.stray_capacitance_f for item in nominal.substitutions),
            any(item.self_capacitance_f for item in nominal.substitutions),
            nominal.tuning is not None,
        ),
        qualified_range_hz=prepared.qualified_range,
        passband_top_hz=prepared.passband_top,
        peak_range_hz=prepared.peak_range,
        tuned_metric_summaries=summarize_cases(tuned_cases(cases), category),
    )
