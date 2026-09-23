"""Engineering-unit value formatting and the E-series match display lines."""

import math

import pytest

from filter_lib.shared.display_helpers import (
    format_component_value,
    format_eseries_match,
    split_value_unit,
)
from filter_lib.shared.formatting import (
    format_capacitance,
    format_frequency,
    format_impedance,
    format_inductance,
    format_restated_frequency,
    format_restated_value,
)


class TestUnitFormatters:
    @pytest.mark.parametrize(
        ("value", "text"),
        [
            (0, "0 Hz"),
            (0.1, "0.1 Hz"),
            (100, "100 Hz"),
            (500e3, "500 kHz"),
            (14.2e6, "14.2 MHz"),
            (14.175e6, "14.18 MHz"),
            (-5e6, "-5 MHz"),
            (2.4e9, "2.4 GHz"),
            (999.9e9, "999.9 GHz"),
            # From 1000x the largest prefix a prefixed mantissa would need ever more digits.
            (1e12, "1.000000e+12 Hz"),
            (3.2e300, "3.200000e+300 Hz"),
        ],
    )
    def test_format_frequency(self, value, text):
        assert format_frequency(value) == text

    @pytest.mark.parametrize(
        ("value", "text"),
        [
            (0, "0.00e+00 F"),
            (0.5e-15, "5.00e-16 F"),
            (1e-15, "1.00 fF"),
            (100e-12, "100.00 pF"),
            (318.30988e-12, "318.31 pF"),
            (-1e-12, "-1.00 pF"),
            (2.2e-9, "2.20 nF"),
            (4.7e-6, "4.70 µF"),
            (1e-3, "1.00 mF"),
            (0.5, "500.00 mF"),
            # Farads keep a fixed-point prefix like henries; only 1000 F and above is
            # scientific.
            (1.0, "1.00 F"),
            (3.1830988618, "3.18 F"),
            (999.994, "999.99 F"),
            (1000.0, "1.000000e+03 F"),
            # A 1e-300 Hz design; the mF prefix used to print a 300-digit number.
            (3.183098861837907e297, "3.183099e+297 F"),
        ],
    )
    def test_format_capacitance(self, value, text):
        assert format_capacitance(value) == text

    @pytest.mark.parametrize(
        ("value", "text"),
        [
            (0, "0.00e+00 H"),
            (0.5e-12, "5.00e-13 H"),
            (1e-12, "1.00 pH"),
            # 10 GHz, 1 ohm T ladder: 15.9 pH used to print as "0.02 nH" (26% off).
            (1.5915494309189542e-11, "15.92 pH"),
            (999e-12, "999.00 pH"),
            (1e-9, "1.00 nH"),
            (100e-9, "100.00 nH"),
            (1.5915494e-6, "1.59 µH"),
            (10e-6, "10.00 µH"),
            (-1e-6, "-1.00 µH"),
            (2.5e-3, "2.50 mH"),
            (1.0, "1.00 H"),
            (999.0, "999.00 H"),
            (1e3, "1.000000e+03 H"),
            (1.591549430918953e299, "1.591549e+299 H"),
        ],
    )
    def test_format_inductance(self, value, text):
        """Picohenries mirror femtofarads; below 1 pH plain henries keep the value readable."""
        assert format_inductance(value) == text

    @pytest.mark.parametrize(
        ("value", "text"),
        [
            (0.5, "0.5 Ω"),
            (50, "50 Ω"),
            (75.5, "75.5 Ω"),
            (1000, "1 kΩ"),
            (2.2e6, "2.2 MΩ"),
            (999e6, "999 MΩ"),
            (1e9, "1.000000e+09 Ω"),
        ],
    )
    def test_format_impedance(self, value, text):
        assert format_impedance(value) == text

    @pytest.mark.parametrize(
        "formatter", [format_frequency, format_capacitance, format_inductance, format_impedance]
    )
    @pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "1", None, 10**400])
    def test_rejects_values_that_are_not_finite_reals(self, formatter, value):
        with pytest.raises(ValueError, match="formatted value must be a finite real number"):
            formatter(value)

    @pytest.mark.parametrize(
        ("formatted", "parts"),
        [
            (format_capacitance(100e-12), ("100.00", "pF")),
            (format_inductance(1e-12), ("1.00", "pH")),
            (format_inductance(1e3), ("1.000000e+03", "H")),
            (format_frequency(14.2e6), ("14.2", "MHz")),
            (format_impedance(2.2e6), ("2.2", "MΩ")),
        ],
    )
    def test_split_value_unit_separates_the_single_space_unit_suffix(self, formatted, parts):
        assert split_value_unit(formatted) == parts


class TestRestatedDesignValues:
    """Headers restate a typed design value exactly and never print binary64 noise."""

    @pytest.mark.parametrize(
        ("value", "text"),
        [
            (7.0735e6, "7.0735 MHz"),
            (14.175e6, "14.175 MHz"),
            (10e6, "10 MHz"),
            (455e3, "455 kHz"),
            (2.4e9, "2.4 GHz"),
            (1575.42e6, "1.57542 GHz"),
            (100.0, "100 Hz"),
            (0.5, "0.5 Hz"),
            # A computed neighbour of 14.175 MHz is not the typed value; it rounds instead
            # of printing 14.175000000000002.
            (math.nextafter(14.175e6, math.inf), "14.18 MHz"),
            (14.17500000001e6, "14.18 MHz"),
            # Rounding picks the prefix, so a value just under 1 MHz reads 1 MHz.
            (999999.9999999999, "1 MHz"),
            (1e12, "1e+12 Hz"),
            (1.23456e15, "1.23456e+15 Hz"),
            (1e-300, "1e-300 Hz"),
        ],
    )
    def test_frequency(self, value, text):
        assert format_restated_frequency(value) == text

    def test_frequency_rounds_computed_values_to_the_requested_digits(self):
        assert format_restated_frequency(99950012.49687695, min_digits=8) == "99.950012 MHz"
        assert format_restated_frequency(math.nextafter(14e6, 0), min_digits=7) == "14 MHz"

    @pytest.mark.parametrize(
        ("value", "text"),
        [
            (12345.0, "12345"),
            (50.0, "50"),
            (12.5, "12.5"),
            (0.25, "0.25"),
            (123456789012.0, "123456789012"),
            (1e16, "1e+16"),
            (1e300, "1e+300"),
            (1e-300, "1e-300"),
            (math.nextafter(50.0, math.inf), "50"),
            (100 / 3, "33.33"),
        ],
    )
    def test_value(self, value, text):
        assert format_restated_value(value) == text

    @pytest.mark.parametrize("formatter", [format_restated_frequency, format_restated_value])
    @pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "1", None, 10**400])
    def test_rejects_values_that_are_not_finite_reals(self, formatter, value):
        with pytest.raises(ValueError, match="formatted value must be a finite real number"):
            formatter(value)


class TestComponentValue:
    @pytest.mark.parametrize(
        ("name", "value", "formatter", "raw", "text"),
        [
            ("C1", 1e-15, format_capacitance, False, "C1: 1.00 fF"),
            ("C1", 1e-15, format_capacitance, True, "C1: 1.000000e-15 F"),
            ("C2", 0, format_capacitance, True, "C2: 0.000000e+00 F"),
            ("L2", 1e-6, format_inductance, False, "L2: 1.00 µH"),
            ("L2", 1e-6, format_inductance, True, "L2: 1.000000e-06 H"),
        ],
    )
    def test_formats_named_value_in_engineering_or_raw_units(
        self, name, value, formatter, raw, text
    ):
        assert format_component_value(name, value, formatter, raw=raw) == text


class TestEseriesMatchLines:
    def test_exact_standard_value_shows_only_the_nearest_part(self):
        lines = format_eseries_match(100e-12, "E12", format_capacitance, "additive")

        assert lines == ["  Nearest Std:  100.00 pF (0.0%)"]

    def test_inductor_uses_harmonic_parallel_pair(self):
        lines = format_eseries_match(1.457e-6, "E24", format_inductance, "harmonic")

        assert lines == [
            "  Nearest Std:  1.50 µH (+3.0%)",
            "  Parallel Std: 2.20 µH || 4.30 µH (-0.1%)",
        ]

    def test_parallel_pair_keeps_units_on_both_values(self):
        """A decade-spanning pair must not print a bare first number."""
        lines = format_eseries_match(2.9e-9, "E12", format_capacitance, "additive")

        assert lines == [
            "  Nearest Std:  2.70 nF (-6.9%)",
            "  Parallel Std: 680.00 pF || 2.20 nF (-0.7%)",
        ]

    def test_sub_pf_target_is_reference_only_and_requires_expert_action(self):
        lines = format_eseries_match(1e-15, "E12", format_capacitance, "additive")

        assert lines[:2] == [
            "  Nearest Std (reference only): 1.00 fF (0.0%)",
            "  Selection:                    EXPERT ACTION REQUIRED; no part selected",
        ]
        assert len(lines) == 3
        assert lines[2].startswith("  Warning: ")
        assert "below the 1 pF" in lines[2]

    def test_non_positive_target_is_rejected(self):
        with pytest.raises(ValueError, match="positive and finite"):
            format_eseries_match(0, "E12", format_capacitance, "additive")
