"""Compatibility facade for named circuit models and topology builders."""

from __future__ import annotations

# Keep the historical non-private module attributes available to direct callers.
import math as math
from dataclasses import dataclass as dataclass
from dataclasses import replace as replace

from .circuit_builders import (
    build_bandpass_top_c_netlist,
    build_hp_netlist,
    build_lp_netlist,
    build_named_circuit,
)
from .circuit_model import Branch, CircuitElement, NamedCircuit

__all__ = [
    "Branch",
    "CircuitElement",
    "NamedCircuit",
    "build_named_circuit",
    "build_lp_netlist",
    "build_hp_netlist",
    "build_bandpass_top_c_netlist",
    "math",
    "dataclass",
    "replace",
]
