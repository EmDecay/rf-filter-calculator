"""Real Textual pilot coverage for the optional realized-build wizard path."""

from __future__ import annotations

import asyncio

from textual.widgets import Button, Checkbox, Input

from filter_lib.wizard.app import FilterWizardApp
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.screens.welcome import WelcomeScreen
from filter_lib.wizard.state import FilterState

_OUTPUT_OPTIONS_APP_PROPERTY = OutputOptionsScreen.app
_RESULTS_APP_PROPERTY = ResultsScreen.app
_WELCOME_APP_PROPERTY = WelcomeScreen.app


def _restore_screen_app_descriptors() -> None:
    """Undo class-level app stubs left by direct-handler unit tests."""
    WelcomeScreen.app = _WELCOME_APP_PROPERTY
    OutputOptionsScreen.app = _OUTPUT_OPTIONS_APP_PROPERTY
    ResultsScreen.app = _RESULTS_APP_PROPERTY


def test_advanced_build_controls_are_keyboard_accessible() -> None:
    async def exercise() -> None:
        # Several direct-handler tests replace Screen.app at class scope.
        # Restore Textual's descriptor so this remains a real integration test
        # regardless of module execution order.
        _restore_screen_app_descriptors()
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
        _restore_screen_app_descriptors()
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
        _restore_screen_app_descriptors()
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
