"""Compatibility facade for realized-build machine and text output."""

from __future__ import annotations

from typing import Any

from .build_output_formatting import (
    _format_measurement,
    _format_metric_value,
    _format_substitution,
    format_build_analysis_block,
)
from .build_output_payloads import (
    _element_payload,
    _measurement_payload,
    _substitution_payload,
    _target_payload,
    build_analysis_fields,
)
from .build_types import BuildAnalysisResult, CircuitMeasurement, ComponentSubstitution
from .formatting import format_capacitance, format_frequency, format_inductance
from .strict_json import validate_finite_tree

__all__ = [
    "Any",
    "BuildAnalysisResult",
    "CircuitMeasurement",
    "ComponentSubstitution",
    "format_capacitance",
    "format_frequency",
    "format_inductance",
    "validate_finite_tree",
    "build_analysis_fields",
    "format_build_analysis_block",
    "_measurement_payload",
    "_substitution_payload",
    "_element_payload",
    "_target_payload",
    "_format_measurement",
    "_format_substitution",
    "_format_metric_value",
]
