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
