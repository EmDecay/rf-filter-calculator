"""Compatibility facade for circuit solving and response measurements."""

import math as math

from . import branch_admittance as _branch_model
from . import nodal_solver as _nodal_solver
from .circuit_model import Branch
from .nodal_solver import solve_s21, solve_transducer_power_gain
from .response_measurement import find_3db_edges, logspace, passband_ripple_db

_is_finite_number = _branch_model.is_finite_number
_normalise_branch = _branch_model.normalise_branch
_branch_admittance = _branch_model.branch_admittance
_solve_complex_linear = _nodal_solver._solve_complex_linear
_stamp = _nodal_solver._stamp
_validate_and_normalise = _nodal_solver._validate_and_normalise
_solve_output_voltages = _nodal_solver._solve_output_voltages

__all__ = [
    "Branch",
    "solve_s21",
    "solve_transducer_power_gain",
    "find_3db_edges",
    "passband_ripple_db",
    "logspace",
    "math",
]
