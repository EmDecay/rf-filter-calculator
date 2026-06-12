"""Tests for wizard state management."""

from filter_lib.wizard.state import FilterState


class TestFilterState:
    """Tests for FilterState dataclass."""

    def test_default_values(self):
        """Test FilterState has correct default values."""
        state = FilterState()
        assert state.category == ""
        assert state.filter_type == "butterworth"
        assert state.topology == "pi"
        assert state.frequency_hz == 0.0
        assert state.bandwidth_hz == 0.0
        assert state.impedance == 50.0
        assert state.order == 3
        assert state.ripple_db == 0.5
        assert state.eseries == "E24"
        assert state.output_format == "table"
        assert state.show_plot is True
        assert state.export_format is None
        assert state.raw_units is False
        assert state.quiet is False
        assert state.result == {}
        assert state.output_text == ""

    def test_state_mutation(self):
        """Test FilterState can be mutated."""
        state = FilterState()
        state.category = "lowpass"
        state.filter_type = "chebyshev"
        state.frequency_hz = 10e6
        state.impedance = 75.0
        state.order = 5
        state.ripple_db = 1.0

        assert state.category == "lowpass"
        assert state.filter_type == "chebyshev"
        assert state.frequency_hz == 10e6
        assert state.impedance == 75.0
        assert state.order == 5
        assert state.ripple_db == 1.0
