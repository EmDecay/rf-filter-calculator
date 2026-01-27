"""Tests for bandpass modules: g_values, formatters, display, diagrams, calculations."""
import json
import pytest

from filter_lib.bandpass.g_values import (
    calculate_butterworth_g_values, get_chebyshev_g_values,
    get_bessel_g_values, get_g_values,
)
from filter_lib.bandpass.formatters import format_json, format_csv, format_quiet
from filter_lib.bandpass.display import display_results
from filter_lib.bandpass.diagrams import print_top_c_diagram, print_shunt_c_diagram
from filter_lib.bandpass.calculations import (
    calculate_bandpass_filter, calculate_min_q, _validate_inputs, _get_fbw_warnings,
)


def _make_result(**overrides):
    """Helper to create a bandpass filter result dict."""
    kwargs = dict(f0=14.175e6, bw=350e3, z0=50.0, n_resonators=3,
                  filter_type='butterworth', coupling='top')
    kwargs.update(overrides)
    return calculate_bandpass_filter(**kwargs)


# --- g_values ---

class TestGValues:
    def test_butterworth_order3(self):
        g = calculate_butterworth_g_values(3)
        assert len(g) == 3
        assert all(v > 0 for v in g)

    def test_chebyshev_valid(self):
        g = get_chebyshev_g_values(5, 0.5)
        assert len(g) == 5

    def test_chebyshev_invalid_ripple(self):
        with pytest.raises(ValueError, match="Ripple .* not supported"):
            get_chebyshev_g_values(3, 0.2)

    def test_chebyshev_even_order(self):
        with pytest.raises(ValueError, match="odd resonator count"):
            get_chebyshev_g_values(4, 0.5)

    def test_bessel_valid(self):
        g = get_bessel_g_values(5)
        assert len(g) == 5

    def test_bessel_invalid_order(self):
        with pytest.raises(ValueError, match="2-9 resonators"):
            get_bessel_g_values(10)

    def test_get_g_values_dispatch(self):
        assert len(get_g_values('butterworth', 4)) == 4
        assert len(get_g_values('chebyshev', 5, 1.0)) == 5
        assert len(get_g_values('bessel', 3)) == 3

    def test_get_g_values_unknown(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            get_g_values('invalid', 3)


# --- formatters ---

class TestFormatters:
    def test_format_json_structure(self):
        result = _make_result()
        output = format_json(result)
        data = json.loads(output)
        assert data['filter_type'] == 'butterworth'
        assert data['coupling'] == 'top'
        assert 'components' in data

    def test_format_json_with_ripple(self):
        result = _make_result(filter_type='chebyshev', n_resonators=5, ripple_db=0.5)
        data = json.loads(format_json(result))
        assert data['ripple_db'] == 0.5

    def test_format_csv_structure(self):
        output = format_csv(_make_result())
        assert 'Component,Value,Unit' in output
        assert 'Cp1' in output
        assert 'L1' in output
        assert 'Cs12' in output

    def test_format_quiet_formatted(self):
        output = format_quiet(_make_result(), raw=False)
        assert 'Cp1:' in output
        assert 'L1:' in output

    def test_format_quiet_raw(self):
        output = format_quiet(_make_result(), raw=True)
        assert 'e' in output.lower()  # scientific notation


# --- display ---

class TestDisplay:
    @pytest.fixture
    def sample_result(self):
        return _make_result()

    def test_display_json(self, sample_result, capsys):
        display_results(sample_result, output_format='json')
        data = json.loads(capsys.readouterr().out)
        assert data['filter_type'] == 'butterworth'

    def test_display_csv(self, sample_result, capsys):
        display_results(sample_result, output_format='csv')
        assert 'Component,Value,Unit' in capsys.readouterr().out

    def test_display_quiet(self, sample_result, capsys):
        display_results(sample_result, quiet=True)
        out = capsys.readouterr().out
        assert 'Cp1:' in out

    def test_display_table(self, sample_result, capsys):
        display_results(sample_result, output_format='table')
        out = capsys.readouterr().out
        assert 'Butterworth' in out

    def test_display_with_eseries(self, sample_result, capsys):
        display_results(sample_result, eseries='E12')
        assert 'E12' in capsys.readouterr().out

    def test_display_with_plot(self, sample_result, capsys):
        display_results(sample_result, show_plot=True)
        out = capsys.readouterr().out
        assert 'Butterworth' in out
        assert '│' in out

    def test_display_plot_data_json(self, sample_result, capsys):
        display_results(sample_result, plot_data='json')
        data = json.loads(capsys.readouterr().out)
        assert 'filter_type' in data

    def test_display_plot_data_csv(self, sample_result, capsys):
        display_results(sample_result, plot_data='csv')
        out = capsys.readouterr().out
        assert 'frequency_hz,magnitude_db' in out


# --- diagrams ---

class TestDiagrams:
    def test_top_c_3_resonators(self, capsys):
        print_top_c_diagram(3)
        out = capsys.readouterr().out
        assert 'IN' in out
        assert 'Cs12' in out
        assert 'GND' in out

    def test_top_c_5_resonators(self, capsys):
        print_top_c_diagram(5)
        assert 'Cs45' in capsys.readouterr().out

    def test_shunt_c_3_resonators(self, capsys):
        print_shunt_c_diagram(3)
        out = capsys.readouterr().out
        assert 'IN' in out
        assert 'Cs12' in out

    def test_shunt_c_4_resonators(self, capsys):
        print_shunt_c_diagram(4)
        assert 'Cs34' in capsys.readouterr().out


# --- calculations (extended) ---

class TestCalculationsExtended:
    def test_calculate_min_q(self):
        q = calculate_min_q(f0=14.175e6, bw=350e3, safety_factor=2.0)
        assert q == pytest.approx((14.175e6 / 350e3) * 2.0, rel=1e-6)

    def test_validate_negative_frequency(self):
        with pytest.raises(ValueError, match="Center frequency must be positive"):
            _validate_inputs(-1e6, 100e3, 50.0, 3, 'butterworth', 'top')

    def test_validate_negative_bandwidth(self):
        with pytest.raises(ValueError, match="Bandwidth must be positive"):
            _validate_inputs(14e6, -100e3, 50.0, 3, 'butterworth', 'top')

    def test_validate_bandwidth_too_wide(self):
        with pytest.raises(ValueError, match="Bandwidth must be less"):
            _validate_inputs(14e6, 15e6, 50.0, 3, 'butterworth', 'top')

    def test_validate_negative_impedance(self):
        with pytest.raises(ValueError, match="Impedance must be positive"):
            _validate_inputs(14e6, 100e3, -50.0, 3, 'butterworth', 'top')

    def test_validate_invalid_resonator_count(self):
        with pytest.raises(ValueError, match="between 2 and 9"):
            _validate_inputs(14e6, 100e3, 50.0, 10, 'butterworth', 'top')

    def test_validate_invalid_filter_type(self):
        with pytest.raises(ValueError, match="Filter type must be"):
            _validate_inputs(14e6, 100e3, 50.0, 3, 'invalid', 'top')

    def test_validate_invalid_coupling(self):
        with pytest.raises(ValueError, match="Coupling must be"):
            _validate_inputs(14e6, 100e3, 50.0, 3, 'butterworth', 'invalid')

    def test_fbw_warnings_shunt_high(self):
        warnings = _get_fbw_warnings(0.15, 'shunt')
        assert any('Shunt-C' in w for w in warnings)

    def test_fbw_warnings_very_wide(self):
        warnings = _get_fbw_warnings(0.45, 'top')
        assert len(warnings) > 0

    def test_bandpass_negative_tank_cap(self):
        with pytest.raises(ValueError, match="Bandwidth too wide"):
            calculate_bandpass_filter(
                f0=14.175e6, bw=10e6, z0=50.0, n_resonators=5,
                filter_type='butterworth', coupling='top')

    def test_bandpass_shunt_coupling(self):
        result = _make_result(coupling='shunt')
        assert result['coupling'] == 'shunt'

    def test_bandpass_chebyshev(self):
        result = _make_result(filter_type='chebyshev', n_resonators=5, ripple_db=0.5)
        assert result['filter_type'] == 'chebyshev'
        assert result['ripple_db'] == 0.5

    def test_bandpass_bessel(self):
        result = _make_result(filter_type='bessel')
        assert result['filter_type'] == 'bessel'
        assert result['ripple_db'] is None
