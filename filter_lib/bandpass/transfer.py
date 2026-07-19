"""Compatibility facade for ideal and circuit-simulated bandpass responses."""

import math as math
from typing import Any as Any

from ..shared.lp_hp_base_transfer_functions import (
    lowpass_bessel_response as lowpass_bessel_response,
)
from ..shared.transfer_functions import chebyshev_polynomial as chebyshev_polynomial
from ..shared.transfer_functions import magnitude_to_db as magnitude_to_db
from .design_constants import (
    BANDPASS_EDGE_CALIBRATION_FBW_MAX as BANDPASS_EDGE_CALIBRATION_FBW_MAX,
)
from .design_constants import (
    CHEBYSHEV_RIPPLE_ALLOWANCE_DB as CHEBYSHEV_RIPPLE_ALLOWANCE_DB,
)
from .design_constants import EDGE_ERROR_LIMIT_REL as EDGE_ERROR_LIMIT_REL
from .design_constants import PASSBAND_SHAPE_ERROR_LIMIT_DB as PASSBAND_SHAPE_ERROR_LIMIT_DB
from .design_constants import STOPBAND_SAMPLE_ERROR_LIMIT_DB as STOPBAND_SAMPLE_ERROR_LIMIT_DB
from .design_constants import THREE_DB_DOWN as THREE_DB_DOWN
from .ideal_response import _bandpass_deviation as _bandpass_deviation
from .ideal_response import chebyshev_3db_deviation as chebyshev_3db_deviation
from .ideal_response import frequency_from_deviation as frequency_from_deviation
from .ideal_response import magnitude_bessel as magnitude_bessel
from .ideal_response import magnitude_butterworth as magnitude_butterworth
from .ideal_response import magnitude_chebyshev as magnitude_chebyshev
from .ideal_response import magnitude_db as magnitude_db
from .passband_measurement import _deviation_grid as _deviation_grid
from .passband_measurement import measure_netlist_passband as measure_netlist_passband
from .response_sweep import _log_sweep_frequencies as _log_sweep_frequencies
from .response_sweep import frequency_response as frequency_response
from .response_sweep import frequency_sweep as frequency_sweep
from .response_sweep import generate_frequency_points as generate_frequency_points
from .response_sweep import netlist_frequency_sweep as netlist_frequency_sweep
from .response_verification import validate_netlist_shape as validate_netlist_shape
