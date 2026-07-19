"""Orchestration for calculated, nominal, and bounded build analysis."""

from .build_response import build_frequency_grid, evaluation_ports, measure_circuit
from .build_types import BuildAnalysisResult, BuildConfig, resolve_build_config
from .circuit_builders import build_named_circuit
from .nominal_realization import realize_nominal_build
from .tolerance_screening import run_screening_cases, summarize_cases


def _analysis_limitations(
    nominal_limitations: tuple[str, ...],
    source: float,
    load: float,
    grid_censored_cases: int,
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
    return tuple(limitations)


def analyze_build(
    result: dict, category: str, config: BuildConfig | None = None
) -> BuildAnalysisResult:
    """Analyze calculated, nominal-build, corners, and seeded uniform cases."""
    active_config = resolve_build_config(config)
    exact_circuit = build_named_circuit(result, category)
    nominal = realize_nominal_build(result, category, active_config)
    freqs = build_frequency_grid(result, category, active_config.grid_points)
    source, load = evaluation_ports(result, category, active_config)
    calculated_measurement = measure_circuit(exact_circuit, result, category, freqs, source, load)
    nominal_measurement = measure_circuit(nominal.circuit, result, category, freqs, source, load)
    cases = run_screening_cases(
        nominal.circuit,
        result,
        category,
        freqs,
        source,
        load,
        active_config,
    )
    censored = sum(case.measurement.at_grid_edge for case in cases)
    return BuildAnalysisResult(
        category=category,
        config=active_config,
        source_resistance_ohm=source,
        load_resistance_ohm=load,
        gain_metric="transducer_power_gain_db",
        calculated=calculated_measurement,
        nominal_build=nominal_measurement,
        nominal_realization=nominal,
        cases=cases,
        metric_summaries=summarize_cases(cases, category),
        limitations=_analysis_limitations(nominal.limitations, source, load, censored),
    )
