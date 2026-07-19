"""Deterministic corners, seeded samples, and summaries for build screening."""

import math
import random
from collections.abc import Callable
from dataclasses import replace

from .build_loss_models import derive_series_resistance
from .build_response import measure_circuit
from .build_types import BuildConfig, CircuitMeasurement, MetricSummary, ScreeningCase
from .circuit_model import CircuitElement, NamedCircuit

MetricExtractor = Callable[[CircuitMeasurement], float | None]


def screened_elements(circuit: NamedCircuit) -> tuple[tuple[str, str], ...]:
    """Return physical parts so screening cases retain stable identities."""
    return tuple((element.name, element.kind) for element in circuit.elements)


def component_tolerance(kind: str, config: BuildConfig) -> float:
    """Return the configured fractional tolerance for one component kind."""
    percentage = config.capacitor_tolerance_pct if kind == "C" else config.inductor_tolerance_pct
    return percentage / 100.0


def perturb_circuit(circuit: NamedCircuit, factors: tuple[tuple[str, float], ...]) -> NamedCircuit:
    """Apply one factor per physical part and keep its loss model coherent."""
    factor_by_name = dict(factors)
    perturbed: list[CircuitElement] = []
    for element in circuit.elements:
        value = element.value * factor_by_name[element.name]
        series_resistance = element.series_resistance_ohm
        if element.quality_factor is not None:
            series_resistance = derive_series_resistance(
                element.kind,
                value,
                element.quality_factor,
                element.loss_reference_frequency_hz,
            )
        perturbed.append(replace(element, value=value, series_resistance_ohm=series_resistance))
    return replace(circuit, elements=tuple(perturbed))


def case_factors(
    physical_elements: tuple[tuple[str, str], ...], config: BuildConfig
) -> list[tuple[str, tuple[tuple[str, float], ...]]]:
    """Return deterministic cases followed by stable seeded uniform samples."""
    nominal = tuple((name, 1.0) for name, _kind in physical_elements)
    cases: list[tuple[str, tuple[tuple[str, float], ...]]] = [("nominal", nominal)]
    for direction, sign in (("low", -1.0), ("high", 1.0)):
        cases.append(
            (
                f"coherent:{direction}",
                tuple(
                    (name, 1.0 + sign * component_tolerance(kind, config))
                    for name, kind in physical_elements
                ),
            )
        )
    for selected_name, selected_kind in physical_elements:
        tolerance = component_tolerance(selected_kind, config)
        for direction, sign in (("low", -1.0), ("high", 1.0)):
            cases.append(
                (
                    f"one:{selected_name}:{direction}",
                    tuple(
                        (name, 1.0 + sign * tolerance if name == selected_name else 1.0)
                        for name, _kind in physical_elements
                    ),
                )
            )
    generator = random.Random(config.seed)
    for sample_index in range(1, config.sample_count + 1):
        cases.append(
            (
                f"sample:{sample_index:04d}",
                tuple(
                    (
                        name,
                        generator.uniform(
                            1.0 - component_tolerance(kind, config),
                            1.0 + component_tolerance(kind, config),
                        ),
                    )
                    for name, kind in physical_elements
                ),
            )
        )
    return cases


def percentile(values: list[float], quantile: float) -> float:
    """Return a linearly interpolated order statistic."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = quantile * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _metric_extractors(category: str) -> tuple[tuple[str, MetricExtractor, bool], ...]:
    common = (
        ("peak_transducer_gain_db", lambda item: item.peak_transducer_gain_db, False),
        ("worst_passband_db", lambda item: item.worst_passband_db, False),
    )
    if category == "lowpass":
        return common + (("cutoff_hz", lambda item: item.f_high, True),)
    if category == "highpass":
        return common + (("cutoff_hz", lambda item: item.f_low, True),)
    return common + (
        ("f_low_hz", lambda item: item.f_low, True),
        ("f_high_hz", lambda item: item.f_high, True),
        ("f0_hz", lambda item: item.f0, True),
        ("bw_hz", lambda item: item.bw, True),
    )


def summarize_cases(cases: tuple[ScreeningCase, ...], category: str) -> tuple[MetricSummary, ...]:
    """Summarize finite, uncensored values while recording all omissions."""
    summaries: list[MetricSummary] = []
    for metric, extractor, exclude_grid_censored in _metric_extractors(category):
        grid_censored = sum(
            case.measurement.at_grid_edge for case in cases if exclude_grid_censored
        )
        values = [
            value
            for case in cases
            if not (exclude_grid_censored and case.measurement.at_grid_edge)
            if (value := extractor(case.measurement)) is not None and math.isfinite(value)
        ]
        if not values:
            continue
        summaries.append(
            MetricSummary(
                metric,
                min(values),
                percentile(values, 0.05),
                percentile(values, 0.50),
                percentile(values, 0.95),
                max(values),
                len(values),
                len(cases) - len(values),
                grid_censored,
            )
        )
    return tuple(summaries)


def run_screening_cases(
    circuit: NamedCircuit,
    result: dict,
    category: str,
    freqs: list[float],
    source: float,
    load: float,
    config: BuildConfig,
) -> tuple[ScreeningCase, ...]:
    """Perturb and measure every configured case in deterministic order."""
    return tuple(
        ScreeningCase(
            case_id,
            factors,
            measure_circuit(
                perturb_circuit(circuit, factors),
                result,
                category,
                freqs,
                source,
                load,
            ),
        )
        for case_id, factors in case_factors(screened_elements(circuit), config)
    )
