"""End-to-end CLI contracts for build analysis and SPICE export."""

import contextlib
import io
import json
import math
import re
import sys

import pytest

from filter_lib.cli import main

_LOWPASS = ("lp", "bw", "pi", "10MHz")
_SIM_BUILD_JSON_ARGS = ("--sim-build", "--no-toroids", "--analysis-points", "101")
_BANDPASS_EDGE_COMMAND = ("bp", "bw", "top", "-n", "2", "--fl", "14MHz", "--fh", "14.35MHz")


def _run(monkeypatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["filter-calc", *arguments])
    main()


def _reject_constant(value: str):
    raise AssertionError(f"non-standard JSON constant: {value}")


def _deck_values(deck: str) -> dict[str, float]:
    """Map each SPICE element name to its value (the last field of its card)."""
    return {
        line.split()[0]: float(line.split()[-1])
        for line in deck.splitlines()
        if line[:1].isalpha() and line.split()[0] != "VINPUT"
    }


@pytest.fixture(scope="module")
def sim_build_json():
    """Run each ``--sim-build --format json`` command once per module.

    Every call returns a freshly parsed payload, so tests share only the expensive
    bandpass simulation, not mutable state.
    """
    outputs: dict[tuple[str, ...], str] = {}

    def run(*command: str) -> dict:
        if command not in outputs:
            stdout = io.StringIO()
            with pytest.MonkeyPatch.context() as patch, contextlib.redirect_stdout(stdout):
                patch.setattr(
                    sys,
                    "argv",
                    ["filter-calc", *command, *_SIM_BUILD_JSON_ARGS, "--format", "json"],
                )
                main()
            outputs[command] = stdout.getvalue()
        return json.loads(outputs[command], parse_constant=_reject_constant)

    return run


@pytest.mark.parametrize(
    "command",
    [_LOWPASS, ("hp", "bw", "t", "10MHz"), _BANDPASS_EDGE_COMMAND],
    ids=["lowpass", "highpass", "bandpass"],
)
def test_sim_build_json_has_category_parity(sim_build_json, command):
    payload = sim_build_json(*command)

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
    tolerance = payload["tolerance_analysis"]
    assert tolerance["grid_points"] == 601
    # The defaults advertised by --help: 5% capacitors, 10% inductors, no screening samples,
    # equal 50-ohm evaluation ports, and a lossless build.
    assert (tolerance["capacitor_tolerance_pct"], tolerance["inductor_tolerance_pct"]) == (5, 10)
    assert (tolerance["sample_count"], tolerance["seed"]) == (0, 0)
    assert [case["case_id"] for case in tolerance["cases"]][0] == "nominal"
    assert not any(case["case_id"].startswith("sample:") for case in tolerance["cases"])
    evaluation = payload["evaluation"]
    assert (evaluation["source_resistance_ohm"], evaluation["load_resistance_ohm"]) == (50, 50)
    assert payload["build_model"]["effective_loss_model"]["is_lossless"] is True
    assert payload["build_model"]["eseries"] == "E24"


def test_bandpass_edge_targets_preserve_exact_requested_values(sim_build_json):
    payload = sim_build_json(*_BANDPASS_EDGE_COMMAND)

    assert payload["target"]["frequency_specification"] == "edge_frequencies"
    assert payload["target"]["order"] == 2
    assert payload["target"]["f_low_hz"] == 14_000_000.0
    assert payload["target"]["f_high_hz"] == 14_350_000.0
    assert payload["target"]["f_low_hz"] == payload["requested_parameters"]["f_low_hz"]
    assert payload["target"]["f_high_hz"] == payload["requested_parameters"]["f_high_hz"]


def test_no_toroid_build_keeps_calculated_inductance_as_disclosed_fallback(monkeypatch, capsys):
    _run(
        monkeypatch,
        "lp",
        "bw",
        "pi",
        "10MHz",
        "--sim-build",
        "--no-toroid-build",
        "--analysis-points",
        "51",
        "--format",
        "json",
    )

    payload = json.loads(capsys.readouterr().out, parse_constant=_reject_constant)
    inductor = next(
        item for item in payload["nominal_build"]["substitutions"] if item["kind"] == "L"
    )
    assert payload["build_model"]["toroid_candidate_screen_enabled"] is False
    assert (inductor["method"], inductor["status"]) == (
        "exact_fallback",
        "candidate_screen_disabled",
    )
    assert inductor["nominal_value_si"] == inductor["calculated_value_si"]
    # Unlike --no-toroids, the build-only opt-out leaves the winding recommendations visible.
    assert payload["components"]["inductors"][0]["toroid_recommendations"]


def test_build_controls_are_forwarded_to_analysis_json(monkeypatch, capsys):
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
    sweep = r"lin \d+" if command[0] == "bp" else "dec 200"
    assert re.search(rf"(?m)^\.ac {sweep} [0-9.e+-]+ [0-9.e+-]+$", deck)
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
    values = _deck_values(deck)
    assert "e_series_parallel" in deck
    assert "exact_fallback" in deck
    # 318.31 pF is realized as the selected E24 pair 47 pF || 270 pF (see sample output).
    assert (values["C1A"], values["C1B"]) == (47e-12, 270e-12)
    assert "calculated=3.18309886184e-10 nominal=3.17e-10" in deck
    # Capacitor Q becomes series R = 1/(w*C*Q) at the default (design) reference frequency.
    omega = 2 * math.pi * 10e6
    for name in ("C1A", "C1B", "C2A", "C2B"):
        expected = 1 / (omega * values[name] * 200)
        assert values[f"RLOSS{name}"] == pytest.approx(expected, rel=1e-9, abs=0)
    assert "RLOSSL1" not in values


@pytest.mark.parametrize(
    "command, cutoff_key, absent_skirt_key",
    [
        (("lp", "bw", "pi", "10MHz"), "f_high_hz", "f_low_hz"),
        (("hp", "bw", "t", "10MHz"), "f_low_hz", "f_high_hz"),
    ],
    ids=["lowpass", "highpass"],
)
def test_deprecated_alias_has_json_parity_and_warning(
    monkeypatch, capsys, command, cutoff_key, absent_skirt_key
):
    _run(monkeypatch, *command, "--sim-matched", "--format", "json", "--no-toroids")

    captured = capsys.readouterr()
    block = json.loads(captured.out, parse_constant=_reject_constant)["matched_sim"]
    assert block["deprecated"] is True
    assert block["replacement"] == "build_analysis"
    assert block["inductors"] == "calculated_exact_value_toroid_selection_disabled"
    assert "Warning: --sim-matched is deprecated; use --sim-build" in captured.err
    for side in ("exact", "matched"):
        assert block[side]["cutoff_hz"] == block[side][cutoff_key]
        assert block[side]["cutoff_hz"] == pytest.approx(10e6, rel=0.05)
        assert block[side][absent_skirt_key] is None
        assert block[side]["f0_hz"] is None
        assert block[side]["bw_hz"] is None


@pytest.mark.parametrize(
    "arguments, expected",
    [
        (
            (*_LOWPASS, "--sim-build", "--no-match"),
            "--sim-build requires selected nominal capacitor values; remove --no-match",
        ),
        (
            (*_LOWPASS, "--sim-build", "--format", "csv"),
            "--sim-build is supported only with table or JSON output",
        ),
        (
            (*_LOWPASS, "--format", "spice", "--sim-build"),
            "--sim-build is supported only with table or JSON output",
        ),
        (
            (*_LOWPASS, "--sim-matched", "--format", "csv"),
            "--sim-matched is supported only with table or JSON output",
        ),
        (
            (*_LOWPASS, "--sim-matched", "--sim-build"),
            "--sim-matched is deprecated; use --sim-build alone",
        ),
        ((*_LOWPASS, "--sim-build", "--quiet"), "--quiet and --sim-build cannot be used together"),
        (
            (*_LOWPASS, "--sim-matched", "--quiet"),
            "--quiet and --sim-matched cannot be used together",
        ),
        (
            (*_LOWPASS, "--cap-tolerance", "5"),
            "--capacitor-tolerance requires --sim-build or --format spice",
        ),
        (
            (*_LOWPASS, "--cap-tolerance", "5", "--seed", "7"),
            "--capacitor-tolerance, --seed require --sim-build or --format spice",
        ),
        (
            (*_LOWPASS, "--sim-build", "--seed", "7"),
            "--seed requires a positive --sample-count",
        ),
        (
            (*_LOWPASS, "--spice-realization", "exact"),
            "--spice-realization requires --format spice",
        ),
        (
            (*_LOWPASS, "--format", "spice", "--cap-tolerance", "5"),
            "--capacitor-tolerance affects tolerance analysis, not a SPICE deck; use --sim-build",
        ),
        (
            (*_LOWPASS, "--format", "spice", "--cap-tolerance", "5", "--seed", "7"),
            "--capacitor-tolerance, --seed affect tolerance analysis, not a SPICE deck; "
            "use --sim-build",
        ),
        (
            (*_LOWPASS, "--format", "spice", "--no-match"),
            "nominal-build SPICE requires selected capacitor values; remove --no-match "
            "or use --spice-realization exact",
        ),
        (
            (*_LOWPASS, "--sim-build", "--loss-reference-frequency", "1MHz"),
            "--loss-reference-frequency requires a Q input",
        ),
        (
            (*_LOWPASS, "--format", "spice", "--loss-reference-frequency", "1MHz"),
            "--loss-reference-frequency requires a Q input",
        ),
        (
            (
                *_LOWPASS,
                "--format",
                "spice",
                "--spice-realization",
                "exact",
                "--inductor-q",
                "100",
            ),
            "--inductor-q cannot affect an exact lossless deck",
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
            "use either --qu/--ql/--qc or --inductor-q/--capacitor-q, not both loss models",
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
    values = _deck_values(deck)
    assert "complete resonator Q" in deck
    # One equivalent inductor loss per tank: R = w0*L/Qu at the 10 MHz center.
    for tank in (1, 2, 3):
        expected = 2 * math.pi * 10e6 * values[f"LT{tank}"] / 100
        assert values[f"RLOSSLT{tank}"] == pytest.approx(expected, rel=1e-9, abs=0)
    assert not any(name.startswith("RLOSSC") for name in values)


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
    values = _deck_values(deck)
    assert "at 1000000 Hz" in deck
    # R = w_ref*L/Q evaluated at the 1 MHz reference, not the 10 MHz cutoff.
    expected = 2 * math.pi * 1e6 * values["L1"] / 100
    assert values["RLOSSL1"] == pytest.approx(expected, rel=1e-9, abs=0)
    assert values["RLOSSL1"] == pytest.approx(0.1, rel=1e-9, abs=0)
