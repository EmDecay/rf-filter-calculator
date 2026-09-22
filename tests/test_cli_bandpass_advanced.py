"""CLI coverage for bandpass resonator and Q-model controls."""

import json
import math
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

    assert data["components"]["inductors"][0]["value_henries"] == pytest.approx(
        1.2e-6, rel=1e-9, abs=0
    )
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
    # The band-pass response is geometrically symmetric, so the design center is the
    # geometric mean of the requested edges and the bandwidth is their difference.
    assert data["center_frequency_hz"] == pytest.approx(math.sqrt(14e6 * 14.35e6), rel=1e-12)
    assert data["bandwidth_hz"] == pytest.approx(350e3, rel=1e-9)


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--qu", "200", "--ql", "180"], "qu and separate ql/qc values are mutually exclusive"),
        (
            ["--resonator-impedance", "100", "--resonator-inductance", "1uH"],
            "resonator_impedance and resonator_inductance are mutually exclusive",
        ),
    ],
)
def test_mutually_exclusive_advanced_controls_fail_cleanly(extra, message, capsys) -> None:
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
    assert capsys.readouterr().err == f"Error: {message}\n"


@pytest.mark.parametrize(
    ("q_flags", "expected_lines"),
    [
        (
            ["--ql", "180", "--qc", "500"],
            [
                "Loss-model complete-resonator unloaded Q: 132.4",
                "  Derived from QL=180 and QC=500 at f₀",
            ],
        ),
        (
            ["--ql", "180"],
            ["Loss-model complete-resonator unloaded Q: 180", "  Derived from QL=180 at f₀"],
        ),
        (
            ["--qc", "500"],
            ["Loss-model complete-resonator unloaded Q: 500", "  Derived from QC=500 at f₀"],
        ),
    ],
)
def test_table_explains_component_q_behind_resonator_q(q_flags, expected_lines, capsys) -> None:
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
        "--no-match",
        *q_flags,
    ]
    with patch("sys.argv", argv):
        cli.main()
    lines = capsys.readouterr().out.splitlines()

    start = lines.index(expected_lines[0])
    assert lines[start : start + len(expected_lines)] == expected_lines


def test_help_describes_q_semantics_and_hides_legacy_q_safety(capsys) -> None:
    with patch("sys.argv", ["filter-calc", "bp", "--help"]), pytest.raises(SystemExit):
        cli.main()

    output = capsys.readouterr().out
    assert "complete resonator" in output
    assert "inductor q" in output.lower()
    assert "capacitor q" in output.lower()
    assert "--q-safety" not in output
