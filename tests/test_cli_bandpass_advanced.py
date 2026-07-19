"""CLI coverage for bandpass resonator and Q-model controls."""

import json
from unittest.mock import patch

import pytest

from filter_lib import cli


def test_component_q_and_resonator_impedance_reach_result(capsys) -> None:
    argv = [
        "filter-calc",
        "bp",
        "bw",
        "top",
        "-f",
        "14.2MHz",
        "-b",
        "500kHz",
        "--format",
        "json",
        "--no-toroids",
        "--ql",
        "180",
        "--qc",
        "500",
        "--resonator-impedance",
        "100ohm",
    ]
    with patch("sys.argv", argv):
        cli.main()
    data = json.loads(capsys.readouterr().out)

    assert data["q_model"]["inductor_ql"] == 180.0
    assert data["q_model"]["capacitor_qc"] == 500.0
    assert data["q_model"]["resonator_qu"] == pytest.approx(1 / (1 / 180 + 1 / 500))
    assert data["internal_synthesis_parameters"]["resonator_impedance_ohms"] == 100.0
    assert data["internal_synthesis_parameters"]["resonator_selection"] == "fixed_impedance"


def test_fixed_resonator_inductance_accepts_units(capsys) -> None:
    argv = [
        "filter-calc",
        "bp",
        "bw",
        "top",
        "-f",
        "14.2MHz",
        "-b",
        "500kHz",
        "--format",
        "json",
        "--no-toroids",
        "--resonator-inductance",
        "1.2uH",
    ]
    with patch("sys.argv", argv):
        cli.main()
    data = json.loads(capsys.readouterr().out)

    assert data["components"]["inductors"][0]["value_henries"] == pytest.approx(1.2e-6)
    assert data["internal_synthesis_parameters"]["resonator_selection"] == "fixed_inductance"


def test_explicit_edge_metadata_preserves_parsed_requested_values(capsys) -> None:
    argv = [
        "filter-calc",
        "bp",
        "bw",
        "top",
        "--fl",
        "14MHz",
        "--fh",
        "14.35MHz",
        "--format",
        "json",
        "--no-toroids",
    ]
    with patch("sys.argv", argv):
        cli.main()
    data = json.loads(capsys.readouterr().out)

    requested = data["requested_parameters"]
    assert requested["frequency_specification"] == "edge_frequencies"
    assert requested["f_low_hz"] == 14_000_000.0
    assert requested["f_high_hz"] == 14_350_000.0


@pytest.mark.parametrize(
    "extra",
    [
        ["--qu", "200", "--ql", "180"],
        ["--resonator-impedance", "100", "--resonator-inductance", "1uH"],
    ],
)
def test_mutually_exclusive_advanced_controls_fail_cleanly(extra, capsys) -> None:
    argv = [
        "filter-calc",
        "bp",
        "bw",
        "top",
        "-f",
        "14.2MHz",
        "-b",
        "500kHz",
        "--no-toroids",
        *extra,
    ]
    with patch("sys.argv", argv), pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1
    assert "mutually exclusive" in capsys.readouterr().err


def test_help_describes_q_semantics_and_hides_legacy_q_safety(capsys) -> None:
    with patch("sys.argv", ["filter-calc", "bp", "--help"]), pytest.raises(SystemExit):
        cli.main()

    output = capsys.readouterr().out
    assert "complete resonator" in output
    assert "inductor q" in output.lower()
    assert "capacitor q" in output.lower()
    assert "--q-safety" not in output
