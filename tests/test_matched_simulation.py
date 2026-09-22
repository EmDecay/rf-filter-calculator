"""Compatibility contract for the deprecated ``--sim-matched`` facade.

``run_matched_simulation`` delegates to realized-build analysis; the build path
itself is covered in ``test_build_simulation.py``.  These tests keep a lean check
of the legacy surface: capacitor-only ``matched_result``, the deprecated summary
aliases, the legacy text block, the ``matched_sim`` JSON block, and CLI wiring.
"""

import json
from types import SimpleNamespace

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.cli.bandpass_cmd import run as bandpass_run
from filter_lib.cli.highpass_cmd import run as highpass_run
from filter_lib.cli.lowpass_cmd import run as lowpass_run
from filter_lib.lowpass.calculations import calculate_butterworth as lp_butterworth
from filter_lib.shared.eseries import match_component
from filter_lib.shared.matched_simulation import (
    CircuitMeasurement,
    MatchedSimSummary,
    _fmt_delta_pct,
    format_matched_sim_block,
    matched_result,
    matched_sim_json_payload,
    run_matched_simulation,
)
from tests.test_cli_and_helpers import _bp_args, _hp_args, _lp_args

# A two-resonator, 10% fractional-bandwidth design keeps the bandpass facade and CLI
# checks to a few screening cases while still exercising every bandpass branch.
_BP_CLI_DESIGN = {"frequency": "10MHz", "bandwidth": "1MHz", "resonators": 2, "eseries": "E96"}


def _lp_result(order: int = 5) -> dict:
    caps, inds, actual_order = lp_butterworth(10e6, 50.0, order, "pi")
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": caps,
        "inductors": inds,
        "order": actual_order,
        "ripple": None,
        "topology": "pi",
    }


def _rows(lines: list[str]) -> dict[str, list[str]]:
    """Map each ``Label: values`` row of the legacy block to its whitespace fields."""
    return {
        label.strip(): values.split()
        for label, sep, values in (line.partition(":") for line in lines)
        if sep
    }


class TestMatchedResult:
    def test_lp_caps_replaced_inductors_exact(self):
        result = _lp_result()
        matched = matched_result(result, "lowpass", "E24")
        assert matched["inductors"] == result["inductors"]
        for exact, m in zip(result["capacitors"], matched["capacitors"]):
            best = match_component(exact, "E24", parallel_mode="additive").best_value
            assert m == best
            assert m != exact  # E24 rounding actually moves the value

    def test_bp_all_cap_groups_replaced(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")
        matched = matched_result(result, "bandpass", "E24")
        assert matched["L_resonant"] == result["L_resonant"]
        for key in ("c_tank", "c_coupling"):
            assert all(m != e for m, e in zip(matched[key], result[key]))
        assert matched["c_end_in"] != result["c_end_in"]
        assert matched["c_end_out"] != result["c_end_out"]

    def test_original_result_not_mutated(self):
        result = _lp_result()
        before = list(result["capacitors"])
        matched_result(result, "lowpass", "E24")
        assert result["capacitors"] == before

    def test_unknown_category_rejected(self):
        with pytest.raises(ValueError, match="Unknown category"):
            matched_result(_lp_result(), "bandstop", "E24")


class TestRunMatchedSimulation:
    def test_bp_matched_metrics_sane(self):
        """BP 10 MHz / 1 MHz / n=2 / E96: the nominal response lands near the design."""
        result = calculate_bandpass_filter(10e6, 1e6, 50, 2, "butterworth", "top")
        bp_summary = run_matched_simulation(result, "bandpass", "E96")

        assert bp_summary.exact.f0 == pytest.approx(10e6, rel=0.01)
        assert bp_summary.exact.bw == pytest.approx(1e6, rel=0.03)
        # Nominal parts stay within a few percent of the calculated circuit
        assert bp_summary.matched.f0 == pytest.approx(bp_summary.exact.f0, rel=0.02)
        assert bp_summary.matched.bw == pytest.approx(bp_summary.exact.bw, rel=0.10)
        assert bp_summary.matched.f_low < bp_summary.matched.f_high
        assert not bp_summary.matched.at_grid_edge

    def test_lp_e96_cutoff_close_to_exact(self):
        """LP n=5 E96: fine series keeps the matched cutoff within ~2%."""
        summary = run_matched_simulation(_lp_result(order=5), "lowpass", "E96")
        exact_cut = summary.exact.f_high
        matched_cut = summary.matched.f_high
        assert exact_cut == pytest.approx(10e6, rel=0.01)
        assert matched_cut == pytest.approx(exact_cut, rel=0.02)

    def test_deprecated_wrapper_forwards_options_and_exposes_legacy_aliases(self, monkeypatch):
        captured = {}
        calculated = CircuitMeasurement(None, 1.0, -3.0, False)
        nominal = CircuitMeasurement(None, 2.0, -3.0, False)

        def fake_analyze_build(result, category, config):
            captured.update(result=result, category=category, config=config)
            return SimpleNamespace(calculated=calculated, nominal_build=nominal)

        monkeypatch.setattr(
            "filter_lib.shared.matched_simulation.analyze_build", fake_analyze_build
        )
        result = _lp_result()

        summary = run_matched_simulation(result, "lowpass", "E96", use_toroid_candidates=False)

        assert captured["result"] is result
        assert captured["category"] == "lowpass"
        assert captured["config"].eseries == "E96"
        assert captured["config"].use_toroid_candidates is False
        assert summary.exact is calculated
        assert summary.matched is nominal
        assert summary.calculated is summary.exact
        assert summary.nominal_build is summary.matched
        assert summary.deprecated is True
        assert summary.series == "E96"
        assert summary.uses_toroid_candidates is False


class TestDisplayBlock:
    def test_bandpass_block_reports_calculated_nominal_edges_and_deltas(self):
        exact = CircuitMeasurement(9.5e6, 10.5e6, -3.0, False)
        nominal = CircuitMeasurement(9.6e6, 10.4e6, -3.5, False)
        lines = format_matched_sim_block(MatchedSimSummary("bandpass", "E24", exact, nominal))

        assert "Nominal Build Simulation (legacy --sim-matched; E24)" in lines
        assert not any("inductors kept exact" in line for line in lines)
        rows = _rows(lines)
        # Geometric centers sqrt(9.5*10.5) and sqrt(9.6*10.4) MHz; BW 1 MHz -> 800 kHz.
        assert rows["Center f0"] == ["9.987", "MHz", "9.992", "MHz", "+0.05%"]
        assert rows["-3 dB BW"] == ["1", "MHz", "800", "kHz", "-20.00%"]
        assert rows["Lower edge"] == ["9.5", "MHz", "9.6", "MHz", "+1.05%"]
        assert rows["Upper edge"] == ["10.5", "MHz", "10.4", "MHz", "-0.95%"]
        assert rows["Worst passband dev"] == ["-3.00", "dB", "-3.50", "dB", "-0.50", "dB"]

    @pytest.mark.parametrize(
        "category, exact, nominal, expected_cutoff_row",
        [
            (
                "lowpass",
                CircuitMeasurement(None, 10e6, -3.0, False),
                CircuitMeasurement(None, 10.2e6, -3.1, False),
                ["10", "MHz", "10.2", "MHz", "+2.00%"],
            ),
            (
                "highpass",
                CircuitMeasurement(10e6, None, -3.0, False),
                CircuitMeasurement(9.9e6, None, -3.1, False),
                ["10", "MHz", "9.9", "MHz", "-1.00%"],
            ),
        ],
    )
    def test_ladder_block_reports_the_category_cutoff_edge(
        self, category, exact, nominal, expected_cutoff_row
    ):
        rows = _rows(format_matched_sim_block(MatchedSimSummary(category, "E24", exact, nominal)))

        assert rows["-3 dB cutoff"] == expected_cutoff_row
        assert rows["Worst passband dev"] == ["-3.00", "dB", "-3.10", "dB", "-0.10", "dB"]
        assert "Center f0" not in rows

    @pytest.mark.parametrize(
        "category, nominal",
        [
            ("bandpass", CircuitMeasurement(None, None, -60.0, False)),
            ("bandpass", CircuitMeasurement(9.0e6, 11.0e6, -3.0, True)),
            # Each ladder keeps only the opposite edge, so the required edge is category-specific.
            ("lowpass", CircuitMeasurement(9.0e6, None, -60.0, False)),
            ("highpass", CircuitMeasurement(None, 11.0e6, -60.0, False)),
        ],
        ids=["bandpass-no-edges", "bandpass-grid-edge", "lowpass-no-cutoff", "highpass-no-cutoff"],
    )
    def test_missing_nominal_passband_gets_guidance_not_a_table(self, category, nominal):
        calculated = CircuitMeasurement(9.7e6, 10.2e6, -3.0, False)
        lines = format_matched_sim_block(MatchedSimSummary(category, "E24", calculated, nominal))

        assert lines[-1] == (
            "Nominal build does not exhibit a clear passband on the simulated "
            "grid; try a finer E-series (e.g. E96)."
        )
        assert "Worst passband dev" not in _rows(lines)

    def test_unresolved_measurement_and_half_power_reference_are_disclosed(self):
        calculated = CircuitMeasurement(9.5e6, 10.5e6, -3.0, False, measurement_converged=False)
        nominal = CircuitMeasurement(
            9.6e6,
            10.4e6,
            -3.5,
            False,
            reference_peak_frequency_hz=10e6,
            reference_peak_gain_db=-0.1,
            threshold_regions=((9.6e6, 10.4e6),),
        )
        lines = format_matched_sim_block(MatchedSimSummary("bandpass", "E24", calculated, nominal))

        assert "Calculated: UNRESOLVED response measurement (refinement budget exhausted)" in lines
        assert "Nominal: UNRESOLVED response measurement (refinement budget exhausted)" not in lines
        assert (
            "Nominal half-power reference: -0.100 dB at 10000000 Hz; 1 connected region(s)" in lines
        )

    def test_delta_blank_when_a_side_is_unmeasurable(self):
        """No delta is rendered against a missing or zero reference."""
        assert _fmt_delta_pct(None, 1.0) == ""
        assert _fmt_delta_pct(1.0, None) == ""
        assert _fmt_delta_pct(0.0, 1.0) == ""


_LADDER_COMMANDS = pytest.mark.parametrize(
    "maker, runner",
    [(_lp_args, lowpass_run), (_hp_args, highpass_run)],
    ids=["lowpass", "highpass"],
)


class TestCliWiring:
    @_LADDER_COMMANDS
    def test_ladder_sim_matched_prints_cutoff_block_and_deprecation(self, maker, runner, capsys):
        runner(maker(quiet=False, no_match=False, sim_matched=True))

        captured = capsys.readouterr()
        assert "Nominal Build Simulation (legacy --sim-matched; E24)" in captured.out
        assert "-3 dB cutoff:" in captured.out
        assert "Warning: --sim-matched is deprecated; use --sim-build" in captured.err

    def test_bp_sim_matched_prints_block(self, capsys):
        bandpass_run(_bp_args(quiet=False, no_match=False, sim_matched=True, **_BP_CLI_DESIGN))

        captured = capsys.readouterr()
        assert "Nominal Build Simulation (legacy --sim-matched; E96)" in captured.out
        assert "Center f0:" in captured.out
        assert "Warning: --sim-matched is deprecated; use --sim-build" in captured.err

    @pytest.mark.parametrize(
        "maker, runner",
        [(_lp_args, lowpass_run), (_hp_args, highpass_run), (_bp_args, bandpass_run)],
        ids=["lowpass", "highpass", "bandpass"],
    )
    def test_sim_matched_with_no_match_is_usage_error(self, maker, runner, capsys):
        with pytest.raises(SystemExit) as exc_info:
            runner(maker(no_match=True, sim_matched=True, quiet=False))
        assert exc_info.value.code == 2
        error = capsys.readouterr().err
        assert "--sim-matched requires selected nominal capacitor values" in error
        assert "remove --no-match" in error

    @_LADDER_COMMANDS
    def test_plot_data_rejects_sim_matched(self, maker, runner, capsys):
        """--plot-data returns before normal display, so it refuses --sim-matched."""
        with pytest.raises(SystemExit) as exc_info:
            runner(maker(no_match=False, sim_matched=True, quiet=False, plot_data="json"))
        assert exc_info.value.code == 2
        error = capsys.readouterr().err
        assert "--plot-data is a standalone output mode; remove --sim-matched" in error

    def test_bp_json_matched_sim_schema(self, capsys):
        args = _bp_args(
            quiet=False,
            no_match=False,
            no_toroids=False,
            sim_matched=True,
            format="json",
            **_BP_CLI_DESIGN,
        )

        bandpass_run(args)

        block = json.loads(capsys.readouterr().out)["matched_sim"]
        assert block["eseries"] == "E96"
        assert block["deprecated"] is True
        assert block["replacement"] == "build_analysis"
        assert block["inductors"] == "verified_integer_turn_candidate_or_explicit_fallback"
        assert block["calculated"] == block["exact"]
        assert block["nominal_build"] == block["matched"]
        for side in ("exact", "matched"):
            measurement = block[side]
            assert measurement["f_low_hz"] < measurement["f0_hz"] < measurement["f_high_hz"]
            assert measurement["bw_hz"] == pytest.approx(
                measurement["f_high_hz"] - measurement["f_low_hz"]
            )
            assert measurement["worst_passband_db"] <= 0.0
            assert "cutoff_hz" not in measurement
        # The calculated design's requested edges sit at its half-power points.
        assert block["exact"]["worst_passband_db"] == pytest.approx(-3.01, abs=0.05)

    def test_bp_json_without_flag_has_no_block(self, capsys):
        bandpass_run(_bp_args(quiet=False, no_match=False, format="json"))
        assert "matched_sim" not in json.loads(capsys.readouterr().out)


class TestJsonPayload:
    def test_no_passband_measurement_serializes_none(self):
        m = CircuitMeasurement(None, None, -60.0, False)
        assert m.f0 is None
        assert m.bw is None
        summary = MatchedSimSummary("bandpass", "E24", m, m)
        payload = matched_sim_json_payload(summary)
        assert payload["matched"]["f0_hz"] is None
        assert payload["matched"]["bw_hz"] is None
