"""Shared pytest fixtures and constants for RF filter calculator tests.

This module provides reusable test fixtures and constants that are commonly
used across multiple test modules. Pytest automatically discovers and makes
these fixtures available to all tests in the tests/ directory.
"""

import pytest

# Test tolerance constants
FLOAT_TOLERANCE = 1e-15  # For exact float comparisons
DB_THREE_POINT = -3.0  # Standard -3dB point for filter responses
FREQ_20M_CENTER = 14.175e6  # 20m amateur band center frequency


@pytest.fixture
def lowpass_result():
    """Sample lowpass Pi filter result for testing display/formatting.

    5th order Butterworth at 10 MHz, 50 Ohm.
    Pi topology: C-L-C-L-C (3 caps, 2 inductors)
    """
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "order": 5,
        "capacitors": [1e-10, 2e-10, 1e-10],  # 100pF, 200pF, 100pF
        "inductors": [1e-6, 1e-6],  # 1µH, 1µH
        "ripple": None,
        "topology": "pi",
    }


@pytest.fixture
def highpass_result():
    """Sample highpass T filter result for testing display/formatting.

    3rd order Chebyshev at 1 MHz, 75 Ohm, 0.5 dB ripple.
    T topology for HP: C-L-C (2 series caps, 1 shunt inductor)
    """
    return {
        "filter_type": "chebyshev",
        "freq_hz": 1e6,
        "impedance": 75.0,
        "order": 3,
        "capacitors": [5e-10, 5e-10],  # 500pF series caps
        "inductors": [2e-6],  # 2µH shunt inductor
        "ripple": 0.5,
        "topology": "t",
    }


@pytest.fixture
def lowpass_t_result():
    """Sample lowpass T topology result for testing.

    5th order Butterworth at 10 MHz, 50 Ohm.
    T topology: L-C-L-C-L (3 inductors, 2 caps)
    """
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "order": 5,
        "inductors": [1e-6, 1e-6, 1e-6],
        "capacitors": [1e-10, 2e-10],
        "ripple": None,
        "topology": "t",
    }


@pytest.fixture
def highpass_pi_result():
    """Sample highpass Pi topology result for testing.

    3rd order Butterworth at 1 MHz, 75 Ohm.
    Pi topology for HP: L-C-L (2 shunt inductors, 1 series cap)
    """
    return {
        "filter_type": "butterworth",
        "freq_hz": 1e6,
        "impedance": 75.0,
        "order": 3,
        "inductors": [2e-6, 2e-6],  # shunt inductors
        "capacitors": [5e-10],  # series capacitor
        "ripple": None,
        "topology": "pi",
    }


@pytest.fixture
def bandpass_result():
    """Sample bandpass filter result for testing.

    3-pole Butterworth at 14.175 MHz (20m band), 350 kHz bandwidth.
    """
    return {
        "filter_type": "butterworth",
        "f0": 14.175e6,
        "bw": 350e3,
        "z0": 50.0,
        "n_resonators": 3,
        "coupling": "top",
        "fbw": 350e3 / 14.175e6,
        "L_resonant": 1e-6,
        "c_tank": [100e-12, 100e-12, 100e-12],
        "c_coupling": [10e-12, 10e-12],
        "qe_in": 50.0,
        "qe_out": 50.0,
        "q_min": 100,
        "q_safety": 2.0,
        "ripple_db": None,
        "warnings": [],
    }
