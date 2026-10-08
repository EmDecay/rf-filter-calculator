"""A saved JSON that uses a build or resonator Q the result shown did not.

The result shown never runs a disabled build: that JSON's design is calculated only when
the user saves it, in a background worker, as the web does when its JSON is downloaded.
A failure there saves no JSON, says why in plain words, and still saves the response
data file. These drive the mounted Results screen so the real worker runs.
"""

from __future__ import annotations

import asyncio

from textual.widgets import RadioButton, RadioSet

from filter_lib.wizard.app import FilterWizardApp
from filter_lib.wizard.screens.results import (
    JSON_NOT_SAVED_PREFIX,
    PREPARING_JSON_MESSAGE,
    ResultsScreen,
)
from filter_lib.wizard.state import FilterState
from tests.cli_parity_helpers import cli_stdout

_LOWPASS_ARGV = ("lowpass", "butterworth", "pi", "10MHz", "-n", "3")


def _csv_with_ticked_build(**overrides) -> FilterState:
    """CSV result with the build ticked: the build is disabled for the result shown."""
    values = dict(
        category="lowpass",
        filter_type="butterworth",
        topology="pi",
        frequency_hz=10e6,
        order=3,
        eseries="E24",
        output_format="csv",
        build_analysis_enabled=True,
        build_grid_points=51,
    )
    values.update(overrides)
    return FilterState(**values)


def _save_json(state: FilterState) -> list[tuple[str, str]]:
    """Show the result, save it as JSON, wait for every worker; return the notices."""
    notices: list[tuple[str, str]] = []

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
            assert isinstance(screen, ResultsScreen)
            # The result shown never depends on the disabled build.
            assert app.filter_state.calculation_status == "success"

            def record(message, *, severity="information", **_kwargs):
                notices.append((severity, str(message)))

            screen.notify = record  # type: ignore[assignment]
            screen.query_one("#export-btn").press()
            await pilot.pause()
            radio_set = screen.query_one("#export-format", RadioSet)
            radio_set.query_one("#export-json", RadioButton).value = True
            await pilot.pause()
            screen.query_one("#save-btn").press()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

    asyncio.run(exercise())
    return notices


def test_a_disabled_build_reaches_the_saved_json_calculated_on_save(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    expected = cli_stdout(
        monkeypatch,
        capsys,
        *_LOWPASS_ARGV,
        "--format",
        "json",
        "--sim-build",
        "--analysis-points",
        "51",
    )

    notices = _save_json(_csv_with_ticked_build())

    saved = list(tmp_path.glob("lowpass-*.json"))
    assert len(saved) == 1
    assert saved[0].read_text(encoding="utf-8") == expected
    assert notices[0] == ("information", PREPARING_JSON_MESSAGE)
    assert notices[-1][1].startswith("Saved to ")


def test_a_json_whose_build_cannot_run_is_not_saved_but_the_response_file_is(
    monkeypatch, capsys, tmp_path
):
    """Q frequency without any Q: the CLI refuses that build, so the JSON says why."""
    monkeypatch.chdir(tmp_path)
    state = _csv_with_ticked_build(build_reference_frequency_hz=5e6, export_format="csv")
    expected_response = cli_stdout(monkeypatch, capsys, *_LOWPASS_ARGV, "--plot-data", "csv")

    notices = _save_json(state)

    assert list(tmp_path.glob("*.json")) == []
    responses = list(tmp_path.glob("lowpass-*-response.csv"))
    assert len(responses) == 1
    assert responses[0].read_text(encoding="utf-8") == expected_response
    errors = [message for severity, message in notices if severity == "error"]
    assert len(errors) == 1
    assert errors[0].startswith(JSON_NOT_SAVED_PREFIX)
    assert "frequency at which the Q values apply" in errors[0]
    assert "Traceback" not in errors[0]


def test_unreadable_hidden_build_fields_are_reported_when_the_json_is_saved(monkeypatch, tmp_path):
    """Fields not checked for the result (the build was disabled) are checked on Save."""
    monkeypatch.chdir(tmp_path)
    message = "Build simulation: Capacitor tolerance must be a number"
    state = _csv_with_ticked_build(build_input_error=message, export_format="json")

    notices = _save_json(state)

    assert [path.name.endswith("-response.json") for path in tmp_path.iterdir()] == [True]
    assert ("error", f"{JSON_NOT_SAVED_PREFIX}{message}") in notices
    # Refused before any calculation started, so no "Preparing" notice.
    assert ("information", PREPARING_JSON_MESSAGE) not in notices


def test_a_json_that_needs_no_design_of_its_own_saves_without_a_worker(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.chdir(tmp_path)
    state = _csv_with_ticked_build(build_analysis_enabled=False)
    expected = cli_stdout(monkeypatch, capsys, *_LOWPASS_ARGV, "--format", "json")

    notices = _save_json(state)

    saved = list(tmp_path.glob("lowpass-*.json"))
    assert [path.read_text(encoding="utf-8") for path in saved] == [expected]
    assert ("information", PREPARING_JSON_MESSAGE) not in notices
