"""Compatibility facade for bandpass synthesis and component calculations.

Implementation lives in focused modules so callers can keep importing the
historical names from ``filter_lib.bandpass.calculations``.
"""

import math as math
from typing import Any as Any

from .bandpass_design import calculate_bandpass_filter as calculate_bandpass_filter
from .coupling_math import (
    calculate_coupling_capacitors as calculate_coupling_capacitors,
)
from .coupling_math import (
    calculate_coupling_coefficients as calculate_coupling_coefficients,
)
from .coupling_math import (
    calculate_end_coupling as calculate_end_coupling,
)
from .coupling_math import (
    calculate_external_q as calculate_external_q,
)
from .coupling_math import (
    calculate_tank_capacitors as calculate_tank_capacitors,
)
from .design_constants import (
    BANDPASS_EDGE_CALIBRATION_FBW_MAX as BANDPASS_EDGE_CALIBRATION_FBW_MAX,
)
from .design_constants import (
    BANDPASS_LUMPED_MODEL_CAUTION_FBW as BANDPASS_LUMPED_MODEL_CAUTION_FBW,
)
from .design_constants import CALIBRATION_MAX_ITERATIONS as _DESIGN_CALIBRATION_MAX_ITERATIONS
from .design_constants import CALIBRATION_POINTS as _DESIGN_CALIBRATION_POINTS
from .design_constants import CALIBRATION_TOLERANCE as _DESIGN_CALIBRATION_TOLERANCE
from .design_constants import VALIDATION_POINTS as _DESIGN_VALIDATION_POINTS
from .g_values import get_g_values as get_g_values
from .input_validation import _get_fbw_warnings as _get_fbw_warnings
from .input_validation import _validate_inputs as _validate_inputs
from .resonator_math import STANDARD_QU_VALUES as STANDARD_QU_VALUES
from .resonator_math import _resolve_resonator_components as _resolve_resonator_components
from .resonator_math import calculate_min_q as calculate_min_q
from .resonator_math import calculate_resonator_components as calculate_resonator_components
from .resonator_math import combine_resonator_q as combine_resonator_q
from .resonator_math import compute_bandpass_3db_edges as compute_bandpass_3db_edges
from .resonator_math import estimate_insertion_loss as estimate_insertion_loss
from .top_c_calibration import _calibrate_top_c as _calibrate_top_c
from .top_c_synthesis import BandpassResult as BandpassResult
from .top_c_synthesis import _synthesize_top_c_raw as _synthesize_top_c_raw

_CALIBRATION_POINTS = _DESIGN_CALIBRATION_POINTS
_VALIDATION_POINTS = _DESIGN_VALIDATION_POINTS
_CALIBRATION_TOLERANCE = _DESIGN_CALIBRATION_TOLERANCE
_CALIBRATION_MAX_ITERATIONS = _DESIGN_CALIBRATION_MAX_ITERATIONS
