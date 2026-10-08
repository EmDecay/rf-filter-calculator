"""Mounted journeys: options that cannot apply are disabled live, with the shared reason.

These drive a real ``FilterWizardApp`` by keyboard, so widget ids, real ``disabled``
states, the visible reason lines, and the focus order are what a user gets.
"""

from __future__ import annotations

import asyncio

from textual.widgets import Checkbox, Input, RadioButton, RadioSet, Static

from filter_lib.design import band_from_edges
from filter_lib.design.option_applicability import (
    ESERIES_VALUES_ONLY_MESSAGE,
    LOSS_Q_DISABLED_MESSAGE,
    RAW_NEEDS_TABLE_MESSAGE,
    SUB_PF_VALUES_ONLY_MESSAGE,
    TEXT_PLOT_NEEDS_TABLE_MESSAGE,
    TOROID_BUILD_NEEDS_TOROIDS_MESSAGE,
    TOROID_DETAIL_NEEDS_TABLE_MESSAGE,
)
from filter_lib.design.render_options import BUILD_NEEDS_TABLE_OR_JSON_MESSAGE
from filter_lib.wizard.app import FilterWizardApp
from filter_lib.wizard.screens.bandpass import BandpassScreen
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.state import CSV_WITH_BUILD_MESSAGE, FilterState


def _reason(screen, option: str) -> str | None:
    """The reason line shown under an option, or None when it is hidden."""
    static = screen.query_one(f"#reason-{option}", Static)
    return str(static.render()) if static.display else None


def _choose(radio_set: RadioSet, button_id: str) -> None:
    radio_set.query_one(f"#{button_id}", RadioButton).value = True


def _lowpass_state() -> FilterState:
    return FilterState(
        category="lowpass", filter_type="butterworth", topology="pi", frequency_hz=10e6
    )


def test_output_options_disable_what_cannot_apply_and_say_why() -> None:
    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = _lowpass_state()
        async with app.run_test(size=(120, 120)) as pilot:
            await pilot.pause()
            app.push_screen(OutputOptionsScreen())
            await pilot.pause()
            screen = app.screen
            fmt = screen.query_one("#format", RadioSet)
            eseries = screen.query_one("#eseries", RadioSet)
            sub_pf = screen.query_one("#allow-sub-pf", Checkbox)

            # The web's defaults: Table, E24, Best detailed, text plot off, build off.
            assert fmt.pressed_button.id == "table"
            assert eseries.pressed_button.id == "E24"
            detail = screen.query_one("#toroid-detail", RadioSet)
            assert detail.pressed_button.id == "toroid-best"
            assert [str(button.label).split(" - ")[0] for button in detail.query(RadioButton)] == [
                "Best, detailed",
                "Up to 3, detailed",
                "Best, one line",
                "None",
            ]
            assert screen.query_one("#plot", Checkbox).value is False
            assert not eseries.disabled and not sub_pf.disabled
            assert fmt.has_focus

            # Values only: the standard values no longer apply, and say why.
            await pilot.press("down", "space")
            await pilot.pause()
            assert fmt.pressed_button.id == "quiet"
            assert eseries.disabled and sub_pf.disabled
            assert _reason(screen, "eseries") == ESERIES_VALUES_ONLY_MESSAGE
            assert _reason(screen, "allow_sub_pf") == SUB_PF_VALUES_ONLY_MESSAGE
            assert eseries.pressed_button.id == "E24"  # the visible choice is kept
            # Enter skips the disabled controls and lands on the toroid choice.
            await pilot.press("enter")
            assert detail.has_focus

            # JSON: table-only options are disabled; the standard values apply again.
            _choose(fmt, "json")
            await pilot.pause()
            assert not eseries.disabled and _reason(screen, "eseries") is None
            assert screen.query_one("#plot", Checkbox).disabled
            assert screen.query_one("#raw", Checkbox).disabled
            assert screen.query_one("#toroid-full", RadioButton).disabled
            assert not screen.query_one("#toroid-none", RadioButton).disabled
            assert _reason(screen, "plot") == TEXT_PLOT_NEEDS_TABLE_MESSAGE
            assert _reason(screen, "raw") == RAW_NEEDS_TABLE_MESSAGE
            assert _reason(screen, "toroid_detail") == TOROID_DETAIL_NEEDS_TABLE_MESSAGE

            # CSV: the build cannot apply; its fields stay hidden even when ticked.
            build = screen.query_one("#build-analysis-enabled", Checkbox)
            build.value = True
            _choose(fmt, "csv")
            await pilot.pause()
            assert build.disabled and build.value is True
            assert _reason(screen, "build") == BUILD_NEEDS_TABLE_OR_JSON_MESSAGE
            assert screen.query_one("#build-analysis-options").display is False

            # Table again: the ticked build applies and shows its fields.
            _choose(fmt, "table")
            await pilot.pause()
            assert not build.disabled and _reason(screen, "build") is None
            assert screen.query_one("#build-analysis-options").display is True
            # Toroid windings None: nothing for the build to simulate as windings.
            _choose(detail, "toroid-none")
            await pilot.pause()
            assert screen.query_one("#build-use-toroids", Checkbox).disabled
            assert _reason(screen, "toroid_build") == TOROID_BUILD_NEEDS_TOROIDS_MESSAGE

            # Values only with the default E24 shows results; nothing is refused (C-3).
            build.value = False
            _choose(fmt, "quiet")
            await pilot.pause()
            screen.query_one("#results-btn").focus()
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)
            state = app.filter_state
            assert state.calculation_status == "success", state.calculation_error
            assert "Standard" not in state.output_text

    asyncio.run(exercise())


def test_enter_reaches_every_output_control_in_the_web_order() -> None:
    """D15: Enter from Format visits each control, the sub-pF box included."""

    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = _lowpass_state()
        async with app.run_test(size=(120, 120)) as pilot:
            await pilot.pause()
            app.push_screen(OutputOptionsScreen())
            await pilot.pause()
            visited = []
            for _ in range(8):
                visited.append(app.screen.focused.id)
                await pilot.press("enter")
            assert visited == [
                "format",
                "eseries",
                "allow-sub-pf",
                "toroid-detail",
                "plot",
                "raw",
                "export",
                "build-analysis-enabled",
            ]
            assert app.screen.focused.id == "results-btn"
            # Enter moved focus without ticking any box.
            assert not app.screen.query_one("#allow-sub-pf", Checkbox).value

    asyncio.run(exercise())


def test_band_edges_and_resonator_q_journey() -> None:
    """D4/D5: the band by its edges; Qu disabled with the reason after choosing CSV."""

    async def exercise() -> None:
        app = FilterWizardApp()
        async with app.run_test(size=(120, 120)) as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "enter")  # Band-Pass
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, BandpassScreen)
            assert screen.query_one("#edge-fields").display is False

            screen.query_one("#band-spec", RadioSet).focus()
            await pilot.press("down", "space")
            await pilot.pause()
            assert screen.query_one("#center-fields").display is False
            assert screen.query_one("#edge-fields").display is True
            await pilot.press("enter")
            f_low = screen.query_one("#f-low", Input)
            assert f_low.has_focus
            f_low.value = "7MHz"
            await pilot.press("enter")
            f_high = screen.query_one("#f-high", Input)
            assert f_high.has_focus
            f_high.value = "7.3MHz"
            await pilot.pause()
            fbw = str(screen.query_one("#fbw-display", Static).render())
            assert fbw.startswith("Fractional bandwidth 4.2% is within the 10%")
            await pilot.press("enter")
            assert screen.query_one("#resonators", Input).has_focus

            qu = screen.query_one("#qu", Input)
            qu.value = "200"
            screen.query_one("#next-btn").focus()
            await pilot.press("enter")
            await pilot.pause()
            options = app.screen
            assert isinstance(options, OutputOptionsScreen)
            state = app.filter_state
            assert (state.frequency_hz, state.bandwidth_hz) == band_from_edges(7e6, 7.3e6)
            assert (state.requested_f_low_hz, state.requested_f_high_hz) == (7e6, 7.3e6)
            assert state.qu == 200.0
            assert _reason(options, "loss_q") is None

            # CSV leaves resonator Q out: the output screen says so, and so does the
            # band-pass screen when the user goes back to it.
            _choose(options.query_one("#format", RadioSet), "csv")
            await pilot.pause()
            assert _reason(options, "loss_q") == LOSS_Q_DISABLED_MESSAGE
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is screen
            assert all(screen.query_one(f"#{name}", Input).disabled for name in ("qu", "ql", "qc"))
            assert _reason(screen, "loss_q") == LOSS_Q_DISABLED_MESSAGE
            assert qu.value == "200"

            # Back to Next: the output screen opens with the CSV choice kept.
            screen.query_one("#next-btn").focus()
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen.query_one("#format", RadioSet).pressed_button.id == "csv"

    asyncio.run(exercise())


def test_results_say_why_csv_cannot_be_saved_with_a_build() -> None:
    """D8: the disabled CSV choice shows the reason."""

    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = FilterState(
            category="lowpass",
            frequency_hz=10e6,
            output_format="json",
            build_analysis_enabled=True,
            build_grid_points=51,
        )
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            app.push_screen(ResultsScreen())
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            screen = app.screen
            assert screen.query_one("#export-csv", RadioButton).disabled
            reason = screen.query_one("#export-csv-reason", Static)
            assert reason.display is True
            assert str(reason.render()) == CSV_WITH_BUILD_MESSAGE

    asyncio.run(exercise())


def test_a_disabled_toroid_choice_cannot_be_pressed_from_a_stale_highlight() -> None:
    """The arrow highlight stays on a choice that becomes disabled; Space must not press it."""

    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = _lowpass_state()
        async with app.run_test(size=(120, 120)) as pilot:
            await pilot.pause()
            app.push_screen(OutputOptionsScreen())
            await pilot.pause()
            screen = app.screen
            detail = screen.query_one("#toroid-detail", RadioSet)
            detail.focus()
            await pilot.press("down")  # highlights "Up to 3", without pressing it
            await pilot.pause()
            assert detail.pressed_button.id == "toroid-best"

            _choose(screen.query_one("#format", RadioSet), "json")
            await pilot.pause()
            assert screen.query_one("#toroid-full", RadioButton).disabled

            detail.focus()
            await pilot.press("space")
            await pilot.pause()
            assert detail.pressed_button.id == "toroid-best"
            assert app.filter_state.toroid_detail == "best"

    asyncio.run(exercise())


def test_hidden_build_fields_never_block_the_result_or_take_focus() -> None:
    """Table + build with a bad field, then CSV: the fields hide and the result opens."""

    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = _lowpass_state()
        async with app.run_test(size=(120, 120)) as pilot:
            await pilot.pause()
            app.push_screen(OutputOptionsScreen())
            await pilot.pause()
            screen = app.screen
            screen.query_one("#build-analysis-enabled", Checkbox).value = True
            await pilot.pause()
            screen.query_one("#build-capacitor-tolerance", Input).value = "abc"
            _choose(screen.query_one("#format", RadioSet), "csv")
            await pilot.pause()
            assert not screen.query_one("#build-analysis-options").display

            screen.query_one("#results-btn").press()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert isinstance(app.screen, ResultsScreen)
            assert app.filter_state.calculation_status == "success"
            assert app.focused is None or app.focused.id != "build-capacitor-tolerance"
            assert app.filter_state.build_input_error == (
                "Build simulation: Capacitor tolerance must be a number"
            )

            # Back: the typed text is still there to fix.
            await pilot.press("escape")
            await pilot.pause()
            assert screen.query_one("#build-capacitor-tolerance", Input).value == "abc"

    asyncio.run(exercise())


def test_a_fresh_bandpass_form_follows_the_format_kept_in_the_state() -> None:
    """The format is chosen later but kept; a new form says so without asking to remove Q."""

    async def exercise() -> None:
        app = FilterWizardApp()
        async with app.run_test(size=(120, 120)) as pilot:
            await pilot.pause()
            for output_format, disabled in (("csv", True), ("table", False), ("quiet", True)):
                app.filter_state = FilterState(category="bandpass", output_format=output_format)
                app.push_screen(BandpassScreen())
                await pilot.pause()
                screen = app.screen
                assert all(
                    screen.query_one(f"#{name}", Input).disabled is disabled
                    for name in ("qu", "ql", "qc")
                )
                assert _reason(screen, "loss_q") == (LOSS_Q_DISABLED_MESSAGE if disabled else None)
                app.pop_screen()
                await pilot.pause()

    asyncio.run(exercise())
