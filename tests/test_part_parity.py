"""Every surface gives the same parts for a non-default capacitor grade and a forced kind.

The matrix below names, for each scenario (capacitor grade "tight", or build inductors
"air-coil"), with the build simulation on and off, and for each output (table, JSON, CSV,
and the chosen-parts and calculated-values SPICE decks), what each surface does:

- the CLI accepts the flags (its output is the reference) or refuses them with its message;
- the web gives the CLI's bytes for a stated set of flags, through the page (table) or the
  real download routes, and when it leaves an option out of a document, the shared rule's
  reason for that document is checked too;
- the wizard's saved files (Text, JSON, CSV, through the mounted Save action) give the CLI's
  bytes, or the CSV is refused when it would lose the build; it offers no SPICE.

Two web cells follow the user's decision that the web uses its build fields ("Inductors in
the build" among them) only while "Simulate the built filter" is ticked: with the build
off, the forced kind is not used, so the page and the chosen-parts deck are the CLI's
without the flag. A forced kind with no part ("air-coil", "chip") states its reason and
simulates the calculated value on all three surfaces, and both sourced exclusion texts reach
all three surfaces for a VHF design.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import pytest

from filter_lib.design.option_applicability import (
    BUILD,
    CAPACITOR_GRADE,
    EXACT_SPICE_MATCHING_MESSAGE,
    OutputChoices,
    document_reasons,
)
from filter_lib.design.render import BUILD_TARGET_NOTE
from filter_lib.design.render_options import BUILD_NEEDS_TABLE_OR_JSON_MESSAGE
from filter_lib.shared.inductor_suggestion import (
    AIR_COIL_EXCLUSION,
    CHIP_NOT_AVAILABLE,
    VHF_TOROID_EXCLUSION,
)
from filter_lib.wizard.state import CSV_WITH_BUILD_MESSAGE, FilterState
from tests.cli_parity_helpers import cli_stderr, cli_stdout

LOWPASS = ("lp", "bw", "pi", "10MHz", "-n", "3")
GRADE = ("--capacitor-grade", "tight")
FORCED = ("--build-inductors", "air-coil")
BUILD_FLAGS = ("--sim-build", "--analysis-points", "51")
OUTPUT_FLAGS = {
    "table": (),
    "json": ("--format", "json"),
    "csv": ("--format", "csv"),
    "spice-nominal": ("--format", "spice"),
    "spice-exact": ("--format", "spice", "--spice-realization", "exact"),
}
SIM_BUILD_FORMAT = "--sim-build is supported only with table or JSON output"
FORCED_NEEDS_BUILD = "--build-inductors requires --sim-build or --format spice"


def _exact_refusal(flag: str) -> str:
    return (
        f"{flag} has no effect on an exact SPICE deck, which uses the calculated values "
        "without losses; remove it or use --spice-realization nominal-build"
    )


@dataclass(frozen=True)
class Accept:
    """The CLI accepts the cell's flags; its output is the reference."""


@dataclass(frozen=True)
class Refuse:
    """The surface refuses the cell with this message."""

    message: str


@dataclass(frozen=True)
class Same:
    """The surface gives the CLI's bytes for these flags (on top of the output's own).

    ``left_out`` names an option the surface leaves out of this document, with the shared
    rule's reason for that document.
    """

    flags: tuple[str, ...]
    left_out: tuple[str, str] | None = None


@dataclass(frozen=True)
class NotOffered:
    """The surface has no such output (the wizard saves no SPICE)."""


@dataclass(frozen=True)
class Cell:
    scenario: str
    build: bool
    output: str
    cli: object
    web: object
    wizard: object

    @property
    def scenario_flags(self) -> tuple[str, ...]:
        return GRADE if self.scenario == "grade" else FORCED

    @property
    def cli_flags(self) -> tuple[str, ...]:
        return self.scenario_flags + (BUILD_FLAGS if self.build else ())

    @property
    def id(self) -> str:
        return f"{self.scenario}-build-{'on' if self.build else 'off'}-{self.output}"


_EXACT_GRADE = (CAPACITOR_GRADE, EXACT_SPICE_MATCHING_MESSAGE)
_CSV_BUILD = (BUILD, BUILD_NEEDS_TABLE_OR_JSON_MESSAGE)
MATRIX = (
    # Capacitor grade "tight", build off.
    Cell("grade", False, "table", Accept(), Same(GRADE), Same(GRADE)),
    Cell("grade", False, "json", Accept(), Same(GRADE), Same(GRADE)),
    Cell("grade", False, "csv", Accept(), Same(GRADE), Same(GRADE)),
    Cell("grade", False, "spice-nominal", Accept(), Same(GRADE), NotOffered()),
    Cell(
        "grade",
        False,
        "spice-exact",
        Refuse(_exact_refusal("--capacitor-grade")),
        Same((), left_out=_EXACT_GRADE),
        NotOffered(),
    ),
    # Capacitor grade "tight", build on.
    Cell("grade", True, "table", Accept(), Same(GRADE + BUILD_FLAGS), Same(GRADE + BUILD_FLAGS)),
    Cell("grade", True, "json", Accept(), Same(GRADE + BUILD_FLAGS), Same(GRADE + BUILD_FLAGS)),
    Cell(
        "grade",
        True,
        "csv",
        Refuse(SIM_BUILD_FORMAT),
        Same(GRADE, left_out=_CSV_BUILD),
        Refuse(CSV_WITH_BUILD_MESSAGE),
    ),
    # The chosen-parts deck uses the build fields (defaults here) but never runs the build.
    Cell("grade", True, "spice-nominal", Refuse(SIM_BUILD_FORMAT), Same(GRADE), NotOffered()),
    Cell(
        "grade",
        True,
        "spice-exact",
        Refuse(SIM_BUILD_FORMAT),
        Same((), left_out=_EXACT_GRADE),
        NotOffered(),
    ),
    # Build inductors "air-coil", build off: the web and wizard keep it with the build.
    Cell("forced", False, "table", Refuse(FORCED_NEEDS_BUILD), Same(()), Same(())),
    Cell("forced", False, "json", Refuse(FORCED_NEEDS_BUILD), Same(()), Same(())),
    Cell("forced", False, "csv", Refuse(FORCED_NEEDS_BUILD), Same(()), Same(())),
    Cell("forced", False, "spice-nominal", Accept(), Same(()), NotOffered()),
    Cell(
        "forced",
        False,
        "spice-exact",
        Refuse(_exact_refusal("--build-inductors")),
        Same(()),
        NotOffered(),
    ),
    # Build inductors "air-coil", build on.
    Cell("forced", True, "table", Accept(), Same(FORCED + BUILD_FLAGS), Same(FORCED + BUILD_FLAGS)),
    Cell("forced", True, "json", Accept(), Same(FORCED + BUILD_FLAGS), Same(FORCED + BUILD_FLAGS)),
    Cell(
        "forced",
        True,
        "csv",
        Refuse(SIM_BUILD_FORMAT),
        Same((), left_out=_CSV_BUILD),
        Refuse(CSV_WITH_BUILD_MESSAGE),
    ),
    Cell("forced", True, "spice-nominal", Refuse(SIM_BUILD_FORMAT), Same(FORCED), NotOffered()),
    Cell("forced", True, "spice-exact", Refuse(SIM_BUILD_FORMAT), Same(()), NotOffered()),
)
IDS = [cell.id for cell in MATRIX]


def test_the_matrix_covers_every_scenario_build_and_output():
    covered = {(cell.scenario, cell.build, cell.output) for cell in MATRIX}

    assert covered == {
        (scenario, build, output)
        for scenario in ("grade", "forced")
        for build in (False, True)
        for output in OUTPUT_FLAGS
    }
    for cell in MATRIX:
        expected_wizard = NotOffered if cell.output.startswith("spice") else (Same, Refuse)
        assert isinstance(cell.wizard, expected_wizard), cell.id


def _flat(text: str) -> str:
    return " ".join(text.split())


# -- CLI ------------------------------------------------------------------------------------


@pytest.mark.parametrize("cell", MATRIX, ids=IDS)
def test_cli_cell(monkeypatch, capsys, cell):
    argv = (*LOWPASS, *OUTPUT_FLAGS[cell.output], *cell.cli_flags)
    if isinstance(cell.cli, Refuse):
        last_line = cli_stderr(monkeypatch, capsys, *argv).strip().splitlines()[-1]
        assert last_line == f"filter-calc lowpass: error: {cell.cli.message}"
        return
    output = cli_stdout(monkeypatch, capsys, *argv)
    if cell.scenario == "forced":
        # No part of the forced kind: its sourced reason, and the calculated value.
        assert _flat(AIR_COIL_EXCLUSION) in _flat(output)
    if cell.scenario == "grade" and cell.output == "csv":
        assert "grade=tight" in output


# -- Web ------------------------------------------------------------------------------------

_WEB_FIELDS = {
    "filter_type": "butterworth",
    "topology": "pi",
    "frequency": "10MHz",
    "components": "3",
    "impedance": "50",
    "eseries": "E24",
    "output_format": "table",
    "inductor_suggestions": "best",
}


def _web_form(cell: Cell) -> dict[str, str]:
    form = dict(_WEB_FIELDS)
    if cell.scenario == "grade":
        form["capacitor_grade"] = "tight"
    else:
        form["build_inductors"] = "air-coil"
    if cell.build:
        form["sim_build"] = "on"
        # A deck sweeps the build's frequency points; keep the CLI's default there.
        form["build_grid_points"] = "601" if cell.output.startswith("spice") else "51"
    return form


@pytest.fixture(scope="module")
def client():
    pytest.importorskip("fastapi")
    from tests.web_helpers import web_client

    with web_client() as test_client:
        yield test_client


@pytest.mark.parametrize("cell", MATRIX, ids=IDS)
def test_web_cell(monkeypatch, capsys, client, cell):
    from tests.web_helpers import HTMX, output_text

    expected = cli_stdout(
        monkeypatch, capsys, *LOWPASS, *OUTPUT_FLAGS[cell.output], *cell.web.flags
    )
    form = _web_form(cell)
    if cell.output == "table":
        response = client.post("/design/lowpass", data=form, headers=HTMX)
        body = output_text(response.text) + "\n"
    else:
        response = client.post(f"/export/lowpass/{cell.output}", data=form)
        body = response.text

    assert response.status_code == 200
    assert body == expected
    if cell.web.left_out is not None:
        option, reason = cell.web.left_out
        choices = OutputChoices(build=cell.build)
        assert document_reasons(choices, cell.output)[option] == reason


# -- Wizard ---------------------------------------------------------------------------------


def _wizard_state(scenario: str, build: bool) -> FilterState:
    values = dict(
        category="lowpass",
        filter_type="butterworth",
        topology="pi",
        frequency_hz=10e6,
        order=3,
        eseries="E24",
        output_format="table",
        show_plot=False,
        build_analysis_enabled=build,
        build_grid_points=51,
    )
    if scenario == "grade":
        values["capacitor_grade"] = "tight"
    else:
        values["build_inductors"] = "air-coil"
    return FilterState(**values)


def _save_each(state: FilterState) -> dict[str, object]:
    """Show the result in the mounted wizard, then Save as Text, JSON, and CSV in turn.

    Returns each saved file's text, or the CSV's refusal (its button disabled, with the
    reason shown) when it cannot be saved.
    """
    from textual.widgets import RadioButton, RadioSet, Static

    from filter_lib.wizard.app import FilterWizardApp
    from filter_lib.wizard.screens.results import ResultsScreen

    saved: dict[str, object] = {}

    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = state
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            app.push_screen(ResultsScreen())
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            screen = app.screen
            assert app.filter_state.calculation_status == "success"
            for button_id, extension in (
                ("export-txt", "txt"),
                ("export-json", "json"),
                ("export-csv", "csv"),
            ):
                screen.query_one("#export-btn").press()
                await pilot.pause()
                radio_set = screen.query_one("#export-format", RadioSet)
                button = radio_set.query_one(f"#{button_id}", RadioButton)
                if button.disabled:
                    reason = screen.query_one("#export-csv-reason", Static)
                    saved[extension] = Refuse(str(reason.render()))
                    continue
                button.value = True
                await pilot.pause()
                screen.query_one("#save-btn").press()
                await pilot.pause()
                await app.workers.wait_for_complete()
                await pilot.pause()

    asyncio.run(exercise())
    return saved


def _as_cli_table(text: str, build: bool) -> str:
    """The wizard's Text as the CLI prints it: no build note, and the CLI's last lines."""
    if build:
        return text.replace(f"\n\n{BUILD_TARGET_NOTE}\n", "\n\n") + "\n"
    return text + "\n\n"


@pytest.mark.parametrize(
    "scenario, build",
    [("grade", False), ("grade", True), ("forced", False), ("forced", True)],
    ids=["grade-build-off", "grade-build-on", "forced-build-off", "forced-build-on"],
)
def test_wizard_cells(monkeypatch, capsys, tmp_path, scenario, build):
    monkeypatch.chdir(tmp_path)
    cells = {
        cell.output: cell
        for cell in MATRIX
        if (cell.scenario, cell.build) == (scenario, build)
        and not isinstance(cell.wizard, NotOffered)
    }
    expected = {
        output: cli_stdout(monkeypatch, capsys, *LOWPASS, *OUTPUT_FLAGS[output], *cell.wizard.flags)
        for output, cell in cells.items()
        if isinstance(cell.wizard, Same)
    }

    results = _save_each(_wizard_state(scenario, build))
    for extension in ("txt", "json", "csv"):
        if not isinstance(results.get(extension), Refuse):
            [path] = tmp_path.glob(f"lowpass-*.{extension}")
            results[extension] = path.read_text(encoding="utf-8")

    assert set(cells) == {"table", "json", "csv"}
    assert _as_cli_table(results["txt"], build) == expected["table"]
    assert results["json"] == expected["json"]
    if isinstance(cells["csv"].wizard, Refuse):
        assert results["csv"] == cells["csv"].wizard
    else:
        assert results["csv"] == expected["csv"]


# -- A forced kind with no part, and the sourced exclusions, on every surface ---------------


@pytest.mark.parametrize(
    "kind, reason", [("air-coil", AIR_COIL_EXCLUSION), ("chip", CHIP_NOT_AVAILABLE)]
)
def test_a_forced_kind_with_no_part_says_why_and_builds_calculated_everywhere(
    monkeypatch, capsys, client, kind, reason
):
    from filter_lib.wizard.calculation_handler import calculate_and_format
    from tests.web_helpers import HTMX, output_text

    flags = ("--build-inductors", kind)
    table = cli_stdout(monkeypatch, capsys, *LOWPASS, *BUILD_FLAGS, *flags)
    document = json.loads(
        cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "json", *BUILD_FLAGS, *flags)
    )
    form = {**_WEB_FIELDS, "sim_build": "on", "build_grid_points": "51", "build_inductors": kind}
    page = output_text(client.post("/design/lowpass", data=form, headers=HTMX).text) + "\n"
    state = FilterState(
        category="lowpass",
        filter_type="butterworth",
        topology="pi",
        frequency_hz=10e6,
        order=3,
        show_plot=False,
        build_analysis_enabled=True,
        build_grid_points=51,
        build_inductors=kind,
    )
    wizard = calculate_and_format(state).output_text

    for text in (table, page, _as_cli_table(wizard, build=True)):
        assert _flat(f"L1: {reason} The simulation uses the calculated value.") in _flat(text)
        assert "calculated value used (no inductor suggestion used)" in text
    assert page == table
    [inductor] = [
        part for part in document["nominal_build"]["substitutions"] if part["logical_name"] == "L1"
    ]
    assert inductor["method"] == "exact_fallback"
    assert inductor["nominal_value_si"] == inductor["calculated_value_si"]


def test_both_sourced_exclusions_reach_every_surface_for_a_vhf_design(monkeypatch, capsys, client):
    from filter_lib.wizard.calculation_handler import calculate_and_format
    from tests.web_helpers import HTMX, output_text

    argv = ("lp", "ch", "pi", "146MHz", "-n", "5", "-r", "0.1")
    table = cli_stdout(monkeypatch, capsys, *argv)
    form = {
        **_WEB_FIELDS,
        "filter_type": "chebyshev",
        "frequency": "146MHz",
        "components": "5",
        "ripple": "0.1",
    }
    page = output_text(client.post("/design/lowpass", data=form, headers=HTMX).text) + "\n"
    state = FilterState(
        category="lowpass",
        filter_type="chebyshev",
        topology="pi",
        frequency_hz=146e6,
        order=5,
        ripple_db=0.1,
        show_plot=False,
    )
    wizard = calculate_and_format(state).output_text

    assert page == table
    assert _as_cli_table(wizard, build=False) == table
    for reason in (VHF_TOROID_EXCLUSION, AIR_COIL_EXCLUSION):
        assert _flat(reason) in _flat(table)
