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
# Wizard toroid choice -> CLI flags; "Best, detailed" is the CLI default (no flag).
_TOROID_FLAGS = {
    "best": (),
    "full": ("--toroid-full",),
    "compact": ("--toroid-compact",),
    "none": ("--no-toroids",),
}


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
        (_ladder("highpass", "chebyshev", "pi", eseries="E12", toroid_detail="full"), ()),
        (_ladder("lowpass", "butterworth", "t", eseries="E24", toroid_detail="none"), ()),
        (_ladder("highpass", "butterworth", "t", eseries="none", raw_units=True), ("--raw",)),
        (_ladder("lowpass", "bessel", "pi", eseries="none", quiet=True), ("-q",)),
    ],
    ids=["lp-plot", "hp-compact-toroids", "hp-full-toroids", "lp-no-toroids", "hp-raw", "lp-quiet"],
)
def test_ladder_table_is_the_cli_table(monkeypatch, capsys, state, flags):
    # Quiet output has no toroid section, and the CLI rejects a detail flag with -q.
    toroid_flag = () if state.quiet else _TOROID_FLAGS[state.toroid_detail]
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
        *_TOROID_FLAGS[state.toroid_detail],
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


# "Allow capacitors below 1 pF": a 5 GHz low-pass has 636.62 fF capacitors.
_SUB_PF_ARGV = ("lp", "bw", "pi", "5GHz", "-n", "3", "--allow-sub-pf")


def _sub_pf_state(**overrides) -> FilterState:
    values = dict(
        category="lowpass",
        filter_type="butterworth",
        topology="pi",
        frequency_hz=5e9,
        order=3,
        show_plot=False,
        allow_sub_pf=True,
    )
    values.update(overrides)
    return FilterState(**values)


@pytest.mark.parametrize(
    "state, flags",
    [
        (_sub_pf_state(), ()),
        (_sub_pf_state(output_format="json"), ("--format", "json")),
        (_sub_pf_state(output_format="csv"), ("--format", "csv")),
        (
            _sub_pf_state(output_format="json", **_BUILD_STATE),
            ("--format", "json", *_BUILD_ARGV),
        ),
    ],
    ids=["table", "json", "csv", "build-json"],
)
def test_sub_pf_option_is_the_cli_allow_sub_pf_output(monkeypatch, capsys, state, flags):
    expected = _cli_stdout(monkeypatch, capsys, *_SUB_PF_ARGV, *flags)

    wizard = _wizard_output(state)

    assert _document(wizard) == _document(expected)
    assert "560.00 fF" in wizard or "5.6e-13" in wizard or "5.60e-13" in wizard


def test_sub_pf_option_reaches_the_saved_json_export(monkeypatch, capsys):
    from filter_lib.wizard.export_formatting import format_component_json

    state = _sub_pf_state()
    calculated = replace(state, result=calculate_and_format(state).result)
    expected = _cli_stdout(monkeypatch, capsys, *_SUB_PF_ARGV, "--format", "json")

    assert format_component_json(calculated) == expected
    assert '"allow_sub_pf": true' in expected


def _saved(state: FilterState):
    """``state`` after its calculation, as the results screen holds it for saving.

    A JSON that needs its own design gets it as the results screen's Save does.
    """
    from filter_lib.design import design
    from filter_lib.wizard.state import CalculationOutcome

    outcome: CalculationOutcome = calculate_and_format(state)
    assert outcome.succeeded, outcome.error
    saved = replace(
        state,
        result=outcome.result,
        output_text=outcome.output_text,
        build_analysis=outcome.build_analysis,
        calculation_status="success",
    )
    if saved.json_needs_own_design():
        saved.json_design = design(saved.json_design_request())
    return saved


# --- Toroid windings "None" (--no-toroids) --------------------------------------------


@pytest.mark.parametrize(
    "state, flags",
    [
        (_bandpass("butterworth", 3, eseries="E24", toroid_detail="none"), ()),
        (
            _bandpass("chebyshev", 5, eseries="E12", toroid_detail="none", output_format="json"),
            ("--format", "json"),
        ),
        (
            _ladder(
                "highpass", "bessel", "pi", eseries="E96", toroid_detail="none", output_format="csv"
            ),
            ("--format", "csv"),
        ),
        (
            _ladder(
                "lowpass",
                "chebyshev",
                "pi",
                eseries="E96",
                toroid_detail="none",
                output_format="json",
                **{**_BUILD_STATE, "build_use_toroid_candidates": True},
            ),
            ("--format", "json", *_BUILD_ARGV[:-1]),
        ),
    ],
    ids=["bp-table", "bp-json", "hp-csv", "lp-build-json"],
)
def test_toroid_none_is_the_cli_no_toroids_output(monkeypatch, capsys, state, flags):
    """None leaves the windings out of every output, and the build uses calculated L."""
    expected = _cli_stdout(
        monkeypatch, capsys, *_design_argv(state), *_eseries_argv(state), "--no-toroids", *flags
    )

    assert _document(_wizard_output(state)) == _document(expected)
    wizard = _wizard_output(state)
    assert "Toroid Winding Suggestions" not in wizard
    assert '"toroid_candidates"' not in wizard


@pytest.mark.parametrize("document", ["json", "csv"])
def test_toroid_none_reaches_the_saved_files(monkeypatch, capsys, document):
    from filter_lib.wizard.export_formatting import format_component_csv, format_component_json

    state = _saved(_bandpass("butterworth", 4, eseries="E96", toroid_detail="none"))
    expected = _cli_stdout(
        monkeypatch,
        capsys,
        *_bandpass_argv(state),
        "-e",
        "E96",
        "--no-toroids",
        "--format",
        document,
    )
    saved = format_component_json if document == "json" else format_component_csv

    assert saved(state) == expected


# --- Band given by its -3 dB edges (--fl/--fh) ---------------------------------------


def _edges(filter_type: str, order: int, **overrides) -> FilterState:
    from filter_lib.design import band_from_edges

    center, width = band_from_edges(14.0e6, 14.35e6)
    return _bandpass(
        filter_type,
        order,
        frequency_hz=center,
        bandwidth_hz=width,
        requested_f_low_hz=14.0e6,
        requested_f_high_hz=14.35e6,
        **overrides,
    )


def _edges_argv(state: FilterState) -> list[str]:
    argv = ["bandpass", _ALIAS[state.filter_type], "top", "--fl", "14MHz", "--fh", "14.35MHz"]
    argv += ["-n", str(state.order), "-z", "75"]
    if state.filter_type == "chebyshev":
        argv += ["-r", "0.25"]
    return argv


@pytest.mark.parametrize(
    "state, flags",
    [
        (_edges("chebyshev", 5, eseries="E24"), ()),
        (_edges("butterworth", 3, eseries="E12", output_format="json"), ("--format", "json")),
        (_edges("bessel", 4, eseries="E96", output_format="csv"), ("--format", "csv")),
    ],
    ids=["table", "json", "csv"],
)
def test_band_edges_are_the_cli_fl_fh_design(monkeypatch, capsys, state, flags):
    expected = _cli_stdout(monkeypatch, capsys, *_edges_argv(state), *_eseries_argv(state), *flags)

    assert _document(_wizard_output(state)) == _document(expected)


# --- Q reference frequency (--loss-reference-frequency) ------------------------------


@pytest.mark.parametrize(
    "state, argv",
    [
        (
            _ladder("lowpass", "butterworth", "pi", eseries="E24", output_format="json"),
            ("--inductor-q", "120"),
        ),
        (
            _bandpass("butterworth", 3, eseries="E24", output_format="json"),
            ("--capacitor-q", "500"),
        ),
    ],
    ids=["lowpass", "bandpass"],
)
def test_q_reference_frequency_is_the_cli_loss_reference_frequency(
    monkeypatch, capsys, state, argv
):
    q_state = (
        {"build_inductor_q": 120.0} if "--inductor-q" in argv else {"build_capacitor_q": 500.0}
    )
    state = replace(
        state,
        build_analysis_enabled=True,
        build_grid_points=51,
        build_reference_frequency_hz=5e6,
        **q_state,
    )
    expected = _cli_stdout(
        monkeypatch,
        capsys,
        *_design_argv(state),
        "-e",
        "E24",
        "--format",
        "json",
        "--sim-build",
        "--analysis-points",
        "51",
        "--loss-reference-frequency",
        "5MHz",
        *argv,
    )

    wizard = _wizard_output(state)
    assert _document(wizard) == _document(expected)
    assert '"reference_frequency_hz": 5000000.0' in wizard


# --- Resonator Q entered on the band-pass design screen (--qu/--ql/--qc) -------------


_RESONATOR_BUILD_ARGV = ("--sim-build", "--samples", "3", "--seed", "42", "--analysis-points", "51")
_RESONATOR_BUILD_STATE = dict(
    build_analysis_enabled=True, build_sample_count=3, build_seed=42, build_grid_points=51
)


@pytest.mark.parametrize(
    "q_state, q_argv, output_format, build",
    [
        ({"qu": 200.0}, ("--qu", "200"), "table", False),
        ({"ql": 150.0, "qc": 900.0}, ("--ql", "150", "--qc", "900"), "table", False),
        ({"qu": 200.0}, ("--qu", "200"), "json", False),
        ({"ql": 150.0}, ("--ql", "150"), "json", True),
    ],
    ids=["qu-table", "ql-qc-table", "qu-json", "ql-build-json"],
)
def test_resonator_q_is_the_cli_qu_ql_qc_design(
    monkeypatch, capsys, q_state, q_argv, output_format, build
):
    state = _bandpass(
        "chebyshev",
        5,
        eseries="E24",
        output_format=output_format,
        **q_state,
        **(_RESONATOR_BUILD_STATE if build else {}),
    )
    flags = ("--format", output_format) if output_format != "table" else ()
    if build:
        flags += _RESONATOR_BUILD_ARGV
    expected = _cli_stdout(
        monkeypatch, capsys, *_bandpass_argv(state), "-e", "E24", *q_argv, *flags
    )

    assert _document(_wizard_output(state)) == _document(expected)


@pytest.mark.parametrize("fmt", ["json", "csv"])
@pytest.mark.parametrize(
    "q_state", [{"qu": 200.0}, {"ql": 150.0, "qc": 900.0}], ids=["qu", "ql-qc"]
)
@pytest.mark.parametrize("output_format", ["table", "json", "csv"])
def test_response_file_with_resonator_q_is_the_cli_plot_data_without_it(
    monkeypatch, capsys, fmt, q_state, output_format
):
    """The response data file leaves Qu/QL/QC out, as the web's response downloads do."""
    state = _saved(_bandpass("chebyshev", 5, eseries="E24", output_format=output_format, **q_state))
    expected = _cli_stdout(monkeypatch, capsys, *_bandpass_argv(state), "--plot-data", fmt)

    assert format_response_export(state, fmt) == expected


# --- Disabled controls reach the saved files that can use them ------------------------


def test_values_only_with_eseries_none_saves_the_cli_no_match_documents(monkeypatch, capsys):
    """Values only disables the E-series; the saved JSON/CSV still use the visible None."""
    from filter_lib.wizard.export_formatting import format_component_csv, format_component_json

    state = _saved(_ladder("lowpass", "chebyshev", "t", eseries="none", output_format="quiet"))
    quiet = _cli_stdout(monkeypatch, capsys, *_ladder_argv(state), "-q")
    json_doc = _cli_stdout(
        monkeypatch, capsys, *_ladder_argv(state), "--no-match", "--format", "json"
    )
    csv_doc = _cli_stdout(
        monkeypatch, capsys, *_ladder_argv(state), "--no-match", "--format", "csv"
    )

    assert _document(state.output_text) == _document(quiet)
    assert format_component_json(state) == json_doc
    assert format_component_csv(state) == csv_doc


def test_values_only_with_a_ticked_build_saves_the_cli_sim_build_json(monkeypatch, capsys):
    from filter_lib.wizard.export_formatting import format_component_json

    state = _saved(
        _ladder(
            "highpass", "butterworth", "pi", eseries="E12", output_format="quiet", **_BUILD_STATE
        )
    )
    quiet = _cli_stdout(monkeypatch, capsys, *_ladder_argv(state), "-q")
    expected = _cli_stdout(
        monkeypatch, capsys, *_ladder_argv(state), "-e", "E12", "--format", "json", *_BUILD_ARGV
    )

    assert state.build_analysis is None
    assert _document(state.output_text) == _document(quiet)
    assert format_component_json(state) == expected


def test_csv_with_resonator_q_saves_the_cli_qu_json(monkeypatch, capsys):
    """Qu is disabled for CSV; the CSV is the plain design and the saved JSON uses Qu."""
    from filter_lib.wizard.export_formatting import format_component_csv, format_component_json

    state = _saved(_bandpass("butterworth", 3, eseries="E24", output_format="csv", qu=200.0))
    csv_doc = _cli_stdout(monkeypatch, capsys, *_bandpass_argv(state), "--format", "csv")
    json_doc = _cli_stdout(
        monkeypatch, capsys, *_bandpass_argv(state), "--format", "json", "--qu", "200"
    )

    assert _document(state.output_text) == _document(csv_doc)
    assert format_component_csv(state) == csv_doc
    assert format_component_json(state) == json_doc
