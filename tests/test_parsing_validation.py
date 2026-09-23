"""Tests for input parsing and validation functions."""

import sys

import pytest

from filter_lib.cli import main
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

    @pytest.mark.parametrize(
        ("text", "hertz"),
        [
            # User-guide spellings not covered above map to the exact binary64 value.
            ("10MHZ", 10e6),
            ("10 MHz", 10e6),
            ("10e6", 10e6),
            ("10E6", 10e6),
            ("10000000", 10e6),
            ("  7.1MHz\t", 7.1e6),
            ("14.175MHz", 14.175e6),
            ("500 k", 500e3),
            ("0.5M", 500e3),
            ("1e-3", 1e-3),
            ("1e15Hz", 1e15),
        ],
    )
    def test_documented_spellings_map_to_exact_hertz(self, text, hertz):
        assert parse_frequency(text) == hertz

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("0", "Frequency must be positive: 0"),
            ("0Hz", "Frequency must be positive: 0Hz"),
            ("0MHz", "Frequency must be positive: 0MHz"),
            ("-0", "Frequency must be positive: -0"),
            ("1e-400", "Frequency must be positive and finite: 1e-400"),
        ],
    )
    def test_zero_and_underflow_have_distinct_messages(self, text, message):
        """A literal zero is non-positive; only an underflowing value is non-representable."""
        with pytest.raises(ValueError, match=f"^{message}$"):
            parse_frequency(text)

    def test_suffix_scaling_preserves_representable_subnormal_token_result(self):
        assert parse_frequency("1e-325GHz") == pytest.approx(1e-316, rel=1e-12, abs=0)

    def test_negative_frequency_raises(self):
        """Negative frequency should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_frequency("-100Hz")
        with pytest.raises(ValueError, match="must be positive"):
            parse_frequency("-10MHz")
        with pytest.raises(ValueError, match="must be positive"):
            parse_frequency("-1")

    @pytest.mark.parametrize("text", ["abc", "", "MHz", "1,000"])
    def test_invalid_format_raises(self, text):
        with pytest.raises(ValueError, match="^Invalid frequency: "):
            parse_frequency(text)

    @pytest.mark.parametrize("text", ["inf", "nan", "-infMHz"])
    def test_non_finite_token_is_rejected(self, text):
        with pytest.raises(ValueError, match="^Frequency must be positive"):
            parse_frequency(text)

    @pytest.mark.parametrize("text", ["1e400", "1e300GHz", "1e-400", "1e-330kHz"])
    def test_result_outside_binary64_range_is_rejected(self, text):
        """Decimal scaling succeeds, but the Hz value overflows or rounds to zero."""
        with pytest.raises(ValueError, match="^Frequency must be positive and finite: "):
            parse_frequency(text)


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

    @pytest.mark.parametrize("text", ["abc", "", "kohm"])
    def test_invalid_format_raises(self, text):
        with pytest.raises(ValueError, match="^Invalid impedance: "):
            parse_impedance(text)

    @pytest.mark.parametrize("text", ["1e400", "1e306kohm", "1e-400ohm"])
    def test_result_outside_binary64_range_is_rejected(self, text):
        with pytest.raises(ValueError, match="^Impedance must be positive and finite: "):
            parse_impedance(text)

    def test_whitespace_handling(self):
        """Whitespace should be handled correctly."""
        assert parse_impedance("  50ohm  ") == 50.0
        assert parse_impedance("  100  ") == 100.0

    @pytest.mark.parametrize(
        ("text", "ohms"),
        [
            ("50", 50.0),
            ("50ohm", 50.0),
            ("50Ω", 50.0),
            ("50 Ohm", 50.0),
            ("50omega", 50.0),
            ("1kohm", 1000.0),
            ("1kΩ", 1000.0),
            ("12.5", 12.5),
            ("0.05k", 50.0),
            ("1.5MΩ", 1.5e6),
        ],
    )
    def test_documented_spellings_map_to_exact_ohms(self, text, ohms):
        assert parse_impedance(text) == ohms


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
        assert parse_inductance(text) == expected

    def test_suffix_scaling_preserves_representable_overflowing_token_result(self):
        assert parse_inductance("1e309nH") == pytest.approx(1e300)

    @pytest.mark.parametrize("text", ["0H", "-1uH", "nan", "inf"])
    def test_non_positive_or_non_finite_rejected(self, text):
        with pytest.raises(ValueError, match="Inductance must be positive"):
            parse_inductance(text)

    @pytest.mark.parametrize("text", ["", "abc", "10pF", "4.7u"])
    def test_invalid_format_rejected(self, text):
        with pytest.raises(ValueError, match="^Invalid inductance: "):
            parse_inductance(text)


@pytest.mark.parametrize(
    ("parser", "label"),
    [
        (parse_frequency, "Frequency"),
        (parse_impedance, "Impedance"),
        (parse_inductance, "Inductance"),
    ],
)
@pytest.mark.parametrize("value", [10e6, None, b"10MHz"])
def test_parsers_require_text_input(parser, label, value):
    with pytest.raises(ValueError, match=f"^{label} must be supplied as text$"):
        parser(value)


@pytest.mark.parametrize(
    ("parser", "text", "label"),
    [
        (parse_frequency, "1e1000000000", "Frequency"),
        (parse_frequency, "1e999999GHz", "Frequency"),
        (parse_impedance, "1e999999k", "Impedance"),
        (parse_inductance, "1e1000000000", "Inductance"),
    ],
)
def test_decimal_context_overflow_is_a_clear_value_error(parser, text, label):
    """Exponents beyond the decimal context overflow before binary64 conversion."""
    with pytest.raises(ValueError, match=f"^{label} must be positive and finite: {text}$"):
        parser(text)


def test_cli_reports_decimal_overflow_as_one_line_usage_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["filter-calc", "lp", "bw", "pi", "1e1000000000"])

    with pytest.raises(SystemExit) as exit_info:
        main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 1
    assert captured.out == ""
    assert captured.err == "Error: Frequency must be positive and finite: 1e1000000000\n"
