"""Coverage-gap tests for CLI entry point, setup parsers, wizard_cmd, cli_helpers,
and additional validation error paths in LP/HP/BP subcommands."""

from __future__ import annotations

import argparse
from argparse import Namespace
from unittest.mock import patch

import pytest

from filter_lib import cli
from filter_lib.cli import bandpass_cmd, highpass_cmd, lowpass_cmd, toroid_flags, wizard_cmd
from filter_lib.cli.bandpass_cmd import run as bandpass_run
from filter_lib.cli.highpass_cmd import run as highpass_run
from filter_lib.cli.lowpass_cmd import run as lowpass_run
from filter_lib.shared.cli_helpers import (
    add_common_filter_args,
    add_eseries_args,
    add_filter_type_args,
    add_output_args,
    add_plot_args,
    get_filter_type_arg,
)

# ---------------------------------------------------------------------------
# cli/__init__.py main() entry point
# ---------------------------------------------------------------------------


class TestCliMain:
    def test_main_dispatches_lowpass_alias(self, capsys):
        """`filter-calc lp bw pi 10MHz -n 3 --no-match -q --no-toroids` exits cleanly."""
        argv = [
            "filter-calc",
            "lp",
            "bw",
            "pi",
            "10MHz",
            "-n",
            "3",
            "--no-match",
            "-q",
            "--no-toroids",
        ]
        with patch("sys.argv", argv):
            cli.main()
        out = capsys.readouterr().out
        # Quiet mode still emits minimal output
        assert out

    def test_main_dispatches_highpass_alias(self, capsys):
        argv = [
            "filter-calc",
            "hp",
            "bw",
            "t",
            "10MHz",
            "-n",
            "3",
            "--no-match",
            "-q",
            "--no-toroids",
        ]
        with patch("sys.argv", argv):
            cli.main()
        assert capsys.readouterr().out

    def test_main_dispatches_bandpass_alias(self, capsys):
        argv = [
            "filter-calc",
            "bp",
            "bw",
            "top",
            "-f",
            "14.175MHz",
            "-b",
            "350kHz",
            "-n",
            "3",
            "--no-match",
            "-q",
            "--no-toroids",
        ]
        with patch("sys.argv", argv):
            cli.main()
        assert capsys.readouterr().out

    def test_main_no_command_runs_wizard(self):
        """When no subcommand is given, main() defers to run_wizard()."""
        argv = ["filter-calc"]
        with patch("sys.argv", argv), patch("filter_lib.wizard.run_wizard") as mock_wiz:
            cli.main()
        mock_wiz.assert_called_once()

    def test_main_value_error_exits_with_code_1(self, capsys):
        """A ValueError raised inside a subcommand is translated to sys.exit(1)."""
        argv = [
            "filter-calc",
            "lp",
            "bw",
            "pi",
            "10MHz",
            "-n",
            "3",
            "--no-match",
            "-q",
            "--no-toroids",
        ]
        with (
            patch("sys.argv", argv),
            patch.object(lowpass_cmd, "run", side_effect=ValueError("boom")),
        ):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "Error: boom" in err

    def test_main_keyboard_interrupt_exits_with_code_1(self, capsys):
        """KeyboardInterrupt produces a friendly 'Cancelled.' message and exits 1."""
        argv = ["filter-calc"]
        with (
            patch("sys.argv", argv),
            patch("filter_lib.wizard.run_wizard", side_effect=KeyboardInterrupt),
        ):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()
        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "Cancelled" in err


# ---------------------------------------------------------------------------
# setup_parser on each subcommand (exercises argparse wiring + toroid_flags)
# ---------------------------------------------------------------------------


class TestSetupParsers:
    def test_lowpass_setup_parser_accepts_expected_args(self):
        parser = argparse.ArgumentParser()
        lowpass_cmd.setup_parser(parser)
        args = parser.parse_args(
            [
                "butterworth",
                "pi",
                "10MHz",
                "-z",
                "75",
                "-n",
                "5",
                "-r",
                "0.5",
                "--format",
                "json",
                "--eseries",
                "E96",
                "--no-match",
                "--raw",
                "--quiet",
                "--plot",
                "--plot-data",
                "csv",
                "--no-toroids",
                "--toroid-compact",
            ]
        )
        assert args.filter_type == "butterworth"
        assert args.topology_pos == "pi"
        assert args.frequency == "10MHz"
        assert args.impedance == "75"
        assert args.components == 5
        assert args.ripple == 0.5
        assert args.format == "json"
        assert args.eseries == "E96"
        assert args.no_match
        assert args.raw
        assert args.quiet
        assert args.plot
        assert args.plot_data == "csv"
        assert args.no_toroids
        assert args.toroid_compact

    def test_highpass_setup_parser_accepts_flag_form(self):
        parser = argparse.ArgumentParser()
        highpass_cmd.setup_parser(parser)
        args = parser.parse_args(["-t", "ch", "--topology", "t", "-f", "10MHz", "-r", "1.0"])
        assert args.type_flag == "ch"
        assert args.topology_flag == "t"
        assert args.freq_flag == "10MHz"
        assert args.ripple == 1.0

    def test_bandpass_setup_parser_accepts_full_form(self):
        parser = argparse.ArgumentParser()
        bandpass_cmd.setup_parser(parser)
        args = parser.parse_args(
            [
                "butterworth",
                "top",
                "-f",
                "14MHz",
                "-b",
                "500kHz",
                "-z",
                "50",
                "-n",
                "5",
                "-r",
                "0.1",
                "--q-safety",
                "3.0",
                "--format",
                "csv",
                "-e",
                "E12",
                "--no-match",
                "--plot",
                "--plot-data",
                "json",
                "--verify",
                "--explain",
                "--raw",
                "--quiet",
                "--no-toroids",
                "--toroid-compact",
            ]
        )
        assert args.filter_type == "butterworth"
        assert args.coupling_pos == "top"
        assert args.frequency == "14MHz"
        assert args.bandwidth == "500kHz"
        assert args.resonators == 5
        assert args.q_safety == 3.0
        assert args.format == "csv"
        assert args.eseries == "E12"
        assert args.verify

    def test_bandpass_setup_parser_accepts_flag_coupling_and_type(self):
        parser = argparse.ArgumentParser()
        bandpass_cmd.setup_parser(parser)
        args = parser.parse_args(["-t", "ch", "-c", "shunt", "--fl", "14MHz", "--fh", "14.35MHz"])
        assert args.type_flag == "ch"
        assert args.coupling_flag == "shunt"
        assert args.f_low == "14MHz"
        assert args.f_high == "14.35MHz"

    def test_toroid_flags_direct_invocation(self):
        """add_toroid_flags can be attached to any parser and parses defaults."""
        parser = argparse.ArgumentParser()
        toroid_flags.add_toroid_flags(parser)
        args = parser.parse_args([])
        assert args.no_toroids is False
        assert args.toroid_compact is False
        args = parser.parse_args(["--no-toroids", "--toroid-compact"])
        assert args.no_toroids is True
        assert args.toroid_compact is True


# ---------------------------------------------------------------------------
# wizard_cmd: setup_parser no-op + run invokes run_wizard
# ---------------------------------------------------------------------------


class TestWizardCmd:
    def test_setup_parser_is_noop(self):
        parser = argparse.ArgumentParser()
        wizard_cmd.setup_parser(parser)  # nothing should blow up
        # Parser with no explicit args still accepts zero-arg invocation
        args = parser.parse_args([])
        assert isinstance(args, argparse.Namespace)

    def test_run_invokes_run_wizard(self):
        with patch("filter_lib.cli.wizard_cmd.run_wizard") as mock_wiz:
            wizard_cmd.run(argparse.Namespace())
        mock_wiz.assert_called_once()


# ---------------------------------------------------------------------------
# cli_helpers.py: exercise the argument-builder helpers
# ---------------------------------------------------------------------------


class TestCliHelperBuilders:
    def test_add_filter_type_args_lowpass_has_topology_pos(self):
        parser = argparse.ArgumentParser()
        add_filter_type_args(parser, "lowpass")
        args = parser.parse_args(["butterworth", "pi", "10MHz"])
        assert args.filter_type == "butterworth"
        assert args.topology_pos == "pi"
        assert args.frequency == "10MHz"

    def test_add_filter_type_args_highpass_has_topology_pos(self):
        parser = argparse.ArgumentParser()
        add_filter_type_args(parser, "highpass")
        args = parser.parse_args(["chebyshev", "t", "5MHz"])
        assert args.topology_pos == "t"

    def test_add_filter_type_args_bandpass_omits_topology(self):
        """Bandpass does not get positional topology, only filter_type + frequency."""
        parser = argparse.ArgumentParser()
        add_filter_type_args(parser, "bandpass")
        args = parser.parse_args(["bessel", "10MHz"])
        assert args.filter_type == "bessel"
        # bandpass shouldn't have topology_pos
        assert not hasattr(args, "topology_pos")

    def test_add_filter_type_args_flag_alternatives(self):
        parser = argparse.ArgumentParser()
        add_filter_type_args(parser, "lowpass")
        args = parser.parse_args(["-t", "bw", "-f", "1MHz", "--topology", "pi"])
        assert args.type_flag == "bw"
        assert args.freq_flag == "1MHz"
        assert args.topology_flag == "pi"

    def test_add_common_filter_args_defaults(self):
        parser = argparse.ArgumentParser()
        add_common_filter_args(parser)
        args = parser.parse_args([])
        # Defaults pulled from cli_aliases
        assert args.impedance  # non-empty default
        assert isinstance(args.components, int)
        assert isinstance(args.ripple, float)

    def test_add_output_args_defaults(self):
        parser = argparse.ArgumentParser()
        add_output_args(parser)
        args = parser.parse_args([])
        assert args.format == "table"
        assert args.raw is False
        assert args.quiet is False
        assert args.explain is False

    def test_add_eseries_args_defaults(self):
        parser = argparse.ArgumentParser()
        add_eseries_args(parser)
        args = parser.parse_args([])
        assert args.eseries  # default set
        assert args.no_match is False

    def test_add_plot_args_defaults(self):
        parser = argparse.ArgumentParser()
        add_plot_args(parser)
        args = parser.parse_args([])
        assert args.plot is False
        assert args.plot_data is None

    def test_get_filter_type_arg_prefers_positional(self):
        ns = Namespace(filter_type="butterworth", type_flag="chebyshev")
        assert get_filter_type_arg(ns) == "butterworth"

    def test_get_filter_type_arg_falls_back_to_flag(self):
        ns = Namespace(filter_type=None, type_flag="chebyshev")
        assert get_filter_type_arg(ns) == "chebyshev"

    def test_get_filter_type_arg_none_when_both_missing(self):
        ns = Namespace(filter_type=None, type_flag=None)
        assert get_filter_type_arg(ns) is None


# ---------------------------------------------------------------------------
# LP/HP: extra validation-error paths
# ---------------------------------------------------------------------------


def _lp_args(**overrides):
    defaults = dict(
        filter_type="butterworth",
        type_flag=None,
        frequency="10MHz",
        freq_flag=None,
        topology_pos="pi",
        topology_flag=None,
        impedance="50",
        components=3,
        ripple=0.5,
        raw=False,
        format="table",
        quiet=True,
        explain=False,
        eseries="E24",
        no_match=True,
        plot=False,
        plot_data=None,
        no_toroids=True,
        toroid_compact=False,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def _hp_args(**overrides):
    defaults = dict(
        filter_type="butterworth",
        type_flag=None,
        frequency="10MHz",
        freq_flag=None,
        topology_pos="t",
        topology_flag=None,
        impedance="50",
        components=3,
        ripple=0.5,
        raw=False,
        format="table",
        quiet=True,
        explain=False,
        eseries="E24",
        no_match=True,
        plot=False,
        plot_data=None,
        no_toroids=True,
        toroid_compact=False,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def _bp_args(**overrides):
    defaults = dict(
        filter_type="butterworth",
        type_flag=None,
        coupling_pos="top",
        coupling_flag=None,
        frequency="14.175MHz",
        bandwidth="350kHz",
        f_low=None,
        f_high=None,
        impedance="50",
        resonators=3,
        ripple=0.5,
        q_safety=2.0,
        raw=False,
        format="table",
        quiet=True,
        verify=False,
        explain=False,
        eseries="E24",
        no_match=True,
        plot=False,
        plot_data=None,
        no_toroids=True,
        toroid_compact=False,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


class TestLowpassExtraValidation:
    def test_explain_without_filter_type_raises(self):
        with pytest.raises(ValueError, match="Filter type required for --explain"):
            lowpass_run(_lp_args(filter_type=None, explain=True))

    def test_missing_frequency_raises(self):
        with pytest.raises(ValueError, match="Frequency required"):
            lowpass_run(_lp_args(frequency=None, freq_flag=None))

    def test_chebyshev_negative_ripple_raises(self):
        with pytest.raises(ValueError, match="Ripple must be positive"):
            lowpass_run(_lp_args(filter_type="chebyshev", ripple=-0.1, components=3))

    def test_freq_flag_used_when_positional_missing(self, capsys):
        lowpass_run(_lp_args(frequency=None, freq_flag="5MHz"))
        assert capsys.readouterr().out

    def test_topology_flag_used_when_positional_missing(self, capsys):
        lowpass_run(_lp_args(topology_pos=None, topology_flag="t"))
        assert capsys.readouterr().out


class TestHighpassExtraValidation:
    def test_explain_without_filter_type_raises(self):
        with pytest.raises(ValueError, match="Filter type required for --explain"):
            highpass_run(_hp_args(filter_type=None, explain=True))

    def test_missing_frequency_raises(self):
        with pytest.raises(ValueError, match="Frequency required"):
            highpass_run(_hp_args(frequency=None, freq_flag=None))

    def test_chebyshev_negative_ripple_raises(self):
        with pytest.raises(ValueError, match="Ripple must be positive"):
            highpass_run(_hp_args(filter_type="chebyshev", ripple=-0.5, components=3))

    def test_topology_flag_used_when_positional_missing(self, capsys):
        highpass_run(_hp_args(topology_pos=None, topology_flag="pi"))
        assert capsys.readouterr().out


class TestBandpassExtraValidation:
    def test_explain_without_filter_type_raises(self):
        with pytest.raises(ValueError, match="Filter type required for --explain"):
            bandpass_run(_bp_args(filter_type=None, explain=True))

    def test_missing_coupling_when_filter_type_given(self):
        with pytest.raises(ValueError, match="Coupling topology required"):
            bandpass_run(_bp_args(coupling_pos=None, coupling_flag=None))

    def test_coupling_flag_used_when_positional_missing(self, capsys):
        bandpass_run(_bp_args(coupling_pos=None, coupling_flag="top"))
        assert capsys.readouterr().out

    def test_shunt_coupling_positional_rejected_while_disabled(self):
        with pytest.raises(ValueError, match="Shunt-C coupling is temporarily disabled"):
            bandpass_run(_bp_args(coupling_pos="shunt"))

    def test_shunt_coupling_flag_rejected_while_disabled(self):
        with pytest.raises(ValueError, match="Shunt-C coupling is temporarily disabled"):
            bandpass_run(_bp_args(coupling_pos=None, coupling_flag="shunt"))

    def test_shunt_coupling_alias_rejected_while_disabled(self):
        with pytest.raises(ValueError, match="Shunt-C coupling is temporarily disabled"):
            bandpass_run(_bp_args(coupling_pos="s"))

    def test_type_flag_used_when_positional_missing(self, capsys):
        bandpass_run(_bp_args(filter_type=None, type_flag="bw"))
        assert capsys.readouterr().out

    def test_q_safety_non_positive_raises(self):
        with pytest.raises(ValueError, match="Q safety factor must be positive"):
            bandpass_run(_bp_args(q_safety=0))

    def test_q_safety_negative_raises(self):
        with pytest.raises(ValueError, match="Q safety factor must be positive"):
            bandpass_run(_bp_args(q_safety=-1.5))

    def test_chebyshev_even_resonators_raises(self):
        with pytest.raises(ValueError, match="Chebyshev requires odd resonator count"):
            bandpass_run(_bp_args(filter_type="chebyshev", resonators=4))

    def test_chebyshev_odd_resonators_accepted(self, capsys):
        bandpass_run(_bp_args(filter_type="chebyshev", resonators=3, ripple=0.1))
        assert capsys.readouterr().out

    def test_both_frequency_methods_raises(self):
        with pytest.raises(ValueError, match="not both"):
            bandpass_run(
                _bp_args(frequency="14MHz", bandwidth="1MHz", f_low="13MHz", f_high="15MHz")
            )

    def test_neither_frequency_method_raises(self):
        with pytest.raises(ValueError, match="Specify frequency"):
            bandpass_run(_bp_args(frequency=None, bandwidth=None, f_low=None, f_high=None))

    def test_fl_ge_fh_raises(self):
        with pytest.raises(ValueError, match="must be less than upper"):
            bandpass_run(_bp_args(frequency=None, bandwidth=None, f_low="15MHz", f_high="14MHz"))

    def test_fl_eq_fh_raises(self):
        with pytest.raises(ValueError, match="must be less than upper"):
            bandpass_run(_bp_args(frequency=None, bandwidth=None, f_low="14MHz", f_high="14MHz"))
