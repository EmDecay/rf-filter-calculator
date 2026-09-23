"""The wizard shows and saves exactly what the CLI computes for the same design.

Each wizard result is compared with ``filter-calc`` output for the same parameters. Every
design moves each field off its ``FilterState`` default (75 Ohm, 7.1 MHz or 14.175 MHz,
order 4/5, 0.25 dB ripple, a non-default E-series or tank setting), so a field the wizard
drops, swaps, or defaults changes the component values and fails the comparison.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from filter_lib import cli
from filter_lib.wizard.calculation_handler import calculate_and_format
from filter_lib.wizard.export_formatting import format_response_export
from filter_lib.wizard.state import FilterState

_ALIAS = {"butterworth": "bw", "chebyshev": "ch", "bessel": "bs"}
_TOROID_FLAG = {"full": "--toroid-full", "compact": "--toroid-compact"}


def _cli_stdout(monkeypatch, capsys, *argv: str) -> str:
    """Run ``filter-calc`` in-process and return its standard output."""
    monkeypatch.setattr("sys.argv", ["filter-calc", *argv])
    capsys.readouterr()
    cli.main()
    return capsys.readouterr().out


def _ladder(category: str, filter_type: str, topology: str, **overrides) -> FilterState:
    values = dict(
        category=category,
        filter_type=filter_type,
        topology=topology,
        frequency_hz=7.1e6,
        impedance=75.0,
        order=5 if filter_type == "chebyshev" else 4,
        ripple_db=0.25,
        show_plot=False,
    )
    values.update(overrides)
    return FilterState(**values)


def _ladder_argv(state: FilterState) -> list[str]:
    argv = [state.category, _ALIAS[state.filter_type], state.topology, "7.1MHz"]
    argv += ["-n", str(state.order), "-z", "75"]
    if state.filter_type == "chebyshev":
        argv += ["-r", "0.25"]
    return argv


def _bandpass(filter_type: str, order: int, **overrides) -> FilterState:
    values = dict(
        category="bandpass",
        filter_type=filter_type,
        topology="top",
        frequency_hz=14.175e6,
        bandwidth_hz=350e3,
        impedance=75.0,
        order=order,
        ripple_db=0.25 if filter_type == "chebyshev" else 0.5,
        show_plot=False,
    )
    values.update(overrides)
    return FilterState(**values)


def _bandpass_argv(state: FilterState) -> list[str]:
    argv = ["bandpass", _ALIAS[state.filter_type], "top", "-f", "14.175MHz", "-b", "350kHz"]
    argv += ["-n", str(state.order), "-z", "75"]
    if state.filter_type == "chebyshev":
        argv += ["-r", "0.25"]
    if state.resonator_impedance is not None:
        argv += ["--resonator-impedance", f"{state.resonator_impedance:g}"]
    if state.resonator_inductance is not None:
        argv += ["--resonator-inductance", f"{state.resonator_inductance:g}H"]
    return argv


def _eseries_argv(state: FilterState) -> list[str]:
    return ["--no-match"] if state.eseries == "none" else ["-e", state.eseries]


def _design_argv(state: FilterState) -> list[str]:
    return _bandpass_argv(state) if state.category == "bandpass" else _ladder_argv(state)


def _document(text: str) -> str:
    """Drop the line terminator ``print`` adds after the CLI's final line."""
    return text.rstrip("\r\n")


def _wizard_output(state: FilterState) -> str:
    outcome = calculate_and_format(state)
    assert outcome.succeeded, outcome.error
    return outcome.output_text


LADDER_MACHINE_CASES = [
    _ladder("lowpass", "butterworth", "t", eseries="E12", output_format="json"),
    _ladder("lowpass", "chebyshev", "t", eseries="E96", output_format="csv"),
    _ladder("lowpass", "bessel", "pi", eseries="none", output_format="json"),
    _ladder("highpass", "butterworth", "pi", eseries="none", output_format="csv"),
    _ladder("highpass", "chebyshev", "t", eseries="E12", output_format="json"),
    _ladder("highpass", "bessel", "t", eseries="E96", output_format="csv"),
]
BANDPASS_MACHINE_CASES = [
    _bandpass("chebyshev", 5, eseries="E12", output_format="json"),
    _bandpass("butterworth", 4, eseries="none", output_format="csv", resonator_impedance=100.0),
    _bandpass("bessel", 3, eseries="E96", output_format="json", resonator_inductance=1.5e-6),
]


def _case_id(state: FilterState) -> str:
    return f"{state.category}-{state.filter_type}-{state.output_format}-{state.eseries}"


@pytest.mark.parametrize("state", LADDER_MACHINE_CASES + BANDPASS_MACHINE_CASES, ids=_case_id)
def test_json_and_csv_output_is_the_cli_document(monkeypatch, capsys, state):
    expected = _cli_stdout(
        monkeypatch,
        capsys,
        *_design_argv(state),
        *_eseries_argv(state),
        "--format",
        state.output_format,
    )

    assert _document(_wizard_output(state)) == _document(expected)


@pytest.mark.parametrize(
    "state, flags",
    [
        (
            _ladder("lowpass", "chebyshev", "t", eseries="E12", show_plot=True),
            ("--plot",),
        ),
        (_ladder("highpass", "bessel", "pi", eseries="E96", toroid_detail="compact"), ()),
        (_ladder("highpass", "butterworth", "t", eseries="none", raw_units=True), ("--raw",)),
        (_ladder("lowpass", "bessel", "pi", eseries="none", quiet=True), ("-q",)),
    ],
    ids=["lp-plot", "hp-compact-toroids", "hp-raw", "lp-quiet"],
)
def test_ladder_table_is_the_cli_table(monkeypatch, capsys, state, flags):
    # Quiet output has no toroid section, and the CLI rejects a detail flag with -q.
    toroid_flag = () if state.quiet else (_TOROID_FLAG[state.toroid_detail],)
    expected = _cli_stdout(
        monkeypatch, capsys, *_ladder_argv(state), *_eseries_argv(state), *toroid_flag, *flags
    )

    assert _document(_wizard_output(state)) == _document(expected)


@pytest.mark.parametrize(
    "state, flags",
    [
        (_bandpass("chebyshev", 5, eseries="E24"), ()),
        (
            _bandpass(
                "butterworth",
                4,
                eseries="none",
                raw_units=True,
                toroid_detail="compact",
                resonator_impedance=100.0,
            ),
            ("--raw",),
        ),
        (
            _bandpass("bessel", 3, eseries="E96", resonator_inductance=1.5e-6, show_plot=True),
            ("--plot",),
        ),
        (
            _bandpass("chebyshev", 5, eseries="E12", toroid_detail="compact", show_plot=True),
            ("--plot",),
        ),
    ],
    ids=[
        "chebyshev-e24",
        "butterworth-raw-tank-impedance",
        "bessel-plot-tank-inductance",
        "chebyshev-plot-compact-toroids",
    ],
)
def test_bandpass_table_is_the_cli_table(monkeypatch, capsys, state, flags):
    expected = _cli_stdout(
        monkeypatch,
        capsys,
        *_bandpass_argv(state),
        *_eseries_argv(state),
        _TOROID_FLAG[state.toroid_detail],
        *flags,
    )

    # Header with both band edges, component tables, preferred values, toroid windings,
    # Q/loss notes, plot, and threshold table: one renderer, so the text is identical.
    assert _document(_wizard_output(state)) == _document(expected)


@pytest.mark.parametrize(
    "state, fmt",
    [
        (_ladder("lowpass", "chebyshev", "t", eseries="E24"), "json"),
        (_ladder("highpass", "bessel", "pi", eseries="E24"), "csv"),
        (_bandpass("chebyshev", 5, eseries="E24"), "json"),
        (_bandpass("butterworth", 4, eseries="E24", resonator_inductance=1.5e-6), "csv"),
    ],
    ids=["lp-json", "hp-csv", "bp-json", "bp-csv"],
)
def test_response_sidecar_is_the_cli_plot_data(monkeypatch, capsys, state, fmt):
    expected = _cli_stdout(monkeypatch, capsys, *_design_argv(state), "--plot-data", fmt)
    calculated = replace(state, result=calculate_and_format(state).result)

    assert _document(format_response_export(calculated, fmt)) == _document(expected)


_BUILD_ARGV = (
    "--sim-build",
    "--capacitor-tolerance",
    "2",
    "--inductor-tolerance",
    "7.5",
    "--inductor-q",
    "120",
    "--capacitor-q",
    "500",
    "--source-resistance",
    "25",
    "--load-resistance",
    "100",
    "--samples",
    "3",
    "--seed",
    "42",
    "--analysis-points",
    "51",
    "--no-toroid-build",
)
_BUILD_STATE = dict(
    build_analysis_enabled=True,
    build_capacitor_tolerance_pct=2.0,
    build_inductor_tolerance_pct=7.5,
    build_inductor_q=120.0,
    build_capacitor_q=500.0,
    build_source_resistance_ohm=25.0,
    build_load_resistance_ohm=100.0,
    build_sample_count=3,
    build_seed=42,
    build_grid_points=51,
    build_use_toroid_candidates=False,
)


@pytest.mark.parametrize(
    "state",
    [
        _ladder("lowpass", "chebyshev", "pi", eseries="E96", output_format="json", **_BUILD_STATE),
        _ladder("highpass", "bessel", "t", eseries="E12", output_format="json", **_BUILD_STATE),
        _bandpass("butterworth", 2, eseries="E96", output_format="json", **_BUILD_STATE),
    ],
    ids=_case_id,
)
def test_realized_build_json_is_the_cli_sim_build_document(monkeypatch, capsys, state):
    expected = _cli_stdout(
        monkeypatch,
        capsys,
        *_design_argv(state),
        "-e",
        state.eseries,
        "--format",
        "json",
        *_BUILD_ARGV,
    )

    assert _document(_wizard_output(state)) == _document(expected)
