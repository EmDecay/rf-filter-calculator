"""Shared result-dictionary fixtures for display and export formatting tests.

The component values are round synthetic numbers chosen to make formatted output easy to
read; they are not synthesized designs. Tests that check component values use the
calculators directly.
"""

import pytest


@pytest.fixture
def lowpass_result():
    """Lowpass Pi result shape (order 5: C-L-C-L-C) with synthetic values."""
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
    """Highpass T result shape (order 3: series C, shunt L, series C) with synthetic values."""
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
    """Lowpass T result shape (order 5: L-C-L-C-L) with synthetic values."""
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
    """Highpass Pi result shape (order 3: shunt L, series C, shunt L) with synthetic values."""
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
    """Three-resonator bandpass result shape (20 m band) with synthetic component values."""
    return {
        "filter_type": "butterworth",
        "f0": 14.175e6,
        "bw": 350e3,
        "z0": 50.0,
        "n_resonators": 3,
        "coupling": "top",
        "fbw": 350e3 / 14.175e6,
        # -3 dB edges of this band: f_high - f_low = bw and f_low * f_high = f0**2.
        "f_low": 14001080.205755044,
        "f_high": 14351080.205755046,
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
