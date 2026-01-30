"""Tests for display formatting modules."""
import json
import pytest
from io import StringIO
import sys

from filter_lib.shared.display_common import (
    format_json_result, format_csv_result, format_quiet_result,
    print_header, print_component_table,
)
from filter_lib.shared.topology_diagrams import (
    _build_line, print_pi_topology_diagram, print_t_topology_diagram,
)
from filter_lib.lowpass.display import (
    format_json, format_csv, format_quiet, display_results as lp_display,
    _primary_component as lp_primary,
)
from filter_lib.highpass.display import (
    format_json as hp_format_json,
    format_csv as hp_format_csv,
    format_quiet as hp_format_quiet,
    display_results as hp_display,
    _primary_component as hp_primary,
)


@pytest.fixture
def lowpass_result():
    """Sample lowpass filter result."""
    return {
        'filter_type': 'butterworth',
        'freq_hz': 10e6,
        'impedance': 50.0,
        'order': 5,
        'capacitors': [1e-10, 2e-10, 1e-10],  # 100pF, 200pF, 100pF
        'inductors': [1e-6, 1e-6],  # 1uH, 1uH
        'ripple': None,
        'topology': 'pi',
    }


@pytest.fixture
def highpass_result():
    """Sample highpass T filter result (series C, shunt L)."""
    return {
        'filter_type': 'chebyshev',
        'freq_hz': 1e6,
        'impedance': 75.0,
        'order': 3,
        'capacitors': [5e-10, 5e-10],  # 500pF series caps (odd positions)
        'inductors': [2e-6],  # 2uH shunt inductor (even position)
        'ripple': 0.5,
        'topology': 't',
    }


@pytest.fixture
def lowpass_t_result():
    """Sample lowpass T topology result (inductors primary)."""
    return {
        'filter_type': 'butterworth',
        'freq_hz': 10e6,
        'impedance': 50.0,
        'order': 5,
        'inductors': [1e-6, 1e-6, 1e-6],
        'capacitors': [1e-10, 2e-10],
        'ripple': None,
        'topology': 't',
    }


@pytest.fixture
def highpass_pi_result():
    """Sample highpass Pi result (shunt L at odd, series C at even)."""
    return {
        'filter_type': 'butterworth',
        'freq_hz': 1e6,
        'impedance': 75.0,
        'order': 3,
        'inductors': [2e-6, 2e-6],  # shunt inductors (odd positions)
        'capacitors': [5e-10],  # series capacitor (even position)
        'ripple': None,
        'topology': 'pi',
    }


class TestFormatJsonResult:
    """Tests for JSON formatting."""

    def test_lowpass_json_structure(self, lowpass_result):
        """JSON output has correct structure for lowpass."""
        output = format_json_result(lowpass_result, primary_component='capacitors')
        data = json.loads(output)

        assert data['filter_type'] == 'butterworth'
        assert data['cutoff_frequency_hz'] == 10e6
        assert data['impedance_ohms'] == 50.0
        assert data['order'] == 5
        assert 'components' in data
        assert 'capacitors' in data['components']
        assert 'inductors' in data['components']

    def test_highpass_json_structure(self, highpass_result):
        """JSON output has correct structure for highpass."""
        output = format_json_result(highpass_result, primary_component='inductors')
        data = json.loads(output)

        assert data['filter_type'] == 'chebyshev'
        assert data['ripple_db'] == 0.5
        assert 'inductors' in data['components']

    def test_capacitor_values_in_json(self, lowpass_result):
        """Capacitor values are correctly formatted in JSON."""
        output = format_json_result(lowpass_result, primary_component='capacitors')
        data = json.loads(output)

        caps = data['components']['capacitors']
        assert len(caps) == 3
        assert caps[0]['name'] == 'C1'
        assert caps[0]['value_farads'] == 1e-10

    def test_inductor_values_in_json(self, lowpass_result):
        """Inductor values are correctly formatted in JSON."""
        output = format_json_result(lowpass_result, primary_component='capacitors')
        data = json.loads(output)

        inds = data['components']['inductors']
        assert len(inds) == 2
        assert inds[0]['name'] == 'L1'
        assert inds[0]['value_henries'] == 1e-6


class TestFormatCsvResult:
    """Tests for CSV formatting."""

    def test_csv_header(self, lowpass_result):
        """CSV has correct header."""
        output = format_csv_result(lowpass_result, primary_component='capacitors')
        lines = output.strip().split('\n')
        assert lines[0] == 'Component,Value,Unit'

    def test_csv_capacitors_first_for_lowpass(self, lowpass_result):
        """Lowpass CSV lists capacitors before inductors."""
        output = format_csv_result(lowpass_result, primary_component='capacitors')
        lines = output.strip().split('\n')

        # After header, C1, C2, C3 should come before L1, L2
        assert lines[1].startswith('C1,')
        assert lines[2].startswith('C2,')
        assert lines[3].startswith('C3,')
        assert lines[4].startswith('L1,')
        assert lines[5].startswith('L2,')

    def test_csv_capacitors_first_for_highpass_t(self, highpass_result):
        """Highpass T CSV lists capacitors before inductors (caps are primary)."""
        output = format_csv_result(highpass_result, primary_component='capacitors')
        lines = output.strip().split('\n')

        # After header, C1, C2 should come before L1
        assert lines[1].startswith('C1,')
        assert lines[2].startswith('C2,')
        assert lines[3].startswith('L1,')

    def test_csv_values_formatted(self, lowpass_result):
        """CSV values use engineering notation units."""
        output = format_csv_result(lowpass_result, primary_component='capacitors')
        lines = output.strip().split('\n')

        # C1 = 100pF should show pF unit
        parts = lines[1].split(',')
        assert parts[0] == 'C1'
        assert 'pF' in parts[2] or 'nF' in parts[2]


class TestFormatQuietResult:
    """Tests for quiet/minimal output formatting."""

    def test_quiet_output_lines(self, lowpass_result):
        """Quiet output has one line per component."""
        output = format_quiet_result(lowpass_result, raw=False, primary_component='capacitors')
        lines = output.strip().split('\n')

        # 3 capacitors + 2 inductors = 5 lines
        assert len(lines) == 5

    def test_quiet_output_format(self, lowpass_result):
        """Quiet output has component name and value."""
        output = format_quiet_result(lowpass_result, raw=False, primary_component='capacitors')
        lines = output.strip().split('\n')

        assert lines[0].startswith('C1')
        assert lines[3].startswith('L1')

    def test_quiet_raw_format(self, lowpass_result):
        """Raw mode shows SI notation."""
        output = format_quiet_result(lowpass_result, raw=True, primary_component='capacitors')

        # Raw mode should show scientific notation
        assert 'e' in output.lower() or 'E' in output


class TestLowpassDisplay:
    """Tests for lowpass-specific display wrappers."""

    def test_format_json_wrapper(self, lowpass_result):
        """Lowpass format_json uses capacitors as primary."""
        output = format_json(lowpass_result)
        data = json.loads(output)

        # Should have capacitors in components
        assert 'capacitors' in data['components']

    def test_format_csv_wrapper(self, lowpass_result):
        """Lowpass format_csv uses capacitors as primary."""
        output = format_csv(lowpass_result)
        lines = output.strip().split('\n')

        # Capacitors should come first
        assert lines[1].startswith('C1,')

    def test_format_quiet_wrapper(self, lowpass_result):
        """Lowpass format_quiet uses capacitors as primary."""
        output = format_quiet(lowpass_result, raw=False)

        # C1 should appear before L1
        c1_pos = output.find('C1')
        l1_pos = output.find('L1')
        assert c1_pos < l1_pos


class TestHighpassDisplay:
    """Tests for highpass-specific display wrappers."""

    def test_format_json_wrapper(self, highpass_result):
        """Highpass format_json uses inductors as primary."""
        output = hp_format_json(highpass_result)
        data = json.loads(output)

        # Should have inductors in components
        assert 'inductors' in data['components']

    def test_format_csv_wrapper(self, highpass_result):
        """Highpass T format_csv uses capacitors as primary."""
        output = hp_format_csv(highpass_result)
        lines = output.strip().split('\n')

        # HPF T: capacitors (series) are primary → listed first
        assert lines[1].startswith('C1,')

    def test_format_quiet_wrapper(self, highpass_result):
        """Highpass T format_quiet uses capacitors as primary."""
        output = hp_format_quiet(highpass_result, raw=False)

        # C1 should appear before L1
        c1_pos = output.find('C1')
        l1_pos = output.find('L1')
        assert c1_pos < l1_pos


class TestPrintFunctions:
    """Tests for print_header and print_component_table."""

    def test_print_header_output(self, lowpass_result, capsys):
        """print_header outputs correct information."""
        print_header(lowpass_result, topology='Pi', filter_category='Low Pass')
        captured = capsys.readouterr()

        assert 'Butterworth' in captured.out
        assert 'Pi' in captured.out
        assert 'Low Pass' in captured.out
        assert '10' in captured.out  # frequency
        assert '50' in captured.out  # impedance
        assert 'Order' in captured.out

    def test_print_header_with_ripple(self, highpass_result, capsys):
        """print_header shows ripple for Chebyshev."""
        print_header(highpass_result, topology='T', filter_category='High Pass')
        captured = capsys.readouterr()

        assert 'Chebyshev' in captured.out
        assert 'Ripple' in captured.out
        assert '0.5' in captured.out

    def test_print_component_table_output(self, lowpass_result, capsys):
        """print_component_table formats table correctly."""
        print_component_table(lowpass_result, raw=False, primary_component='capacitors')
        captured = capsys.readouterr()

        assert 'Capacitors' in captured.out
        assert 'Inductors' in captured.out
        assert 'C1' in captured.out
        assert 'L1' in captured.out

    def test_print_component_table_raw_mode(self, lowpass_result, capsys):
        """print_component_table shows scientific notation in raw mode."""
        print_component_table(lowpass_result, raw=True, primary_component='capacitors')
        captured = capsys.readouterr()

        # Raw mode should show 'e' for scientific notation
        assert 'e' in captured.out.lower() or 'E' in captured.out


class TestBuildLine:
    """Tests for _build_line helper in topology_diagrams."""

    def test_single_element_centered(self):
        """Single element placed at correct position."""
        result = _build_line([10], ['X'], 20)
        assert result[10] == 'X'
        assert len(result) == 20

    def test_multiple_elements(self):
        """Multiple elements placed at correct positions."""
        result = _build_line([5, 15], ['AB', 'CD'], 20)
        # AB centered at 5: starts at 4
        assert result[4:6] == 'AB'
        # CD centered at 15: starts at 14
        assert result[14:16] == 'CD'

    def test_empty_positions(self):
        """No elements produces blank line."""
        result = _build_line([], [], 10)
        assert result == ' ' * 10

    def test_wide_element(self):
        """Wide element like 'GND' centered correctly."""
        result = _build_line([10], ['GND'], 20)
        assert 'GND' in result

    def test_boundary_clipping(self):
        """Elements near boundary don't cause index error."""
        # Element at position 0 - part may clip
        result = _build_line([0], ['ABC'], 5)
        assert len(result) == 5


class TestPrintPiTopologyDiagram:
    """Tests for Pi topology ASCII diagram rendering."""

    def test_pi_3cap_2ind(self, capsys):
        """Pi diagram with 3 capacitors and 2 inductors (n=5)."""
        print_pi_topology_diagram(3, 2)
        out = capsys.readouterr().out

        assert 'IN' in out
        assert 'OUT' in out
        assert 'L1' in out
        assert 'L2' in out
        assert 'C1' in out
        assert 'C2' in out
        assert 'C3' in out
        assert out.count('GND') == 3

    def test_pi_2cap_1ind(self, capsys):
        """Pi diagram with 2 capacitors and 1 inductor (n=3)."""
        print_pi_topology_diagram(2, 1)
        out = capsys.readouterr().out

        assert 'L1' in out
        assert 'C1' in out
        assert 'C2' in out
        assert 'L2' not in out
        assert out.count('GND') == 2

    def test_pi_2cap_2ind(self, capsys):
        """Pi diagram with equal caps and inductors (n=4)."""
        print_pi_topology_diagram(2, 2)
        out = capsys.readouterr().out

        assert 'L1' in out
        assert 'L2' in out
        assert 'C1' in out
        assert 'C2' in out

    def test_pi_diagram_has_branch_points(self, capsys):
        """Pi diagram has branch points for shunt elements."""
        print_pi_topology_diagram(3, 2)
        out = capsys.readouterr().out
        # Branch points (┬) for each capacitor
        first_line = out.split('\n')[0]
        assert first_line.count('┬') == 3


class TestPrintTTopologyDiagram:
    """Tests for T topology ASCII diagram rendering."""

    def test_t_3ind_2cap(self, capsys):
        """T diagram with 3 series and 2 shunt elements (n=5)."""
        print_t_topology_diagram(3, 2)
        out = capsys.readouterr().out

        assert 'IN' in out
        assert 'OUT' in out
        assert 'L1' in out
        assert 'L2' in out
        assert 'L3' in out
        assert 'C1' in out
        assert 'C2' in out
        assert out.count('GND') == 2

    def test_t_2ind_1cap(self, capsys):
        """T diagram with 2 series and 1 shunt (n=3)."""
        print_t_topology_diagram(2, 1)
        out = capsys.readouterr().out

        assert 'L1' in out
        assert 'L2' in out
        assert 'C1' in out
        assert 'C2' not in out

    def test_t_2ind_2cap(self, capsys):
        """T diagram with equal series and shunt (n=4)."""
        print_t_topology_diagram(2, 2)
        out = capsys.readouterr().out

        assert 'L1' in out
        assert 'L2' in out
        assert 'C1' in out
        assert 'C2' in out

    def test_t_diagram_has_branch_points(self, capsys):
        """T diagram has branch points for shunt elements."""
        print_t_topology_diagram(3, 2)
        out = capsys.readouterr().out
        first_line = out.split('\n')[0]
        assert first_line.count('┬') == 2


class TestPrimaryComponent:
    """Tests for _primary_component helpers in display modules."""

    def test_lowpass_pi_primary_is_capacitors(self):
        assert lp_primary({'topology': 'pi'}) == 'capacitors'

    def test_lowpass_t_primary_is_inductors(self):
        assert lp_primary({'topology': 't'}) == 'inductors'

    def test_lowpass_default_is_capacitors(self):
        """Lowpass defaults to pi (capacitors) when topology missing."""
        assert lp_primary({}) == 'capacitors'

    def test_highpass_t_primary_is_capacitors(self):
        """HPF T: series caps are primary."""
        assert hp_primary({'topology': 't'}) == 'capacitors'

    def test_highpass_pi_primary_is_inductors(self):
        """HPF Pi: shunt inductors are primary."""
        assert hp_primary({'topology': 'pi'}) == 'inductors'

    def test_highpass_default_is_capacitors(self):
        """Highpass defaults to t (capacitors) when topology missing."""
        assert hp_primary({}) == 'capacitors'


class TestDisplayResultsTopology:
    """Tests for display_results with different topologies."""

    def test_lowpass_pi_display(self, lowpass_result, capsys):
        """LPF Pi display shows Pi diagram and capacitor recommendations."""
        lp_display(lowpass_result, show_plot=False, show_match=True)
        out = capsys.readouterr().out

        assert 'Low Pass' in out
        assert 'PI' in out
        assert 'Capacitor Recommendations' in out

    def test_lowpass_t_display(self, lowpass_t_result, capsys):
        """LPF T display shows T diagram and capacitor recommendations."""
        lp_display(lowpass_t_result, show_plot=False, show_match=True)
        out = capsys.readouterr().out

        assert 'Low Pass' in out
        assert 'Capacitor Recommendations' in out

    def test_highpass_t_display(self, highpass_result, capsys):
        """HPF T display shows T diagram and capacitor recommendations."""
        hp_display(highpass_result, show_plot=False, show_match=True)
        out = capsys.readouterr().out

        assert 'High Pass' in out
        assert 'Capacitor Recommendations' in out

    def test_highpass_pi_display(self, highpass_pi_result, capsys):
        """HPF Pi display shows Pi diagram and capacitor recommendations."""
        hp_display(highpass_pi_result, show_plot=False, show_match=True)
        out = capsys.readouterr().out

        assert 'High Pass' in out
        assert 'Capacitor Recommendations' in out

    def test_lowpass_pi_json_format(self, lowpass_result, capsys):
        """LPF Pi JSON output works via display_results."""
        lp_display(lowpass_result, output_format='json')
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data['topology'] == 'pi'

    def test_lowpass_t_csv_format(self, lowpass_t_result, capsys):
        """LPF T CSV lists inductors first."""
        lp_display(lowpass_t_result, output_format='csv')
        out = capsys.readouterr().out
        lines = out.strip().split('\n')
        assert lines[1].startswith('L1,')

    def test_lowpass_t_quiet_format(self, lowpass_t_result, capsys):
        """LPF T quiet mode lists inductors first."""
        lp_display(lowpass_t_result, quiet=True)
        out = capsys.readouterr().out
        l1_pos = out.find('L1')
        c1_pos = out.find('C1')
        assert l1_pos < c1_pos

    def test_highpass_pi_json_format(self, highpass_pi_result, capsys):
        """HPF Pi JSON output includes topology."""
        hp_display(highpass_pi_result, output_format='json')
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data['topology'] == 'pi'

    def test_display_no_match_raw(self, lowpass_result, capsys):
        """Display with raw=True skips E-series matching."""
        lp_display(lowpass_result, raw=True, show_match=True)
        out = capsys.readouterr().out
        assert 'Recommendations' not in out
