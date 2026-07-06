"""Tests for the E-series matched-value simulation (--sim-matched)."""

import json

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
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


class TestSimulatePair:
    def test_bp_matched_metrics_sane(self):
        """BP 10 MHz / 500 kHz / n=3 / E24: matched response lands near design."""
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")
        summary = run_matched_simulation(result, "bandpass", "E24")

        assert summary.exact.f0 == pytest.approx(10e6, rel=0.01)
        assert summary.exact.bw == pytest.approx(0.5e6, rel=0.03)
        # Matched circuit stays within a few percent of the exact one
        assert summary.matched.f0 == pytest.approx(summary.exact.f0, rel=0.02)
        assert summary.matched.bw == pytest.approx(summary.exact.bw, rel=0.10)
        assert summary.matched.f_low < summary.matched.f_high
        assert not summary.matched.at_grid_edge

    def test_lp_e96_cutoff_close_to_exact(self):
        """LP n=5 E96: fine series keeps the matched cutoff within ~2%."""
        summary = run_matched_simulation(_lp_result(order=5), "lowpass", "E96")
        exact_cut = summary.exact.f_high
        matched_cut = summary.matched.f_high
        assert exact_cut == pytest.approx(10e6, rel=0.01)
        assert matched_cut == pytest.approx(exact_cut, rel=0.02)


class TestDisplayBlock:
    def test_bp_block_shows_edges_and_deltas(self):
        result = calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")
        summary = run_matched_simulation(result, "bandpass", "E24")
        text = "\n".join(format_matched_sim_block(summary))
        for label in ("Center f0:", "-3 dB BW:", "Lower edge:", "Upper edge:", "%"):
            assert label in text
        assert "inductors kept exact" in text

    def test_lp_block_shows_cutoff(self):
        summary = run_matched_simulation(_lp_result(), "lowpass", "E24")
        text = "\n".join(format_matched_sim_block(summary))
        assert "-3 dB cutoff:" in text
        assert "Worst passband dev:" in text

    def test_no_passband_fallback_message(self):
        """A matched circuit with no clear passband gets guidance, not a crash."""
        good = CircuitMeasurement(9.7e6, 10.2e6, -3.0, False)
        bad = CircuitMeasurement(None, None, -60.0, False)
        summary = MatchedSimSummary("bandpass", "E24", good, bad)
        text = "\n".join(format_matched_sim_block(summary))
        assert "does not exhibit a clear passband" in text

    def test_delta_blank_when_a_side_is_unmeasurable(self):
        """No delta is rendered against a missing or zero reference."""
        assert _fmt_delta_pct(None, 1.0) == ""
        assert _fmt_delta_pct(1.0, None) == ""
        assert _fmt_delta_pct(0.0, 1.0) == ""

    def test_grid_edge_fallback_message(self):
        good = CircuitMeasurement(9.7e6, 10.2e6, -3.0, False)
        detuned = CircuitMeasurement(9.0e6, 11.0e6, -3.0, True)
        summary = MatchedSimSummary("bandpass", "E24", good, detuned)
        text = "\n".join(format_matched_sim_block(summary))
        assert "does not exhibit a clear passband" in text


class TestCliWiring:
    def test_lp_sim_matched_prints_block(self, capsys):
        _lp = _lp_args(quiet=False, no_match=False, sim_matched=True)
        from filter_lib.cli.lowpass_cmd import run as lowpass_run

        lowpass_run(_lp)
        assert "Matched-Value Simulation" in capsys.readouterr().out

    def test_hp_sim_matched_prints_block(self, capsys):
        _hp = _hp_args(quiet=False, no_match=False, sim_matched=True)
        from filter_lib.cli.highpass_cmd import run as highpass_run

        highpass_run(_hp)
        assert "Matched-Value Simulation" in capsys.readouterr().out

    def test_bp_sim_matched_prints_block(self, capsys):
        _bp = _bp_args(quiet=False, no_match=False, sim_matched=True)
        from filter_lib.cli.bandpass_cmd import run as bandpass_run

        bandpass_run(_bp)
        assert "Matched-Value Simulation" in capsys.readouterr().out

    @pytest.mark.parametrize("maker", [_lp_args, _hp_args, _bp_args])
    def test_sim_matched_with_no_match_is_usage_error(self, maker, capsys):
        from filter_lib.cli.bandpass_cmd import run as bandpass_run
        from filter_lib.cli.highpass_cmd import run as highpass_run
        from filter_lib.cli.lowpass_cmd import run as lowpass_run

        runner = {_lp_args: lowpass_run, _hp_args: highpass_run, _bp_args: bandpass_run}[maker]
        with pytest.raises(SystemExit) as exc_info:
            runner(maker(no_match=True, sim_matched=True, quiet=False))
        assert exc_info.value.code == 2
        assert "--sim-matched requires E-series matching" in capsys.readouterr().err

    @pytest.mark.parametrize("maker", [_lp_args, _hp_args])
    def test_conflict_also_caught_on_plot_data_path(self, maker, capsys):
        """The flag conflict is a usage error in every output mode, including
        --plot-data, which returns before normal display."""
        from filter_lib.cli.highpass_cmd import run as highpass_run
        from filter_lib.cli.lowpass_cmd import run as lowpass_run

        runner = {_lp_args: lowpass_run, _hp_args: highpass_run}[maker]
        with pytest.raises(SystemExit) as exc_info:
            runner(maker(no_match=True, sim_matched=True, quiet=False, plot_data="json"))
        assert exc_info.value.code == 2
        assert "--sim-matched requires E-series matching" in capsys.readouterr().err

    def test_bp_json_matched_sim_schema(self, capsys):
        _bp = _bp_args(quiet=False, no_match=False, sim_matched=True, format="json")
        from filter_lib.cli.bandpass_cmd import run as bandpass_run

        bandpass_run(_bp)
        payload = json.loads(capsys.readouterr().out)
        block = payload["matched_sim"]
        assert block["eseries"] == "E24"
        assert block["inductors"] == "exact"
        for side in ("exact", "matched"):
            for key in ("f_low_hz", "f_high_hz", "f0_hz", "bw_hz", "worst_passband_db"):
                assert key in block[side]

    def test_bp_json_without_flag_has_no_block(self, capsys):
        _bp = _bp_args(quiet=False, no_match=False, format="json")
        from filter_lib.cli.bandpass_cmd import run as bandpass_run

        bandpass_run(_bp)
        assert "matched_sim" not in json.loads(capsys.readouterr().out)


class TestJsonPayload:
    def test_payload_round_trips(self):
        summary = run_matched_simulation(_lp_result(), "lowpass", "E24")
        payload = matched_sim_json_payload(summary)
        assert json.loads(json.dumps(payload)) == payload

    def test_no_passband_measurement_serializes_none(self):
        m = CircuitMeasurement(None, None, -60.0, False)
        assert m.f0 is None
        assert m.bw is None
        summary = MatchedSimSummary("bandpass", "E24", m, m)
        payload = matched_sim_json_payload(summary)
        assert payload["matched"]["f0_hz"] is None
        assert payload["matched"]["bw_hz"] is None


class TestBestValueSelection:
    def test_exact_series_value_prefers_single(self):
        """A target already on the E24 grid keeps the single match (0% error
        cannot be strictly beaten by a parallel combo)."""
        match = match_component(100e-12, "E24", parallel_mode="additive")
        assert not match.prefers_parallel
        assert match.best_value == pytest.approx(100e-12)

    def test_off_grid_value_prefers_parallel(self):
        """318.31 pF: E24 single is +3.7%, 47||270 parallel is -0.4%."""
        match = match_component(318.31e-12, "E24", parallel_mode="additive")
        assert match.prefers_parallel
        assert match.best_value == pytest.approx(317e-12, rel=1e-6)
