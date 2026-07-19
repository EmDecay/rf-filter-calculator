"""End-to-end CLI contracts for build analysis and SPICE export."""

import json
import re
import sys

import pytest

from filter_lib.cli import main


def _run(monkeypatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["filter-calc", *arguments])
    main()


def _reject_constant(value: str):
    raise AssertionError(f"non-standard JSON constant: {value}")


@pytest.mark.parametrize(
    "command",
    [
        ("lp", "bw", "pi", "10MHz"),
        ("hp", "bw", "t", "10MHz"),
        ("bp", "bw", "top", "-f", "10MHz", "-b", "500kHz"),
    ],
)
def test_sim_build_json_has_category_parity(monkeypatch, capsys, command):
    _run(
        monkeypatch,
        *command,
        "--sim-build",
        "--no-toroids",
        "--analysis-points",
        "101",
        "--format",
        "json",
    )

    payload = json.loads(capsys.readouterr().out, parse_constant=_reject_constant)

    assert {"target", "simulated", "nominal_build", "tolerance_analysis"} <= payload.keys()
    assert payload["simulated"]["realization"] == "calculated_exact_values"
    assert payload["nominal_build"]["substitutions"]
    assert payload["tolerance_analysis"]["grid_points"] == 101
    assert payload["evaluation"]["gain_metric"] == "transducer_power_gain_db"


def test_sim_build_uses_accuracy_safe_default_grid(monkeypatch, capsys):
    _run(
        monkeypatch,
        "lp",
        "bw",
        "pi",
        "10MHz",
        "--sim-build",
        "--no-toroids",
        "--format",
        "json",
    )

    payload = json.loads(capsys.readouterr().out, parse_constant=_reject_constant)
    assert payload["tolerance_analysis"]["grid_points"] == 601


def test_bandpass_edge_targets_preserve_exact_requested_values(monkeypatch, capsys):
    _run(
        monkeypatch,
        "bp",
        "bw",
        "top",
        "--fl",
        "14MHz",
        "--fh",
        "14.35MHz",
        "--sim-build",
        "--no-toroids",
        "--analysis-points",
        "101",
        "--format",
        "json",
    )

    payload = json.loads(capsys.readouterr().out, parse_constant=_reject_constant)
    assert payload["target"]["frequency_specification"] == "edge_frequencies"
    assert payload["target"]["f_low_hz"] == 14_000_000.0
    assert payload["target"]["f_high_hz"] == 14_350_000.0
    assert payload["target"]["f_low_hz"] == payload["requested_parameters"]["f_low_hz"]
    assert payload["target"]["f_high_hz"] == payload["requested_parameters"]["f_high_hz"]


def test_sim_build_table_is_explicitly_not_a_measurement(monkeypatch, capsys):
    _run(
        monkeypatch,
        "lp",
        "bw",
        "pi",
        "10MHz",
        "--sim-build",
        "--no-toroids",
        "--analysis-points",
        "101",
    )

    output = capsys.readouterr().out
    assert "Realized-Build Analysis (simulation, not a measurement)" in output
    assert "Calculated exact values" in output
    assert "Selected nominal build" in output
    assert "not guaranteed worst case or probability" in output


def test_build_controls_are_recorded_and_drive_repeatable_cases(monkeypatch, capsys):
    _run(
        monkeypatch,
        "hp",
        "bw",
        "t",
        "10MHz",
        "--sim-build",
        "--no-toroids",
        "--cap-tolerance",
        "2.5",
        "--ind-tolerance",
        "7.5",
        "--inductor-q",
        "80",
        "--capacitor-q",
        "300",
        "--source-resistance",
        "25ohm",
        "--load-resistance",
        "100ohm",
        "--samples",
        "2",
        "--seed",
        "73",
        "--analysis-points",
        "101",
        "--format",
        "json",
    )

    payload = json.loads(capsys.readouterr().out, parse_constant=_reject_constant)
    tolerance = payload["tolerance_analysis"]
    assert tolerance["capacitor_tolerance_pct"] == 2.5
    assert tolerance["inductor_tolerance_pct"] == 7.5
    assert tolerance["sample_count"] == 2
    assert tolerance["seed"] == 73
    assert [case["case_id"] for case in tolerance["cases"]][-2:] == [
        "sample:0001",
        "sample:0002",
    ]
    assert payload["evaluation"]["source_resistance_ohm"] == 25
    assert payload["evaluation"]["load_resistance_ohm"] == 100
    assert payload["build_model"]["inductor_q"] == 80
    assert payload["build_model"]["capacitor_q"] == 300


@pytest.mark.parametrize(
    "command, expected_element",
    [
        (("lp", "bw", "pi", "10MHz"), "C1"),
        (("hp", "bw", "t", "10MHz"), "C1"),
        (("bp", "bw", "top", "-f", "10MHz", "-b", "500kHz"), "CT1"),
    ],
)
@pytest.mark.parametrize("realization", ["exact", "nominal-build"])
def test_spice_export_covers_every_category_and_realization(
    monkeypatch, capsys, command, expected_element, realization
):
    arguments = [*command, "--format", "spice", "--spice-realization", realization]
    if realization == "exact":
        arguments.append("--no-match")
    _run(monkeypatch, *arguments)

    deck = capsys.readouterr().out
    assert (
        f"* realization: {'calculated_exact' if realization == 'exact' else 'nominal_build'}"
        in deck
    )
    assert re.search(rf"(?m)^{expected_element}\w*\s", deck)
    assert re.search(r"(?m)^\.ac dec 200 [0-9.e+-]+ [0-9.e+-]+$", deck)
    assert deck.endswith(".end\n")
    assert not re.search(r"(?i)(?<![a-z])(?:nan|[+-]?inf(?:inity)?)(?![a-z])", deck)


def test_nominal_spice_uses_physical_parallel_caps_and_q_loss(monkeypatch, capsys):
    _run(
        monkeypatch,
        "lp",
        "bw",
        "pi",
        "10MHz",
        "--format",
        "spice",
        "--spice-realization",
        "nominal-build",
        "--capacitor-q",
        "200",
        "--no-toroids",
    )

    deck = capsys.readouterr().out
    assert re.search(r"(?m)^C1A\s", deck)
    assert re.search(r"(?m)^C1B\s", deck)
    assert re.search(r"(?m)^RLOSSC1A\s", deck)
    assert "e_series_parallel" in deck
    assert "exact_fallback" in deck


@pytest.mark.parametrize(
    "command",
    [("lp", "bw", "pi", "10MHz"), ("hp", "bw", "t", "10MHz")],
)
def test_deprecated_alias_has_json_parity_and_warning(monkeypatch, capsys, command):
    _run(monkeypatch, *command, "--sim-matched", "--format", "json", "--no-toroids")

    captured = capsys.readouterr()
    payload = json.loads(captured.out, parse_constant=_reject_constant)
    assert payload["matched_sim"]["deprecated"] is True
    assert payload["matched_sim"]["replacement"] == "build_analysis"
    assert payload["matched_sim"]["inductors"] == "calculated_exact_value_toroid_selection_disabled"
    assert "--sim-matched is deprecated" in captured.err


@pytest.mark.parametrize(
    "arguments, expected",
    [
        (
            ("lp", "bw", "pi", "10MHz", "--sim-build", "--no-match"),
            "requires selected nominal capacitor values",
        ),
        (
            ("lp", "bw", "pi", "10MHz", "--sim-build", "--format", "csv"),
            "supported only with table or JSON",
        ),
        (
            ("lp", "bw", "pi", "10MHz", "--cap-tolerance", "5"),
            "require --sim-build or --format spice",
        ),
        (
            ("lp", "bw", "pi", "10MHz", "--sim-build", "--seed", "7"),
            "--seed requires a positive --sample-count",
        ),
        (
            ("lp", "bw", "pi", "10MHz", "--format", "spice", "--cap-tolerance", "5"),
            "affect tolerance analysis, not a SPICE deck",
        ),
        (
            (
                "lp",
                "bw",
                "pi",
                "10MHz",
                "--sim-build",
                "--loss-reference-frequency",
                "1MHz",
            ),
            "requires a Q input",
        ),
        (
            (
                "lp",
                "bw",
                "pi",
                "10MHz",
                "--format",
                "spice",
                "--loss-reference-frequency",
                "1MHz",
            ),
            "requires a Q input",
        ),
        (
            (
                "lp",
                "bw",
                "pi",
                "10MHz",
                "--format",
                "spice",
                "--spice-realization",
                "exact",
                "--inductor-q",
                "100",
            ),
            "cannot affect an exact lossless deck",
        ),
        (
            (
                "bp",
                "bw",
                "top",
                "-f",
                "10MHz",
                "-b",
                "500kHz",
                "--sim-build",
                "--qu",
                "100",
                "--inductor-q",
                "100",
            ),
            "not both loss models",
        ),
    ],
)
def test_incompatible_or_ignored_options_are_usage_errors(monkeypatch, capsys, arguments, expected):
    with pytest.raises(SystemExit) as exc_info:
        _run(monkeypatch, *arguments)

    assert exc_info.value.code == 2
    assert expected in capsys.readouterr().err


@pytest.mark.parametrize("q_flag", ["--qu", "--ql", "--qc"])
def test_exact_bandpass_spice_rejects_loss_model_q(monkeypatch, capsys, q_flag):
    with pytest.raises(SystemExit) as exc_info:
        _run(
            monkeypatch,
            "bp",
            "bw",
            "top",
            "-f",
            "10MHz",
            "-b",
            "500kHz",
            "--format",
            "spice",
            "--spice-realization",
            "exact",
            q_flag,
            "100",
        )

    assert exc_info.value.code == 2
    assert "Loss-Q input" in capsys.readouterr().err


@pytest.mark.parametrize(
    "mode_args, expected_error",
    [
        (("--format", "csv"), "Loss-Q input --qu is not represented"),
        (("--quiet",), "Loss-Q input --qu is not represented"),
        (("--plot-data", "json"), "Loss-Q input --qu is not represented"),
        (("--explain",), "--explain is standalone"),
    ],
)
def test_bandpass_q_rejects_modes_that_cannot_show_it(
    monkeypatch, capsys, mode_args, expected_error
):
    with pytest.raises(SystemExit) as exc_info:
        _run(
            monkeypatch,
            "bp",
            "bw",
            "top",
            "-f",
            "10MHz",
            "-b",
            "500kHz",
            "--qu",
            "100",
            *mode_args,
        )

    assert exc_info.value.code == 2
    assert expected_error in capsys.readouterr().err


def test_legacy_q_safety_is_limited_to_compatibility_json(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc_info:
        _run(
            monkeypatch,
            "bp",
            "bw",
            "top",
            "-f",
            "10MHz",
            "-b",
            "500kHz",
            "--q-safety",
            "3",
        )

    assert exc_info.value.code == 2
    assert "compatibility-only JSON field" in capsys.readouterr().err


def test_legacy_q_safety_remains_available_in_json(monkeypatch, capsys):
    _run(
        monkeypatch,
        "bp",
        "bw",
        "top",
        "-f",
        "10MHz",
        "-b",
        "500kHz",
        "--q-safety",
        "3",
        "--format",
        "json",
        "--no-toroids",
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["q_min"] == pytest.approx(60)
    assert "deprecated" in captured.err
    assert "legacy Q heuristic" in captured.err


def test_nominal_bandpass_spice_applies_complete_resonator_q(monkeypatch, capsys):
    _run(
        monkeypatch,
        "bp",
        "bw",
        "top",
        "-f",
        "10MHz",
        "-b",
        "500kHz",
        "--qu",
        "100",
        "--format",
        "spice",
        "--no-toroids",
    )

    deck = capsys.readouterr().out
    assert re.search(r"(?m)^RLOSSLT1\s", deck)
    assert "complete resonator Q" in deck


def test_loss_reference_frequency_is_applied_when_q_is_supplied(monkeypatch, capsys):
    _run(
        monkeypatch,
        "lp",
        "bw",
        "pi",
        "10MHz",
        "--format",
        "spice",
        "--inductor-q",
        "100",
        "--loss-reference-frequency",
        "1MHz",
        "--no-toroids",
    )

    deck = capsys.readouterr().out
    assert "at 1000000 Hz" in deck
    assert re.search(r"(?m)^RLOSSL1\s", deck)
