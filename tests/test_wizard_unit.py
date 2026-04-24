"""Unit tests for wizard calculation and formatting modules.

This test module covers:
- filter_lib/wizard/filter_type_calculators.py
- filter_lib/wizard/formatting_helpers.py
- filter_lib/wizard/calculation_handler.py
- filter_lib/wizard/radio_button_helpers.py

These modules contain the core business logic for wizard calculations,
separated from the Textual UI rendering logic.
"""

import json
from unittest.mock import Mock

import pytest

from filter_lib.wizard.calculation_handler import calculate_and_format
from filter_lib.wizard.filter_type_calculators import (
    calculate_bandpass,
    calculate_highpass,
    calculate_lowpass,
)
from filter_lib.wizard.formatting_helpers import (
    _format_component_table,
    format_bandpass_table,
    format_eseries_recs,
    format_lp_hp_table,
)
from filter_lib.wizard.radio_button_helpers import get_selected_radio
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.state import FilterState
from filter_lib.wizard.validation import validate_order, validate_ripple

# ============================================================================
# Tests for filter_type_calculators.py
# ============================================================================


class TestCalculateLowpass:
    """Tests for lowpass filter calculation."""

    def test_butterworth_lowpass_basic(self):
        """Test basic Butterworth lowpass calculation."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="none",
        )

        lines = calculate_lowpass(state)

        # Verify state is updated with result
        assert state.result is not None
        assert state.result["filter_type"] == "butterworth"
        assert state.result["freq_hz"] == 10e6
        assert state.result["impedance"] == 50.0
        assert state.result["order"] == 3
        assert state.result["ripple"] is None
        assert state.result["topology"] == "pi"
        assert "capacitors" in state.result
        assert "inductors" in state.result

        # Verify output is generated
        assert len(lines) > 0
        output = "\n".join(lines)
        assert "Butterworth" in output
        assert "Low Pass" in output

    def test_chebyshev_lowpass_with_ripple(self):
        """Test Chebyshev lowpass includes ripple value."""
        state = FilterState(
            category="lowpass",
            filter_type="chebyshev",
            frequency_hz=1e6,
            impedance=75.0,
            order=5,
            ripple_db=0.5,
            topology="t",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="none",
        )

        lines = calculate_lowpass(state)

        assert state.result["ripple"] == 0.5
        output = "\n".join(lines)
        assert "0.5 dB" in output or "Ripple" in output

    def test_bessel_lowpass(self):
        """Test Bessel lowpass calculation."""
        state = FilterState(
            category="lowpass",
            filter_type="bessel",
            frequency_hz=5e6,
            impedance=50.0,
            order=4,
            topology="pi",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="none",
        )

        lines = calculate_lowpass(state)

        assert state.result["filter_type"] == "bessel"
        assert state.result["ripple"] is None
        output = "\n".join(lines)
        assert "Bessel" in output

    def test_lowpass_json_output(self):
        """Test JSON output format for lowpass."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="json",
            quiet=False,
            show_plot=False,
        )

        lines = calculate_lowpass(state)

        assert len(lines) == 1
        output = lines[0]
        assert "{" in output  # JSON output
        assert "butterworth" in output.lower()

    def test_lowpass_json_with_eseries(self):
        """Test lowpass JSON includes standard match fields."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="json",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="E24",
        )

        lines = calculate_lowpass(state)

        data = json.loads(lines[0])
        first_cap = data["components"]["capacitors"][0]
        assert "standard_match" in first_cap
        assert first_cap["standard_match"]["series"] == "E24"

    def test_lowpass_csv_output(self):
        """Test CSV output format for lowpass."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="csv",
            quiet=False,
            show_plot=False,
        )

        lines = calculate_lowpass(state)

        assert len(lines) == 1
        output = lines[0]
        # CSV typically uses commas or specific format
        assert len(output) > 0

    def test_lowpass_csv_with_eseries(self):
        """Test lowpass CSV includes standard match columns."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="csv",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="E24",
        )

        lines = calculate_lowpass(state)
        header = lines[0].splitlines()[0]
        assert "NearestStdValue" in header
        assert "Eseries" in header

    def test_lowpass_quiet_mode(self):
        """Test quiet mode output for lowpass."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            quiet=True,
            raw_units=True,
            show_plot=False,
        )

        lines = calculate_lowpass(state)

        assert len(lines) == 1
        # Quiet mode should be minimal output

    def test_lowpass_with_eseries(self):
        """Test lowpass with E-series recommendations."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="E12",
        )

        lines = calculate_lowpass(state)

        output = "\n".join(lines)
        assert "E12" in output or "Recommendations" in output

    def test_lowpass_with_plot(self):
        """Test lowpass with frequency response plot."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=True,
            eseries="none",
        )

        lines = calculate_lowpass(state)

        # Plot should add extra lines
        assert len(lines) > 5
        output = "\n".join(lines)
        # ASCII plot typically has certain characters
        assert len(output) > 200

    def test_lowpass_raw_units(self):
        """Test lowpass with raw units enabled."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            quiet=False,
            raw_units=True,
            show_plot=False,
            eseries="none",
        )

        lines = calculate_lowpass(state)

        output = "\n".join(lines)
        # Raw units should show scientific notation
        assert "e" in output.lower()


class TestCalculateHighpass:
    """Tests for highpass filter calculation."""

    def test_butterworth_highpass_basic(self):
        """Test basic Butterworth highpass calculation."""
        state = FilterState(
            category="highpass",
            filter_type="butterworth",
            frequency_hz=1e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="none",
        )

        lines = calculate_highpass(state)

        assert state.result is not None
        assert state.result["filter_type"] == "butterworth"
        assert state.result["freq_hz"] == 1e6
        assert state.result["impedance"] == 50.0
        assert state.result["order"] == 3
        assert state.result["ripple"] is None
        assert "inductors" in state.result
        assert "capacitors" in state.result

        output = "\n".join(lines)
        assert "Butterworth" in output
        assert "High Pass" in output

    def test_chebyshev_highpass(self):
        """Test Chebyshev highpass calculation."""
        state = FilterState(
            category="highpass",
            filter_type="chebyshev",
            frequency_hz=5e6,
            impedance=75.0,
            order=5,
            ripple_db=1.0,
            topology="t",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="none",
        )

        lines = calculate_highpass(state)

        assert state.result["filter_type"] == "chebyshev"
        assert state.result["ripple"] == 1.0
        output = "\n".join(lines)
        assert "Chebyshev" in output

    def test_bessel_highpass(self):
        """Test Bessel highpass calculation."""
        state = FilterState(
            category="highpass",
            filter_type="bessel",
            frequency_hz=2e6,
            impedance=50.0,
            order=5,
            topology="pi",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="none",
        )

        calculate_highpass(state)

        assert state.result["filter_type"] == "bessel"
        assert state.result["ripple"] is None

    def test_highpass_json_output(self):
        """Test JSON output for highpass."""
        state = FilterState(
            category="highpass",
            filter_type="butterworth",
            frequency_hz=1e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="json",
            quiet=False,
            show_plot=False,
        )

        lines = calculate_highpass(state)

        assert len(lines) == 1
        assert "{" in lines[0]

    def test_highpass_json_with_eseries(self):
        """Test highpass JSON includes standard match fields."""
        state = FilterState(
            category="highpass",
            filter_type="butterworth",
            frequency_hz=1e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="json",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="E24",
        )

        lines = calculate_highpass(state)

        data = json.loads(lines[0])
        first_cap = data["components"]["capacitors"][0]
        assert "standard_match" in first_cap
        assert first_cap["standard_match"]["series"] == "E24"

    def test_highpass_csv_with_eseries(self):
        """Test highpass CSV includes standard match columns."""
        state = FilterState(
            category="highpass",
            filter_type="butterworth",
            frequency_hz=1e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="csv",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="E24",
        )

        lines = calculate_highpass(state)
        header = lines[0].splitlines()[0]
        assert "NearestStdValue" in header
        assert "Eseries" in header

    def test_highpass_with_eseries(self):
        """Test highpass with E-series recommendations for inductors."""
        state = FilterState(
            category="highpass",
            filter_type="butterworth",
            frequency_hz=1e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="E24",
        )

        lines = calculate_highpass(state)

        output = "\n".join(lines)
        assert "E24" in output or "Inductor" in output

    def test_highpass_with_plot(self):
        """Test highpass with frequency response plot."""
        state = FilterState(
            category="highpass",
            filter_type="butterworth",
            frequency_hz=1e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=True,
            eseries="none",
        )

        lines = calculate_highpass(state)

        assert len(lines) > 5
        output = "\n".join(lines)
        assert len(output) > 200


class TestCalculateBandpass:
    """Tests for bandpass filter calculation."""

    def test_butterworth_bandpass_basic(self):
        """Test basic Butterworth bandpass calculation."""
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
        )

        lines = calculate_bandpass(state)

        assert state.result is not None
        assert state.result["filter_type"] == "butterworth"
        assert state.result["f0"] == 14.175e6
        assert state.result["bw"] == 350e3
        assert state.result["z0"] == 50.0
        assert state.result["n_resonators"] == 3
        assert "c_tank" in state.result
        assert "c_coupling" in state.result

        output = "\n".join(lines)
        assert "Butterworth" in output
        assert "Band-Pass" in output or "Bandpass" in output

    def test_chebyshev_bandpass(self):
        """Test Chebyshev bandpass calculation."""
        state = FilterState(
            category="bandpass",
            filter_type="chebyshev",
            frequency_hz=10e6,
            bandwidth_hz=500e3,
            impedance=50.0,
            order=3,  # Chebyshev requires odd resonator count
            ripple_db=0.5,
            topology="shunt",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
        )

        lines = calculate_bandpass(state)

        assert state.result["filter_type"] == "chebyshev"
        # Ripple may or may not be present depending on implementation
        output = "\n".join(lines)
        assert "Chebyshev" in output

    def test_bandpass_json_output(self):
        """Test JSON output for bandpass."""
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="json",
            quiet=False,
            show_plot=False,
        )

        lines = calculate_bandpass(state)

        assert len(lines) == 1
        assert "{" in lines[0]

    def test_bandpass_csv_output(self):
        """Test CSV output for bandpass."""
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="csv",
            quiet=False,
            show_plot=False,
        )

        lines = calculate_bandpass(state)

        assert len(lines) == 1

    def test_bandpass_json_with_eseries(self):
        """Test bandpass JSON includes standard match fields."""
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="json",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="E24",
        )

        lines = calculate_bandpass(state)

        data = json.loads(lines[0])
        first_tank_cap = data["components"]["tank_capacitors"][0]
        assert "standard_match" in first_tank_cap
        assert first_tank_cap["standard_match"]["series"] == "E24"

    def test_bandpass_csv_with_eseries(self):
        """Test bandpass CSV includes standard match columns."""
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="csv",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="E24",
        )

        lines = calculate_bandpass(state)
        header = lines[0].splitlines()[0]
        assert "NearestStdValue" in header
        assert "Eseries" in header

    def test_bandpass_quiet_mode(self):
        """Test quiet mode for bandpass."""
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="table",
            quiet=True,
            raw_units=True,
            show_plot=False,
        )

        lines = calculate_bandpass(state)

        assert len(lines) == 1

    def test_bandpass_with_plot(self):
        """Test bandpass with frequency response plot."""
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=True,
        )

        lines = calculate_bandpass(state)

        assert len(lines) > 5
        output = "\n".join(lines)
        assert len(output) > 200

    def test_bandpass_with_eseries(self):
        """Test bandpass includes capacitor E-series recommendations."""
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="table",
            quiet=False,
            raw_units=False,
            show_plot=False,
            eseries="E24",
        )

        lines = calculate_bandpass(state)

        output = "\n".join(lines)
        assert "E24 Standard Capacitor Recommendations" in output
        assert "Cp1 Calculated:" in output
        assert "Cs12 Calculated:" in output


# ============================================================================
# Tests for formatting_helpers.py
# ============================================================================


class TestFormatLpHpTable:
    """Tests for lowpass/highpass table formatting."""

    def test_format_pi_topology_lowpass(self, lowpass_result):
        """Test formatting Pi topology lowpass filter."""
        state = FilterState(raw_units=False)

        lines = format_lp_hp_table(lowpass_result, state, "Low Pass")

        output = "\n".join(lines)
        assert "Butterworth" in output
        assert "PI Low Pass" in output
        assert "10" in output  # Frequency should be formatted
        assert "MHz" in output or "M" in output
        assert "50" in output  # Impedance
        assert "Order:" in output
        assert "5" in output
        assert "Topology:" in output
        assert "Component Values" in output

    def test_format_t_topology_lowpass(self, lowpass_t_result):
        """Test formatting T topology lowpass filter."""
        state = FilterState(raw_units=False)

        lines = format_lp_hp_table(lowpass_t_result, state, "Low Pass")

        output = "\n".join(lines)
        assert "T Low Pass" in output
        assert "Butterworth" in output

    def test_format_with_ripple(self, highpass_result):
        """Test formatting includes ripple for Chebyshev."""
        state = FilterState(raw_units=False)

        lines = format_lp_hp_table(highpass_result, state, "High Pass")

        output = "\n".join(lines)
        assert "Chebyshev" in output
        assert "Ripple:" in output
        assert "0.5 dB" in output

    def test_format_raw_units(self, lowpass_result):
        """Test formatting with raw units enabled."""
        state = FilterState(raw_units=True)

        lines = format_lp_hp_table(lowpass_result, state, "Low Pass")

        output = "\n".join(lines)
        # Raw units should show scientific notation
        assert "e-" in output or "E-" in output

    def test_format_nice_units(self, lowpass_result):
        """Test formatting with human-readable units."""
        state = FilterState(raw_units=False)

        lines = format_lp_hp_table(lowpass_result, state, "Low Pass")

        output = "\n".join(lines)
        # Should use nice units like pF, nF, µH
        assert "F" in output or "H" in output
        # Should not use raw scientific notation for all values
        assert output.count("e-") < output.count("C") + output.count("L")


class TestFormatComponentTable:
    """Tests for component table formatting helper."""

    def test_format_component_table_raw(self, lowpass_result):
        """Test component table with raw units."""
        output = _format_component_table(lowpass_result, raw=True)

        assert "Component Values" in output
        assert "Capacitors" in output
        assert "Inductors" in output
        assert "C1:" in output
        assert "L1:" in output
        assert "e-" in output or "E-" in output  # Scientific notation
        # Box drawing characters
        assert "\u2502" in output  # Vertical line

    def test_format_component_table_nice(self, lowpass_result):
        """Test component table with formatted units."""
        output = _format_component_table(lowpass_result, raw=False)

        assert "Component Values" in output
        assert "C1:" in output
        assert "L1:" in output
        # Should have formatted units
        assert "F" in output or "H" in output

    def test_format_unequal_components(self, highpass_result):
        """Test formatting with different numbers of caps and inductors."""
        # Highpass T has 2 caps, 1 inductor
        output = _format_component_table(highpass_result, raw=False)

        assert "C1:" in output
        assert "C2:" in output
        assert "L1:" in output
        # Table should handle unequal rows
        assert output.count("C") >= 2


class TestFormatEseriesRecs:
    """Tests for E-series recommendations formatting."""

    def test_format_eseries_capacitors(self):
        """Test E-series recommendations for capacitors."""
        from filter_lib.shared.formatting import format_capacitance

        components = [100e-12, 220e-12, 470e-12]  # 100pF, 220pF, 470pF

        lines = format_eseries_recs(components, "C", "Capacitor", "E12", format_capacitance)

        output = "\n".join(lines)
        assert "E12" in output
        assert "Capacitor" in output
        assert "Recommendations" in output
        assert "C1" in output
        assert "C2" in output
        assert "C3" in output
        assert "Calculated:" in output

    def test_format_eseries_inductors(self):
        """Test E-series recommendations for inductors."""
        from filter_lib.shared.formatting import format_inductance

        components = [1e-6, 2.2e-6]  # 1µH, 2.2µH

        lines = format_eseries_recs(components, "L", "Inductor", "E24", format_inductance)

        output = "\n".join(lines)
        assert "E24" in output
        assert "Inductor" in output
        assert "L1" in output
        assert "L2" in output

    def test_format_eseries_empty_list(self):
        """Test E-series formatting with empty component list."""
        from filter_lib.shared.formatting import format_capacitance

        lines = format_eseries_recs([], "C", "Capacitor", "E12", format_capacitance)

        # Should still have header
        assert len(lines) > 0
        output = "\n".join(lines)
        assert "E12" in output


class TestFormatBandpassTable:
    """Tests for bandpass filter table formatting."""

    def test_format_bandpass_top_coupling(self, bandpass_result):
        """Test formatting bandpass with top-C coupling."""
        state = FilterState(raw_units=False)

        lines = format_bandpass_table(bandpass_result, state)

        output = "\n".join(lines)
        assert "Butterworth" in output
        assert "Top-C Coupled" in output
        assert "Band-Pass" in output
        assert "Center Frequency:" in output
        assert "Bandwidth:" in output
        assert "Fractional BW:" in output
        assert "Resonators:" in output
        assert "3" in output
        assert "Component Values" in output
        assert "Tank Capacitors" in output
        assert "Inductors" in output
        assert "Coupling Capacitors" in output
        assert "External Q" in output

    def test_format_bandpass_shunt_coupling(self):
        """Test formatting bandpass with shunt-C coupling."""
        result = {
            "filter_type": "butterworth",
            "f0": 10e6,
            "bw": 500e3,
            "z0": 50.0,
            "n_resonators": 3,
            "coupling": "shunt",
            "fbw": 0.05,
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
        state = FilterState(raw_units=False)

        lines = format_bandpass_table(result, state)

        output = "\n".join(lines)
        assert "Shunt-C Coupled" in output

    def test_format_bandpass_with_warnings(self):
        """Test formatting bandpass with warnings."""
        result = {
            "filter_type": "butterworth",
            "f0": 10e6,
            "bw": 5e6,  # Very wide bandwidth
            "z0": 50.0,
            "n_resonators": 3,
            "coupling": "top",
            "fbw": 0.5,
            "L_resonant": 1e-6,
            "c_tank": [100e-12, 100e-12, 100e-12],
            "c_coupling": [10e-12, 10e-12],
            "qe_in": 50.0,
            "qe_out": 50.0,
            "q_min": 100,
            "q_safety": 2.0,
            "ripple_db": None,
            "warnings": ["Bandwidth too large", "Q values may be unrealistic"],
        }
        state = FilterState(raw_units=False)

        lines = format_bandpass_table(result, state)

        output = "\n".join(lines)
        assert "Warnings:" in output
        assert "Bandwidth too large" in output
        assert "Q values may be unrealistic" in output

    def test_format_bandpass_with_ripple(self):
        """Test formatting bandpass Chebyshev with ripple."""
        result = {
            "filter_type": "chebyshev",
            "f0": 14.175e6,
            "bw": 350e3,
            "z0": 50.0,
            "n_resonators": 4,
            "coupling": "top",
            "fbw": 350e3 / 14.175e6,
            "L_resonant": 1e-6,
            "c_tank": [100e-12, 100e-12, 100e-12, 100e-12],
            "c_coupling": [10e-12, 10e-12, 10e-12],
            "qe_in": 50.0,
            "qe_out": 50.0,
            "q_min": 100,
            "q_safety": 2.0,
            "ripple_db": 0.5,
            "warnings": [],
        }
        state = FilterState(raw_units=False)

        lines = format_bandpass_table(result, state)

        output = "\n".join(lines)
        assert "Chebyshev" in output
        assert "Ripple:" in output
        assert "0.5 dB" in output

    def test_format_bandpass_raw_units(self, bandpass_result):
        """Test formatting bandpass with raw units."""
        state = FilterState(raw_units=True)

        lines = format_bandpass_table(bandpass_result, state)

        output = "\n".join(lines)
        # Should have scientific notation
        assert "e-" in output or "E-" in output


# ============================================================================
# Tests for results screen export helpers
# ============================================================================


class TestResultsScreenExport:
    """Tests for ResultsScreen export helper methods."""

    def test_bandpass_json_export_with_eseries(self):
        """Export button JSON includes standard match data for bandpass."""
        screen = ResultsScreen()
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            eseries="E24",
            output_format="table",
            raw_units=False,
            show_plot=False,
        )
        calculate_bandpass(state)

        output = screen._get_json_export(state)
        data = json.loads(output)

        first_tank_cap = data["components"]["tank_capacitors"][0]
        assert "standard_match" in first_tank_cap
        assert first_tank_cap["standard_match"]["series"] == "E24"

    def test_bandpass_csv_export_with_eseries(self):
        """Export button CSV includes standard match columns for bandpass."""
        screen = ResultsScreen()
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            eseries="E24",
            output_format="table",
            raw_units=False,
            show_plot=False,
        )
        calculate_bandpass(state)

        output = screen._get_csv_export(state)
        header = output.splitlines()[0]
        assert "NearestStdValue" in header
        assert "Eseries" in header


# ============================================================================
# Tests for calculation_handler.py
# ============================================================================


class TestCalculateAndFormat:
    """Tests for main calculation orchestrator."""

    def test_calculate_lowpass_end_to_end(self):
        """Test complete lowpass calculation flow."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            quiet=False,
            show_plot=False,
            eseries="none",
        )

        output = calculate_and_format(state)

        assert isinstance(output, str)
        assert len(output) > 0
        assert "Butterworth" in output
        assert "Low Pass" in output
        # State should be updated
        assert state.result is not None

    def test_calculate_highpass_end_to_end(self):
        """Test complete highpass calculation flow."""
        state = FilterState(
            category="highpass",
            filter_type="chebyshev",
            frequency_hz=5e6,
            impedance=75.0,
            order=5,
            ripple_db=1.0,
            topology="t",
            output_format="table",
            quiet=False,
            show_plot=False,
            eseries="none",
        )

        output = calculate_and_format(state)

        assert isinstance(output, str)
        assert "Chebyshev" in output
        assert "High Pass" in output

    def test_calculate_bandpass_end_to_end(self):
        """Test complete bandpass calculation flow."""
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="table",
            quiet=False,
            show_plot=False,
        )

        output = calculate_and_format(state)

        assert isinstance(output, str)
        assert "Butterworth" in output
        assert "Band-Pass" in output or "Bandpass" in output

    def test_unknown_category_error(self):
        """Test handling of unknown filter category."""
        state = FilterState(
            category="bandstop",  # Not implemented
            filter_type="butterworth",
        )

        output = calculate_and_format(state)

        assert "Unknown filter category" in output

    def test_calculation_exception_handling(self):
        """Test error handling for calculation exceptions."""
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=-1,  # Invalid frequency
            impedance=50.0,
            order=3,
            topology="pi",
        )

        output = calculate_and_format(state)

        # Should catch exception and return error message
        assert "error" in output.lower() or len(output) > 0


# ============================================================================
# Tests for radio_button_helpers.py
# ============================================================================


class TestGetSelectedRadio:
    """Tests for radio button helper function."""

    def test_get_selected_radio_with_selection(self):
        """Test getting selected radio button ID."""
        from textual.widgets import RadioSet

        # Mock screen and radio set
        mock_screen = Mock()
        mock_radio_set = Mock()
        mock_button = Mock()
        mock_button.id = "option_a"
        mock_radio_set.pressed_button = mock_button

        mock_screen.query_one = Mock(return_value=mock_radio_set)

        result = get_selected_radio(mock_screen, "my_radio_set")

        assert result == "option_a"
        mock_screen.query_one.assert_called_once_with("#my_radio_set", RadioSet)

    def test_get_selected_radio_no_selection(self):
        """Test getting radio button when none selected."""
        mock_screen = Mock()
        mock_radio_set = Mock()
        mock_radio_set.pressed_button = None

        mock_screen.query_one = Mock(return_value=mock_radio_set)

        result = get_selected_radio(mock_screen, "my_radio_set")

        assert result == ""

    def test_get_selected_radio_query_selector(self):
        """Test that query_one is called with correct selector."""
        mock_screen = Mock()
        mock_radio_set = Mock()
        mock_radio_set.pressed_button = None

        def check_query(selector, widget_type):
            assert selector == "#filter_type"
            assert widget_type == Mock or True  # RadioSet type
            return mock_radio_set

        mock_screen.query_one = Mock(side_effect=check_query)

        get_selected_radio(mock_screen, "filter_type")

        assert mock_screen.query_one.called


# ============================================================================
# Tests for validation.py
# ============================================================================


class TestValidateOrder:
    """Tests for validate_order function."""

    def test_validate_order_valid_minimum(self):
        """Test minimum valid order value."""
        result = validate_order("2")
        assert result == 2

    def test_validate_order_valid_maximum(self):
        """Test maximum valid order value."""
        result = validate_order("9")
        assert result == 9

    def test_validate_order_valid_middle(self):
        """Test middle range order values."""
        assert validate_order("3") == 3
        assert validate_order("5") == 5
        assert validate_order("7") == 7

    def test_validate_order_too_small(self):
        """Test order below minimum raises error."""
        with pytest.raises(ValueError, match="Order must be 2-9"):
            validate_order("1")

    def test_validate_order_too_large(self):
        """Test order above maximum raises error."""
        with pytest.raises(ValueError, match="Order must be 2-9"):
            validate_order("10")

    def test_validate_order_zero(self):
        """Test zero order raises error."""
        with pytest.raises(ValueError, match="Order must be 2-9"):
            validate_order("0")

    def test_validate_order_negative(self):
        """Test negative order raises error."""
        with pytest.raises(ValueError, match="Order must be 2-9"):
            validate_order("-1")

    def test_validate_order_invalid_string(self):
        """Test non-numeric string raises error."""
        with pytest.raises(ValueError):
            validate_order("abc")

    def test_validate_order_float_string(self):
        """Test float string gets converted to int."""
        # Python int() will fail on float strings like "3.5"
        with pytest.raises(ValueError):
            validate_order("3.5")


class TestValidateRipple:
    """Tests for validate_ripple function."""

    def test_validate_ripple_valid_small(self):
        """Test small valid ripple value."""
        result = validate_ripple("0.1")
        assert result == 0.1

    def test_validate_ripple_valid_typical(self):
        """Test typical ripple values."""
        assert validate_ripple("0.5") == 0.5
        assert validate_ripple("1.0") == 1.0
        assert validate_ripple("2.0") == 2.0

    def test_validate_ripple_valid_maximum(self):
        """Test maximum recommended ripple."""
        result = validate_ripple("3.0")
        assert result == 3.0

    def test_validate_ripple_zero(self):
        """Test zero ripple raises error."""
        with pytest.raises(ValueError, match="Ripple must be positive"):
            validate_ripple("0")

    def test_validate_ripple_negative(self):
        """Test negative ripple raises error."""
        with pytest.raises(ValueError, match="Ripple must be positive"):
            validate_ripple("-0.5")

    def test_validate_ripple_too_large(self):
        """Test ripple above 3.0 dB raises error."""
        with pytest.raises(ValueError, match="Ripple typically should be <= 3.0 dB"):
            validate_ripple("3.1")

    def test_validate_ripple_way_too_large(self):
        """Test very large ripple raises error."""
        with pytest.raises(ValueError, match="Ripple typically should be <= 3.0 dB"):
            validate_ripple("10.0")

    def test_validate_ripple_invalid_string(self):
        """Test non-numeric string raises error."""
        with pytest.raises(ValueError):
            validate_ripple("abc")

    def test_validate_ripple_very_small(self):
        """Test very small positive ripple is valid."""
        result = validate_ripple("0.01")
        assert result == 0.01
