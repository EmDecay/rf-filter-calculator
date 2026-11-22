"""Every surface gives the same parts for a non-default capacitor grade and a forced kind.

The matrix below names, for each scenario (capacitor grade "tight", build inductors
"air-coil", or build inductors "chip"), with the build simulation on and off, and for each
output (table, JSON, CSV, and the chosen-parts and calculated-values SPICE decks), what
each surface does:

- the CLI accepts the flags (its output is the reference) or refuses them with its message;
- the web gives the CLI's bytes for a stated set of flags, through the page (table) or the
  real download routes, and when it leaves an option out of a document, the shared rule's
  reason for that document is checked too;
- the wizard's saved files (through the mounted Save action, which offers Text, JSON and
  CSV only, never SPICE): JSON and CSV give the CLI's bytes, or the CSV is refused when it
  would lose the build; Text saves the table as the wizard shows it, which is the CLI's
  table with two stated differences (``ScreenText``).

The grade scenario uses a 146 MHz low-pass whose C1 is 4.3 pF || 9.1 pF at the standard
grade and 2.4 pF || 11 pF at the tight one, so a surface that dropped the grade would fail;
the forced-kind scenario uses a 10 MHz low-pass whose toroids the forced kind replaces. The
chip scenario uses a 40 MHz, 12.5 ohm low-pass whose 99.47 nH inductor auto builds as a
T25-6 winding and the forced kind as a chip inductor with its self-capacitance, so a surface
that dropped the choice would show the toroid.

Two web cells follow the user's decision that the web uses its build fields ("Inductors in
the build" among them) only while "Simulate the built filter" is ticked: with the build
off, the forced kind is not used, so the page and the chosen-parts deck are the CLI's
without the flag. A forced kind with no part ("air-coil", "chip") states its reason and
simulates the calculated value on all three surfaces, and both sourced exclusion texts reach
all three surfaces for a VHF design.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from dataclasses import dataclass

import pytest

from filter_lib.design.option_applicability import (
    BUILD,
    BUILD_INDUCTORS,
    CAPACITOR_GRADE,
    CSV_BUILD_INDUCTORS_MESSAGE,
    EXACT_SPICE_BUILD_INDUCTORS_MESSAGE,
    EXACT_SPICE_MATCHING_MESSAGE,
    OutputChoices,
    document_own_options,
    document_reasons,
)
from filter_lib.design.render import BUILD_TARGET_NOTE
from filter_lib.design.render_options import BUILD_NEEDS_TABLE_OR_JSON_MESSAGE
from filter_lib.shared.build_output_formatting import BUILD_SIMULATION_HEADING
from filter_lib.shared.chip_selection import no_qualifying_chip_reason
from filter_lib.shared.inductor_suggestion import (
    AIR_COIL_EXCLUSION,
    VHF_TOROID_EXCLUSION,
)
from filter_lib.shared.srf_screen import LIMIT_ALLOWANCE, CheckWindow
from filter_lib.wizard.state import CSV_WITH_BUILD_MESSAGE, FilterState
from tests.cli_parity_helpers import cli_stderr, cli_stdout

LOWPASS = ("lp", "bw", "pi", "10MHz", "-n", "3")
# The 10 MHz low-pass's inductor (about 1.6 µH) is far above the chip catalog.
LOWPASS_CHIP_REASON = no_qualifying_chip_reason(frozenset({LIMIT_ALLOWANCE}), CheckWindow(0, 10e6))
# The grades choose different parts here (see the module docstring).
GRADE_DESIGN = ("lp", "bw", "pi", "146MHz", "-n", "5")
TIGHT_C1 = ("C1A 1 0 2.4e-12", "C1B 1 0 1.1e-11")
STANDARD_C1 = ("C1A 1 0 4.3e-12", "C1B 1 0 9.1e-12")
GRADE = ("--capacitor-grade", "tight")
FORCED = ("--build-inductors", "air-coil")
CHIP_DESIGN = ("lp", "bw", "pi", "40MHz", "-n", "3", "-z", "12.5")
CHIP = ("--build-inductors", "chip")
# Each scenario's design, its flags, and the same choices as web fields and wizard state.
SCENARIOS = {
    "grade": (
        GRADE_DESIGN,
        GRADE,
        {"frequency": "146MHz", "components": "5", "capacitor_grade": "tight"},
        {"frequency_hz": 146e6, "order": 5, "capacitor_grade": "tight"},
    ),
    "forced": (LOWPASS, FORCED, {"build_inductors": "air-coil"}, {"build_inductors": "air-coil"}),
    "chip": (
        CHIP_DESIGN,
        CHIP,
        {"frequency": "40MHz", "impedance": "12.5", "build_inductors": "chip"},
        {"frequency_hz": 40e6, "impedance": 12.5, "build_inductors": "chip"},
    ),
}
# The forced kind of each scenario that forces one.
FORCED_KINDS = {"forced": "air-coil", "chip": "chip"}
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
class ScreenText:
    """The wizard's Text file: the CLI's table for these flags, as the wizard shows it.

    Two differences are part of the wizard's design: it ends without the CLI's blank line,
    and with the build shown it adds ``BUILD_TARGET_NOTE`` between the ideal design and
    the build simulation (``RenderOptions(trailing_blank=False, build_target_note=True)``).
    """

    flags: tuple[str, ...]


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
        return SCENARIOS[self.scenario][1]

    @property
    def base(self) -> tuple[str, ...]:
        return SCENARIOS[self.scenario][0]

    @property
    def cli_flags(self) -> tuple[str, ...]:
        return self.scenario_flags + (BUILD_FLAGS if self.build else ())

    @property
    def id(self) -> str:
        return f"{self.scenario}-build-{'on' if self.build else 'off'}-{self.output}"


_EXACT_GRADE = (CAPACITOR_GRADE, EXACT_SPICE_MATCHING_MESSAGE)
_EXACT_FORCED = (BUILD_INDUCTORS, EXACT_SPICE_BUILD_INDUCTORS_MESSAGE)
_CSV_BUILD = (BUILD, BUILD_NEEDS_TABLE_OR_JSON_MESSAGE)
_CSV_FORCED = (BUILD_INDUCTORS, CSV_BUILD_INDUCTORS_MESSAGE)
MATRIX = (
    # Capacitor grade "tight", build off.
    Cell("grade", False, "table", Accept(), Same(GRADE), ScreenText(GRADE)),
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
    Cell(
        "grade",
        True,
        "table",
        Accept(),
        Same(GRADE + BUILD_FLAGS),
        ScreenText(GRADE + BUILD_FLAGS),
    ),
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
    Cell("forced", False, "table", Refuse(FORCED_NEEDS_BUILD), Same(()), ScreenText(())),
    Cell("forced", False, "json", Refuse(FORCED_NEEDS_BUILD), Same(()), Same(())),
    Cell("forced", False, "csv", Refuse(FORCED_NEEDS_BUILD), Same(()), Same(())),
    Cell("forced", False, "spice-nominal", Accept(), Same(()), NotOffered()),
    Cell(
        "forced",
        False,
        "spice-exact",
        Refuse(_exact_refusal("--build-inductors")),
        Same((), left_out=_EXACT_FORCED),
        NotOffered(),
    ),
    # Build inductors "air-coil", build on.
    Cell(
        "forced",
        True,
        "table",
        Accept(),
        Same(FORCED + BUILD_FLAGS),
        ScreenText(FORCED + BUILD_FLAGS),
    ),
    Cell("forced", True, "json", Accept(), Same(FORCED + BUILD_FLAGS), Same(FORCED + BUILD_FLAGS)),
    Cell(
        "forced",
        True,
        "csv",
        Refuse(SIM_BUILD_FORMAT),
        Same((), left_out=_CSV_FORCED),
        Refuse(CSV_WITH_BUILD_MESSAGE),
    ),
    Cell("forced", True, "spice-nominal", Refuse(SIM_BUILD_FORMAT), Same(FORCED), NotOffered()),
    Cell(
        "forced",
        True,
        "spice-exact",
        Refuse(SIM_BUILD_FORMAT),
        Same((), left_out=_EXACT_FORCED),
        NotOffered(),
    ),
)


def _as_chip(cell: Cell) -> Cell:
    """A forced-kind cell with "chip" forced instead: the same rules for every kind."""

    def swap(value):
        if isinstance(value, (Same, ScreenText)) and value.flags[: len(FORCED)] == FORCED:
            return dataclasses.replace(value, flags=CHIP + value.flags[len(FORCED) :])
        return value

    return dataclasses.replace(cell, scenario="chip", web=swap(cell.web), wizard=swap(cell.wizard))


MATRIX = MATRIX + tuple(_as_chip(cell) for cell in MATRIX if cell.scenario == "forced")
IDS = [cell.id for cell in MATRIX]


def test_the_matrix_covers_every_scenario_build_and_output():
    covered = {(cell.scenario, cell.build, cell.output) for cell in MATRIX}

    assert covered == {
        (scenario, build, output)
        for scenario in SCENARIOS
        for build in (False, True)
        for output in OUTPUT_FLAGS
    }
    for cell in MATRIX:
        expected_wizard = {
            "table": ScreenText,
            "json": (Same, Refuse),
            "csv": (Same, Refuse),
        }.get(cell.output, NotOffered)
        assert isinstance(cell.wizard, expected_wizard), cell.id


def test_the_chip_design_tells_the_kinds_apart(monkeypatch, capsys):
    auto = cli_stdout(monkeypatch, capsys, *CHIP_DESIGN, "--format", "spice")
    chip = cli_stdout(monkeypatch, capsys, *CHIP_DESIGN, "--format", "spice", *CHIP)

    assert "part=T25-6 turns=6" in auto and "CSELF_" not in auto
    assert "part=LQW18ANR10G00D" in chip
    assert "CSELF_L1 1 2 7.84219687634e-14" in chip.splitlines()


def test_the_grade_design_tells_the_grades_apart(monkeypatch, capsys):
    standard = cli_stdout(monkeypatch, capsys, *GRADE_DESIGN, "--format", "spice")
    tight = cli_stdout(monkeypatch, capsys, *GRADE_DESIGN, "--format", "spice", *GRADE)

    assert all(line in standard.splitlines() for line in STANDARD_C1)
    assert all(line in tight.splitlines() for line in TIGHT_C1)


def _flat(text: str) -> str:
    return " ".join(text.split())


# -- CLI ------------------------------------------------------------------------------------


def _assert_tight_deck(deck: str) -> None:
    assert all(line in deck.splitlines() for line in TIGHT_C1), deck


@pytest.mark.parametrize("cell", MATRIX, ids=IDS)
def test_cli_cell(monkeypatch, capsys, cell):
    argv = (*cell.base, *OUTPUT_FLAGS[cell.output], *cell.cli_flags)
    if isinstance(cell.cli, Refuse):
        last_line = cli_stderr(monkeypatch, capsys, *argv).strip().splitlines()[-1]
        assert last_line == f"filter-calc lowpass: error: {cell.cli.message}"
        return
    output = cli_stdout(monkeypatch, capsys, *argv)
    if cell.scenario == "forced":
        # No part of the forced kind: its sourced reason, and the calculated value.
        assert _flat(AIR_COIL_EXCLUSION) in _flat(output)
    if cell.scenario == "chip" and (cell.build or cell.output == "spice-nominal"):
        # The forced chip inductor is built with its self-capacitance.
        assert "LQW18ANR10G00D" in output
        assert "CSELF_L1" in output or "self-capacitance" in output
    if cell.scenario == "grade" and cell.output == "csv":
        assert "grade=tight" in output
    if cell.scenario == "grade" and cell.output == "spice-nominal":
        _assert_tight_deck(output)


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


# Each option a document's own rule leaves out, and the form field that carries it.
_OPTION_FIELDS = {CAPACITOR_GRADE: "capacitor_grade", BUILD_INDUCTORS: "build_inductors"}


def _web_form(cell: Cell) -> dict[str, str]:
    form = dict(_WEB_FIELDS)
    form.update(SCENARIOS[cell.scenario][2])
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
        monkeypatch, capsys, *cell.base, *OUTPUT_FLAGS[cell.output], *cell.web.flags
    )
    form = _web_form(cell)
    from filter_lib.web import routes_design, routes_export

    route = routes_design if cell.output == "table" else routes_export
    requests = []
    real_design = route.design
    monkeypatch.setattr(
        route,
        "design",
        lambda request, **kwargs: requests.append(request) or real_design(request, **kwargs),
    )
    if cell.output == "table":
        response = client.post("/design/lowpass", data=form, headers=HTMX)
        body = output_text(response.text) + "\n"
    else:
        response = client.post(f"/export/lowpass/{cell.output}", data=form)
        body = response.text

    assert response.status_code == 200
    assert body == expected
    # The policy that reaches part resolution is the one the CLI reference uses.
    [request] = requests
    own = document_own_options(cell.output) if cell.output != "table" else frozenset()
    kind = FORCED_KINDS.get(cell.scenario)
    forced = kind is not None and cell.build and BUILD_INDUCTORS not in own
    graded = cell.scenario == "grade" and CAPACITOR_GRADE not in own
    assert request.build_inductors == (kind if forced else "auto")
    assert request.capacitor_grade == ("tight" if graded else "standard")
    if cell.scenario == "grade" and cell.output == "spice-nominal":
        _assert_tight_deck(body)
    if cell.web.left_out is not None:
        from filter_lib.web.download_inputs import download_fields

        option, reason = cell.web.left_out
        choices = OutputChoices(build=cell.build)
        assert document_reasons(choices, cell.output)[option] == reason
        if option in document_own_options(cell.output):
            # The download leaves the field out, so it never reaches part resolution.
            assert _OPTION_FIELDS[option] in form
            assert _OPTION_FIELDS[option] not in download_fields(form, cell.output)


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
    values.update(SCENARIOS[scenario][3])
    return FilterState(**values)


def _save_each(state: FilterState) -> dict[str, object]:
    """Show the result in the mounted wizard, then Save as Text, JSON, and CSV in turn.

    Returns each saved file's text, or the CSV's refusal (its button disabled, with the
    reason shown) when it cannot be saved, and under ``"offered"`` the formats the Save
    dialog offers.
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
            radio_set = screen.query_one("#export-format", RadioSet)
            saved["offered"] = [button.id for button in radio_set.query(RadioButton)]
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


def _screen_text(cli_table: str, build: bool) -> str:
    """The CLI's table as the wizard shows it (``ScreenText``).

    The CLI prints the table, a blank line, then any build simulation, and ``print`` adds a
    newline. The wizard leaves out that blank line and, with the build, puts
    ``BUILD_TARGET_NOTE`` there instead, followed by a blank line.
    """
    text = cli_table.removesuffix("\n")
    if not build:
        return text.removesuffix("\n")
    cli_gap = f"\n\n\n{BUILD_SIMULATION_HEADING}\n"
    assert text.count(cli_gap) == 1
    return text.replace(cli_gap, f"\n\n{BUILD_TARGET_NOTE}\n\n{BUILD_SIMULATION_HEADING}\n")


@pytest.mark.parametrize(
    "scenario, build",
    [(scenario, build) for scenario in SCENARIOS for build in (False, True)],
    ids=[f"{scenario}-build-{on}" for scenario in SCENARIOS for on in ("off", "on")],
)
def test_wizard_cells(monkeypatch, capsys, tmp_path, scenario, build):
    monkeypatch.chdir(tmp_path)
    cells = {
        cell.output: cell
        for cell in MATRIX
        if (cell.scenario, cell.build) == (scenario, build)
        and not isinstance(cell.wizard, NotOffered)
    }
    base = SCENARIOS[scenario][0]
    expected = {
        output: cli_stdout(monkeypatch, capsys, *base, *OUTPUT_FLAGS[output], *cell.wizard.flags)
        for output, cell in cells.items()
        if isinstance(cell.wizard, (Same, ScreenText))
    }

    results = _save_each(_wizard_state(scenario, build))
    for extension in ("txt", "json", "csv"):
        if not isinstance(results.get(extension), Refuse):
            [path] = tmp_path.glob(f"lowpass-*.{extension}")
            results[extension] = path.read_text(encoding="utf-8")

    assert set(cells) == {"table", "json", "csv"}
    # No SPICE: the matrix's SPICE cells for the wizard are "not offered".
    assert results["offered"] == ["export-txt", "export-json", "export-csv"]
    assert results["txt"] == _screen_text(expected["table"], build)
    assert results["json"] == expected["json"]
    if isinstance(cells["csv"].wizard, Refuse):
        assert results["csv"] == cells["csv"].wizard
    else:
        assert results["csv"] == expected["csv"]


# -- A forced kind with no part, and the sourced exclusions, on every surface ---------------


@pytest.mark.parametrize(
    "kind, reason", [("air-coil", AIR_COIL_EXCLUSION), ("chip", LOWPASS_CHIP_REASON)]
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

    for text in (table, page, wizard):
        assert _flat(f"L1: {reason} The simulation uses the calculated value.") in _flat(text)
        assert "calculated value used (no inductor suggestion used)" in text
    assert page == table
    assert wizard == _screen_text(table, build=True)
    [inductor] = [
        part for part in document["nominal_build"]["substitutions"] if part["logical_name"] == "L1"
    ]
    assert inductor["method"] == "exact_fallback"
    assert inductor["nominal_value_si"] == inductor["calculated_value_si"]


def test_both_sourced_exclusions_reach_every_surface_for_a_vhf_design(monkeypatch, capsys, client):
    from filter_lib.wizard.calculation_handler import calculate_and_format
    from tests.web_helpers import HTMX, output_text

    # A chip inductor qualifies, so the kinds with no part state why only in full detail.
    argv = ("lp", "ch", "pi", "146MHz", "-n", "5", "-r", "0.1", "--inductor-suggestions", "full")
    table = cli_stdout(monkeypatch, capsys, *argv)
    form = {
        **_WEB_FIELDS,
        "filter_type": "chebyshev",
        "frequency": "146MHz",
        "components": "5",
        "ripple": "0.1",
        "inductor_suggestions": "full",
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
        inductor_detail="full",
    )
    wizard = calculate_and_format(state).output_text

    assert page == table
    assert wizard == _screen_text(table, build=False)
    assert "1. Chip inductor LQW15AN75NG80D" in table
    for reason in (VHF_TOROID_EXCLUSION, AIR_COIL_EXCLUSION):
        assert _flat(reason) in _flat(table)


def test_calculated_values_with_no_suggestions_are_recorded_alike_everywhere(
    monkeypatch, capsys, client
):
    """Only the forced kinds conflict with None, so Calculated values reaches every JSON."""
    from filter_lib.wizard.calculation_handler import calculate_and_format

    flags = ("--inductor-suggestions", "none", "--build-inductors", "calculated")
    expected = cli_stdout(monkeypatch, capsys, *LOWPASS, "--format", "json", *BUILD_FLAGS, *flags)
    form = {
        **_WEB_FIELDS,
        "output_format": "json",
        "inductor_suggestions": "none",
        "sim_build": "on",
        "build_grid_points": "51",
        "build_inductors": "calculated",
    }
    api = client.post("/api/design/lowpass", data=form).text
    download = client.post("/export/lowpass/json", data=form).text
    state = FilterState(
        category="lowpass",
        filter_type="butterworth",
        topology="pi",
        frequency_hz=10e6,
        order=3,
        output_format="json",
        inductor_detail="none",
        build_analysis_enabled=True,
        build_grid_points=51,
        build_inductors="calculated",
    )
    wizard = calculate_and_format(state).output_text + "\n"

    assert json.loads(expected)["build_model"]["build_inductor_choice"] == "calculated"
    assert api == download == wizard == expected


def test_the_tank_trimmers_and_coupling_advice_are_the_same_everywhere(monkeypatch, capsys, client):
    """The 2 m band-pass: its advice, every tank's split, and the tuned build with its
    untuned and retuned tolerance cases read the same on the CLI, the web and the wizard."""
    from filter_lib.wizard.calculation_handler import calculate_and_format
    from tests.web_helpers import HTMX, output_text

    argv = ("bp", "ch", "top", "-f", "146MHz", "-b", "4MHz", "-n", "3", "-r", "0.5")
    table = cli_stdout(monkeypatch, capsys, *argv, *BUILD_FLAGS)
    document = cli_stdout(monkeypatch, capsys, *argv, "--format", "json", *BUILD_FLAGS)
    form = {
        "filter_type": "chebyshev",
        "coupling": "top",
        "frequency": "146MHz",
        "bandwidth": "4MHz",
        "resonators": "3",
        "ripple": "0.5",
        "impedance": "50",
        "eseries": "E24",
        "output_format": "table",
        "inductor_suggestions": "best",
        "sim_build": "on",
        "build_grid_points": "51",
    }
    page = output_text(client.post("/design/bandpass", data=form, headers=HTMX).text) + "\n"
    api = client.post("/api/design/bandpass", data={**form, "output_format": "json"}).text
    state = FilterState(
        category="bandpass",
        filter_type="chebyshev",
        topology="top",
        frequency_hz=146e6,
        bandwidth_hz=4e6,
        order=3,
        ripple_db=0.5,
        show_plot=False,
        build_analysis_enabled=True,
        build_grid_points=51,
    )
    wizard = calculate_and_format(state).output_text

    assert page == table
    assert api.strip() == document.strip()
    assert wizard == _screen_text(table, build=True)
    for heading in ("\nCoupling Advice\n", "\nTank Trimmers\n", "Spread after retuning"):
        assert heading in table
    data = json.loads(document)
    assert data["coupling_advice"]["advised"]["setting"] == "21nH"
    assert all(case["tuning"] for case in data["tolerance_analysis"]["cases"])


def test_a_forced_inductor_does_not_change_the_tank_split(client):
    """At 29 MHz with 75 nH tanks both a T50-2 winding and a chip inductor qualify. The
    tanks are sized for the first suggestion whatever the build uses, so the page and JSON
    with a forced chip and the Components CSV give the same sizing."""
    import csv
    import io

    from tests.web_helpers import HTMX, output_text

    form = {
        "filter_type": "chebyshev",
        "coupling": "top",
        "frequency": "29MHz",
        "bandwidth": "870kHz",
        "resonators": "3",
        "ripple": "0.5",
        "impedance": "50",
        "resonator_inductance": "75nH",
        "eseries": "E24",
        "output_format": "table",
        "inductor_suggestions": "best",
        "sim_build": "on",
        "build_grid_points": "51",
    }
    chip = {**form, "build_inductors": "chip"}

    def tanks(fields):
        body = client.post("/api/design/bandpass", data={**fields, "output_format": "json"}).text
        return json.loads(body)["tank_trimmers"]

    def section(fields):
        text = output_text(client.post("/design/bandpass", data=fields, headers=HTMX).text)
        return text.split("\nTank Trimmers\n", 1)[1].split("\nInductor Suggestions", 1)[0]

    assert tanks(chip) == tanks(form)
    assert tanks(chip)["sized_for_inductor"] == {"kind": "toroid", "part": "T50-2"}
    forced, default = " ".join(section(chip).split()), " ".join(section(form).split())
    note = (
        "The tanks are sized for toroid winding T50-2, the first inductor suggestion; the "
        "build uses chip inductor"
    )
    assert note in forced and note not in default
    rows = list(csv.DictReader(io.StringIO(client.post("/export/bandpass/csv", data=chip).text)))
    for row, tank in zip(rows[:3], tanks(chip)["tanks"], strict=True):
        assert row["Component"] == tank["name"]
        assert (row["TrimmerFit"] == "no_fit") == (not tank["fits"])
