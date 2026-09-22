"""Wizard entry point and Welcome screen category selection."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from textual.widgets import OptionList

from filter_lib.wizard import interactive
from filter_lib.wizard.screens.bandpass import BandpassScreen
from filter_lib.wizard.screens.highpass import HighpassScreen
from filter_lib.wizard.screens.lowpass import LowpassScreen
from filter_lib.wizard.screens.welcome import WelcomeScreen
from filter_lib.wizard.state import FilterState


def test_run_wizard_constructs_and_runs_the_textual_app():
    with patch("filter_lib.wizard.app.FilterWizardApp") as app_class:
        interactive.run_wizard()

    app_class.assert_called_once_with()
    app_class.return_value.run.assert_called_once_with()


def _welcome(monkeypatch) -> tuple[WelcomeScreen, Mock, list]:
    screen = WelcomeScreen()
    app = Mock(filter_state=FilterState())
    pushed: list = []
    app.push_screen = pushed.append
    monkeypatch.setattr(WelcomeScreen, "app", property(lambda _self: app))
    return screen, app, pushed


def _selected(option_id: str) -> Mock:
    event = Mock(spec=OptionList.OptionSelected)
    event.option = Mock(id=option_id)
    return event


@pytest.mark.parametrize(
    "option_id, screen_cls",
    [("lowpass", LowpassScreen), ("highpass", HighpassScreen), ("bandpass", BandpassScreen)],
)
def test_choosing_a_category_records_it_and_opens_its_form(monkeypatch, option_id, screen_cls):
    screen, app, pushed = _welcome(monkeypatch)

    screen.on_option_list_option_selected(_selected(option_id))

    assert app.filter_state.category == option_id
    assert [type(pushed_screen) for pushed_screen in pushed] == [screen_cls]


def test_unknown_option_is_ignored(monkeypatch):
    screen, app, pushed = _welcome(monkeypatch)

    screen.on_option_list_option_selected(_selected("bandstop"))

    assert pushed == []
    assert app.filter_state.category == ""


def test_escape_on_welcome_quits_the_app(monkeypatch):
    screen, app, _pushed = _welcome(monkeypatch)

    screen.action_quit()

    app.exit.assert_called_once_with()
