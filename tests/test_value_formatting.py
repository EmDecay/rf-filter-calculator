"""Engineering-unit value formatting and the E-series match display lines."""

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
            (1e12, "1000 GHz"),
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
        ],
    )
    def test_format_capacitance(self, value, text):
        assert format_capacitance(value) == text

    @pytest.mark.parametrize(
        ("value", "text"),
        [
            (0, "0.00 nH"),
            (1e-12, "1.000000e-12 H"),
            (100e-9, "100.00 nH"),
            (1.5915494e-6, "1.59 µH"),
            (10e-6, "10.00 µH"),
            (-1e-6, "-1.00 µH"),
            (2.5e-3, "2.50 mH"),
            (1.0, "1.00 H"),
        ],
    )
    def test_format_inductance(self, value, text):
        """Values that round to 0.00 in the smallest unit fall back to plain henries."""
        assert format_inductance(value) == text

    @pytest.mark.parametrize(
        ("value", "text"),
        [(0.5, "0.5 Ω"), (50, "50 Ω"), (75.5, "75.5 Ω"), (1000, "1 kΩ"), (2.2e6, "2.2 MΩ")],
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
            (format_inductance(1e-12), ("1.000000e-12", "H")),
            (format_frequency(14.2e6), ("14.2", "MHz")),
            (format_impedance(2.2e6), ("2.2", "MΩ")),
        ],
    )
    def test_split_value_unit_separates_the_single_space_unit_suffix(self, formatted, parts):
        assert split_value_unit(formatted) == parts


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
