"""Tests for transfer function modules (lowpass, highpass, bandpass, shared)."""
import math
import json
import pytest

from filter_lib.shared.transfer_functions import (
    generate_frequency_points, chebyshev_polynomial,
    magnitude_to_db, export_response_json, export_response_csv,
)
from filter_lib.lowpass import transfer as lp_transfer
from filter_lib.highpass import transfer as hp_transfer
from filter_lib.bandpass import transfer as bp_transfer


# --- Shared transfer_functions ---

class TestSharedTransferFunctions:
    """Tests for shared transfer function utilities."""

    def test_generate_frequency_points_count(self):
        points = generate_frequency_points(10e6, num_points=51)
        assert len(points) == 51

    def test_generate_frequency_points_range(self):
        points = generate_frequency_points(10e6)
        assert points[0] == pytest.approx(1e6, rel=0.01)
        assert points[-1] == pytest.approx(100e6, rel=0.01)

    def test_generate_frequency_points_invalid(self):
        with pytest.raises(ValueError, match="positive"):
            generate_frequency_points(-1)

    def test_chebyshev_polynomial_base_cases(self):
        assert chebyshev_polynomial(0, 0.5) == 1.0
        assert chebyshev_polynomial(1, 0.5) == 0.5

    def test_chebyshev_polynomial_recurrence(self):
        # T2(x) = 2x^2 - 1
        assert chebyshev_polynomial(2, 0.5) == pytest.approx(2 * 0.25 - 1)

    def test_magnitude_to_db_unity(self):
        assert magnitude_to_db(1.0) == pytest.approx(0.0)

    def test_magnitude_to_db_zero(self):
        assert magnitude_to_db(0.0) == -120.0

    def test_magnitude_to_db_half(self):
        assert magnitude_to_db(0.5) == pytest.approx(20 * math.log10(0.5))

    def test_export_response_json(self):
        info = {'filter_type': 'butterworth', 'freq_hz': 10e6, 'order': 3}
        result = export_response_json([1e6, 10e6], [-0.1, -3.0], info)
        data = json.loads(result)
        assert data['filter_type'] == 'butterworth'
        assert len(data['data']) == 2

    def test_export_response_csv(self):
        result = export_response_csv([1e6, 10e6], [-0.1, -3.0])
        lines = result.split('\n')
        assert lines[0] == 'frequency_hz,magnitude_db'
        assert len(lines) == 3


# --- Lowpass transfer ---

class TestLowpassTransfer:
    """Tests for lowpass transfer functions."""

    def test_butterworth_dc_gain(self):
        assert lp_transfer.butterworth_response(0, 10e6, 5) == pytest.approx(1.0)

    def test_butterworth_at_cutoff(self):
        mag = lp_transfer.butterworth_response(10e6, 10e6, 3)
        db = magnitude_to_db(mag)
        assert db == pytest.approx(-3.0, abs=0.1)

    def test_butterworth_attenuation(self):
        mag = lp_transfer.butterworth_response(100e6, 10e6, 5)
        assert mag < 0.01

    def test_chebyshev_response(self):
        mag = lp_transfer.chebyshev_response(5e6, 10e6, 4, 0.5)
        assert 0 < mag <= 1.0

    def test_bessel_response(self):
        mag = lp_transfer.bessel_response(5e6, 10e6, 3)
        assert 0 < mag <= 1.0

    def test_bessel_invalid_order(self):
        with pytest.raises(ValueError, match="Order must be between 2 and 9"):
            lp_transfer.bessel_response(5e6, 10e6, 1)

    def test_bessel_valid_orders(self):
        for order in range(2, 10):
            mag = lp_transfer.bessel_response(5e6, 10e6, order)
            assert 0 <= mag <= 1.0

    def test_frequency_response_butterworth(self):
        freqs = [1e6, 10e6, 100e6]
        resp = lp_transfer.frequency_response('butterworth', freqs, 10e6, 3)
        assert len(resp) == 3
        assert resp[0] > resp[2]  # LPF: low freq better than high

    def test_frequency_response_chebyshev(self):
        resp = lp_transfer.frequency_response('ch', [1e6, 10e6], 10e6, 4, 1.0)
        assert len(resp) == 2

    def test_frequency_response_bessel(self):
        resp = lp_transfer.frequency_response('bessel', [1e6, 10e6], 10e6, 5)
        assert len(resp) == 2

    def test_frequency_response_invalid_type(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            lp_transfer.frequency_response('invalid', [1e6], 10e6, 3)


# --- Highpass transfer ---

class TestHighpassTransfer:
    """Tests for highpass transfer functions."""

    def test_butterworth_dc_blocking(self):
        assert hp_transfer.butterworth_response(0, 10e6, 3) == 0.0

    def test_butterworth_at_cutoff(self):
        mag = hp_transfer.butterworth_response(10e6, 10e6, 3)
        db = magnitude_to_db(mag)
        assert db == pytest.approx(-3.0, abs=0.1)

    def test_butterworth_high_freq_passthrough(self):
        mag = hp_transfer.butterworth_response(1e9, 10e6, 3)
        assert mag > 0.99

    def test_chebyshev_dc_blocking(self):
        assert hp_transfer.chebyshev_response(0, 10e6, 3, 0.5) == 0.0

    def test_chebyshev_passband(self):
        mag = hp_transfer.chebyshev_response(100e6, 10e6, 4, 0.5)
        assert mag > 0.9

    def test_bessel_dc_blocking(self):
        assert hp_transfer.bessel_response(0, 10e6, 3) == 0.0

    def test_bessel_invalid_order(self):
        with pytest.raises(ValueError, match="Order must be between 2 and 9"):
            hp_transfer.bessel_response(10e6, 10e6, 1)

    def test_bessel_valid_orders(self):
        for order in range(2, 10):
            mag = hp_transfer.bessel_response(100e6, 10e6, order)
            assert 0 <= mag <= 1.0

    def test_frequency_response_rising(self):
        freqs = [1e6, 10e6, 100e6]
        resp = hp_transfer.frequency_response('bw', freqs, 10e6, 3)
        assert len(resp) == 3
        assert resp[2] > resp[0]  # HPF: high freq better than low

    def test_frequency_response_invalid_type(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            hp_transfer.frequency_response('unknown', [1e6], 10e6, 3)


# --- Bandpass transfer ---

class TestBandpassTransfer:
    """Tests for bandpass transfer functions."""

    def test_bandpass_deviation_at_center(self):
        assert bp_transfer._bandpass_deviation(14e6, 14e6, 1e6) == pytest.approx(0.0)

    def test_bandpass_deviation_invalid_freq(self):
        with pytest.raises(ValueError, match="must be positive"):
            bp_transfer._bandpass_deviation(-1, 14e6, 1e6)

    def test_bandpass_deviation_invalid_bw(self):
        with pytest.raises(ValueError, match="must be positive"):
            bp_transfer._bandpass_deviation(14e6, 14e6, -1)

    def test_magnitude_butterworth_at_center(self):
        assert bp_transfer.magnitude_butterworth(14e6, 14e6, 1e6, 3) == pytest.approx(1.0)

    def test_magnitude_butterworth_off_center(self):
        mag = bp_transfer.magnitude_butterworth(20e6, 14e6, 1e6, 3)
        assert mag < 0.5

    def test_magnitude_chebyshev_at_center(self):
        assert bp_transfer.magnitude_chebyshev(14e6, 14e6, 1e6, 3, 0.5) == pytest.approx(1.0)

    def test_magnitude_bessel_uses_butterworth(self):
        mag_bes = bp_transfer.magnitude_bessel(10e6, 14e6, 1e6, 3)
        mag_bw = bp_transfer.magnitude_butterworth(10e6, 14e6, 1e6, 3)
        assert mag_bes == mag_bw

    def test_magnitude_db_at_center(self):
        assert bp_transfer.magnitude_db(14e6, 14e6, 1e6, 3, 'butterworth') == pytest.approx(0.0)

    def test_magnitude_db_chebyshev(self):
        assert bp_transfer.magnitude_db(14e6, 14e6, 1e6, 3, 'chebyshev', 0.5) == pytest.approx(0.0)

    def test_magnitude_db_bessel(self):
        assert bp_transfer.magnitude_db(14e6, 14e6, 1e6, 3, 'bessel') == pytest.approx(0.0)

    def test_magnitude_db_invalid_type(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            bp_transfer.magnitude_db(14e6, 14e6, 1e6, 3, 'invalid')

    def test_magnitude_db_floor(self):
        db = bp_transfer.magnitude_db(100e6, 14e6, 1e6, 5, 'butterworth')
        assert db >= -100.0

    def test_frequency_sweep_defaults(self):
        result = bp_transfer.frequency_sweep(14e6, 1e6, 3, 'butterworth')
        assert len(result) == 61
        assert all(isinstance(r, tuple) and len(r) == 2 for r in result)

    def test_frequency_sweep_custom_points(self):
        result = bp_transfer.frequency_sweep(14e6, 1e6, 3, 'butterworth', points=31)
        assert len(result) == 31

    def test_generate_frequency_points_bandpass(self):
        points = bp_transfer.generate_frequency_points(14e6, 1e6, points=101)
        assert len(points) == 101
        assert all(f > 0 for f in points)

    def test_frequency_response_with_result(self):
        result = {
            'f0': 14e6, 'bw': 1e6, 'n_resonators': 3,
            'filter_type': 'butterworth', 'ripple_db': 0.5,
        }
        resp = bp_transfer.frequency_response(result, [13e6, 14e6, 15e6])
        assert len(resp) == 3
        assert resp[1] > resp[0]  # Peak at center

    def test_export_response_json_bandpass(self):
        result = {
            'filter_type': 'butterworth', 'coupling': 'top',
            'f0': 14e6, 'bw': 1e6, 'n_resonators': 3, 'ripple_db': None,
        }
        s = bp_transfer.export_response_json([13e6, 14e6], [-3.0, 0.0], result)
        data = json.loads(s)
        assert data['filter']['type'] == 'bandpass'
        assert data['filter']['coupling'] == 'top'

    def test_export_response_csv_bandpass(self):
        csv_str = bp_transfer.export_response_csv([13e6, 14e6], [-3.0, 0.0])
        lines = csv_str.split('\n')
        assert lines[0] == 'freq_hz,magnitude_db'
        assert len(lines) == 3
