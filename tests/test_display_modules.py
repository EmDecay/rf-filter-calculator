"""Tests for display formatting modules."""
import json
import pytest
from io import StringIO
import sys

from filter_lib.shared.display_common import (
    format_json_result, format_csv_result, format_quiet_result,
    print_header, print_component_table,
)
from filter_lib.lowpass.display import format_json, format_csv, format_quiet
from filter_lib.highpass.display import (
    format_json as hp_format_json,
    format_csv as hp_format_csv,
    format_quiet as hp_format_quiet,
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
    }


@pytest.fixture
def highpass_result():
    """Sample highpass filter result."""
    return {
        'filter_type': 'chebyshev',
        'freq_hz': 1e6,
        'impedance': 75.0,
        'order': 3,
        'inductors': [2e-6, 2e-6],  # 2uH, 2uH
        'capacitors': [5e-10],  # 500pF
        'ripple': 0.5,
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

    def test_csv_inductors_first_for_highpass(self, highpass_result):
        """Highpass CSV lists inductors before capacitors."""
        output = format_csv_result(highpass_result, primary_component='inductors')
        lines = output.strip().split('\n')

        # After header, L1, L2 should come before C1
        assert lines[1].startswith('L1,')
        assert lines[2].startswith('L2,')
        assert lines[3].startswith('C1,')

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
        """Highpass format_csv uses inductors as primary."""
        output = hp_format_csv(highpass_result)
        lines = output.strip().split('\n')

        # Inductors should come first
        assert lines[1].startswith('L1,')

    def test_format_quiet_wrapper(self, highpass_result):
        """Highpass format_quiet uses inductors as primary."""
        output = hp_format_quiet(highpass_result, raw=False)

        # L1 should appear before C1
        l1_pos = output.find('L1')
        c1_pos = output.find('C1')
        assert l1_pos < c1_pos


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
