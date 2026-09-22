"""Mounted Textual journeys through the low-pass, high-pass, and band-pass design forms.

Each journey starts at the Welcome screen of a real ``FilterWizardApp`` and drives the
composed widgets by keyboard, so a renamed widget id, a changed default selection, or a
broken Enter/Escape chain fails here even though the direct-handler unit tests (which stub
``query_one``) would still pass.
"""

from __future__ import annotations

import asyncio

from textual.widgets import Button, Input, RadioButton, RadioSet, Static

from filter_lib.wizard.app import FilterWizardApp
from filter_lib.wizard.screens.bandpass import BandpassScreen
from filter_lib.wizard.screens.highpass import HighpassScreen
from filter_lib.wizard.screens.lowpass import LowpassScreen
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.screens.welcome import WelcomeScreen


def _record_notifications(app: FilterWizardApp) -> list[tuple[str, str]]:
    """Capture (severity, message) for every notification while still showing it."""
    notes: list[tuple[str, str]] = []
    show = app.notify

    def record(message, **kwargs):
        notes.append((kwargs.get("severity", "information"), message))
        return show(message, **kwargs)

    app.notify = record  # type: ignore[method-assign]
    return notes


def _radio_labels(screen, radio_set_id: str) -> dict[str, str]:
    radio_set = screen.query_one(f"#{radio_set_id}", RadioSet)
    return {button.id: str(button.label) for button in radio_set.query(RadioButton)}


def _pressed(screen, radio_set_id: str) -> str:
    return screen.query_one(f"#{radio_set_id}", RadioSet).pressed_button.id


def test_lowpass_keyboard_journey_blocks_even_chebyshev_then_stores_design() -> None:
    async def exercise() -> None:
        app = FilterWizardApp()
        notes = _record_notifications(app)
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, WelcomeScreen)
            await pilot.press("enter")  # first option: Low-Pass
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, LowpassScreen)
            assert _radio_labels(screen, "filter-type")["bessel"] == (
                "Bessel - Flat-delay low-pass prototype"
            )
            assert _radio_labels(screen, "topology") == {
                "pi": "Shunt-first ladder - C first, then alternating L/C",
                "t": "Series-first ladder - L first, then alternating C/L",
            }
            ripple_section = screen.query_one("#ripple-section")
            assert screen.query_one("#filter-type", RadioSet).has_focus
            assert ripple_section.display is False

            # Space selects inside a RadioSet; Enter advances through the form.
            await pilot.press("down", "space")
            await pilot.pause()
            assert ripple_section.display is True
            assert "odd only" in str(screen.query_one("#order-label", Static).render())
            await pilot.press("enter", "down", "space", "enter")
            # Values are entered directly (Input.Changed still fires); Enter drives
            # each field's Submitted handler along the documented focus chain.
            for field_id, value in (("frequency", "7.1MHz"), ("impedance", "75"), ("order", "4")):
                field = screen.query_one(f"#{field_id}", Input)
                assert field.has_focus
                field.value = value
                await pilot.press("enter")
            ripple = screen.query_one("#ripple", Input)
            assert ripple.has_focus
            # Below the field validator's 0.01 dB styling floor, yet a legal design:
            # Chebyshev ripple is accepted over 0 < ripple <= 3.0 dB.
            ripple.value = "0.005"
            await pilot.press("enter", "enter")
            await pilot.pause()

            assert app.screen is screen
            assert notes == [
                (
                    "warning",
                    "With equal source/load terminations, Chebyshev lowpass requires odd "
                    "order (3, 5, 7, or 9)",
                )
            ]
            assert screen.query_one("#order", Input).has_focus
            assert app.filter_state.frequency_hz == 0.0

            screen.query_one("#order", Input).value = "5"
            # Button.press() rather than Enter: the Enter binding is ignored while the
            # previous press's active effect is still showing.
            screen.query_one("#next-btn", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, OutputOptionsScreen)
            state = app.filter_state
            assert (state.category, state.filter_type, state.topology) == (
                "lowpass",
                "chebyshev",
                "t",
            )
            assert state.frequency_hz == 7.1e6
            assert state.impedance == 75.0
            assert state.order == 5
            assert state.ripple_db == 0.005

    asyncio.run(exercise())


def test_highpass_defaults_reach_results_and_a_later_edit_invalidates_them() -> None:
    async def exercise() -> None:
        app = FilterWizardApp()
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            await pilot.press("down", "enter")  # second option: High-Pass
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HighpassScreen)
            assert _pressed(screen, "filter-type") == "butterworth"
            # High-pass defaults to the series-first ladder, unlike low-pass.
            assert _pressed(screen, "topology") == "t"
            assert _radio_labels(screen, "topology") == {
                "t": "Series-first ladder - C first, then alternating L/C",
                "pi": "Shunt-first ladder - L first, then alternating C/L",
            }
            assert _radio_labels(screen, "filter-type")["bessel"] == (
                "Bessel - High-pass transform does not preserve flat group delay"
            )

            # An empty cutoff falls back to the visible 10MHz placeholder.
            screen.query_one("#next-btn").focus()
            await pilot.press("enter")
            await pilot.pause()
            options = app.screen
            assert isinstance(options, OutputOptionsScreen)
            state = app.filter_state
            assert (state.category, state.filter_type, state.topology) == (
                "highpass",
                "butterworth",
                "t",
            )
            assert (state.frequency_hz, state.impedance, state.order) == (10e6, 50.0, 3)
            assert _radio_labels(options, "eseries") == {
                "E24": "E24 - 24 preferred values per decade (default)",
                "E12": "E12 - 12 preferred values per decade",
                "E96": "E96 - 96 preferred values per decade",
                "none": "None - Calculated values only",
            }

            options.query_one("#results-btn").focus()
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert isinstance(app.screen, ResultsScreen)
            assert state.calculation_status == "success"
            assert "High Pass" in state.output_text

            await pilot.press("escape", "escape")
            await pilot.pause()
            assert app.screen is screen
            revision = state.calculation_revision
            screen.query_one("#frequency", Input).value = "7MHz"
            await pilot.pause()
            assert state.calculation_revision > revision
            assert state.calculation_status == "idle"
            assert state.result == {}
            assert state.output_text == ""

    asyncio.run(exercise())


def test_bandpass_journey_updates_fbw_feedback_and_stores_tank_inductance() -> None:
    async def exercise() -> None:
        app = FilterWizardApp()
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "enter")  # third option: Band-Pass
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, BandpassScreen)
            assert _radio_labels(screen, "coupling") == {
                "top": "Top-C (Series) - capacitively coupled resonators"
            }
            assert _radio_labels(screen, "filter-type")["bessel"] == (
                "Bessel - Band-pass transform does not preserve flat group delay"
            )

            await pilot.press("down", "down", "space", "enter", "enter")
            assert _pressed(screen, "filter-type") == "bessel"
            assert screen.query_one("#ripple-section").display is False
            assert screen.query_one("#frequency", Input).has_focus

            fbw = screen.query_one("#fbw-display", Static)
            screen.query_one("#frequency", Input).value = "14.2MHz"
            await pilot.press("enter")
            bandwidth = screen.query_one("#bandwidth", Input)
            assert bandwidth.has_focus
            bandwidth.value = "5MHz"
            await pilot.pause()
            assert str(fbw.render()).startswith("Fractional BW: 35.21% · Outside studied")
            assert fbw.has_class("fbw-warning")
            bandwidth.value = "500kHz"
            await pilot.pause()
            assert str(fbw.render()).startswith("Fractional BW: 3.52% · Within studied")
            assert fbw.has_class("fbw-display")
            assert not fbw.has_class("fbw-warning")

            inductance = screen.query_one("#resonator-inductance", Input)
            inductance.focus()
            inductance.value = "1uH"
            await pilot.press("enter", "enter")
            await pilot.pause()
            assert isinstance(app.screen, OutputOptionsScreen)
            state = app.filter_state
            assert (state.category, state.filter_type, state.topology) == (
                "bandpass",
                "bessel",
                "top",
            )
            assert (state.frequency_hz, state.bandwidth_hz) == (14.2e6, 500e3)
            assert state.order == 3
            assert state.resonator_inductance == 1e-6
            assert state.resonator_impedance is None

            # Ctrl+C exits from any screen whose focused widget does not claim it.
            assert app.return_code is None
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert app.return_code == 0

    asyncio.run(exercise())
