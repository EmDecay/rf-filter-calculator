"""Finite-Q loss assumptions used by nominal build realization."""

from __future__ import annotations

import math
from dataclasses import replace

from .build_types import BuildConfig
from .circuit_model import CircuitElement
from .numeric import is_finite_real


def _is_finite_number(value: object) -> bool:
    return is_finite_real(value)


def derive_series_resistance(
    kind: str, value: float, quality_factor: float, reference_frequency_hz: float
) -> float:
    """Convert Q at one reference frequency to a constant series resistance."""
    if not isinstance(kind, str) or kind not in {"C", "L"}:
        raise ValueError("kind must be 'C' or 'L'")
    for name, candidate in (
        ("value", value),
        ("quality_factor", quality_factor),
        ("reference_frequency_hz", reference_frequency_hz),
    ):
        if not _is_finite_number(candidate) or candidate <= 0:
            raise ValueError(f"{name} must be positive and finite")
    log_reactance = math.log(2.0 * math.pi) + math.log(reference_frequency_hz) + math.log(value)
    log_resistance = (
        log_reactance - math.log(quality_factor)
        if kind == "L"
        else -log_reactance - math.log(quality_factor)
    )
    try:
        resistance = math.exp(log_resistance)
    except OverflowError as error:
        raise ValueError("derived series resistance is outside the finite numeric range") from error
    if not math.isfinite(resistance) or resistance <= 0:
        raise ValueError("derived series resistance is outside the finite numeric range")
    return resistance


def _design_frequency(result: dict, category: str) -> float:
    key = "f0" if category == "bandpass" else "freq_hz"
    frequency = result.get(key)
    if not _is_finite_number(frequency) or frequency <= 0:
        raise ValueError(f"{key} must be positive and finite")
    return frequency


def _loss_reference_frequency(result: dict, category: str, config: BuildConfig) -> float:
    if config.reference_frequency_hz is not None:
        return config.reference_frequency_hz
    if category == "bandpass":
        q_model = result.get("q_model")
        if isinstance(q_model, dict) and q_model.get("reference_frequency_hz") is not None:
            reference = q_model["reference_frequency_hz"]
            if not _is_finite_number(reference) or reference <= 0:
                raise ValueError("q_model reference_frequency_hz must be positive and finite")
            return reference
    return _design_frequency(result, category)


def _loss_quality_factors(
    result: dict, category: str, config: BuildConfig
) -> tuple[float | None, float | None, bool, tuple[str, ...]]:
    limitations: list[str] = []
    if config.resonator_q is not None:
        if category != "bandpass":
            raise ValueError("resonator_q is supported only for bandpass build analysis")
        limitations.append(
            "The supplied complete resonator Q is represented by one equivalent "
            "inductor series-loss channel per resonator."
        )
        return config.resonator_q, None, False, tuple(limitations)
    if config.inductor_q is not None or config.capacitor_q is not None:
        return config.inductor_q, config.capacitor_q, False, ()
    if category != "bandpass":
        return None, None, False, ()

    q_model = result.get("q_model") or {}
    ql = q_model.get("inductor_ql")
    qc = q_model.get("capacitor_qc")
    if ql is not None or qc is not None:
        if qc is not None:
            limitations.append(
                "The synthesis capacitor Q describes resonator tank capacitors and is "
                "applied only to CT elements; coupling and end capacitors remain lossless."
            )
        return ql, qc, True, tuple(limitations)
    resonator_qu = q_model.get("resonator_qu")
    if resonator_qu is not None:
        limitations.append(
            "The complete resonator Q from synthesis is represented by one "
            "equivalent inductor series-loss channel per resonator."
        )
        return resonator_qu, None, False, tuple(limitations)
    return None, None, False, ()


def _with_loss(
    element: CircuitElement,
    quality_factor: float | None,
    reference_frequency_hz: float,
) -> CircuitElement:
    if quality_factor is None or element.kind not in {"C", "L"}:
        return element
    return replace(
        element,
        quality_factor=quality_factor,
        loss_reference_frequency_hz=reference_frequency_hz,
        series_resistance_ohm=derive_series_resistance(
            element.kind, element.value, quality_factor, reference_frequency_hz
        ),
    )
