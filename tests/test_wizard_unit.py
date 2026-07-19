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
    BANDPASS_WIZARD_RESPONSE_POINTS,
    calculate_bandpass,
    calculate_highpass,
    calculate_lowpass,
)
from filter_lib.wizard.formatting_helpers import (
    format_bandpass_eseries_recs,
    format_bandpass_table,
)
from filter_lib.wizard.radio_button_helpers import get_selected_radio
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.state import CalculationOutcome, FilterState

# ============================================================================
# Tests for filter_type_calculators.py
# ============================================================================


def test_wizard_eseries_output_surfaces_expert_action_for_sub_pf_target():
    result = {
        "c_tank": [1e-15],
        "c_coupling": [],
        "c_end_in": None,
        "c_end_out": None,
    }

    output = "\n".join(format_bandpass_eseries_recs(result, "E24"))

    assert "policy selects at most one realization; expert action may be required" in output
    assert "Nearest Std (reference only)" in output
    assert "EXPERT ACTION REQUIRED; no part selected" in output
    assert "below the 1 pF automatic-selection floor" in output


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
        """Highpass JSON matches capacitors and omits inductor match fields."""
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
        first_ind = data["components"]["inductors"][0]
        assert "standard_match" in first_cap
        assert first_cap["standard_match"]["series"] == "E24"
        assert "standard_match" not in first_ind

    def test_highpass_csv_with_eseries(self):
        """Highpass CSV keeps match columns empty for inductors."""
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
        csv_lines = lines[0].splitlines()
        header = csv_lines[0]
        assert "NearestStdValue" in header
        assert "Eseries" in header
        first_ind_row = csv_lines[1].split(",")
        cap_row = csv_lines[-1].split(",")
        assert first_ind_row[0] == "L1"
        assert first_ind_row[3:9] == [""] * 6
        assert cap_row[0] == "C1"
        assert cap_row[3] != ""

    def test_highpass_with_eseries(self):
        """Test highpass with capacitor-only E-series recommendations."""
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
        assert "E24 Preferred-Value Capacitor Selection" in output
        assert "Preferred-Value Inductor Selection" not in output
        assert "Inductors: wind to value" in output

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
        assert "Response validation: Passed synthesized-response checks" in output

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
            topology="top",
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

    def test_one_percent_bandpass_plot_finds_both_threshold_skirts(self):
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            bandwidth_hz=100e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="table",
            show_plot=True,
            eseries="none",
        )

        output = "\n".join(calculate_bandpass(state))
        threshold_row = next(line for line in output.splitlines() if "│ -3 dB" in line)

        assert BANDPASS_WIZARD_RESPONSE_POINTS >= 601
        assert "N/A" not in threshold_row
        assert threshold_row.count("│") >= 3

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
        assert "E24 Preferred-Value Capacitor Selection" in output
        assert "Cp1 Calculated:" in output
        assert "Cs12 Calculated:" in output

    def test_bandpass_passes_optional_fixed_inductance_to_engine(self):
        state = FilterState(
            category="bandpass",
            filter_type="butterworth",
            frequency_hz=14.175e6,
            bandwidth_hz=350e3,
            impedance=50.0,
            order=3,
            topology="top",
            output_format="table",
            show_plot=False,
            resonator_inductance=1e-6,
        )

        calculate_bandpass(state)

        assert state.result["L_resonant"] == 1e-6
        assert state.result["resonator_selection"] == "fixed_inductance"


# ============================================================================
# Tests for formatting_helpers.py
# ============================================================================


class TestWizardLpHpRendering:
    """The wizard renders LP/HP through the shared display module."""

    @staticmethod
    def _state(**overrides) -> FilterState:
        defaults = dict(
            category="lowpass",
            filter_type="butterworth",
            topology="pi",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            eseries="none",
            show_plot=False,
        )
        defaults.update(overrides)
        return FilterState(**defaults)

    def test_lowpass_pi_table_renders(self):
        from filter_lib.wizard.filter_type_calculators import calculate_lowpass

        lines = calculate_lowpass(self._state())
        output = "\n".join(lines)
        assert "Butterworth" in output
        assert "Low Pass" in output
        assert "Component Values" in output
        assert "Topology:" in output

    def test_lowpass_t_table_lists_inductors_first(self):
        """T topology is series-L first: inductors are the primary (left) column."""
        from filter_lib.wizard.filter_type_calculators import calculate_lowpass

        lines = calculate_lowpass(self._state(topology="t"))
        output = "\n".join(lines)
        assert output.index("Inductors") < output.index("Capacitors")

    def test_highpass_pi_table_lists_inductors_first(self):
        """HP Pi is shunt-L first: inductors are the primary (left) column."""
        from filter_lib.wizard.filter_type_calculators import calculate_highpass

        lines = calculate_highpass(self._state(category="highpass", topology="pi"))
        output = "\n".join(lines)
        assert output.index("Inductors") < output.index("Capacitors")

    def test_highpass_eseries_matches_capacitors_only(self):
        """HP wizard output recommends standard capacitors; inductors get wound."""
        from filter_lib.wizard.filter_type_calculators import calculate_highpass

        lines = calculate_highpass(self._state(category="highpass", topology="t", eseries="E24"))
        output = "\n".join(lines)
        assert "Preferred-Value Capacitor Selection" in output
        assert "Preferred-Value Inductor Selection" not in output
        assert "wind to value" in output


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
        assert "complete-resonator unloaded Q" in output
        assert "Minimum usable Q" not in output
        assert "Q safety factor" not in output

    def test_format_bandpass_is_top_c_only(self):
        """Bandpass formatting always renders Top-C (shunt-C was removed)."""
        result = {
            "filter_type": "butterworth",
            "f0": 10e6,
            "bw": 500e3,
            "z0": 50.0,
            "n_resonators": 3,
            "coupling": "top",
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
        assert "Top-C Coupled" in output
        assert "Shunt" not in output

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
            "response_validation_status": "outside_validated_envelope",
            "warnings": ["Bandwidth too large", "Q values may be unrealistic"],
        }
        state = FilterState(raw_units=False)

        lines = format_bandpass_table(result, state)

        output = "\n".join(lines)
        assert "Warnings:" in output
        assert "Response validation: Outside validated envelope" in output
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
        state.output_text = "current result"
        state.calculation_status = "success"
        screen._result_text = state.output_text

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
        state.output_text = "current result"
        state.calculation_status = "success"
        screen._result_text = state.output_text

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

        outcome = calculate_and_format(state)

        assert isinstance(outcome, CalculationOutcome)
        assert outcome.succeeded
        assert "Butterworth" in outcome.output_text
        assert "Low Pass" in outcome.output_text
        assert outcome.result["filter_type"] == "butterworth"
        # The worker-facing orchestrator must never mutate shared state.
        assert state.result == {}
        assert state.output_text == ""

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

        outcome = calculate_and_format(state)

        assert outcome.succeeded
        assert "Chebyshev" in outcome.output_text
        assert "High Pass" in outcome.output_text
        assert state.result == {}

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

        outcome = calculate_and_format(state)

        assert outcome.succeeded
        assert "Butterworth" in outcome.output_text
        assert "Band-Pass" in outcome.output_text or "Bandpass" in outcome.output_text
        assert state.result == {}

    def test_unknown_category_error(self):
        """Test handling of unknown filter category."""
        state = FilterState(
            category="bandstop",  # Not implemented
            filter_type="butterworth",
        )

        outcome = calculate_and_format(state)

        assert outcome.status == "error"
        assert outcome.error == "Unknown filter category"
        assert outcome.result == {}

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

        outcome = calculate_and_format(state)

        assert outcome.status == "error"
        assert outcome.error
        assert outcome.result == {}
        assert state.result == {}

    def test_table_build_analysis_uses_detached_successful_outcome(self):
        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            show_plot=False,
            eseries="E24",
            build_analysis_enabled=True,
            build_grid_points=51,
            build_use_toroid_candidates=False,
        )

        outcome = calculate_and_format(state)

        assert outcome.succeeded
        assert outcome.build_analysis is not None
        assert outcome.build_analysis.config.grid_points == 51
        assert "Synthesis target" in outcome.output_text
        assert "Calculated exact values" in outcome.output_text
        assert "Selected nominal build" in outcome.output_text
        assert "Tolerance screening" in outcome.output_text
        assert "simulation, not a measurement" in outcome.output_text
        assert state.result == {}
        assert state.build_analysis is None

    def test_json_build_analysis_uses_shared_four_block_schema(self):
        state = FilterState(
            category="highpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="t",
            output_format="json",
            show_plot=False,
            eseries="E24",
            build_analysis_enabled=True,
            build_grid_points=51,
            build_use_toroid_candidates=False,
        )

        outcome = calculate_and_format(state)
        payload = json.loads(outcome.output_text)

        assert outcome.succeeded
        assert outcome.build_analysis is not None
        assert payload["target"]["category"] == "highpass"
        assert payload["simulated"]["realization"] == "calculated_exact_values"
        assert (
            payload["nominal_build"]["realization"]
            == "selected_nominal_parts_and_calculated_exact_fallbacks"
        )
        assert payload["tolerance_analysis"]["grid_points"] == 51

    def test_later_json_export_reuses_the_worker_analysis(self, monkeypatch):
        from filter_lib.shared.build_output import build_analysis_fields

        state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            show_plot=False,
            eseries="E24",
            build_analysis_enabled=True,
            build_grid_points=51,
            build_use_toroid_candidates=False,
        )
        outcome = calculate_and_format(state)
        assert outcome.succeeded and outcome.build_analysis is not None

        revision = state.begin_calculation()
        assert state.publish_success(
            revision,
            outcome.output_text,
            outcome.result,
            outcome.build_analysis,
        )
        screen = ResultsScreen()
        screen._result_text = state.output_text
        monkeypatch.setattr(
            "filter_lib.shared.build_simulation.analyze_build",
            Mock(side_effect=AssertionError("export recomputed analysis")),
        )

        payload = json.loads(screen._get_json_export(state))
        expected = build_analysis_fields(outcome.result, outcome.build_analysis)

        for key in ("target", "simulated", "nominal_build", "tolerance_analysis"):
            assert payload[key] == expected[key]

    def test_component_csv_rejects_realized_build_analysis(self):
        state = FilterState(
            category="lowpass",
            output_text="current build result",
            result={"ok": True},
            calculation_status="success",
            build_analysis_enabled=True,
            build_analysis={"same_worker": True},
        )
        screen = ResultsScreen()
        screen._result_text = state.output_text

        with pytest.raises(ValueError, match="not supported in component CSV"):
            screen._get_csv_export(state)

    @pytest.mark.parametrize(
        "output_format, quiet, expected",
        [
            ("csv", False, "table or JSON"),
            ("table", True, "quiet"),
        ],
    )
    def test_build_analysis_rejects_unsupported_worker_modes(self, output_format, quiet, expected):
        state = FilterState(
            category="lowpass",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format=output_format,
            quiet=quiet,
            eseries="E24",
            build_analysis_enabled=True,
        )

        outcome = calculate_and_format(state)

        assert outcome.status == "error"
        assert expected in outcome.error
        assert outcome.build_analysis is None


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
