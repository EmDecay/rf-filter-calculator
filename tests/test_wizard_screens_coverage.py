"""Coverage-gap tests for wizard screens.

Uses the Mock(spec=RadioSet/Input/...) pattern from
test_wizard_screens_regressions.py to exercise screen methods without a
running Textual app.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from textual.widgets import Button, Input, OptionList, RadioSet, SelectionList, Static

from filter_lib.wizard.filter_screen_navigation_mixin import FilterScreenNavigationMixin
from filter_lib.wizard.screens.bandpass import BandpassScreen
from filter_lib.wizard.screens.highpass import HighpassScreen
from filter_lib.wizard.screens.lowpass import LowpassScreen
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.screens.welcome import WelcomeScreen
from filter_lib.wizard.state import FilterState

# ---------------------------------------------------------------------------
# FilterScreenNavigationMixin.on_key
# ---------------------------------------------------------------------------


def _make_event(key: str) -> Mock:
    event = Mock()
    event.key = key
    return event


class _NavScreen(FilterScreenNavigationMixin):
    """Concrete-for-testing subclass that provides a query_one shim."""

    def __init__(self, widgets: dict) -> None:
        self._widgets = widgets

    def query_one(self, selector: str, widget_type=None):
        if selector not in self._widgets:
            raise LookupError(selector)
        return self._widgets[selector]


class TestFilterScreenNavigationMixin:
    def test_non_enter_key_is_ignored(self):
        screen = _NavScreen({})
        screen.RADIO_SET_FLOW = ["filter-type", "topology"]
        screen.FIRST_INPUT_ID = "frequency"
        event = _make_event("tab")
        screen.on_key(event)
        event.prevent_default.assert_not_called()

    def test_enter_on_first_radio_focuses_next_radio(self):
        first = Mock(spec=RadioSet)
        first.has_focus = True
        second = Mock(spec=RadioSet)
        second.has_focus = False
        screen = _NavScreen({"#filter-type": first, "#topology": second})
        screen.RADIO_SET_FLOW = ["filter-type", "topology"]
        screen.FIRST_INPUT_ID = "frequency"
        event = _make_event("enter")
        screen.on_key(event)
        second.focus.assert_called_once()
        event.prevent_default.assert_called_once()
        event.stop.assert_called_once()

    def test_enter_on_last_radio_focuses_first_input(self):
        first = Mock(spec=RadioSet)
        first.has_focus = False
        second = Mock(spec=RadioSet)
        second.has_focus = True
        freq_input = Mock(spec=Input)
        screen = _NavScreen({"#filter-type": first, "#topology": second, "#frequency": freq_input})
        screen.RADIO_SET_FLOW = ["filter-type", "topology"]
        screen.FIRST_INPUT_ID = "frequency"
        screen.on_key(_make_event("enter"))
        freq_input.focus.assert_called_once()

    def test_enter_on_last_radio_without_first_input_stops_event(self):
        """Mixin still consumes the event even when FIRST_INPUT_ID is empty."""
        last = Mock(spec=RadioSet)
        last.has_focus = True
        screen = _NavScreen({"#topology": last})
        screen.RADIO_SET_FLOW = ["topology"]
        screen.FIRST_INPUT_ID = ""  # no input to advance to
        event = _make_event("enter")
        screen.on_key(event)
        # prevent_default + stop still fire so Textual doesn't process Enter further
        event.prevent_default.assert_called_once()
        event.stop.assert_called_once()

    def test_enter_when_no_radio_has_focus_is_safe(self):
        first = Mock(spec=RadioSet)
        first.has_focus = False
        screen = _NavScreen({"#filter-type": first})
        screen.RADIO_SET_FLOW = ["filter-type"]
        screen.FIRST_INPUT_ID = "frequency"
        event = _make_event("enter")
        screen.on_key(event)
        event.prevent_default.assert_not_called()

    def test_missing_widget_is_swallowed(self):
        """LookupError during query_one is caught by the mixin (widget not mounted)."""
        screen = _NavScreen({})  # no widgets mapped
        screen.RADIO_SET_FLOW = ["filter-type"]
        screen.FIRST_INPUT_ID = "frequency"
        event = _make_event("enter")
        screen.on_key(event)  # should not raise


# ---------------------------------------------------------------------------
# WelcomeScreen option handling + quit
# ---------------------------------------------------------------------------


def _make_welcome_screen() -> tuple[WelcomeScreen, Mock, list, Mock]:
    screen = WelcomeScreen()
    app = Mock()
    app.filter_state = FilterState()
    pushed: list = []
    app.push_screen = pushed.append
    app.exit = Mock()
    type(screen).app = property(lambda _self: app)  # type: ignore[misc]
    return screen, app, pushed, app.exit


def _make_option_selected_event(option_id: str) -> Mock:
    event = Mock(spec=OptionList.OptionSelected)
    event.option = Mock()
    event.option.id = option_id
    return event


class TestWelcomeScreen:
    def test_select_lowpass_pushes_lowpass_screen(self):
        screen, app, pushed, _ = _make_welcome_screen()
        screen.on_option_list_option_selected(_make_option_selected_event("lowpass"))
        assert app.filter_state.category == "lowpass"
        assert len(pushed) == 1
        assert type(pushed[0]).__name__ == "LowpassScreen"

    def test_select_highpass_pushes_highpass_screen(self):
        screen, app, pushed, _ = _make_welcome_screen()
        screen.on_option_list_option_selected(_make_option_selected_event("highpass"))
        assert app.filter_state.category == "highpass"
        assert type(pushed[0]).__name__ == "HighpassScreen"

    def test_select_bandpass_pushes_bandpass_screen(self):
        screen, app, pushed, _ = _make_welcome_screen()
        screen.on_option_list_option_selected(_make_option_selected_event("bandpass"))
        assert app.filter_state.category == "bandpass"
        assert type(pushed[0]).__name__ == "BandpassScreen"

    def test_unknown_option_does_nothing(self):
        screen, app, pushed, _ = _make_welcome_screen()
        screen.on_option_list_option_selected(_make_option_selected_event("garbage"))
        assert pushed == []
        assert app.filter_state.category == ""

    def test_action_quit_calls_app_exit(self):
        screen, _app, _pushed, exit_mock = _make_welcome_screen()
        screen.action_quit()
        exit_mock.assert_called_once()


# ---------------------------------------------------------------------------
# LP/HP shared-validation helpers (leverage existing regression fixture style)
# ---------------------------------------------------------------------------


def _lp_hp_mock_screen(
    screen_cls,
    *,
    freq_value: str = "10MHz",
    impedance_value: str = "50",
    order_value: str = "3",
    ripple_value: str = "0.5",
    filter_type: str = "butterworth",
    topology: str = "pi",
):
    """Build an LP/HP screen with stubbed Input/RadioSet queries."""
    screen = screen_cls()
    state = FilterState()
    app = Mock()
    app.filter_state = state
    notifications: list[tuple[str, str]] = []
    ripple_section = Mock()
    ripple_section.display = filter_type == "chebyshev"

    def _input(value: str) -> Mock:
        inp = Mock(spec=Input)
        inp.value = value
        inp.placeholder = ""
        inp.focus = Mock()
        return inp

    def _radio_set(selected_id: str) -> Mock:
        rs = Mock(spec=RadioSet)
        btn = Mock()
        btn.id = selected_id
        rs.pressed_button = btn
        return rs

    widget_map: dict[str, Mock] = {
        "#frequency": _input(freq_value),
        "#impedance": _input(impedance_value),
        "#order": _input(order_value),
        "#ripple": _input(ripple_value),
        "#filter-type": _radio_set(filter_type),
        "#topology": _radio_set(topology),
        "#ripple-section": ripple_section,
        "#next-btn": Mock(spec=Button),
    }

    def fake_query_one(selector: str, widget_type=None):
        return widget_map[selector]

    screen.query_one = fake_query_one  # type: ignore[assignment]
    type(screen).app = property(lambda _self: app)  # type: ignore[misc]
    screen.notify = lambda msg, severity="information": notifications.append((severity, msg))  # type: ignore[assignment]
    pushed: list = []
    app.push_screen = pushed.append
    return screen, state, notifications, pushed, widget_map


class TestLowpassScreenValidation:
    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_invalid_frequency_notifies_and_blocks(self, cls):
        screen, _state, notes, pushed, widgets = _lp_hp_mock_screen(cls, freq_value="notafreq")
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid frequency" in msg for _sev, msg in notes)
        widgets["#frequency"].focus.assert_called()

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_non_numeric_impedance_notifies(self, cls):
        screen, _state, notes, pushed, _ = _lp_hp_mock_screen(cls, impedance_value="abc")
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid impedance" in msg for _sev, msg in notes)

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_zero_impedance_notifies(self, cls):
        screen, _state, notes, pushed, _ = _lp_hp_mock_screen(cls, impedance_value="0")
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid impedance" in msg for _sev, msg in notes)

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_suffixed_impedance_accepted(self, cls):
        """Wizard accepts the same suffixed impedance forms as the CLI."""
        screen, state, _notes, pushed, _ = _lp_hp_mock_screen(cls, impedance_value="50ohm")
        screen._validate_and_continue()
        assert pushed
        assert state.impedance == 50.0

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_kilo_impedance_accepted(self, cls):
        screen, state, _notes, pushed, _ = _lp_hp_mock_screen(cls, impedance_value="1k")
        screen._validate_and_continue()
        assert pushed
        assert state.impedance == 1000.0

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_order_out_of_range_notifies(self, cls):
        screen, _state, notes, pushed, _ = _lp_hp_mock_screen(cls, order_value="1")
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid order" in msg for _sev, msg in notes)

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_non_integer_order_notifies(self, cls):
        screen, _state, notes, pushed, _ = _lp_hp_mock_screen(cls, order_value="xyz")
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid order" in msg for _sev, msg in notes)

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_chebyshev_negative_ripple_notifies(self, cls):
        screen, _state, notes, pushed, _ = _lp_hp_mock_screen(
            cls, filter_type="chebyshev", order_value="3", ripple_value="-0.1"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid ripple" in msg for _sev, msg in notes)

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_chebyshev_non_numeric_ripple_notifies(self, cls):
        screen, _state, notes, pushed, _ = _lp_hp_mock_screen(
            cls, filter_type="chebyshev", order_value="3", ripple_value="nope"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid ripple" in msg for _sev, msg in notes)

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_butterworth_happy_path_advances(self, cls):
        screen, state, _notes, pushed, _ = _lp_hp_mock_screen(cls, filter_type="butterworth")
        screen._validate_and_continue()
        assert pushed, "butterworth happy path should navigate"
        assert state.filter_type == "butterworth"
        assert state.frequency_hz > 0

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_empty_frequency_uses_placeholder(self, cls):
        """Empty freq + a valid placeholder should parse the placeholder."""
        screen, state, _notes, pushed, widgets = _lp_hp_mock_screen(cls, freq_value="")
        widgets["#frequency"].placeholder = "5MHz"
        screen._validate_and_continue()
        assert pushed, "placeholder fallback should allow navigation"
        assert state.frequency_hz == 5e6


# ---------------------------------------------------------------------------
# LP/HP screen on_button_pressed + _reset_form + action_back
# ---------------------------------------------------------------------------


class TestLowpassButtonDispatch:
    def _make(self, cls):
        return _lp_hp_mock_screen(cls)

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_next_button_triggers_validation(self, cls):
        screen, _state, _notes, pushed, _ = self._make(cls)
        event = Mock()
        event.button = Mock()
        event.button.id = "next-btn"
        screen.on_button_pressed(event)
        assert pushed  # happy path

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_reset_button_clears_inputs(self, cls):
        screen, _state, _notes, _pushed, widgets = self._make(cls)
        event = Mock()
        event.button = Mock()
        event.button.id = "reset-btn"
        screen.on_button_pressed(event)
        # _reset_form sets frequency="" etc. via widget.value assignment
        assert widgets["#frequency"].value == ""
        assert widgets["#impedance"].value == "50"
        assert widgets["#order"].value == "3"
        assert widgets["#ripple"].value == "0.5"
        widgets["#frequency"].focus.assert_called()

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_unknown_button_is_noop(self, cls):
        screen, _state, _notes, pushed, widgets = self._make(cls)
        event = Mock()
        event.button = Mock()
        event.button.id = "unknown"
        screen.on_button_pressed(event)
        assert pushed == []

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_action_back_pops_screen(self, cls):
        screen = cls()
        app = Mock()
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        screen.action_back()
        app.pop_screen.assert_called_once()


# ---------------------------------------------------------------------------
# Bandpass screen validation + happy path + reset
# ---------------------------------------------------------------------------


def _bp_mock_screen(
    *,
    freq_value: str = "14.175MHz",
    bw_value: str = "350kHz",
    impedance_value: str = "50",
    resonators_value: str = "3",
    ripple_value: str = "0.5",
    filter_type: str = "butterworth",
    coupling: str = "top",
):
    screen = BandpassScreen()
    state = FilterState()
    app = Mock()
    app.filter_state = state
    notifications: list[tuple[str, str]] = []
    ripple_section = Mock()
    ripple_section.display = filter_type == "chebyshev"

    def _input(value: str) -> Mock:
        inp = Mock(spec=Input)
        inp.value = value
        inp.placeholder = ""
        inp.focus = Mock()
        return inp

    def _radio_set(selected_id: str) -> Mock:
        rs = Mock(spec=RadioSet)
        btn = Mock()
        btn.id = selected_id
        rs.pressed_button = btn
        return rs

    fbw_display = Mock(spec=Static)
    widgets: dict[str, Mock] = {
        "#frequency": _input(freq_value),
        "#bandwidth": _input(bw_value),
        "#impedance": _input(impedance_value),
        "#resonators": _input(resonators_value),
        "#ripple": _input(ripple_value),
        "#filter-type": _radio_set(filter_type),
        "#coupling": _radio_set(coupling),
        "#ripple-section": ripple_section,
        "#fbw-display": fbw_display,
        "#next-btn": Mock(spec=Button),
    }

    def fake_query_one(selector: str, widget_type=None):
        return widgets[selector]

    screen.query_one = fake_query_one  # type: ignore[assignment]
    type(screen).app = property(lambda _self: app)  # type: ignore[misc]
    screen.notify = lambda msg, severity="information": notifications.append((severity, msg))  # type: ignore[assignment]
    pushed: list = []
    app.push_screen = pushed.append
    return screen, state, notifications, pushed, widgets


class TestBandpassScreenValidation:
    def test_happy_path_butterworth(self):
        screen, state, _notes, pushed, _ = _bp_mock_screen()
        screen._validate_and_continue()
        assert pushed
        assert state.filter_type == "butterworth"
        assert state.frequency_hz == 14.175e6
        assert state.bandwidth_hz == 350e3

    def test_invalid_center_frequency(self):
        screen, _state, notes, pushed, _ = _bp_mock_screen(freq_value="junk")
        screen._validate_and_continue()
        assert pushed == []
        assert any("center frequency" in msg for _sev, msg in notes)

    def test_invalid_bandwidth(self):
        screen, _state, notes, pushed, _ = _bp_mock_screen(bw_value="junk")
        screen._validate_and_continue()
        assert pushed == []
        assert any("bandwidth" in msg.lower() for _sev, msg in notes)

    def test_zero_impedance(self):
        screen, _state, notes, pushed, _ = _bp_mock_screen(impedance_value="0")
        screen._validate_and_continue()
        assert pushed == []
        assert any("impedance" in msg.lower() for _sev, msg in notes)

    def test_out_of_range_resonators(self):
        screen, _state, notes, pushed, _ = _bp_mock_screen(resonators_value="1")
        screen._validate_and_continue()
        assert pushed == []
        assert any("resonators" in msg.lower() for _sev, msg in notes)

    def test_non_integer_resonators(self):
        screen, _state, notes, pushed, _ = _bp_mock_screen(resonators_value="xxx")
        screen._validate_and_continue()
        assert pushed == []
        assert any("resonators" in msg.lower() for _sev, msg in notes)

    def test_chebyshev_even_resonators_blocked(self):
        screen, _state, notes, pushed, _ = _bp_mock_screen(
            filter_type="chebyshev", resonators_value="4"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert any("odd number of resonators" in msg for _sev, msg in notes)

    def test_chebyshev_invalid_ripple_notifies(self):
        screen, _state, notes, pushed, _ = _bp_mock_screen(
            filter_type="chebyshev", resonators_value="3", ripple_value="-0.1"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid ripple" in msg for _sev, msg in notes)

    def test_chebyshev_happy_path(self):
        screen, state, _notes, pushed, _ = _bp_mock_screen(
            filter_type="chebyshev", resonators_value="3", ripple_value="0.1"
        )
        screen._validate_and_continue()
        assert pushed
        assert state.ripple_db == 0.1

    def test_empty_freq_uses_placeholder(self):
        screen, state, _notes, pushed, widgets = _bp_mock_screen(freq_value="")
        widgets["#frequency"].placeholder = "14MHz"
        screen._validate_and_continue()
        assert pushed
        assert state.frequency_hz == 14e6

    def test_empty_bandwidth_uses_placeholder(self):
        screen, state, _notes, pushed, widgets = _bp_mock_screen(bw_value="")
        widgets["#bandwidth"].placeholder = "1MHz"
        screen._validate_and_continue()
        assert pushed
        assert state.bandwidth_hz == 1e6


class TestBandpassFbwDisplay:
    def test_fbw_display_normal(self):
        screen, _state, _notes, _pushed, widgets = _bp_mock_screen()
        screen._update_fbw_display()
        widgets["#fbw-display"].update.assert_called()
        call_text = widgets["#fbw-display"].update.call_args[0][0]
        assert "%" in call_text

    def test_fbw_display_wide_bandwidth_warns(self):
        screen, _state, _notes, _pushed, widgets = _bp_mock_screen(
            freq_value="10MHz",
            bw_value="8MHz",  # 80% bandwidth
        )
        screen._update_fbw_display()
        call_text = widgets["#fbw-display"].update.call_args[0][0]
        assert "Wide" in call_text
        widgets["#fbw-display"].add_class.assert_any_call("fbw-warning")

    def test_fbw_display_invalid_input_clears(self):
        screen, _state, _notes, _pushed, widgets = _bp_mock_screen(
            freq_value="junk", bw_value="junk"
        )
        screen._update_fbw_display()
        # On parse failure the display is set to an empty string
        widgets["#fbw-display"].update.assert_called_with("")

    def test_fbw_display_zero_center_clears(self):
        """Division-by-zero in fractional-bandwidth calc must be swallowed."""
        screen, _state, _notes, _pushed, widgets = _bp_mock_screen(
            freq_value="0MHz", bw_value="1MHz"
        )
        screen._update_fbw_display()
        widgets["#fbw-display"].update.assert_called_with("")


class TestBandpassButtonsAndReset:
    def test_calculate_button(self):
        screen, _state, _notes, pushed, _ = _bp_mock_screen()
        event = Mock()
        event.button = Mock()
        event.button.id = "next-btn"
        screen.on_button_pressed(event)
        assert pushed

    def test_reset_button_resets_form(self):
        screen, _state, _notes, _pushed, widgets = _bp_mock_screen()
        event = Mock()
        event.button = Mock()
        event.button.id = "reset-btn"
        screen.on_button_pressed(event)
        assert widgets["#frequency"].value == ""
        assert widgets["#bandwidth"].value == ""
        assert widgets["#impedance"].value == "50"
        assert widgets["#resonators"].value == "3"
        assert widgets["#ripple"].value == "0.5"
        widgets["#frequency"].focus.assert_called()

    def test_action_back_pops_screen(self):
        screen = BandpassScreen()
        app = Mock()
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        screen.action_back()
        app.pop_screen.assert_called_once()


# ---------------------------------------------------------------------------
# OutputOptionsScreen: on_key navigation + button dispatch
# ---------------------------------------------------------------------------


def _make_output_options(
    focus_target: str,
    eseries_id: str = "E24",
    format_id: str = "table",
    export_id: str = "no-export",
):
    screen = OutputOptionsScreen()
    app = Mock()
    app.filter_state = FilterState()
    pushed: list = []
    app.push_screen = pushed.append
    type(screen).app = property(lambda _self: app)  # type: ignore[misc]

    def make_focus_flag(which: str, target_focus: str) -> bool:
        return which == target_focus

    eseries = Mock(spec=RadioSet)
    eseries.has_focus = make_focus_flag("eseries", focus_target)
    btn = Mock()
    btn.id = eseries_id
    eseries.pressed_button = btn

    fmt = Mock(spec=RadioSet)
    fmt.has_focus = make_focus_flag("format", focus_target)
    fbtn = Mock()
    fbtn.id = format_id
    fmt.pressed_button = fbtn

    opts = Mock(spec=SelectionList)
    opts.has_focus = make_focus_flag("options-list", focus_target)
    opts.selected = []

    export = Mock(spec=RadioSet)
    export.has_focus = make_focus_flag("export", focus_target)
    ebtn = Mock()
    ebtn.id = export_id
    export.pressed_button = ebtn

    results_btn = Mock(spec=Button)

    widgets = {
        "#eseries": eseries,
        "#format": fmt,
        "#options-list": opts,
        "#export": export,
        "#results-btn": results_btn,
    }

    def fake_query_one(selector: str, widget_type=None):
        if selector not in widgets:
            raise LookupError(selector)
        return widgets[selector]

    screen.query_one = fake_query_one  # type: ignore[assignment]
    return screen, app, pushed, widgets


class TestOutputOptionsOnKey:
    def test_non_enter_ignored(self):
        screen, _app, _pushed, widgets = _make_output_options("eseries")
        event = _make_event("tab")
        screen.on_key(event)
        event.prevent_default.assert_not_called()

    def test_enter_on_eseries_focuses_format(self):
        screen, _app, _pushed, widgets = _make_output_options("eseries")
        event = _make_event("enter")
        screen.on_key(event)
        widgets["#format"].focus.assert_called_once()
        event.prevent_default.assert_called_once()

    def test_enter_on_format_focuses_options_list(self):
        screen, _app, _pushed, widgets = _make_output_options("format")
        event = _make_event("enter")
        screen.on_key(event)
        widgets["#options-list"].focus.assert_called_once()

    def test_enter_on_options_list_focuses_export(self):
        screen, _app, _pushed, widgets = _make_output_options("options-list")
        event = _make_event("enter")
        screen.on_key(event)
        widgets["#export"].focus.assert_called_once()

    def test_enter_on_export_focuses_results_button(self):
        screen, _app, _pushed, widgets = _make_output_options("export")
        event = _make_event("enter")
        screen.on_key(event)
        widgets["#results-btn"].focus.assert_called_once()

    def test_lookup_error_swallowed(self):
        screen = OutputOptionsScreen()
        screen.query_one = lambda *_a, **_k: (_ for _ in ()).throw(  # type: ignore[assignment]
            LookupError("boom")
        )
        event = _make_event("enter")
        screen.on_key(event)  # must not raise


class TestOutputOptionsButtons:
    def test_results_button_calls_show_results(self):
        screen, _app, pushed, _ = _make_output_options("eseries")
        event = Mock()
        event.button = Mock()
        event.button.id = "results-btn"
        screen.on_button_pressed(event)
        assert len(pushed) == 1
        assert type(pushed[0]).__name__ == "ResultsScreen"

    def test_back_button_pops_screen(self):
        screen, app, _pushed, _ = _make_output_options("eseries")
        event = Mock()
        event.button = Mock()
        event.button.id = "back-btn"
        screen.on_button_pressed(event)
        app.pop_screen.assert_called_once()

    def test_action_back_pops_screen(self):
        screen, app, _pushed, _ = _make_output_options("eseries")
        screen.action_back()
        app.pop_screen.assert_called_once()


class TestShowResultsExportFlags:
    @pytest.mark.parametrize(
        "export_id, expected",
        [
            ("export-json", "json"),
            ("export-csv", "csv"),
            ("no-export", None),
        ],
    )
    def test_show_results_maps_export_to_state(self, export_id, expected):
        screen, _app, _pushed, _ = _make_output_options("eseries", export_id=export_id)
        screen._show_results()
        assert screen.app.filter_state.export_format == expected


# ---------------------------------------------------------------------------
# ResultsScreen: export formatter dispatch per category
# ---------------------------------------------------------------------------


def _lp_result():
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "order": 3,
        "capacitors": [1e-10, 1e-10],
        "inductors": [1e-6],
        "ripple": None,
        "topology": "pi",
    }


def _hp_result():
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "order": 3,
        "inductors": [2e-6, 2e-6],
        "capacitors": [5e-10],
        "ripple": None,
        "topology": "t",
    }


def _bp_result():
    return {
        "filter_type": "butterworth",
        "f0": 14.175e6,
        "bw": 350e3,
        "f_low": 14.0e6,
        "f_high": 14.35e6,
        "z0": 50.0,
        "n_resonators": 3,
        "coupling": "top",
        "fbw": 350e3 / 14.175e6,
        "L_resonant": 1e-6,
        "c_tank": [100e-12, 100e-12, 100e-12],
        "c_coupling": [10e-12, 10e-12],
        "qe_in": 50.0,
        "qe_out": 50.0,
        "q_min": 100,
        "q_safety": 2.0,
        "ripple_db": None,
        "warnings": [],
    }


class TestResultsScreenExportDispatch:
    @pytest.mark.parametrize(
        "category, result_fn",
        [
            ("lowpass", _lp_result),
            ("highpass", _hp_result),
            ("bandpass", _bp_result),
        ],
    )
    def test_json_export_per_category(self, category, result_fn):
        screen = ResultsScreen()
        state = FilterState()
        state.category = category
        state.eseries = "E24"
        state.result = result_fn()
        out = screen._get_json_export(state)
        assert out  # non-empty JSON string

    @pytest.mark.parametrize(
        "category, result_fn",
        [
            ("lowpass", _lp_result),
            ("highpass", _hp_result),
            ("bandpass", _bp_result),
        ],
    )
    def test_csv_export_per_category(self, category, result_fn):
        screen = ResultsScreen()
        state = FilterState()
        state.category = category
        state.eseries = "E24"
        state.result = result_fn()
        out = screen._get_csv_export(state)
        assert out

    @pytest.mark.parametrize(
        "category, result_fn",
        [
            ("lowpass", _lp_result),
            ("highpass", _hp_result),
            ("bandpass", _bp_result),
        ],
    )
    def test_json_export_respects_none_eseries(self, category, result_fn):
        screen = ResultsScreen()
        state = FilterState()
        state.category = category
        state.eseries = "none"
        state.result = result_fn()
        out = screen._get_json_export(state)
        assert out


class TestResultsScreenWorkerHook:
    def test_worker_success_updates_result_text(self):
        screen = ResultsScreen()
        static_mock = Mock()
        screen.query_one = lambda *_a, **_k: static_mock  # type: ignore[assignment]
        event = Mock()
        event.state = SimpleNamespace(name="SUCCESS")
        event.worker = Mock()
        event.worker.result = "result-text-from-worker"
        screen.on_worker_state_changed(event)
        assert screen._result_text == "result-text-from-worker"
        static_mock.update.assert_called_once_with("result-text-from-worker")

    def test_worker_non_success_does_nothing(self):
        screen = ResultsScreen()
        event = Mock()
        event.state = SimpleNamespace(name="RUNNING")
        event.worker = Mock()
        event.worker.result = "should-not-be-used"
        screen.on_worker_state_changed(event)
        assert screen._result_text == ""

    def test_worker_error_shows_failure_instead_of_hanging(self):
        screen = ResultsScreen()
        static_mock = Mock()
        screen.query_one = lambda *_a, **_k: static_mock  # type: ignore[assignment]
        event = Mock()
        event.state = SimpleNamespace(name="ERROR")
        event.worker = Mock()
        event.worker.error = RuntimeError("solver exploded")
        screen.on_worker_state_changed(event)
        text = static_mock.update.call_args[0][0]
        assert "solver exploded" in text
        assert "Esc" in text


class TestResultsScreenActions:
    def test_action_back_pops(self):
        screen = ResultsScreen()
        app = Mock()
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        screen.action_back()
        app.pop_screen.assert_called_once()

    def test_action_quit_exits(self):
        screen = ResultsScreen()
        app = Mock()
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        screen.action_quit()
        app.exit.assert_called_once()

    def test_on_button_pressed_quit(self):
        screen = ResultsScreen()
        app = Mock()
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        event = Mock()
        event.button = Mock()
        event.button.id = "quit-btn"
        screen.on_button_pressed(event)
        app.exit.assert_called_once()

    def test_on_button_pressed_export_shows_section(self):
        screen = ResultsScreen()
        section = Mock()
        export_format = Mock(spec=RadioSet)
        screen.query_one = lambda selector, *_a, **_k: (  # type: ignore[assignment]
            section if selector == "#export-section" else export_format
        )
        event = Mock()
        event.button = Mock()
        event.button.id = "export-btn"
        screen.on_button_pressed(event)
        assert section.display is True
        export_format.focus.assert_called_once()

    def test_on_button_pressed_cancel_export_hides_section(self):
        screen = ResultsScreen()
        section = Mock()
        screen.query_one = lambda *_a, **_k: section  # type: ignore[assignment]
        event = Mock()
        event.button = Mock()
        event.button.id = "cancel-export-btn"
        screen.on_button_pressed(event)
        assert section.display is False

    def test_on_button_pressed_save_routes_through_save(self, tmp_path, monkeypatch):
        """`save-btn` triggers _save_export without crashing for text format."""
        screen = ResultsScreen()
        screen._result_text = "result-text"
        state = FilterState()
        state.category = "lowpass"
        app = Mock()
        app.filter_state = state
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]

        export_format = Mock(spec=RadioSet)
        btn = Mock()
        btn.id = "export-txt"
        export_format.pressed_button = btn
        section = Mock()
        widgets = {"#export-format": export_format, "#export-section": section}

        def fake_query_one(selector: str, widget_type=None):
            return widgets[selector]

        screen.query_one = fake_query_one  # type: ignore[assignment]
        screen.notify = Mock()  # type: ignore[assignment]
        monkeypatch.chdir(tmp_path)

        event = Mock()
        event.button = Mock()
        event.button.id = "save-btn"
        screen.on_button_pressed(event)
        # A .txt file should now exist in cwd
        txt_files = list(tmp_path.glob("lowpass-*.txt"))
        assert len(txt_files) == 1
        assert txt_files[0].read_text() == "result-text"

    def test_save_export_handles_os_error(self, monkeypatch):
        """If open() raises OSError, error is caught and reported via notify."""
        screen = ResultsScreen()
        screen._result_text = "result-text"
        state = FilterState()
        state.category = "lowpass"
        app = Mock()
        app.filter_state = state
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]

        export_format = Mock(spec=RadioSet)
        btn = Mock()
        btn.id = "export-txt"
        export_format.pressed_button = btn
        section = Mock()
        widgets = {"#export-format": export_format, "#export-section": section}

        def fake_query_one(selector: str, widget_type=None):
            return widgets[selector]

        screen.query_one = fake_query_one  # type: ignore[assignment]
        notifications: list = []
        screen.notify = lambda msg, severity="information": notifications.append(  # type: ignore[assignment]
            (severity, msg)
        )

        # Monkeypatch open at the screens.results module level to raise
        import filter_lib.wizard.screens.results as results_mod

        def raising_open(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(results_mod, "open", raising_open, raising=False)

        screen._save_export()
        assert any("Error saving" in msg for _sev, msg in notifications)

    def test_save_export_defaults_format_id_when_no_pressed_button(self, tmp_path, monkeypatch):
        """If pressed_button is None, the code falls back to export-txt."""
        screen = ResultsScreen()
        screen._result_text = "fallback-text"
        state = FilterState()
        state.category = "highpass"
        app = Mock()
        app.filter_state = state
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]

        export_format = Mock(spec=RadioSet)
        export_format.pressed_button = None
        section = Mock()
        widgets = {"#export-format": export_format, "#export-section": section}

        def fake_query_one(selector: str, widget_type=None):
            return widgets[selector]

        screen.query_one = fake_query_one  # type: ignore[assignment]
        screen.notify = Mock()  # type: ignore[assignment]
        monkeypatch.chdir(tmp_path)
        screen._save_export()
        txt_files = list(tmp_path.glob("highpass-*.txt"))
        assert len(txt_files) == 1

    def test_on_key_enter_on_export_format_triggers_save(self, tmp_path, monkeypatch):
        screen = ResultsScreen()
        screen._result_text = "by-enter"
        state = FilterState()
        state.category = "bandpass"
        state.result = _bp_result()
        state.eseries = "E24"
        app = Mock()
        app.filter_state = state
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]

        export_format = Mock(spec=RadioSet)
        export_format.has_focus = True
        btn = Mock()
        btn.id = "export-json"
        export_format.pressed_button = btn
        section = Mock()

        def fake_query_one(selector: str, widget_type=None):
            if selector == "#export-format":
                return export_format
            if selector == "#export-section":
                return section
            raise LookupError(selector)

        screen.query_one = fake_query_one  # type: ignore[assignment]
        screen.notify = Mock()  # type: ignore[assignment]
        monkeypatch.chdir(tmp_path)
        event = _make_event("enter")
        screen.on_key(event)
        json_files = list(tmp_path.glob("bandpass-*.json"))
        assert len(json_files) == 1

    def test_on_key_enter_swallows_lookup_error(self):
        screen = ResultsScreen()

        def raising(*_a, **_k):
            raise LookupError("widget gone")

        screen.query_one = raising  # type: ignore[assignment]
        event = _make_event("enter")
        screen.on_key(event)  # must not raise

    def test_on_key_non_enter_ignored(self):
        screen = ResultsScreen()
        event = _make_event("escape")
        screen.on_key(event)
        event.prevent_default.assert_not_called()

    def test_design_another_pops_stack_and_pushes_welcome(self):
        screen = ResultsScreen()
        app = Mock()
        app.filter_state = FilterState()
        # Simulate a stack with 3 items -> pop 2x until len == 1
        app.screen_stack = [Mock(), Mock(), Mock()]

        def pop():
            app.screen_stack.pop()

        app.pop_screen = Mock(side_effect=pop)
        pushed: list = []
        app.push_screen = pushed.append
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        screen._design_another()
        # One screen left in stack + welcome pushed
        assert type(pushed[-1]).__name__ == "WelcomeScreen"
        # State should be reset
        assert isinstance(app.filter_state, FilterState)

    def test_on_button_pressed_another_triggers_design_another(self):
        screen = ResultsScreen()
        app = Mock()
        app.filter_state = FilterState()
        app.screen_stack = [Mock()]
        pushed: list = []
        app.push_screen = pushed.append
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        event = Mock()
        event.button = Mock()
        event.button.id = "another-btn"
        screen.on_button_pressed(event)
        assert pushed, "Welcome screen should be pushed"
