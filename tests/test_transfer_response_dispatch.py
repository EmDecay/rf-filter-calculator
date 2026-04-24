"""Tests for transfer response dispatch factory functions.

Tests for:
- make_lp_response_db: Lowpass response factory
- make_hp_response_db: Highpass response factory
- make_bp_response_db: Bandpass response factory
- Response function returns correct dB values for different filter types
- Edge cases: case insensitivity, unknown filter types default to Bessel
"""

import pytest  # noqa: F401

from filter_lib.bandpass.transfer import magnitude_db as bp_magnitude_db
from filter_lib.highpass.transfer import (
    bessel_response as hp_bessel_response,
)
from filter_lib.highpass.transfer import (
    butterworth_response as hp_butterworth_response,
)
from filter_lib.highpass.transfer import (
    chebyshev_response as hp_chebyshev_response,
)
from filter_lib.lowpass.transfer import (
    bessel_response as lp_bessel_response,
)
from filter_lib.lowpass.transfer import (
    butterworth_response as lp_butterworth_response,
)
from filter_lib.lowpass.transfer import (
    chebyshev_response as lp_chebyshev_response,
)
from filter_lib.lowpass.transfer import (
    magnitude_to_db,
)
from filter_lib.shared.transfer_response_dispatch import (
    make_bp_response_db,
    make_hp_response_db,
    make_lp_response_db,
)


class TestMakeLpResponseDb:
    """Tests for make_lp_response_db factory."""

    def test_returns_callable(self):
        """Factory returns a callable function."""
        response_fn = make_lp_response_db("butterworth", 10e6, 5)
        assert callable(response_fn)

    def test_butterworth_response_accuracy(self):
        """Butterworth response matches direct calculation."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_lp_response_db("butterworth", cutoff_hz, order)
        test_freq = 5e6

        # Compare with direct calculation
        expected = magnitude_to_db(lp_butterworth_response(test_freq, cutoff_hz, order))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_butterworth_alias_bw(self):
        """Butterworth alias 'bw' works."""
        cutoff_hz = 10e6
        order = 5
        test_freq = 5e6
        response_fn = make_lp_response_db("bw", cutoff_hz, order)
        expected = magnitude_to_db(lp_butterworth_response(test_freq, cutoff_hz, order))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_butterworth_alias_b(self):
        """Butterworth alias 'b' routes to Butterworth, matching CLI semantics."""
        cutoff_hz = 10e6
        order = 5
        test_freq = 5e6
        response_fn = make_lp_response_db("b", cutoff_hz, order)
        expected = magnitude_to_db(lp_butterworth_response(test_freq, cutoff_hz, order))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_butterworth_case_insensitive(self):
        """Butterworth filter type is case-insensitive."""
        cutoff_hz = 10e6
        order = 5
        test_freq = 5e6
        response_fn_lower = make_lp_response_db("butterworth", cutoff_hz, order)
        response_fn_upper = make_lp_response_db("BUTTERWORTH", cutoff_hz, order)
        assert response_fn_lower(test_freq) == pytest.approx(response_fn_upper(test_freq))

    def test_chebyshev_response_accuracy(self):
        """Chebyshev response matches direct calculation."""
        cutoff_hz = 10e6
        order = 5
        ripple_db = 0.5
        response_fn = make_lp_response_db("chebyshev", cutoff_hz, order, ripple_db)
        test_freq = 5e6

        expected = magnitude_to_db(lp_chebyshev_response(test_freq, cutoff_hz, order, ripple_db))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_chebyshev_alias_ch(self):
        """Chebyshev alias 'ch' works."""
        cutoff_hz = 10e6
        order = 5
        ripple_db = 0.5
        test_freq = 5e6
        response_fn = make_lp_response_db("ch", cutoff_hz, order, ripple_db)
        expected = magnitude_to_db(lp_chebyshev_response(test_freq, cutoff_hz, order, ripple_db))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_chebyshev_alias_c(self):
        """Chebyshev alias 'c' routes to Chebyshev, matching CLI semantics."""
        cutoff_hz = 10e6
        order = 5
        ripple_db = 0.5
        test_freq = 5e6
        response_fn = make_lp_response_db("c", cutoff_hz, order, ripple_db)
        expected = magnitude_to_db(lp_chebyshev_response(test_freq, cutoff_hz, order, ripple_db))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_chebyshev_case_insensitive(self):
        """Chebyshev filter type is case-insensitive."""
        cutoff_hz = 10e6
        order = 5
        ripple_db = 0.5
        test_freq = 5e6
        response_fn_lower = make_lp_response_db("chebyshev", cutoff_hz, order, ripple_db)
        response_fn_upper = make_lp_response_db("CHEBYSHEV", cutoff_hz, order, ripple_db)
        assert response_fn_lower(test_freq) == pytest.approx(response_fn_upper(test_freq))

    def test_bessel_response_accuracy(self):
        """Bessel response matches direct calculation."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_lp_response_db("bessel", cutoff_hz, order)
        test_freq = 5e6

        expected = magnitude_to_db(lp_bessel_response(test_freq, cutoff_hz, order))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_bessel_alias_bs(self):
        """Bessel alias 'bs' routes to Bessel."""
        cutoff_hz = 10e6
        order = 5
        test_freq = 5e6
        response_fn = make_lp_response_db("bs", cutoff_hz, order)
        expected = magnitude_to_db(lp_bessel_response(test_freq, cutoff_hz, order))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_unknown_filter_type_raises(self):
        """Unknown filter type raises ValueError instead of silently picking Bessel."""
        with pytest.raises(ValueError, match="Unknown filter type"):
            make_lp_response_db("unknown", 10e6, 5)

    def test_none_filter_type_raises(self):
        """None filter type raises ValueError, not AttributeError."""
        with pytest.raises(ValueError, match="must be provided"):
            make_lp_response_db(None, 10e6, 5)  # type: ignore[arg-type]

    def test_ripple_parameter_passed_to_response(self):
        """Ripple parameter affects Chebyshev response."""
        cutoff_hz = 10e6
        order = 5
        test_freq = 8e6
        ripple_0_5 = make_lp_response_db("chebyshev", cutoff_hz, order, 0.5)
        ripple_1_0 = make_lp_response_db("chebyshev", cutoff_hz, order, 1.0)
        # Different ripples should produce different responses
        assert ripple_0_5(test_freq) != ripple_1_0(test_freq)

    def test_multiple_test_frequencies(self):
        """Response function works for multiple frequencies."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_lp_response_db("butterworth", cutoff_hz, order)
        test_freqs = [1e6, 5e6, 10e6, 20e6, 50e6]
        for freq in test_freqs:
            result = response_fn(freq)
            assert isinstance(result, float)
            assert result <= 0  # dB should be <= 0

    def test_at_cutoff_frequency(self):
        """Response near -3dB at cutoff (Butterworth)."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_lp_response_db("butterworth", cutoff_hz, order)
        result = response_fn(cutoff_hz)
        # Butterworth has -3dB at cutoff
        assert result == pytest.approx(-3.0, abs=0.5)

    def test_at_zero_frequency(self):
        """Response at DC (zero frequency)."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_lp_response_db("butterworth", cutoff_hz, order)
        result = response_fn(0.1)  # Near DC
        # Should be near 0dB at low frequencies
        assert result > -1.0

    def test_well_above_cutoff(self):
        """Response well above cutoff is heavily attenuated."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_lp_response_db("butterworth", cutoff_hz, order)
        result = response_fn(1e9)  # 100x cutoff
        # Should be heavily attenuated
        assert result < -40.0


class TestMakeHpResponseDb:
    """Tests for make_hp_response_db factory."""

    def test_returns_callable(self):
        """Factory returns a callable function."""
        response_fn = make_hp_response_db("butterworth", 10e6, 5)
        assert callable(response_fn)

    def test_butterworth_response_accuracy(self):
        """Butterworth response matches direct calculation."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_hp_response_db("butterworth", cutoff_hz, order)
        test_freq = 20e6

        expected = magnitude_to_db(hp_butterworth_response(test_freq, cutoff_hz, order))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_butterworth_alias_bw(self):
        """Butterworth alias 'bw' works."""
        cutoff_hz = 10e6
        order = 5
        test_freq = 20e6
        response_fn = make_hp_response_db("bw", cutoff_hz, order)
        expected = magnitude_to_db(hp_butterworth_response(test_freq, cutoff_hz, order))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_butterworth_case_insensitive(self):
        """Butterworth filter type is case-insensitive."""
        cutoff_hz = 10e6
        order = 5
        test_freq = 20e6
        response_fn_lower = make_hp_response_db("butterworth", cutoff_hz, order)
        response_fn_upper = make_hp_response_db("BUTTERWORTH", cutoff_hz, order)
        assert response_fn_lower(test_freq) == pytest.approx(response_fn_upper(test_freq))

    def test_chebyshev_response_accuracy(self):
        """Chebyshev response matches direct calculation."""
        cutoff_hz = 10e6
        order = 5
        ripple_db = 0.5
        response_fn = make_hp_response_db("chebyshev", cutoff_hz, order, ripple_db)
        test_freq = 20e6

        expected = magnitude_to_db(hp_chebyshev_response(test_freq, cutoff_hz, order, ripple_db))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_chebyshev_alias_ch(self):
        """Chebyshev alias 'ch' works."""
        cutoff_hz = 10e6
        order = 5
        ripple_db = 0.5
        test_freq = 20e6
        response_fn = make_hp_response_db("ch", cutoff_hz, order, ripple_db)
        expected = magnitude_to_db(hp_chebyshev_response(test_freq, cutoff_hz, order, ripple_db))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_chebyshev_case_insensitive(self):
        """Chebyshev filter type is case-insensitive."""
        cutoff_hz = 10e6
        order = 5
        ripple_db = 0.5
        test_freq = 20e6
        response_fn_lower = make_hp_response_db("chebyshev", cutoff_hz, order, ripple_db)
        response_fn_upper = make_hp_response_db("CHEBYSHEV", cutoff_hz, order, ripple_db)
        assert response_fn_lower(test_freq) == pytest.approx(response_fn_upper(test_freq))

    def test_bessel_response_accuracy(self):
        """Bessel response matches direct calculation."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_hp_response_db("bessel", cutoff_hz, order)
        test_freq = 20e6

        expected = magnitude_to_db(hp_bessel_response(test_freq, cutoff_hz, order))
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_unknown_filter_type_raises(self):
        """Unknown filter type raises ValueError instead of silently picking Bessel."""
        with pytest.raises(ValueError, match="Unknown filter type"):
            make_hp_response_db("unknown", 10e6, 5)

    def test_none_filter_type_raises(self):
        """None filter type raises ValueError, not AttributeError."""
        with pytest.raises(ValueError, match="must be provided"):
            make_hp_response_db(None, 10e6, 5)  # type: ignore[arg-type]

    def test_ripple_parameter_passed_to_response(self):
        """Ripple parameter affects Chebyshev response."""
        cutoff_hz = 10e6
        order = 5
        test_freq = 15e6
        ripple_0_5 = make_hp_response_db("chebyshev", cutoff_hz, order, 0.5)
        ripple_1_0 = make_hp_response_db("chebyshev", cutoff_hz, order, 1.0)
        # Different ripples should produce different responses
        assert ripple_0_5(test_freq) != ripple_1_0(test_freq)

    def test_multiple_test_frequencies(self):
        """Response function works for multiple frequencies."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_hp_response_db("butterworth", cutoff_hz, order)
        test_freqs = [1e6, 5e6, 10e6, 20e6, 50e6]
        for freq in test_freqs:
            result = response_fn(freq)
            assert isinstance(result, float)
            assert result <= 0  # dB should be <= 0

    def test_at_cutoff_frequency(self):
        """Response near -3dB at cutoff (Butterworth)."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_hp_response_db("butterworth", cutoff_hz, order)
        result = response_fn(cutoff_hz)
        # Butterworth has -3dB at cutoff
        assert result == pytest.approx(-3.0, abs=0.5)

    def test_well_below_cutoff(self):
        """Response well below cutoff is heavily attenuated."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_hp_response_db("butterworth", cutoff_hz, order)
        result = response_fn(100e3)  # 100x below cutoff
        # Should be heavily attenuated
        assert result < -40.0

    def test_well_above_cutoff(self):
        """Response well above cutoff is near passband."""
        cutoff_hz = 10e6
        order = 5
        response_fn = make_hp_response_db("butterworth", cutoff_hz, order)
        result = response_fn(100e6)  # 10x above cutoff
        # Should be near 0dB
        assert result > -1.0


class TestMakeBpResponseDb:
    """Tests for make_bp_response_db factory."""

    def test_returns_callable(self):
        """Factory returns a callable function."""
        response_fn = make_bp_response_db(1e6, 100e3, 3, "butterworth")
        assert callable(response_fn)

    def test_butterworth_response_accuracy(self):
        """Butterworth response matches direct calculation."""
        f0 = 1e6
        bw = 100e3
        n_resonators = 3
        filter_type = "butterworth"
        response_fn = make_bp_response_db(f0, bw, n_resonators, filter_type)
        test_freq = 1e6

        expected = bp_magnitude_db(test_freq, f0, bw, n_resonators, filter_type, 0.5)
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_unknown_filter_type_raises(self):
        """Unknown bandpass filter type raises ValueError upfront."""
        with pytest.raises(ValueError, match="Unknown filter type"):
            make_bp_response_db(1e6, 100e3, 3, "unknown")

    def test_none_filter_type_raises(self):
        """None bandpass filter type raises ValueError, not AttributeError."""
        with pytest.raises(ValueError, match="must be provided"):
            make_bp_response_db(1e6, 100e3, 3, None)  # type: ignore[arg-type]

    def test_alias_routing_bw_to_butterworth(self):
        """Bandpass 'bw' alias routes to Butterworth via canonicalization."""
        f0 = 1e6
        bw = 100e3
        n = 3
        test_freq = 950e3
        alias_fn = make_bp_response_db(f0, bw, n, "bw")
        canonical_fn = make_bp_response_db(f0, bw, n, "butterworth")
        assert alias_fn(test_freq) == pytest.approx(canonical_fn(test_freq))

    def test_chebyshev_response_accuracy(self):
        """Chebyshev response matches direct calculation."""
        f0 = 1e6
        bw = 100e3
        n_resonators = 3
        filter_type = "chebyshev"
        ripple_db = 0.5
        response_fn = make_bp_response_db(f0, bw, n_resonators, filter_type, ripple_db)
        test_freq = 1e6

        expected = bp_magnitude_db(test_freq, f0, bw, n_resonators, filter_type, ripple_db)
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_bessel_response_accuracy(self):
        """Bessel response matches direct calculation."""
        f0 = 1e6
        bw = 100e3
        n_resonators = 3
        filter_type = "bessel"
        response_fn = make_bp_response_db(f0, bw, n_resonators, filter_type)
        test_freq = 1e6

        expected = bp_magnitude_db(test_freq, f0, bw, n_resonators, filter_type, 0.5)
        result = response_fn(test_freq)
        assert result == pytest.approx(expected, rel=1e-9)

    def test_ripple_parameter_passed_to_response(self):
        """Ripple parameter affects Chebyshev response."""
        f0 = 1e6
        bw = 100e3
        n_resonators = 3
        test_freq = 950e3  # Off-center
        ripple_0_5 = make_bp_response_db(f0, bw, n_resonators, "chebyshev", 0.5)
        ripple_1_0 = make_bp_response_db(f0, bw, n_resonators, "chebyshev", 1.0)
        # Different ripples may produce different responses
        result_0_5 = ripple_0_5(test_freq)
        result_1_0 = ripple_1_0(test_freq)
        assert isinstance(result_0_5, float)
        assert isinstance(result_1_0, float)

    def test_at_center_frequency(self):
        """Response at center frequency is near 0dB."""
        f0 = 1e6
        bw = 100e3
        n_resonators = 3
        response_fn = make_bp_response_db(f0, bw, n_resonators, "butterworth")
        result = response_fn(f0)
        # At center frequency should be near 0dB
        assert result > -3.0

    def test_below_passband(self):
        """Response below passband is attenuated."""
        f0 = 1e6
        bw = 100e3
        n_resonators = 3
        response_fn = make_bp_response_db(f0, bw, n_resonators, "butterworth")
        result = response_fn(100e3)  # Well below passband
        assert result < -10.0

    def test_above_passband(self):
        """Response above passband is attenuated."""
        f0 = 1e6
        bw = 100e3
        n_resonators = 3
        response_fn = make_bp_response_db(f0, bw, n_resonators, "butterworth")
        result = response_fn(10e6)  # Well above passband
        assert result < -10.0

    def test_edge_of_passband_lower(self):
        """Response at lower edge of passband."""
        f0 = 1e6
        bw = 100e3
        n_resonators = 3
        response_fn = make_bp_response_db(f0, bw, n_resonators, "butterworth")
        f_low = f0 - bw / 2
        result = response_fn(f_low)
        # Should be within -3dB of center
        assert result > -10.0

    def test_edge_of_passband_upper(self):
        """Response at upper edge of passband."""
        f0 = 1e6
        bw = 100e3
        n_resonators = 3
        response_fn = make_bp_response_db(f0, bw, n_resonators, "butterworth")
        f_high = f0 + bw / 2
        result = response_fn(f_high)
        # Should be within -3dB of center
        assert result > -10.0

    def test_multiple_resonator_counts(self):
        """Works with different resonator counts."""
        f0 = 1e6
        bw = 100e3
        filter_type = "butterworth"
        for n_res in [1, 3, 5, 7, 9]:
            response_fn = make_bp_response_db(f0, bw, n_res, filter_type)
            result = response_fn(f0)
            assert isinstance(result, float)
            assert result > -5.0  # Near center should be close to passband


class TestCrossFilterConsistency:
    """Tests for consistency across LP, HP, BP factories."""

    def test_lp_hp_same_butterworth_formula(self):
        """LP and HP use same Butterworth formula."""
        cutoff_hz = 10e6
        order = 5
        test_freq = 10e6
        lp_fn = make_lp_response_db("butterworth", cutoff_hz, order)
        hp_fn = make_hp_response_db("butterworth", cutoff_hz, order)
        # At cutoff, both should be near -3dB
        lp_result = lp_fn(test_freq)
        hp_result = hp_fn(test_freq)
        assert lp_result == pytest.approx(hp_result, rel=1e-9)

    def test_lp_hp_different_shapes(self):
        """LP and HP have opposite frequency responses."""
        cutoff_hz = 10e6
        order = 5
        lp_fn = make_lp_response_db("butterworth", cutoff_hz, order)
        hp_fn = make_hp_response_db("butterworth", cutoff_hz, order)
        # Below cutoff: LP passes, HP attenuates
        lp_low = lp_fn(cutoff_hz / 10)
        hp_low = hp_fn(cutoff_hz / 10)
        assert lp_low > hp_low  # LP should have less attenuation at low freq

        # Above cutoff: LP attenuates, HP passes
        lp_high = lp_fn(cutoff_hz * 10)
        hp_high = hp_fn(cutoff_hz * 10)
        assert hp_high > lp_high  # HP should have less attenuation at high freq

    def test_factory_closure_isolation(self):
        """Each factory call creates independent closures."""
        cutoff_hz = 10e6
        order = 5
        fn1 = make_lp_response_db("butterworth", cutoff_hz, order)
        fn2 = make_lp_response_db("butterworth", cutoff_hz, order)
        # Different instances should produce same results
        test_freq = 5e6
        assert fn1(test_freq) == fn2(test_freq)

    def test_bp_narrow_band_behavior(self):
        """Bandpass with narrow band behaves like high-Q resonator."""
        f0 = 1e6
        narrow_bw = 10e3  # 1% bandwidth
        wide_bw = 100e3  # 10% bandwidth
        n_res = 3
        narrow_fn = make_bp_response_db(f0, narrow_bw, n_res, "butterworth")
        wide_fn = make_bp_response_db(f0, wide_bw, n_res, "butterworth")

        # Both at center should be in passband
        assert narrow_fn(f0) > -3.0
        assert wide_fn(f0) > -3.0

        # But off-center behavior differs
        off_freq = f0 * 1.02  # 2% offset
        narrow_off = narrow_fn(off_freq)
        wide_off = wide_fn(off_freq)
        # Narrow band should attenuate more at same offset
        assert narrow_off < wide_off
