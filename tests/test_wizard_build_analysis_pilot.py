"""Real Textual pilot coverage for the optional realized-build wizard path."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import pytest
from textual.widgets import Button, Checkbox, Input

import filter_lib.shared.tolerance_screening as tolerance_screening
import filter_lib.wizard.screens.results as results_module
from filter_lib.wizard.app import FilterWizardApp
from filter_lib.wizard.screens import OutputOptionsScreen, ResultsScreen
from filter_lib.wizard.state import FilterState


def test_advanced_build_controls_are_keyboard_accessible() -> None:
    async def exercise() -> None:
        app = FilterWizardApp()
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            app.push_screen(OutputOptionsScreen())
            await pilot.pause()

            toggle = app.screen.query_one("#build-analysis-enabled", Checkbox)
            options = app.screen.query_one("#build-analysis-options")
            assert toggle.value is False
            assert options.display is False
            assert app.screen.query_one("#build-source-resistance", Input).value == ""
            assert app.screen.query_one("#build-load-resistance", Input).value == ""
            assert app.screen.query_one("#build-capacitor-tolerance", Input).value == "5"
            assert app.screen.query_one("#build-inductor-tolerance", Input).value == "10"
            assert app.screen.query_one("#build-inductor-q", Input).value == ""
            assert app.screen.query_one("#build-capacitor-q", Input).value == ""
            assert app.screen.query_one("#build-resonator-q", Input).value == ""
            assert app.screen.query_one("#build-resonator-q", Input).display is False
            assert app.screen.query_one("#build-sample-count", Input).value == "0"
            assert app.screen.query_one("#build-seed", Input).value == "0"
            assert app.screen.query_one("#build-grid-points", Input).value == "601"
            assert app.screen.query_one("#build-use-toroids", Checkbox).value is True

            toggle.focus()
            await pilot.press("space")
            await pilot.pause()
            source = app.screen.query_one("#build-source-resistance", Input)
            assert toggle.value is True
            assert options.display is True
            assert source.has_focus

            await pilot.press("enter")
            assert app.screen.query_one("#build-load-resistance", Input).has_focus

            app.screen.query_one("#build-capacitor-q", Input).focus()
            await pilot.press("enter")
            assert app.screen.query_one("#build-sample-count", Input).has_focus

    asyncio.run(exercise())


def test_complete_resonator_q_is_visible_only_for_bandpass() -> None:
    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state.category = "bandpass"
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            app.push_screen(OutputOptionsScreen())
            await pilot.pause()

            assert app.screen.query_one("#build-resonator-q", Input).display is True
            assert app.screen.query_one("#build-resonator-q-label").display is True
            app.screen.query_one("#build-capacitor-q", Input).focus()
            await pilot.press("enter")
            assert app.screen.query_one("#build-resonator-q", Input).has_focus

    asyncio.run(exercise())


def test_realized_build_worker_completes_in_running_app() -> None:
    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = FilterState(
            category="lowpass",
            filter_type="butterworth",
            frequency_hz=10e6,
            impedance=50.0,
            order=3,
            topology="pi",
            output_format="table",
            show_plot=False,
            eseries="E24",
            build_analysis_enabled=True,
            build_grid_points=51,
            build_use_toroid_candidates=False,
        )
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            app.push_screen(ResultsScreen())
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            state = app.filter_state
            assert state.calculation_status == "success"
            assert state.build_analysis is not None
            assert "Calculated exact values" in state.output_text
            assert "Selected nominal build" in state.output_text
            assert "Tolerance screening" in state.output_text
            assert app.screen.query_one("#export-btn", Button).disabled is False

    asyncio.run(exercise())


def _minutes_long_build_state() -> FilterState:
    """A realized-build analysis of 10 000 samples on a 5001-point grid (minutes of work)."""
    return FilterState(
        category="lowpass",
        filter_type="butterworth",
        frequency_hz=10e6,
        order=3,
        topology="pi",
        show_plot=False,
        eseries="E24",
        build_analysis_enabled=True,
        build_sample_count=10_000,
        build_grid_points=5001,
        build_use_toroid_candidates=False,
    )


def _track_worker(monkeypatch) -> SimpleNamespace:
    """Record the Results worker thread, when screening starts, and when it returns."""
    tracker = SimpleNamespace(
        threads=[], outcomes=[], screening=threading.Event(), finished=threading.Event()
    )
    real_calculate = results_module.calculate_and_format
    real_measure = tolerance_screening.measure_circuit

    def calculate(snapshot, *args, **kwargs):
        tracker.threads.append(threading.current_thread())
        try:
            outcome = real_calculate(snapshot, *args, **kwargs)
            tracker.outcomes.append(outcome)
            return outcome
        finally:
            tracker.finished.set()

    def measure(*args, **kwargs):
        tracker.screening.set()
        return real_measure(*args, **kwargs)

    monkeypatch.setattr(results_module, "calculate_and_format", calculate)
    monkeypatch.setattr(tolerance_screening, "measure_circuit", measure)
    return tracker


def _run_then_join_worker_threads(exercise, tracker: SimpleNamespace) -> None:
    """Run ``exercise`` on its own loop and require its worker thread to have stopped.

    ``asyncio.run`` joins executor threads before returning, which would turn a worker
    that ignores cancellation into a silent multi-minute wait. Here the calculation must
    return within 5 s of the app closing; only then is the executor shut down.
    """
    threads_before = set(threading.enumerate())
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(exercise())
        assert tracker.finished.wait(timeout=5), "the calculation kept running after quit"
        loop.run_until_complete(loop.shutdown_default_executor())
    finally:
        loop.close()
    assert [outcome.error for outcome in tracker.outcomes] == ["Calculation cancelled"]
    assert [thread for thread in threading.enumerate() if thread not in threads_before] == []


def test_quitting_during_a_long_build_analysis_stops_its_worker_thread(monkeypatch) -> None:
    tracker = _track_worker(monkeypatch)

    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = _minutes_long_build_state()
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            app.push_screen(ResultsScreen())
            assert await asyncio.to_thread(tracker.screening.wait, 10)
            await pilot.press("q")

    _run_then_join_worker_threads(exercise, tracker)


@pytest.mark.parametrize("leave_by", ["escape", "design another"])
def test_leaving_results_during_a_long_build_analysis_stops_its_worker_thread(
    monkeypatch, leave_by
) -> None:
    tracker = _track_worker(monkeypatch)

    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = _minutes_long_build_state()
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            app.push_screen(OutputOptionsScreen())
            await pilot.pause()
            app.push_screen(ResultsScreen())
            assert await asyncio.to_thread(tracker.screening.wait, 10)

            if leave_by == "escape":
                await pilot.press("escape")
            else:
                app.screen.query_one("#another-btn", Button).press()
            # The app is still running, so only the worker's own cancellation can stop it.
            assert await asyncio.to_thread(tracker.finished.wait, 5)
            await pilot.pause()

            assert not isinstance(app.screen, ResultsScreen)
            assert (app.filter_state.calculation_status, app.filter_state.output_text) == (
                "idle",
                "",
            )
            assert app.return_code is None

    _run_then_join_worker_threads(exercise, tracker)
