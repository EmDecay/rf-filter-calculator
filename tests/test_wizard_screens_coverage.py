"""Coverage-gap tests for wizard screens.

Uses the Mock(spec=RadioSet/Input/...) pattern from
test_wizard_screens_regressions.py to exercise screen methods without a
running Textual app.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, mock_open

import pytest
from textual.widgets import Button, Checkbox, Input, OptionList, RadioSet, SelectionList, Static

from filter_lib.wizard.filter_screen_navigation_mixin import FilterScreenNavigationMixin
from filter_lib.wizard.screens.bandpass import BandpassScreen
from filter_lib.wizard.screens.highpass import HighpassScreen
from filter_lib.wizard.screens.lowpass import LowpassScreen
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.screens.welcome import WelcomeScreen
from filter_lib.wizard.state import CalculationOutcome, FilterState

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
    def test_chebyshev_nan_ripple_notifies(self, cls):
        screen, state, notes, pushed, _ = _lp_hp_mock_screen(
            cls, filter_type="chebyshev", order_value="3", ripple_value="nan"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert state.ripple_db == 0.5
        assert any("Invalid ripple" in msg and "finite" in msg for _sev, msg in notes)

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_chebyshev_ripple_above_max_notifies(self, cls):
        screen, _state, notes, pushed, _ = _lp_hp_mock_screen(
            cls, filter_type="chebyshev", order_value="3", ripple_value="3.1"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid ripple" in msg and "<= 3.0 dB" in msg for _sev, msg in notes)

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
    resonator_impedance_value: str = "",
    resonator_inductance_value: str = "",
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
        "#resonator-impedance": _input(resonator_impedance_value),
        "#resonator-inductance": _input(resonator_inductance_value),
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

    def test_bandwidth_equal_to_center_frequency_is_blocked(self):
        screen, _state, notes, pushed, widgets = _bp_mock_screen(
            freq_value="10MHz", bw_value="10MHz"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert any("less than center frequency" in msg.lower() for _sev, msg in notes)
        widgets["#bandwidth"].focus.assert_called_once()

    def test_bandwidth_above_center_frequency_is_blocked(self):
        screen, _state, _notes, pushed, _ = _bp_mock_screen(freq_value="10MHz", bw_value="11MHz")
        screen._validate_and_continue()
        assert pushed == []

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

    def test_chebyshev_nan_ripple_notifies(self):
        screen, state, notes, pushed, _ = _bp_mock_screen(
            filter_type="chebyshev", resonators_value="3", ripple_value="nan"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert state.ripple_db == 0.5
        assert any("Invalid ripple" in msg and "finite" in msg for _sev, msg in notes)

    def test_chebyshev_ripple_above_max_notifies(self):
        screen, _state, notes, pushed, _ = _bp_mock_screen(
            filter_type="chebyshev", resonators_value="3", ripple_value="3.1"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert any("Invalid ripple" in msg and "<= 3.0 dB" in msg for _sev, msg in notes)

    def test_chebyshev_happy_path(self):
        screen, state, _notes, pushed, _ = _bp_mock_screen(
            filter_type="chebyshev", resonators_value="3", ripple_value="0.1"
        )
        screen._validate_and_continue()
        assert pushed
        assert state.ripple_db == 0.1

    def test_optional_tank_impedance_is_parsed(self):
        screen, state, _notes, pushed, _ = _bp_mock_screen(resonator_impedance_value="75ohm")
        screen._validate_and_continue()
        assert pushed
        assert state.resonator_impedance == 75.0
        assert state.resonator_inductance is None

    def test_optional_fixed_inductance_is_parsed(self):
        screen, state, _notes, pushed, _ = _bp_mock_screen(resonator_inductance_value="1.2uH")
        screen._validate_and_continue()
        assert pushed
        assert state.resonator_inductance == pytest.approx(1.2e-6)
        assert state.resonator_impedance is None

    def test_tank_impedance_and_inductance_are_mutually_exclusive(self):
        screen, _state, notes, pushed, widgets = _bp_mock_screen(
            resonator_impedance_value="75",
            resonator_inductance_value="1uH",
        )
        screen._validate_and_continue()
        assert pushed == []
        assert any("only one" in msg.lower() for _sev, msg in notes)
        widgets["#resonator-inductance"].focus.assert_called_once()

    def test_invalid_optional_fixed_inductance_is_blocked(self):
        screen, _state, notes, pushed, widgets = _bp_mock_screen(
            resonator_inductance_value="not-an-inductor"
        )
        screen._validate_and_continue()
        assert pushed == []
        assert any("inductance" in msg.lower() for _sev, msg in notes)
        widgets["#resonator-inductance"].focus.assert_called_once()

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
    def test_fbw_display_studied_range_is_neutral_and_defers_validation(self):
        screen, _state, _notes, _pushed, widgets = _bp_mock_screen()
        screen._update_fbw_display()
        call_text = widgets["#fbw-display"].update.call_args[0][0]
        assert "studied edge-calibration range" in call_text
        assert "after calculation" in call_text
        assert "validated" not in call_text.lower()
        assert "✓" not in call_text
        widgets["#fbw-display"].add_class.assert_any_call("fbw-display")

    def test_fbw_display_above_studied_range_warns(self):
        screen, _state, _notes, _pushed, widgets = _bp_mock_screen(
            freq_value="10MHz", bw_value="2MHz"
        )
        screen._update_fbw_display()
        call_text = widgets["#fbw-display"].update.call_args[0][0]
        assert "Outside studied edge-calibration range" in call_text
        assert "after calculation" in call_text
        widgets["#fbw-display"].add_class.assert_any_call("fbw-warning")

    @pytest.mark.parametrize(
        "bw_value, expected_class",
        [
            ("1MHz", "fbw-display"),  # exactly 10% remains in the studied range
            ("4MHz", "fbw-warning"),  # exactly 40% is caution, not strong caution
            ("4.01MHz", "fbw-danger"),
        ],
    )
    def test_fbw_public_threshold_boundaries(self, bw_value, expected_class):
        screen, _state, _notes, _pushed, widgets = _bp_mock_screen(
            freq_value="10MHz", bw_value=bw_value
        )
        screen._update_fbw_display()
        widgets["#fbw-display"].add_class.assert_any_call(expected_class)

    def test_fbw_display_wide_bandwidth_warns(self):
        screen, _state, _notes, _pushed, widgets = _bp_mock_screen(
            freq_value="10MHz",
            bw_value="8MHz",  # 80% bandwidth
        )
        screen._update_fbw_display()
        call_text = widgets["#fbw-display"].update.call_args[0][0]
        assert "Lumped-model caution" in call_text
        assert "transmission-line" in call_text
        widgets["#fbw-display"].add_class.assert_any_call("fbw-danger")

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
        assert widgets["#resonator-impedance"].value == ""
        assert widgets["#resonator-inductance"].value == ""
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
    options_selected: tuple[str, ...] = (),
    build_enabled: bool = False,
    build_values: dict[str, str] | None = None,
    use_toroids: bool = True,
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
    opts.selected = list(options_selected)

    export = Mock(spec=RadioSet)
    export.has_focus = make_focus_flag("export", focus_target)
    ebtn = Mock()
    ebtn.id = export_id
    export.pressed_button = ebtn

    results_btn = Mock(spec=Button)

    build_toggle = Mock(spec=Checkbox)
    build_toggle.value = build_enabled
    build_options = Mock()
    build_options.display = build_enabled
    toroid_toggle = Mock(spec=Checkbox)
    toroid_toggle.value = use_toroids

    values = {
        "#build-source-resistance": "",
        "#build-load-resistance": "",
        "#build-capacitor-tolerance": "5",
        "#build-inductor-tolerance": "10",
        "#build-inductor-q": "",
        "#build-capacitor-q": "",
        "#build-resonator-q": "",
        "#build-sample-count": "0",
        "#build-seed": "0",
        "#build-grid-points": "601",
    }
    values.update(build_values or {})

    def make_input(value: str) -> Mock:
        widget = Mock(spec=Input)
        widget.value = value
        widget.focus = Mock()
        return widget

    widgets = {
        "#eseries": eseries,
        "#format": fmt,
        "#options-list": opts,
        "#export": export,
        "#build-analysis-enabled": build_toggle,
        "#build-analysis-options": build_options,
        "#build-use-toroids": toroid_toggle,
        "#results-btn": results_btn,
    }
    widgets.update({selector: make_input(value) for selector, value in values.items()})

    def fake_query_one(selector: str, widget_type=None):
        if selector not in widgets:
            raise LookupError(selector)
        return widgets[selector]

    screen.query_one = fake_query_one  # type: ignore[assignment]
    screen.notify = Mock()  # type: ignore[assignment]
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

    @pytest.mark.parametrize(
        ("format_id", "options", "eseries", "message"),
        [
            ("json", ("plot",), "E24", "only with table"),
            ("csv", ("raw",), "E24", "only with table"),
            ("json", ("quiet",), "E24", "only with table"),
            ("table", ("quiet", "plot"), "none", "cannot be combined"),
            ("table", ("raw",), "E24", "not represented"),
            ("table", ("quiet",), "E24", "not represented"),
        ],
    )
    def test_invisible_output_selections_are_rejected(self, format_id, options, eseries, message):
        screen, _app, pushed, widgets = _make_output_options(
            "eseries",
            eseries_id=eseries,
            format_id=format_id,
            options_selected=options,
        )

        screen._show_results()

        assert pushed == []
        assert message in screen.notify.call_args[0][0]
        focus = "#eseries" if "not represented" in message else "#options-list"
        widgets[focus].focus.assert_called_once()


class TestOutputOptionsBuildAnalysis:
    def test_defaults_are_off_and_preserved(self):
        screen, app, pushed, _widgets = _make_output_options("eseries")
        screen._show_results()
        state = app.filter_state
        assert pushed
        assert state.build_analysis_enabled is False
        assert state.build_capacitor_tolerance_pct == 5.0
        assert state.build_inductor_tolerance_pct == 10.0
        assert state.build_sample_count == 0
        assert state.build_seed == 0
        assert state.build_grid_points == 601
        assert state.build_use_toroid_candidates is True

    def test_enabled_controls_parse_into_state(self):
        screen, app, pushed, _widgets = _make_output_options(
            "eseries",
            eseries_id="E96",
            build_enabled=True,
            build_values={
                "#build-source-resistance": "25ohm",
                "#build-load-resistance": "100",
                "#build-capacitor-tolerance": "2.5",
                "#build-inductor-tolerance": "7.5",
                "#build-inductor-q": "120",
                "#build-capacitor-q": "500",
                "#build-sample-count": "7",
                "#build-seed": "42",
                "#build-grid-points": "301",
            },
            use_toroids=False,
        )
        screen._show_results()
        state = app.filter_state
        assert pushed
        assert state.build_analysis_enabled is True
        assert state.build_source_resistance_ohm == 25.0
        assert state.build_load_resistance_ohm == 100.0
        assert state.build_capacitor_tolerance_pct == 2.5
        assert state.build_inductor_tolerance_pct == 7.5
        assert state.build_inductor_q == 120.0
        assert state.build_capacitor_q == 500.0
        assert state.build_resonator_q is None
        assert state.build_sample_count == 7
        assert state.build_seed == 42
        assert state.build_grid_points == 301
        assert state.build_use_toroid_candidates is False

    def test_raw_build_analysis_uses_eseries_for_nominal_selection(self):
        screen, app, pushed, _widgets = _make_output_options(
            "eseries",
            eseries_id="E12",
            options_selected=("raw",),
            build_enabled=True,
        )

        screen._show_results()

        assert pushed
        assert app.filter_state.raw_units is True
        assert app.filter_state.eseries == "E12"
        assert app.filter_state.build_analysis_enabled is True

    @pytest.mark.parametrize(
        "format_id, options_selected, eseries_id, expected_text",
        [
            ("csv", (), "E24", "table or JSON"),
            ("table", ("quiet",), "E24", "quiet"),
            ("table", (), "none", "E-series"),
        ],
    )
    def test_incompatible_output_modes_are_rejected(
        self, format_id, options_selected, eseries_id, expected_text
    ):
        screen, _app, pushed, _widgets = _make_output_options(
            "eseries",
            format_id=format_id,
            options_selected=options_selected,
            eseries_id=eseries_id,
            build_enabled=True,
        )
        screen._show_results()
        assert pushed == []
        assert expected_text in screen.notify.call_args[0][0]

    def test_custom_build_control_is_not_ignored_when_analysis_is_off(self):
        screen, _app, pushed, widgets = _make_output_options(
            "eseries",
            build_values={"#build-sample-count": "4"},
        )
        screen._show_results()
        assert pushed == []
        assert "Enable realized-build analysis" in screen.notify.call_args[0][0]
        widgets["#build-analysis-enabled"].focus.assert_called_once()

    @pytest.mark.parametrize(
        "build_values, expected_text",
        [
            ({"#build-source-resistance": "not-ohms"}, "source resistance"),
            ({"#build-load-resistance": "not-ohms"}, "load resistance"),
            ({"#build-capacitor-tolerance": "100"}, "capacitor_tolerance_pct"),
            ({"#build-inductor-q": "0"}, "inductor_q"),
            ({"#build-sample-count": "1.5"}, "sample count"),
            ({"#build-sample-count": "10001"}, "sample_count"),
            ({"#build-seed": "1.5"}, "seed"),
            ({"#build-grid-points": "50"}, "grid_points"),
        ],
    )
    def test_invalid_build_controls_are_rejected(self, build_values, expected_text):
        screen, _app, pushed, widgets = _make_output_options(
            "eseries", build_enabled=True, build_values=build_values
        )
        screen._show_results()
        assert pushed == []
        assert expected_text in screen.notify.call_args[0][0]
        if "source" in expected_text:
            widgets["#build-source-resistance"].focus.assert_called_once()
        elif "load" in expected_text:
            widgets["#build-load-resistance"].focus.assert_called_once()

    def test_resonator_q_is_mutually_exclusive_with_component_q(self):
        screen, _app, pushed, _widgets = _make_output_options(
            "eseries",
            build_enabled=True,
            build_values={"#build-inductor-q": "100", "#build-resonator-q": "200"},
        )
        screen._show_results()
        assert pushed == []
        assert "mutually exclusive" in screen.notify.call_args[0][0]

    def test_build_toggle_controls_advanced_group_visibility(self):
        screen, _app, _pushed, widgets = _make_output_options("eseries")
        event = Mock()
        event.value = True
        screen._on_build_analysis_changed(event)
        assert widgets["#build-analysis-options"].display is True
        widgets["#build-source-resistance"].focus.assert_called_once()


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
        "output_format, sidecar_format, expected_id",
        [
            ("json", None, "export-json"),
            ("table", "csv", "export-txt"),
            ("csv", "json", "export-csv"),
        ],
    )
    def test_component_preselection_is_independent_of_response_sidecar(
        self, output_format, sidecar_format, expected_id
    ):
        screen = ResultsScreen()
        state = FilterState(output_format=output_format, export_format=sidecar_format)
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        buttons = []
        for button_id in ("export-txt", "export-json", "export-csv"):
            button = Mock(id=button_id, value=False, disabled=False)
            buttons.append(button)
        radio_set = Mock(spec=RadioSet)
        radio_set.query.return_value = buttons
        screen.query_one = lambda *_a, **_k: radio_set  # type: ignore[assignment]

        screen._preselect_export_format()

        assert next(button for button in buttons if button.id == expected_id).value is True

    def test_build_result_preselects_component_format_and_disables_csv(self):
        screen = ResultsScreen()
        state = FilterState(
            output_format="json",
            export_format="csv",
            build_analysis_enabled=True,
        )
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        buttons = []
        for button_id in ("export-txt", "export-json", "export-csv"):
            button = Mock()
            button.id = button_id
            button.value = False
            button.disabled = False
            buttons.append(button)
        radio_set = Mock(spec=RadioSet)
        radio_set.query.return_value = buttons
        screen.query_one = lambda *_a, **_k: radio_set  # type: ignore[assignment]

        screen._preselect_export_format()

        assert next(b for b in buttons if b.id == "export-json").value is True
        assert next(b for b in buttons if b.id == "export-csv").disabled is True

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
        state.output_text = "current result"
        state.calculation_status = "success"
        screen._result_text = state.output_text
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
        state.output_text = "current result"
        state.calculation_status = "success"
        screen._result_text = state.output_text
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
        state.output_text = "current result"
        state.calculation_status = "success"
        screen._result_text = state.output_text
        out = screen._get_json_export(state)
        assert out


class TestResultsScreenWorkerHook:
    def test_worker_success_updates_result_text(self):
        screen = ResultsScreen()
        state = FilterState()
        revision = state.begin_calculation()
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        static_mock = Mock(spec=Static)
        export_button = Mock(spec=Button)
        widgets = {"#results-text": static_mock, "#export-btn": export_button}
        screen.query_one = lambda selector, *_a, **_k: widgets[selector]  # type: ignore[assignment]
        event = Mock()
        event.state = SimpleNamespace(name="SUCCESS")
        event.worker = Mock()
        event.worker.result = CalculationOutcome(
            status="success",
            output_text="result-text-from-worker",
            result={"filter_type": "butterworth"},
        )
        screen._active_worker = event.worker
        screen._calculation_revision = revision
        screen._accept_worker_events = True
        screen.on_worker_state_changed(event)
        assert screen._result_text == "result-text-from-worker"
        static_mock.update.assert_called_once_with("result-text-from-worker")
        assert state.calculation_status == "success"
        assert state.result == {"filter_type": "butterworth"}
        assert export_button.disabled is False

    def test_worker_success_publishes_realized_build_analysis(self):
        screen = ResultsScreen()
        state = FilterState(build_analysis_enabled=True)
        revision = state.begin_calculation()
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        static_mock = Mock(spec=Static)
        export_button = Mock(spec=Button)
        widgets = {"#results-text": static_mock, "#export-btn": export_button}
        screen.query_one = lambda selector, *_a, **_k: widgets[selector]  # type: ignore[assignment]
        analysis = {"worker": "analysis"}
        event = Mock(state=SimpleNamespace(name="SUCCESS"), worker=Mock())
        event.worker.result = CalculationOutcome(
            status="success",
            output_text="target/exact/nominal/tolerance",
            result={"filter_type": "butterworth"},
            build_analysis=analysis,
        )
        screen._active_worker = event.worker
        screen._calculation_revision = revision
        screen._accept_worker_events = True

        screen.on_worker_state_changed(event)

        assert state.build_analysis == analysis
        assert state.is_exportable
        assert export_button.disabled is False

    def test_build_success_without_analysis_is_published_as_failure(self):
        screen = ResultsScreen()
        state = FilterState(build_analysis_enabled=True)
        revision = state.begin_calculation()
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        static_mock = Mock(spec=Static)
        export_button = Mock(spec=Button)
        widgets = {"#results-text": static_mock, "#export-btn": export_button}
        screen.query_one = lambda selector, *_a, **_k: widgets[selector]  # type: ignore[assignment]
        event = Mock(state=SimpleNamespace(name="SUCCESS"), worker=Mock())
        event.worker.result = CalculationOutcome(
            status="success",
            output_text="component result only",
            result={"filter_type": "butterworth"},
        )
        screen._active_worker = event.worker
        screen._calculation_revision = revision
        screen._accept_worker_events = True

        screen.on_worker_state_changed(event)

        assert state.calculation_status == "error"
        assert state.build_analysis is None
        assert not state.is_exportable
        assert "no realized-build analysis" in static_mock.update.call_args[0][0]
        assert export_button.disabled is True

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
        state = FilterState()
        revision = state.begin_calculation()
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        static_mock = Mock(spec=Static)
        export_button = Mock(spec=Button)
        widgets = {"#results-text": static_mock, "#export-btn": export_button}
        screen.query_one = lambda selector, *_a, **_k: widgets[selector]  # type: ignore[assignment]
        event = Mock()
        event.state = SimpleNamespace(name="ERROR")
        event.worker = Mock()
        event.worker.error = RuntimeError("solver exploded")
        screen._active_worker = event.worker
        screen._calculation_revision = revision
        screen._accept_worker_events = True
        screen.on_worker_state_changed(event)
        text = static_mock.update.call_args[0][0]
        assert "solver exploded" in text
        assert "Esc" in text
        assert state.calculation_status == "error"
        assert state.result == {}
        assert export_button.disabled is True

    def test_success_outcome_after_newer_revision_is_ignored(self):
        screen = ResultsScreen()
        state = FilterState()
        old_revision = state.begin_calculation()
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        old_worker = Mock()
        screen._active_worker = old_worker
        screen._calculation_revision = old_revision
        screen._accept_worker_events = True
        state.invalidate_calculation()
        screen.query_one = Mock(side_effect=AssertionError("stale worker touched UI"))  # type: ignore[assignment]
        event = Mock(
            state=SimpleNamespace(name="SUCCESS"),
            worker=old_worker,
        )
        event.worker.result = CalculationOutcome(
            status="success",
            output_text="stale",
            result={"stale": True},
            build_analysis={"stale": True},
        )

        screen.on_worker_state_changed(event)

        assert state.result == {}
        assert state.calculation_status == "idle"
        assert state.build_analysis is None
        assert screen._result_text == ""

    def test_popped_screen_ignores_completed_worker(self):
        screen = ResultsScreen()
        state = FilterState()
        revision = state.begin_calculation()
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        worker = Mock()
        screen._active_worker = worker
        screen._calculation_revision = revision
        screen._accept_worker_events = True

        screen.on_unmount()

        worker.cancel.assert_called_once_with()
        assert state.calculation_status == "idle"
        assert state.result == {}
        event = Mock(state=SimpleNamespace(name="SUCCESS"), worker=worker)
        event.worker.result = CalculationOutcome(
            status="success",
            output_text="late",
            result={"late": True},
            build_analysis={"late": True},
        )
        screen.on_worker_state_changed(event)
        assert state.result == {}
        assert state.build_analysis is None

    def test_success_followed_by_failure_clears_exportable_result(self):
        state = FilterState(
            calculation_status="success",
            result={"old": True},
            output_text="old result",
        )
        revision = state.begin_calculation()
        assert state.publish_error(revision, "new calculation failed")
        assert state.result == {}
        assert state.output_text == ""
        assert not state.is_exportable


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
        state = FilterState(
            calculation_status="success",
            result={"ok": True},
            output_text="current result",
        )
        screen._result_text = state.output_text
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
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

    def test_pending_calculation_cannot_save_any_file(self, tmp_path, monkeypatch):
        screen = ResultsScreen()
        state = FilterState(category="lowpass")
        state.begin_calculation()
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        section = Mock()
        screen.query_one = lambda selector, *_a, **_k: {"#export-section": section}[selector]  # type: ignore[assignment]
        screen.notify = Mock()  # type: ignore[assignment]
        monkeypatch.chdir(tmp_path)

        screen._save_export()

        assert not list(tmp_path.iterdir())
        assert "No current successful calculation" in screen.notify.call_args[0][0]

    def test_on_button_pressed_save_routes_through_save(self, tmp_path, monkeypatch):
        """`save-btn` triggers _save_export without crashing for text format."""
        screen = ResultsScreen()
        screen._result_text = "result-text"
        state = FilterState()
        state.category = "lowpass"
        state.result = {"ok": True}
        state.output_text = screen._result_text
        state.calculation_status = "success"
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

    def test_save_rejects_component_csv_for_build_analysis(self, tmp_path, monkeypatch):
        screen = ResultsScreen()
        state = FilterState(
            category="lowpass",
            result={"ok": True},
            output_text="current build result",
            calculation_status="success",
            build_analysis_enabled=True,
            build_analysis={"same_worker": True},
        )
        screen._result_text = state.output_text
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        export_format = Mock(spec=RadioSet)
        export_format.pressed_button = Mock(id="export-csv")
        widgets = {"#export-format": export_format, "#export-section": Mock()}
        screen.query_one = lambda selector, *_a, **_k: widgets[selector]  # type: ignore[assignment]
        screen.notify = Mock()  # type: ignore[assignment]
        monkeypatch.chdir(tmp_path)

        screen._save_export()

        assert not list(tmp_path.iterdir())
        assert "not supported in component CSV" in screen.notify.call_args[0][0]

    def test_save_export_handles_os_error(self, monkeypatch):
        """If open() raises OSError, error is caught and reported via notify."""
        screen = ResultsScreen()
        screen._result_text = "result-text"
        state = FilterState()
        state.category = "lowpass"
        state.result = {"ok": True}
        state.output_text = screen._result_text
        state.calculation_status = "success"
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

    def test_save_export_opens_unicode_payload_as_utf8(self, monkeypatch):
        screen = ResultsScreen()
        screen._result_text = "Ω 1 µH ───"
        state = FilterState(
            category="lowpass",
            result={"ok": True},
            output_text=screen._result_text,
            calculation_status="success",
        )
        app = Mock(filter_state=state)
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]
        export_format = Mock(spec=RadioSet)
        export_format.pressed_button = Mock(id="export-txt")
        widgets = {"#export-format": export_format, "#export-section": Mock()}
        screen.query_one = lambda selector, *_a, **_k: widgets[selector]  # type: ignore[assignment]
        screen.notify = Mock()  # type: ignore[assignment]

        import filter_lib.wizard.screens.results as results_mod

        open_mock = mock_open()
        monkeypatch.setattr(results_mod, "open", open_mock, raising=False)

        screen._save_export()

        open_mock.assert_called_once()
        assert open_mock.call_args.kwargs == {"encoding": "utf-8", "newline": ""}
        open_mock().write.assert_called_once_with("Ω 1 µH ───")

    def test_save_export_defaults_format_id_when_no_pressed_button(self, tmp_path, monkeypatch):
        """If pressed_button is None, the code falls back to export-txt."""
        screen = ResultsScreen()
        screen._result_text = "fallback-text"
        state = FilterState()
        state.category = "highpass"
        state.result = {"ok": True}
        state.output_text = screen._result_text
        state.calculation_status = "success"
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
        state.output_text = screen._result_text
        state.calculation_status = "success"
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
