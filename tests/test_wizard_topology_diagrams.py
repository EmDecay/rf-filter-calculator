"""Tests for topology diagram formatting functions."""

from filter_lib.bandpass.diagrams import format_shunt_c_diagram, format_top_c_diagram
from filter_lib.shared.topology_diagrams import (
    format_pi_topology_diagram,
    format_t_topology_diagram,
)


class TestPiTopologyDiagram:
    """Tests for Pi topology diagram formatting."""

    def test_basic_3_element(self):
        """Test basic 3-element Pi diagram."""
        result = format_pi_topology_diagram(2, 1)
        assert "IN" in result
        assert "OUT" in result
        assert "L1" in result
        assert "C1" in result
        assert "C2" in result
        assert "GND" in result

    def test_5_element(self):
        """Test 5-element Pi diagram."""
        result = format_pi_topology_diagram(3, 2)
        assert "L1" in result
        assert "L2" in result
        assert "C1" in result
        assert "C2" in result
        assert "C3" in result

    def test_custom_labels(self):
        """Test Pi diagram with custom labels."""
        result = format_pi_topology_diagram(2, 1, series_label="X", shunt_label="Y")
        assert "X1" in result
        assert "Y1" in result
        assert "Y2" in result

    def test_returns_string(self):
        """Test that function returns a string."""
        result = format_pi_topology_diagram(2, 1)
        assert isinstance(result, str)
        assert "\n" in result


class TestTTopologyDiagram:
    """Tests for T topology diagram formatting."""

    def test_basic_3_element(self):
        """Test basic 3-element T diagram."""
        result = format_t_topology_diagram(2, 1)
        assert "IN" in result
        assert "OUT" in result
        assert "L1" in result
        assert "L2" in result
        assert "C1" in result
        assert "GND" in result

    def test_5_element(self):
        """Test 5-element T diagram."""
        result = format_t_topology_diagram(3, 2)
        assert "L1" in result
        assert "L2" in result
        assert "L3" in result
        assert "C1" in result
        assert "C2" in result

    def test_custom_labels(self):
        """Test T diagram with custom labels."""
        result = format_t_topology_diagram(2, 1, series_label="X", shunt_label="Y")
        assert "X1" in result
        assert "X2" in result
        assert "Y1" in result

    def test_returns_string(self):
        """Test that function returns a string."""
        result = format_t_topology_diagram(2, 1)
        assert isinstance(result, str)
        assert "\n" in result


class TestTopCDiagram:
    """Tests for Top-C bandpass diagram formatting."""

    def test_3_resonators(self):
        """Test 3-resonator Top-C diagram."""
        result = format_top_c_diagram(3)
        assert "IN" in result
        assert "OUT" in result
        # Tank components
        assert "Cp1" in result
        assert "L1" in result
        assert "Cp2" in result
        assert "L2" in result
        assert "Cp3" in result
        assert "L3" in result
        # Coupling capacitors
        assert "Cs12" in result
        assert "Cs23" in result
        assert "GND" in result

    def test_5_resonators(self):
        """Test 5-resonator Top-C diagram."""
        result = format_top_c_diagram(5)
        assert "Cp5" in result
        assert "L5" in result
        assert "Cs45" in result

    def test_returns_string(self):
        """Test that function returns a string."""
        result = format_top_c_diagram(3)
        assert isinstance(result, str)
        assert "\n" in result


class TestShuntCDiagram:
    """Tests for Shunt-C bandpass diagram formatting."""

    def test_3_resonators(self):
        """Test 3-resonator Shunt-C diagram."""
        result = format_shunt_c_diagram(3)
        assert "IN" in result
        assert "OUT" in result
        # Tank components
        assert "Cp1" in result
        assert "L1" in result
        assert "Cp2" in result
        assert "L2" in result
        assert "Cp3" in result
        assert "L3" in result
        # Coupling capacitors
        assert "Cs12" in result
        assert "Cs23" in result
        assert "GND" in result

    def test_4_resonators(self):
        """Test 4-resonator Shunt-C diagram."""
        result = format_shunt_c_diagram(4)
        assert "Cp4" in result
        assert "L4" in result
        assert "Cs34" in result

    def test_returns_string(self):
        """Test that function returns a string."""
        result = format_shunt_c_diagram(3)
        assert isinstance(result, str)
        assert "\n" in result
