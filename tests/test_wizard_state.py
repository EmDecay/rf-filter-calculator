"""Tests for wizard state management."""

import pytest

from filter_lib.wizard.state import FilterState
from filter_lib.wizard.validation import validate_order, validate_ripple


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


class TestValidateOrder:
    """Tests for validate_order function."""

    def test_valid_orders(self):
        """Test valid order values."""
        assert validate_order("2") == 2
        assert validate_order("5") == 5
        assert validate_order("9") == 9

    def test_order_too_low(self):
        """Test order below minimum."""
        with pytest.raises(ValueError, match="Order must be 2-9"):
            validate_order("1")

    def test_order_too_high(self):
        """Test order above maximum."""
        with pytest.raises(ValueError, match="Order must be 2-9"):
            validate_order("10")

    def test_order_invalid_string(self):
        """Test non-numeric order."""
        with pytest.raises(ValueError):
            validate_order("abc")


class TestValidateRipple:
    """Tests for validate_ripple function."""

    def test_valid_ripple_values(self):
        """Test valid ripple values."""
        assert validate_ripple("0.1") == 0.1
        assert validate_ripple("0.5") == 0.5
        assert validate_ripple("1.0") == 1.0
        assert validate_ripple("2.5") == 2.5

    def test_ripple_zero(self):
        """Test zero ripple is invalid."""
        with pytest.raises(ValueError, match="must be positive"):
            validate_ripple("0")

    def test_ripple_negative(self):
        """Test negative ripple is invalid."""
        with pytest.raises(ValueError, match="must be positive"):
            validate_ripple("-0.5")

    def test_ripple_too_high(self):
        """Test ripple above typical maximum."""
        with pytest.raises(ValueError, match="typically should be"):
            validate_ripple("5.0")

    def test_ripple_invalid_string(self):
        """Test non-numeric ripple."""
        with pytest.raises(ValueError):
            validate_ripple("abc")
