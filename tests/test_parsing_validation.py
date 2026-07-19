"""Tests for input parsing and validation functions."""

import pytest

from filter_lib.shared.parsing import parse_frequency, parse_impedance, parse_inductance


class TestParseFrequency:
    """Tests for parse_frequency function."""

    def test_hz_suffix(self):
        """Parse frequency with Hz suffix."""
        assert parse_frequency("1000Hz") == 1000.0
        assert parse_frequency("100 hz") == 100.0

    def test_khz_suffix(self):
        """Parse frequency with kHz suffix."""
        assert parse_frequency("10kHz") == 10000.0
        assert parse_frequency("1.5 khz") == 1500.0

    def test_mhz_suffix(self):
        """Parse frequency with MHz suffix."""
        assert parse_frequency("14.2MHz") == 14.2e6
        assert parse_frequency("100 mhz") == 100e6

    def test_ghz_suffix(self):
        """Parse frequency with GHz suffix."""
        assert parse_frequency("1GHz") == 1e9
        assert parse_frequency("2.4 ghz") == 2.4e9

    def test_no_suffix_assumes_hz(self):
        """Parse frequency without suffix as Hz."""
        assert parse_frequency("1000") == 1000.0
        assert parse_frequency("500.5") == 500.5

    def test_shorthand_suffixes(self):
        """Parse frequency with shorthand suffixes (M, k, G)."""
        assert parse_frequency("10M") == 10e6
        assert parse_frequency("14.2m") == 14.2e6
        assert parse_frequency("500k") == 500e3
        assert parse_frequency("1.5K") == 1.5e3
        assert parse_frequency("2.4G") == 2.4e9
        assert parse_frequency("1g") == 1e9

    def test_suffix_scaling_preserves_representable_subnormal_token_result(self):
        assert parse_frequency("1e-325GHz") == pytest.approx(1e-316)

    def test_negative_frequency_raises(self):
        """Negative frequency should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_frequency("-100Hz")
        with pytest.raises(ValueError, match="must be positive"):
            parse_frequency("-10MHz")
        with pytest.raises(ValueError, match="must be positive"):
            parse_frequency("-1")

    def test_zero_frequency_raises(self):
        """Zero frequency should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_frequency("0Hz")
        with pytest.raises(ValueError, match="must be positive"):
            parse_frequency("0")

    def test_invalid_format_raises(self):
        """Invalid format should raise ValueError."""
        with pytest.raises(ValueError):
            parse_frequency("abc")
        with pytest.raises(ValueError):
            parse_frequency("")


class TestParseImpedance:
    """Tests for parse_impedance function."""

    def test_ohm_suffix(self):
        """Parse impedance with ohm suffix."""
        assert parse_impedance("50ohm") == 50.0
        assert parse_impedance("75 ohm") == 75.0

    def test_kohm_suffix(self):
        """Parse impedance with kohm suffix."""
        assert parse_impedance("1kohm") == 1000.0
        assert parse_impedance("4.7 kohm") == 4700.0

    def test_mohm_suffix(self):
        """Parse impedance with Mohm suffix."""
        assert parse_impedance("1Mohm") == 1e6
        assert parse_impedance("2.2 mohm") == 2.2e6

    def test_omega_symbol(self):
        """Parse impedance with omega symbol."""
        assert parse_impedance("50\u03a9") == 50.0  # Uppercase omega
        assert parse_impedance("75\u03c9") == 75.0  # Lowercase omega

    def test_bare_k_suffix(self):
        """Bare k means kilohms."""
        assert parse_impedance("1k") == 1000.0
        assert parse_impedance("4.7K") == 4700.0

    def test_bare_m_suffix_means_mega(self):
        """Bare m/M means megohms (mega, not milli \u2014 matches frequency parsing)."""
        assert parse_impedance("1M") == 1e6
        assert parse_impedance("2.2m") == 2.2e6

    def test_no_suffix_assumes_ohm(self):
        """Parse impedance without suffix as ohms."""
        assert parse_impedance("50") == 50.0
        assert parse_impedance("600") == 600.0

    def test_negative_impedance_raises(self):
        """Negative impedance should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_impedance("-50ohm")
        with pytest.raises(ValueError, match="must be positive"):
            parse_impedance("-1kohm")
        with pytest.raises(ValueError, match="must be positive"):
            parse_impedance("-50")

    def test_zero_impedance_raises(self):
        """Zero impedance should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_impedance("0ohm")
        with pytest.raises(ValueError, match="must be positive"):
            parse_impedance("0")

    def test_invalid_format_raises(self):
        """Invalid format should raise ValueError."""
        with pytest.raises(ValueError):
            parse_impedance("abc")
        with pytest.raises(ValueError):
            parse_impedance("")

    def test_whitespace_handling(self):
        """Whitespace should be handled correctly."""
        assert parse_impedance("  50ohm  ") == 50.0
        assert parse_impedance("  100  ") == 100.0


class TestParseInductance:
    """Tests for the band-pass resonator-inductance parser."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1H", 1.0),
            ("2.2mH", 2.2e-3),
            ("4.7uH", 4.7e-6),
            ("4.7µH", 4.7e-6),
            ("4.7μH", 4.7e-6),
            ("330nH", 330e-9),
            ("1e-6", 1e-6),
        ],
    )
    def test_supported_units(self, text, expected):
        assert parse_inductance(text) == pytest.approx(expected)

    def test_suffix_scaling_preserves_representable_overflowing_token_result(self):
        assert parse_inductance("1e309nH") == pytest.approx(1e300)

    @pytest.mark.parametrize("text", ["0H", "-1uH", "nan", "inf"])
    def test_non_positive_or_non_finite_rejected(self, text):
        with pytest.raises(ValueError, match="Inductance must be positive"):
            parse_inductance(text)

    @pytest.mark.parametrize("text", ["", "abc", "10pF", "4.7u"])
    def test_invalid_format_rejected(self, text):
        with pytest.raises(ValueError):
            parse_inductance(text)
