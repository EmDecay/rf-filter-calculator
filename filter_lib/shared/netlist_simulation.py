"""Compatibility facade for circuit solving and response measurements."""

import math as math

from .circuit_model import Branch
from .nodal_solver import solve_s21, solve_transducer_power_gain
from .response_measurement import find_3db_edges, logspace, passband_ripple_db

__all__ = [
    "Branch",
    "solve_s21",
    "solve_transducer_power_gain",
    "find_3db_edges",
    "passband_ripple_db",
    "logspace",
    "math",
]
