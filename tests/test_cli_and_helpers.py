"""Tests for CLI commands, plotting, cli_helpers, and formatting modules."""
import json
import pytest
from argparse import Namespace
from unittest.mock import patch

from filter_lib.shared.cli_helpers import validate_filter_args, export_plot_data
from filter_lib.shared.plotting import (
    _format_freq_compact, _find_3db_frequency, render_ascii_plot,
    render_bandpass_plot, generate_frequency_points, export_json, export_csv,
)
from filter_lib.shared.formatting import (
    format_frequency, format_capacitance, format_inductance, format_impedance,
)
from filter_lib.cli.lowpass_cmd import run as lowpass_run
from filter_lib.cli.highpass_cmd import run as highpass_run
from filter_lib.cli.bandpass_cmd import run as bandpass_run


# --- cli_helpers ---

class TestCliHelpers:
    def test_validate_valid(self):
        validate_filter_args(10e6, 50, 5)

    def test_validate_negative_freq(self):
        with pytest.raises(ValueError, match="Frequency must be positive"):
            validate_filter_args(-10e6, 50, 5)

    def test_validate_zero_impedance(self):
        with pytest.raises(ValueError, match="Impedance must be positive"):
            validate_filter_args(10e6, 0, 5)

    def test_validate_invalid_components_low(self):
        with pytest.raises(ValueError, match="Components must be 2-9"):
            validate_filter_args(10e6, 50, 1)

    def test_validate_invalid_components_high(self):
        with pytest.raises(ValueError, match="Components must be 2-9"):
            validate_filter_args(10e6, 50, 10)

    def test_export_plot_data_json(self, capsys):
        args = Namespace(plot_data='json')
        exported = export_plot_data(
            args, [1e6], [-3.0], {'type': 'test'},
            lambda f, r, res: '{"test": true}',
            lambda f, r: 'csv'
        )
        assert exported is True
        assert 'test' in capsys.readouterr().out

    def test_export_plot_data_csv(self, capsys):
        args = Namespace(plot_data='csv')
        exported = export_plot_data(
            args, [1e6], [-3.0], {},
            lambda f, r, res: 'json',
            lambda f, r: 'freq,db\n1000000,-3.0'
        )
        assert exported is True

    def test_export_plot_data_none(self):
        args = Namespace(plot_data=None)
        assert export_plot_data(args, [], [], {}, None, None) is False


# --- plotting ---

class TestPlotting:
    def test_format_freq_compact_ghz(self):
        assert _format_freq_compact(2.4e9) == '2.4G'

    def test_format_freq_compact_mhz(self):
        assert _format_freq_compact(14.2e6) == '14.2M'

    def test_format_freq_compact_khz(self):
        assert _format_freq_compact(500e3) == '500k'

    def test_format_freq_compact_hz(self):
        assert _format_freq_compact(100) == '100'

    def test_find_3db_falling(self):
        freqs = [1e6, 10e6, 20e6, 30e6]
        resp = [-0.1, -0.5, -4.0, -10.0]
        f = _find_3db_frequency(freqs, resp, direction='falling')
        assert f is not None
        assert 10e6 < f < 20e6

    def test_find_3db_rising(self):
        freqs = [1e6, 10e6, 20e6, 30e6]
        resp = [-30.0, -10.0, -0.5, -0.1]
        f = _find_3db_frequency(freqs, resp, direction='rising')
        assert f is not None
        assert 10e6 < f < 20e6

    def test_find_3db_not_found(self):
        assert _find_3db_frequency([1e6, 10e6], [-0.1, -0.5], 'falling') is None

    def test_render_ascii_plot_basic(self):
        freqs = [1e6, 5e6, 10e6, 20e6, 50e6]
        resp = [-0.1, -0.5, -3.0, -10.0, -30.0]
        plot = render_ascii_plot(freqs, resp, 10e6, filter_type='lowpass')
        assert 'Frequency Response' in plot
        assert '│' in plot

    def test_render_ascii_plot_mismatched(self):
        with pytest.raises(ValueError, match="same length"):
            render_ascii_plot([1e6, 2e6], [-3.0], 1e6)

    def test_render_ascii_plot_empty(self):
        assert 'No data' in render_ascii_plot([], [], 1e6)

    def test_render_bandpass_plot(self):
        sweep = [(13e6, -30.0), (14e6, -3.0), (14.5e6, 0.0),
                 (15e6, -3.0), (16e6, -30.0)]
        plot = render_bandpass_plot(sweep, 14.5e6, 1e6)
        assert '│' in plot

    def test_render_bandpass_plot_empty(self):
        assert 'No data' in render_bandpass_plot([], 14e6, 1e6)

    def test_generate_frequency_points(self):
        pts = generate_frequency_points(10e6)
        assert len(pts) == 41  # 2 decades * 20 pts/decade + 1

    def test_generate_frequency_points_custom(self):
        pts = generate_frequency_points(1e6, decades=1.0, points_per_decade=10)
        assert len(pts) == 11

    def test_export_json_plotting(self):
        sweep = [(10e6, -3.0), (20e6, -10.0)]
        s = export_json(sweep, 15e6, 5e6, 'butterworth', 5)
        data = json.loads(s)
        assert data['filter_type'] == 'butterworth'
        assert data['f0_hz'] == 15e6

    def test_export_csv_plotting(self):
        sweep = [(10e6, -3.01), (20e6, -10.52)]
        csv_str = export_csv(sweep)
        lines = csv_str.split('\n')
        assert lines[0] == 'frequency_hz,magnitude_db'
        assert len(lines) == 3


# --- formatting ---

class TestFormatting:
    def test_format_frequency_ghz(self):
        assert 'GHz' in format_frequency(2.4e9)

    def test_format_frequency_mhz(self):
        assert 'MHz' in format_frequency(14.2e6)

    def test_format_frequency_khz(self):
        assert 'kHz' in format_frequency(500e3)

    def test_format_frequency_hz(self):
        assert 'Hz' in format_frequency(100)

    def test_format_capacitance_pf(self):
        assert 'pF' in format_capacitance(100e-12)

    def test_format_capacitance_nf(self):
        assert 'nF' in format_capacitance(10e-9)

    def test_format_inductance_nh(self):
        assert 'nH' in format_inductance(100e-9)

    def test_format_inductance_uh(self):
        assert 'µH' in format_inductance(10e-6)

    def test_format_impedance_ohm(self):
        assert 'Ω' in format_impedance(50)

    def test_format_impedance_kohm(self):
        assert 'kΩ' in format_impedance(1000)


# --- CLI commands ---

def _lp_args(**overrides):
    """Build lowpass CLI Namespace."""
    defaults = dict(
        filter_type='butterworth', type_flag=None,
        frequency='10MHz', freq_flag=None,
        topology_pos='pi', topology_flag=None,
        impedance='50', components=3, ripple=0.5,
        raw=False, format='table', quiet=True, explain=False,
        eseries='E24', no_match=True, plot=False, plot_data=None,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def _hp_args(**overrides):
    """Build highpass CLI Namespace."""
    defaults = dict(
        filter_type='butterworth', type_flag=None,
        frequency='10MHz', freq_flag=None,
        topology_pos='t', topology_flag=None,
        impedance='50', components=3, ripple=0.5,
        raw=False, format='table', quiet=True, explain=False,
        eseries='E24', no_match=True, plot=False, plot_data=None,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def _bp_args(**overrides):
    """Build bandpass CLI Namespace."""
    defaults = dict(
        filter_type='butterworth', type_flag=None,
        coupling_pos='top', coupling_flag=None,
        frequency='14.175MHz', bandwidth='350kHz',
        f_low=None, f_high=None,
        impedance='50', resonators=3, ripple=0.5, q_safety=2.0,
        raw=False, format='table', quiet=True, verify=False, explain=False,
        eseries='E24', no_match=True, plot=False, plot_data=None,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


class TestLowpassCmd:
    def test_butterworth_pi(self, capsys):
        lowpass_run(_lp_args())
        assert capsys.readouterr().out  # produces output

    def test_chebyshev_t(self, capsys):
        lowpass_run(_lp_args(filter_type='chebyshev', topology_pos='t'))
        assert capsys.readouterr().out

    def test_missing_filter_type(self):
        with pytest.raises(ValueError, match="Filter type required"):
            lowpass_run(_lp_args(filter_type=None))

    def test_missing_topology(self):
        with pytest.raises(ValueError, match="Topology required"):
            lowpass_run(_lp_args(topology_pos=None))

    def test_explain(self, capsys):
        lowpass_run(_lp_args(explain=True))
        assert capsys.readouterr().out

    def test_json_output(self, capsys):
        lowpass_run(_lp_args(format='json', quiet=False, no_match=True))
        data = json.loads(capsys.readouterr().out)
        assert 'capacitors' in data or 'filter_type' in data


class TestHighpassCmd:
    def test_butterworth_t(self, capsys):
        highpass_run(_hp_args())
        assert capsys.readouterr().out

    def test_missing_filter_type(self):
        with pytest.raises(ValueError, match="Filter type required"):
            highpass_run(_hp_args(filter_type=None))

    def test_missing_topology(self):
        with pytest.raises(ValueError, match="Topology required"):
            highpass_run(_hp_args(topology_pos=None))

    def test_explain(self, capsys):
        highpass_run(_hp_args(explain=True))
        assert capsys.readouterr().out


class TestBandpassCmd:
    def test_butterworth_top(self, capsys):
        bandpass_run(_bp_args())
        assert capsys.readouterr().out

    def test_missing_filter_type(self):
        with pytest.raises(ValueError, match="Filter type required"):
            bandpass_run(_bp_args(filter_type=None))

    def test_missing_coupling(self):
        with pytest.raises(ValueError, match="Coupling topology required"):
            bandpass_run(_bp_args(coupling_pos=None))

    def test_verify(self, capsys):
        bandpass_run(_bp_args(verify=True))
        assert 'passed' in capsys.readouterr().out.lower()

    def test_explain(self, capsys):
        bandpass_run(_bp_args(explain=True))
        assert capsys.readouterr().out

    def test_fl_fh_method(self, capsys):
        bandpass_run(_bp_args(frequency=None, bandwidth=None,
                              f_low='14MHz', f_high='14.35MHz'))
        assert capsys.readouterr().out
