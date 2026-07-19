"""Compatibility facade for reproducible realized-build analysis.

Calculated values, nominal physical substitutions, and bounded screening cases
remain distinct. The model is not a measured assembly and makes no probability
or guaranteed-worst-case claim.
"""

from __future__ import annotations

# Preserve historical direct attributes while implementation lives in focused modules.
import math as math
import random as random
from dataclasses import dataclass as dataclass
from dataclasses import field as field
from dataclasses import replace as replace

from . import build_loss_models as _loss_models
from . import build_response as _build_response
from . import component_realization as _component_realization
from . import tolerance_screening as _tolerance_screening
from .build_analysis import analyze_build
from .build_loss_models import derive_series_resistance
from .build_types import (
    BuildAnalysisResult,
    BuildConfig,
    CircuitMeasurement,
    ComponentSubstitution,
    MetricSummary,
    NominalRealization,
    ScreeningCase,
)
from .circuit_builders import build_named_circuit
from .circuit_model import CircuitElement, NamedCircuit
from .eseries import DEFAULT_MATCH_POLICY, E_SERIES, MatchPolicy, match_component
from .nodal_solver import solve_transducer_power_gain
from .nominal_realization import realize_nominal_build
from .response_measurement import find_3db_edges
from .toroid_selection import find_core_candidates

_is_finite_number = _loss_models._is_finite_number
_design_frequency = _loss_models._design_frequency
_loss_reference_frequency = _loss_models._loss_reference_frequency
_loss_quality_factors = _loss_models._loss_quality_factors
_with_loss = _loss_models._with_loss
_realize_capacitor = _component_realization._realize_capacitor
_realize_inductor = _component_realization._realize_inductor
_frequency_grid = _build_response.build_frequency_grid
_ports = _build_response.evaluation_ports
_measure_circuit = _build_response.measure_circuit
_screened_elements = _tolerance_screening.screened_elements
_tolerance = _tolerance_screening.component_tolerance
_perturb_circuit = _tolerance_screening.perturb_circuit
_case_factors = _tolerance_screening.case_factors
_percentile = _tolerance_screening.percentile
_summaries = _tolerance_screening.summarize_cases

__all__ = [
    "BuildConfig",
    "ComponentSubstitution",
    "NominalRealization",
    "CircuitMeasurement",
    "ScreeningCase",
    "MetricSummary",
    "BuildAnalysisResult",
    "CircuitElement",
    "NamedCircuit",
    "DEFAULT_MATCH_POLICY",
    "E_SERIES",
    "MatchPolicy",
    "match_component",
    "build_named_circuit",
    "find_3db_edges",
    "find_core_candidates",
    "solve_transducer_power_gain",
    "derive_series_resistance",
    "realize_nominal_build",
    "analyze_build",
    "math",
    "random",
    "dataclass",
    "field",
    "replace",
]
