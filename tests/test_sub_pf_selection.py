"""The opt-in sub-1 pF capacitor selection: ``--allow-sub-pf`` and ``DesignRequest.allow_sub_pf``.

Without the switch no part is chosen below 1 pF and every output says how to turn it on.
With it, the table, CSV, JSON, build simulation, and chosen-parts SPICE deck all pick the
same standard capacitors.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re

import pytest

from filter_lib.cli import bandpass_cmd, highpass_cmd, lowpass_cmd
from filter_lib.design import (
    DesignRequest,
    RenderOptions,
    design,
    export_spice,
    render_lines,
    with_build_analysis,
)
from filter_lib.design.design_service import apply_sub_pf_policy
from filter_lib.design.render_options import SUB_PF_NEEDS_ESERIES_MESSAGE
from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.eseries import (
    DEFAULT_MATCH_POLICY,
    SUB_PF_CLI_FLAG,
    SUB_PF_OPTION_LABEL,
    MatchPolicy,
)
from tests.cli_parity_helpers import cli_stderr, cli_stdout

# A 5 GHz 3-element Butterworth Pi low-pass has two 636.62 fF shunt capacitors.
SUB_PF_LOWPASS = ("lp", "bw", "pi", "5GHz", "-n", "3")
# A 500 MHz, 10 MHz wide bandpass has sub-pF coupling (90 fF) and end (909 fF) capacitors.
SUB_PF_BANDPASS = ("bp", "bw", "top", "-f", "500MHz", "-b", "10MHz")
SUB_PF_WARNING = (
    "Below 1 pF no part is chosen automatically. Choose one manually, or turn on "
    '"Allow capacitors below 1 pF" (--allow-sub-pf).'
)


def _request(**overrides) -> DesignRequest:
    fields = {
        "category": "lowpass",
        "filter_type": "butterworth",
        "topology": "pi",
        "frequency_hz": 5e9,
        "impedance": 50.0,
        "order": 3,
    }
    return DesignRequest(**{**fields, **overrides})


def _first_capacitor_match(document: str) -> dict:
    return json.loads(document)["components"]["capacitors"][0]["standard_match"]


class TestParser:
    @pytest.mark.parametrize(
        ("setup", "design_args"),
        [
            (lowpass_cmd.setup_parser, ["bw", "pi", "10MHz"]),
            (highpass_cmd.setup_parser, ["bw", "t", "10MHz"]),
            (bandpass_cmd.setup_parser, ["bw", "top", "-f", "10MHz", "-b", "1MHz"]),
        ],
        ids=["lowpass", "highpass", "bandpass"],
    )
    def test_flag_is_off_by_default_and_on_when_given(self, setup, design_args):
        parser = argparse.ArgumentParser()
        setup(parser)

        assert parser.parse_args(design_args).allow_sub_pf is False
        assert parser.parse_args([*design_args, SUB_PF_CLI_FLAG]).allow_sub_pf is True

    @pytest.mark.parametrize("command", ["lp", "hp", "bp"])
    def test_help_says_what_the_flag_does(self, monkeypatch, capsys, command):
        monkeypatch.setattr("sys.argv", ["filter-calc", command, "--help"])
        with pytest.raises(SystemExit):
            from filter_lib import cli

            cli.main()
        text = " ".join(capsys.readouterr().out.split())

        assert "--allow-sub-pf Also choose standard values for capacitors below 1 pF." in text


class TestDefaultChoosesNoSubPfPart:
    def test_table_names_both_ways_to_turn_selection_on(self, monkeypatch, capsys):
        out = cli_stdout(monkeypatch, capsys, *SUB_PF_LOWPASS, "--no-toroids")

        assert "  Use:            none (below 1 pF; see warning)" in out
        assert (
            "  Warning: Below 1 pF no part is chosen automatically. Choose one manually, or" in out
        )
        assert f'           turn on "{SUB_PF_OPTION_LABEL}" ({SUB_PF_CLI_FLAG}).' in out
        assert "expert" not in out.lower()

    def test_json_and_csv_keep_their_keys_and_report_the_policy(self, monkeypatch, capsys):
        match = _first_capacitor_match(
            cli_stdout(monkeypatch, capsys, *SUB_PF_LOWPASS, "--format", "json")
        )
        rows = list(
            csv.DictReader(
                io.StringIO(cli_stdout(monkeypatch, capsys, *SUB_PF_LOWPASS, "--format", "csv"))
            )
        )

        assert match["status"] == "expert_override_required"
        assert match["selected"] is None
        assert match["policy"]["allow_sub_pf"] is False
        assert match["warnings"] == [SUB_PF_WARNING]
        assert rows[0]["RecommendedStdKind"] == "none"
        assert rows[0]["RecommendationWarnings"] == SUB_PF_WARNING
        assert rows[0]["RecommendationPolicy"].endswith("minimum-cap=1pF")

    def test_build_and_spice_keep_the_calculated_value(self, monkeypatch, capsys):
        build = json.loads(
            cli_stdout(monkeypatch, capsys, *SUB_PF_LOWPASS, "--sim-build", "--format", "json")
        )
        deck = cli_stdout(monkeypatch, capsys, *SUB_PF_LOWPASS, "--format", "spice")

        substitution = build["nominal_build"]["substitutions"][0]
        assert substitution["method"] == "exact_fallback"
        assert SUB_PF_WARNING in substitution["warnings"]
        assert build["build_model"]["match_policy"]["allow_sub_pf"] is False
        # Once, naming the parts, as in the table's build block.
        assert deck.count(SUB_PF_WARNING) == 1
        assert f"* warning: C1, C2: {SUB_PF_WARNING}" in deck
        assert re.search(r"^C1 1 0 6\.36619772368e-13$", deck, re.M)


class TestFlagChoosesSubPfParts:
    def test_table_csv_json_build_and_spice_choose_the_same_parts(self, monkeypatch, capsys):
        table = cli_stdout(monkeypatch, capsys, *SUB_PF_LOWPASS, "--no-toroids", SUB_PF_CLI_FLAG)
        match = _first_capacitor_match(
            cli_stdout(monkeypatch, capsys, *SUB_PF_LOWPASS, "--format", "json", SUB_PF_CLI_FLAG)
        )
        row = next(
            csv.DictReader(
                io.StringIO(
                    cli_stdout(
                        monkeypatch, capsys, *SUB_PF_LOWPASS, "--format", "csv", SUB_PF_CLI_FLAG
                    )
                )
            )
        )
        build = json.loads(
            cli_stdout(
                monkeypatch,
                capsys,
                *SUB_PF_LOWPASS,
                "--sim-build",
                "--format",
                "json",
                SUB_PF_CLI_FLAG,
            )
        )
        deck = cli_stdout(
            monkeypatch, capsys, *SUB_PF_LOWPASS, "--format", "spice", SUB_PF_CLI_FLAG
        )

        assert "  Use:            75.00 fF || 560.00 fF (-0.3%)" in table
        assert "Warning" not in table
        assert match["status"] == "recommended"
        assert match["policy"]["allow_sub_pf"] is True
        assert [part["value_farads"] for part in match["selected"]["components"]] == [
            7.5e-14,
            5.6e-13,
        ]
        assert row["RecommendedStdValues"] == "75.00 fF || 560.00 fF"
        assert row["RecommendationPolicy"].endswith("minimum-cap=disabled")
        substitution = build["nominal_build"]["substitutions"][0]
        assert substitution["physical_parts_si"] == [7.5e-14, 5.6e-13]
        assert build["build_model"]["match_policy"]["allow_sub_pf"] is True
        assert re.search(r"^C1A 1 0 7\.5e-14$", deck, re.M)
        assert re.search(r"^C1B 1 0 5\.6e-13$", deck, re.M)
        assert SUB_PF_WARNING not in deck

    def test_bandpass_coupling_capacitors_follow_the_flag(self, monkeypatch, capsys):
        default = cli_stdout(monkeypatch, capsys, *SUB_PF_BANDPASS, "--no-toroids")
        allowed = cli_stdout(monkeypatch, capsys, *SUB_PF_BANDPASS, "--no-toroids", SUB_PF_CLI_FLAG)
        deck = cli_stdout(
            monkeypatch, capsys, *SUB_PF_BANDPASS, "--format", "spice", SUB_PF_CLI_FLAG
        )

        assert "Cs12 calculated 89.95 fF\n  Use:            none (below 1 pF" in default
        assert "Cs12 calculated 89.95 fF\n  Use:            43.00 fF || 47.00 fF (+0.1%)" in allowed
        assert re.search(r"^CK1A 1 2 4\.3e-14$", deck, re.M)
        assert re.search(r"^CIN 4 1 9\.1e-13$", deck, re.M)

    def test_capacitors_above_one_picofarad_are_unchanged(self, monkeypatch, capsys):
        design_args = ("lp", "bw", "pi", "10MHz", "--format", "json", "--no-toroids")

        assert cli_stdout(monkeypatch, capsys, *design_args).replace(
            '"allow_sub_pf": false', '"allow_sub_pf": true'
        ) == cli_stdout(monkeypatch, capsys, *design_args, SUB_PF_CLI_FLAG)


class TestCliRejectsTheFlagWhereItHasNoEffect:
    @pytest.mark.parametrize(
        ("extra", "message"),
        [
            (("--no-match",), "--allow-sub-pf cannot be combined with --no-match"),
            (
                ("-e", "E12", "--no-match"),
                "--eseries, --allow-sub-pf cannot be combined with --no-match",
            ),
            (
                ("--quiet",),
                "--allow-sub-pf has no effect with --quiet, which prints only calculated "
                "values; remove --allow-sub-pf",
            ),
            (
                ("--raw",),
                "--allow-sub-pf has no effect with --raw, which skips standard-value matching; "
                "remove --allow-sub-pf",
            ),
            (
                ("--sim-matched",),
                "--allow-sub-pf cannot be used with the deprecated --sim-matched; use --sim-build",
            ),
            (
                ("--plot-data", "json"),
                "--plot-data prints only frequency-response data; remove --allow-sub-pf",
            ),
            (
                ("--format", "spice", "--spice-realization", "exact"),
                "--allow-sub-pf has no effect on an exact SPICE deck, which uses the calculated "
                "values without losses; remove it or use --spice-realization nominal-build",
            ),
        ],
    )
    @pytest.mark.parametrize("design_args", [SUB_PF_LOWPASS, SUB_PF_BANDPASS], ids=["lp", "bp"])
    def test_usage_error(self, monkeypatch, capsys, design_args, extra, message):
        err = cli_stderr(monkeypatch, capsys, *design_args, SUB_PF_CLI_FLAG, *extra)

        assert err.rstrip().endswith(f"error: {message}")

    @pytest.mark.parametrize("command", ["lp", "bp"])
    def test_explain_rejects_it(self, monkeypatch, capsys, command):
        err = cli_stderr(monkeypatch, capsys, command, "bw", "--explain", SUB_PF_CLI_FLAG)

        assert err.rstrip().endswith(
            "error: --explain prints only a description of the filter type; remove --allow-sub-pf"
        )

    def test_raw_table_with_build_simulation_accepts_it(self, monkeypatch, capsys):
        out = cli_stdout(
            monkeypatch, capsys, *SUB_PF_LOWPASS, "--raw", "--sim-build", SUB_PF_CLI_FLAG
        )

        # The build block lists the chosen parts; the raw table itself has no E-series rows.
        assert "75.00 fF" in out and "560.00 fF" in out
        assert "Use:" not in out


class TestDesignLayer:
    def test_request_switch_defaults_off_and_must_be_a_boolean(self):
        assert _request().allow_sub_pf is False
        for value in (1, "yes", None):
            with pytest.raises(ValueError, match=f'^"{SUB_PF_OPTION_LABEL}" must be on or off$'):
                _request(allow_sub_pf=value)

    def test_result_carries_the_switch_as_a_match_policy(self):
        assert design(_request()).match_policy == DEFAULT_MATCH_POLICY
        policy = design(_request(allow_sub_pf=True)).match_policy

        assert policy.allow_sub_pf is True
        assert policy.minimum_capacitance_f == DEFAULT_MATCH_POLICY.minimum_capacitance_f

    def test_render_needs_an_eseries_when_the_switch_is_on(self):
        outcome = design(_request(allow_sub_pf=True))

        with pytest.raises(ValueError, match=f"^{re.escape(SUB_PF_NEEDS_ESERIES_MESSAGE)}$"):
            render_lines(outcome, RenderOptions(eseries=None))
        assert render_lines(design(_request()), RenderOptions(eseries=None))

    def test_request_build_config_follows_the_request_switch(self):
        stale = BuildConfig(match_policy=MatchPolicy(allow_sub_pf=False))
        outcome = design(_request(allow_sub_pf=True, build=stale))

        assert outcome.build_analysis.config.match_policy.allow_sub_pf is True
        substitution = outcome.build_analysis.nominal_realization.substitutions[0]
        assert substitution.method == "e_series_parallel"

    def test_explicit_build_config_opt_in_is_kept_when_the_request_switch_is_off(self):
        """Either switch allows sub-pF parts; an explicit BuildConfig opt-in is never dropped."""
        opted_in = BuildConfig(match_policy=MatchPolicy(allow_sub_pf=True))

        outcome = design(_request(build=opted_in))

        assert outcome.allow_sub_pf is True
        assert outcome.build_analysis.config.match_policy.allow_sub_pf is True
        substitution = outcome.build_analysis.nominal_realization.substitutions[0]
        assert substitution.method == "e_series_parallel"
        # The table picks the same capacitors as the build.
        table = "\n".join(render_lines(outcome, RenderOptions(eseries="E24")))
        assert re.search(r"Use: +75.00 fF \|\| 560.00 fF", table)

    def test_with_build_analysis_and_spice_combine_the_two_switches(self):
        opted_in = BuildConfig(match_policy=MatchPolicy(allow_sub_pf=True))
        outcome = design(_request())

        combined = with_build_analysis(outcome, opted_in)
        deck = export_spice(outcome, "nominal_build", opted_in)

        assert combined.allow_sub_pf is True
        assert combined.build_analysis.config.match_policy.allow_sub_pf is True
        assert SUB_PF_WARNING not in deck
        assert SUB_PF_WARNING in export_spice(outcome, "nominal_build", None)
        assert SUB_PF_WARNING not in export_spice(
            design(_request(allow_sub_pf=True)), "nominal_build", None
        )

    def test_apply_sub_pf_policy_keeps_other_policy_fields(self):
        custom = BuildConfig(match_policy=MatchPolicy(prefer_single_within_pct=2.5))

        updated = apply_sub_pf_policy(custom, True)

        assert updated.match_policy == MatchPolicy(prefer_single_within_pct=2.5, allow_sub_pf=True)
        assert apply_sub_pf_policy(custom, False) is custom
        assert apply_sub_pf_policy(updated, False) is updated
        assert apply_sub_pf_policy(None, False) is None
        assert apply_sub_pf_policy(None, True).match_policy.allow_sub_pf is True
