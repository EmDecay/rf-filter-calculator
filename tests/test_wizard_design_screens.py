"""Low-pass, high-pass, and band-pass design-form behavior without a running app.

Handlers are called directly on screens whose ``query_one`` returns ``Mock(spec=...)``
widgets. Widget-id wiring and real key handling are covered by the mounted journeys in
``test_wizard_design_screen_journeys.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from textual.widgets import Button, Input, RadioSet, Static

from filter_lib.wizard.bandpass_form import (
    BandpassFormError,
    BandpassFormValues,
    fractional_bandwidth_feedback,
    parse_bandpass_form,
)
from filter_lib.wizard.filter_screen_navigation_mixin import FilterScreenNavigationMixin
from filter_lib.wizard.screens.bandpass import BandpassScreen
from filter_lib.wizard.screens.highpass import HighpassScreen
from filter_lib.wizard.screens.lowpass import LowpassScreen
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.state import FilterState

LP_HP_SCREENS = [LowpassScreen, HighpassScreen]


def _key(key: str) -> Mock:
    return Mock(key=key)


def _input(value: str = "", placeholder: str = "") -> Mock:
    widget = Mock(spec=Input)
    widget.value = value
    widget.placeholder = placeholder
    return widget


def _radio_set(selected_id: str, *, has_focus: bool = False) -> Mock:
    radio_set = Mock(spec=RadioSet)
    radio_set.pressed_button = Mock(id=selected_id)
    radio_set.has_focus = has_focus
    return radio_set


def _mount(monkeypatch, screen, widgets: dict[str, Mock]) -> SimpleNamespace:
    """Attach a stub app and widget map to ``screen``; ``monkeypatch`` undoes the class stub."""
    app = Mock(filter_state=FilterState())
    pushed: list = []
    notes: list[tuple[str, str]] = []
    app.push_screen = pushed.append
    monkeypatch.setattr(type(screen), "app", property(lambda _self: app))
    screen.query_one = lambda selector, *_args: widgets[selector]  # type: ignore[assignment]
    screen.notify = lambda message, severity="information": notes.append((severity, message))  # type: ignore[assignment]
    return SimpleNamespace(
        screen=screen, app=app, state=app.filter_state, pushed=pushed, notes=notes, w=widgets
    )


# ---------------------------------------------------------------------------
# Enter-key flow between RadioSets (shared by the three design screens)
# ---------------------------------------------------------------------------


class _NavScreen(FilterScreenNavigationMixin):
    RADIO_SET_FLOW = ["filter-type", "topology"]
    FIRST_INPUT_ID = "frequency"

    def __init__(self, widgets: dict) -> None:
        self._widgets = widgets

    def query_one(self, selector: str, widget_type=None):
        if selector not in self._widgets:
            raise LookupError(selector)
        return self._widgets[selector]


class TestRadioSetEnterNavigation:
    def test_enter_on_first_radio_set_focuses_the_next_and_consumes_the_key(self):
        first, second = _radio_set("a", has_focus=True), _radio_set("b")
        screen = _NavScreen({"#filter-type": first, "#topology": second})
        event = _key("enter")

        screen.on_key(event)

        second.focus.assert_called_once_with()
        event.prevent_default.assert_called_once_with()
        event.stop.assert_called_once_with()

    def test_enter_on_last_radio_set_focuses_the_first_input(self):
        frequency = _input()
        screen = _NavScreen(
            {
                "#filter-type": _radio_set("a"),
                "#topology": _radio_set("b", has_focus=True),
                "#frequency": frequency,
            }
        )

        screen.on_key(_key("enter"))

        frequency.focus.assert_called_once_with()

    def test_last_radio_set_without_a_first_input_still_consumes_enter(self):
        screen = _NavScreen({"#topology": _radio_set("b", has_focus=True)})
        screen.RADIO_SET_FLOW = ["topology"]
        screen.FIRST_INPUT_ID = ""
        event = _key("enter")

        screen.on_key(event)

        event.prevent_default.assert_called_once_with()
        event.stop.assert_called_once_with()

    @pytest.mark.parametrize("key, focused", [("tab", True), ("enter", False)])
    def test_other_keys_or_unfocused_radio_sets_are_left_alone(self, key, focused):
        second = _radio_set("b")
        screen = _NavScreen(
            {"#filter-type": _radio_set("a", has_focus=focused), "#topology": second}
        )
        event = _key(key)

        screen.on_key(event)

        second.focus.assert_not_called()
        event.prevent_default.assert_not_called()

    def test_enter_before_widgets_are_mounted_is_ignored(self):
        event = _key("enter")

        _NavScreen({}).on_key(event)

        event.prevent_default.assert_not_called()


# ---------------------------------------------------------------------------
# Low-pass / high-pass form
# ---------------------------------------------------------------------------


def _lp_hp_form(
    monkeypatch,
    screen_cls,
    *,
    frequency: str = "10MHz",
    impedance: str = "50",
    order: str = "3",
    ripple: str = "0.5",
    filter_type: str = "butterworth",
    topology: str = "pi",
) -> SimpleNamespace:
    ripple_section = Mock(display=filter_type == "chebyshev")
    widgets = {
        "#frequency": _input(frequency, placeholder="10MHz"),
        "#impedance": _input(impedance),
        "#order": _input(order),
        "#ripple": _input(ripple),
        "#filter-type": _radio_set(filter_type),
        "#topology": _radio_set(topology),
        "#ripple-section": ripple_section,
        "#order-label": Mock(spec=Static),
        "#next-btn": Mock(spec=Button),
    }
    return _mount(monkeypatch, screen_cls(), widgets)


LP_HP_REJECTIONS = [
    ({"frequency": "notafreq"}, "error", "Invalid frequency", "#frequency"),
    ({"impedance": "abc"}, "error", "Invalid impedance", "#impedance"),
    ({"impedance": "0"}, "error", "Invalid impedance", "#impedance"),
    ({"order": "1"}, "error", "Invalid order: must be 2-9", "#order"),
    ({"order": "10"}, "error", "Invalid order: must be 2-9", "#order"),
    ({"order": "xyz"}, "error", "Invalid order", "#order"),
    ({"filter_type": "chebyshev", "order": "4"}, "warning", "requires odd order", "#order"),
    (
        {"filter_type": "chebyshev", "ripple": "0"},
        "error",
        "Invalid ripple: must be positive",
        "#ripple",
    ),
    ({"filter_type": "chebyshev", "ripple": "-0.1"}, "error", "must be positive", "#ripple"),
    ({"filter_type": "chebyshev", "ripple": "nope"}, "error", "Invalid ripple", "#ripple"),
    (
        {"filter_type": "chebyshev", "ripple": "nan"},
        "error",
        "Invalid ripple: must be finite",
        "#ripple",
    ),
    (
        {"filter_type": "chebyshev", "ripple": "inf"},
        "error",
        "Invalid ripple: must be finite",
        "#ripple",
    ),
    ({"filter_type": "chebyshev", "ripple": "3.1"}, "error", "must be <= 3.0 dB", "#ripple"),
]


class TestLowpassHighpassForm:
    @pytest.mark.parametrize("screen_cls", LP_HP_SCREENS)
    @pytest.mark.parametrize("overrides, severity, message, focus", LP_HP_REJECTIONS)
    def test_invalid_input_is_reported_on_its_field_and_blocks_navigation(
        self, monkeypatch, screen_cls, overrides, severity, message, focus
    ):
        form = _lp_hp_form(monkeypatch, screen_cls, **overrides)

        form.screen._validate_and_continue()

        assert form.pushed == []
        assert len(form.notes) == 1
        assert form.notes[0][0] == severity
        assert message in form.notes[0][1]
        form.w[focus].focus.assert_called_once_with()
        assert form.state.category == ""
        assert form.state.ripple_db == 0.5

    @pytest.mark.parametrize(
        "screen_cls, category, topology",
        [(LowpassScreen, "lowpass", "t"), (HighpassScreen, "highpass", "pi")],
    )
    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"impedance": "50ohm"}, {"impedance": 50.0}),
            ({"impedance": "1k"}, {"impedance": 1000.0}),
            ({"impedance": ""}, {"impedance": 50.0}),
            ({"frequency": ""}, {"frequency_hz": 10e6}),
            ({"frequency": "7.1MHz", "order": "9"}, {"frequency_hz": 7.1e6, "order": 9}),
            (
                {"filter_type": "chebyshev", "order": "5", "ripple": "3.0"},
                {"filter_type": "chebyshev", "ripple_db": 3.0},
            ),
            ({"filter_type": "bessel", "order": "2"}, {"filter_type": "bessel", "order": 2}),
            # A ripple left in the hidden field must not reach a non-Chebyshev design.
            ({"filter_type": "butterworth", "ripple": "1.5"}, {"ripple_db": 0.5}),
        ],
    )
    def test_valid_design_is_stored_and_opens_output_options(
        self, monkeypatch, screen_cls, category, topology, overrides, expected
    ):
        form = _lp_hp_form(monkeypatch, screen_cls, topology=topology, **overrides)
        form.state.ripple_db = 2.0  # stale value from an earlier Chebyshev pass

        form.screen._validate_and_continue()

        assert [type(screen) for screen in form.pushed] == [OutputOptionsScreen]
        assert form.notes == []
        assert (form.state.category, form.state.topology) == (category, topology)
        for field, value in expected.items():
            assert getattr(form.state, field) == value

    @pytest.mark.parametrize("screen_cls", LP_HP_SCREENS)
    def test_accepting_a_design_invalidates_the_previous_result(self, monkeypatch, screen_cls):
        form = _lp_hp_form(monkeypatch, screen_cls)
        revision = form.state.begin_calculation()
        form.state.publish_success(revision, "old table", {"old": True})

        form.screen._validate_and_continue()

        assert form.state.calculation_revision == revision + 1
        assert form.state.calculation_status == "idle"
        assert form.state.result == {}

    @pytest.mark.parametrize("screen_cls", LP_HP_SCREENS)
    def test_buttons_dispatch_to_validate_and_reset(self, monkeypatch, screen_cls):
        form = _lp_hp_form(monkeypatch, screen_cls, frequency="7MHz", order="5")

        form.screen.on_button_pressed(Mock(button=Mock(id="unknown")))
        assert form.pushed == []

        form.screen.on_button_pressed(Mock(button=Mock(id="reset-btn")))
        assert [
            form.w[f"#{name}"].value for name in ("frequency", "impedance", "order", "ripple")
        ] == [
            "",
            "50",
            "3",
            "0.5",
        ]
        form.w["#frequency"].focus.assert_called_once_with()

        form.screen.on_button_pressed(Mock(button=Mock(id="next-btn")))
        assert [type(screen) for screen in form.pushed] == [OutputOptionsScreen]
        assert form.state.frequency_hz == 10e6  # reset value falls back to the placeholder

    @pytest.mark.parametrize("screen_cls", LP_HP_SCREENS)
    def test_escape_action_returns_to_the_previous_screen(self, monkeypatch, screen_cls):
        form = _lp_hp_form(monkeypatch, screen_cls)

        form.screen.action_back()

        form.app.pop_screen.assert_called_once_with()

    @pytest.mark.parametrize("screen_cls", LP_HP_SCREENS)
    @pytest.mark.parametrize(
        "handler, ripple_visible, focused",
        [
            ("_on_frequency_submitted", False, "#impedance"),
            ("_on_impedance_submitted", False, "#order"),
            ("_on_order_submitted", True, "#ripple"),
            ("_on_order_submitted", False, "#next-btn"),
            ("_on_ripple_submitted", True, "#next-btn"),
        ],
    )
    def test_submitting_a_field_advances_focus(
        self, monkeypatch, screen_cls, handler, ripple_visible, focused
    ):
        form = _lp_hp_form(monkeypatch, screen_cls)
        form.w["#ripple-section"].display = ripple_visible

        getattr(form.screen, handler)(Mock())

        form.w[focused].focus.assert_called_once_with()

    @pytest.mark.parametrize("screen_cls", LP_HP_SCREENS)
    @pytest.mark.parametrize(
        "pressed, ripple_visible, label",
        [
            ("chebyshev", True, "Order (Chebyshev: odd only — 3, 5, 7, 9):"),
            ("butterworth", False, "Order (2-9 components):"),
            ("bessel", False, "Order (2-9 components):"),
        ],
    )
    def test_response_type_toggles_ripple_and_order_hint(
        self, monkeypatch, screen_cls, pressed, ripple_visible, label
    ):
        form = _lp_hp_form(monkeypatch, screen_cls)
        revision = form.state.calculation_revision

        form.screen._on_filter_type_changed(Mock(pressed=Mock(id=pressed)))

        assert form.w["#ripple-section"].display is ripple_visible
        form.w["#order-label"].update.assert_called_once_with(label)
        assert form.state.calculation_revision == revision + 1


# ---------------------------------------------------------------------------
# Band-pass form parsing (pure) and screen mapping
# ---------------------------------------------------------------------------


def _bp_values(**overrides) -> BandpassFormValues:
    values = dict(
        frequency="14.175MHz",
        bandwidth="350kHz",
        impedance="50",
        resonators="3",
        ripple="0.5",
        resonator_impedance="",
        resonator_inductance="",
        filter_type="butterworth",
        coupling="top",
    )
    values.update(overrides)
    return BandpassFormValues(**values)


class TestParseBandpassForm:
    def test_valid_form_returns_si_values(self):
        design = parse_bandpass_form(_bp_values())

        assert design.frequency_hz == 14.175e6
        assert design.bandwidth_hz == 350e3
        assert design.impedance == 50.0
        assert design.resonators == 3
        assert design.ripple_db == 0.5
        assert (design.resonator_impedance, design.resonator_inductance) == (None, None)
        assert (design.filter_type, design.coupling) == ("butterworth", "top")

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"filter_type": "chebyshev", "ripple": "0.1"}, {"ripple_db": 0.1}),
            ({"filter_type": "chebyshev", "ripple": "3.0"}, {"ripple_db": 3.0}),
            ({"filter_type": "bessel", "resonators": "2"}, {"resonators": 2}),
            ({"resonator_impedance": "75ohm"}, {"resonator_impedance": 75.0}),
            (
                {"resonator_inductance": "1.2uH"},
                {"resonator_inductance": pytest.approx(1.2e-6, rel=1e-12, abs=0)},
            ),
            # Ripple is ignored (and defaulted) for non-Chebyshev responses.
            ({"filter_type": "butterworth", "ripple": "nope"}, {"ripple_db": 0.5}),
        ],
    )
    def test_optional_and_response_specific_values(self, overrides, expected):
        design = parse_bandpass_form(_bp_values(**overrides))

        for field, value in expected.items():
            assert getattr(design, field) == value

    @pytest.mark.parametrize(
        "overrides, message, field_id, severity",
        [
            ({"frequency": "junk"}, "Invalid center frequency", "frequency", "error"),
            ({"bandwidth": "junk"}, "Invalid bandwidth", "bandwidth", "error"),
            (
                {"frequency": "10MHz", "bandwidth": "10MHz"},
                "Bandwidth must be less than center frequency",
                "bandwidth",
                "error",
            ),
            (
                {"frequency": "10MHz", "bandwidth": "11MHz"},
                "Bandwidth must be less than center frequency",
                "bandwidth",
                "error",
            ),
            ({"impedance": "0"}, "Invalid impedance", "impedance", "error"),
            (
                {"resonator_impedance": "75", "resonator_inductance": "1uH"},
                "Choose only one advanced tank setting",
                "resonator-inductance",
                "error",
            ),
            (
                {"resonator_impedance": "abc"},
                "Invalid tank impedance",
                "resonator-impedance",
                "error",
            ),
            (
                {"resonator_inductance": "not-an-inductor"},
                "Invalid tank inductance",
                "resonator-inductance",
                "error",
            ),
            ({"resonators": "1"}, "Invalid resonators: must be 2-9", "resonators", "error"),
            ({"resonators": "xxx"}, "Invalid resonators", "resonators", "error"),
            (
                {"filter_type": "chebyshev", "resonators": "4"},
                "odd number of resonators",
                "resonators",
                "warning",
            ),
            ({"filter_type": "chebyshev", "ripple": "-0.1"}, "must be positive", "ripple", "error"),
            ({"filter_type": "chebyshev", "ripple": "nan"}, "must be finite", "ripple", "error"),
            ({"filter_type": "chebyshev", "ripple": "3.1"}, "must be <= 3.0 dB", "ripple", "error"),
        ],
    )
    def test_invalid_values_name_the_field_to_focus(self, overrides, message, field_id, severity):
        with pytest.raises(BandpassFormError, match=message) as caught:
            parse_bandpass_form(_bp_values(**overrides))

        assert caught.value.field_id == field_id
        assert caught.value.severity == severity


class TestFractionalBandwidthFeedback:
    @pytest.mark.parametrize(
        "frequency, bandwidth, percent, style, wording",
        [
            (
                "14.175MHz",
                "350kHz",
                "2.47%",
                "fbw-display",
                "Within studied edge-calibration range",
            ),
            ("10MHz", "1MHz", "10.00%", "fbw-display", "Within studied edge-calibration range"),
            ("10MHz", "2MHz", "20.00%", "fbw-warning", "Outside studied edge-calibration range"),
            ("10MHz", "4MHz", "40.00%", "fbw-warning", "Outside studied edge-calibration range"),
            ("10MHz", "4.01MHz", "40.10%", "fbw-danger", "consider a transmission-line design"),
        ],
    )
    def test_threshold_bands_defer_final_validation(
        self, frequency, bandwidth, percent, style, wording
    ):
        text, class_name = fractional_bandwidth_feedback(frequency, bandwidth)

        assert class_name == style
        assert text.startswith(f"Fractional BW: {percent} · ")
        assert wording in text
        assert text.endswith("final response validation runs after calculation.")
        assert "validated" not in text.lower()

    @pytest.mark.parametrize(
        "frequency, bandwidth", [("junk", "1MHz"), ("10MHz", ""), ("0MHz", "1MHz")]
    )
    def test_partial_or_zero_input_gives_no_feedback(self, frequency, bandwidth):
        assert fractional_bandwidth_feedback(frequency, bandwidth) is None


def _bp_form(monkeypatch, filter_type: str = "butterworth", **inputs: str) -> SimpleNamespace:
    """Band-pass screen stub; ``inputs`` use field names with ``_`` for ``-`` in widget ids."""
    values = {
        "frequency": "14.175MHz",
        "bandwidth": "350kHz",
        "impedance": "50",
        "resonators": "3",
        "ripple": "0.5",
        "resonator_impedance": "",
        "resonator_inductance": "",
    }
    values.update(inputs)
    placeholders = {"frequency": "14.175MHz", "bandwidth": "350kHz"}
    widgets = {
        "#" + name.replace("_", "-"): _input(value, placeholders.get(name, ""))
        for name, value in values.items()
    }
    widgets.update(
        {
            "#filter-type": _radio_set(filter_type),
            "#coupling": _radio_set("top"),
            "#ripple-section": Mock(display=filter_type == "chebyshev"),
            "#resonators-label": Mock(spec=Static),
            "#fbw-display": Mock(spec=Static),
            "#next-btn": Mock(spec=Button),
        }
    )
    return _mount(monkeypatch, BandpassScreen(), widgets)


class TestBandpassScreen:
    def test_valid_design_is_stored_and_opens_output_options(self, monkeypatch):
        form = _bp_form(
            monkeypatch,
            filter_type="chebyshev",
            frequency="",
            bandwidth="500kHz",
            ripple="0.1",
            resonator_impedance="75ohm",
        )

        form.screen._validate_and_continue()

        assert [type(screen) for screen in form.pushed] == [OutputOptionsScreen]
        state = form.state
        assert (state.category, state.filter_type, state.topology) == (
            "bandpass",
            "chebyshev",
            "top",
        )
        assert state.frequency_hz == 14.175e6  # empty field falls back to the placeholder
        assert state.bandwidth_hz == 500e3
        assert (state.impedance, state.order, state.ripple_db) == (50.0, 3, 0.1)
        assert (state.resonator_impedance, state.resonator_inductance) == (75.0, None)

    @pytest.mark.parametrize(
        "values, severity, focus",
        [
            ({"bandwidth": "20MHz"}, "error", "#bandwidth"),
            ({"filter_type": "chebyshev", "resonators": "4"}, "warning", "#resonators"),
            (
                {"resonator_impedance": "75", "resonator_inductance": "1uH"},
                "error",
                "#resonator-inductance",
            ),
        ],
    )
    def test_form_errors_notify_and_focus_the_named_field(
        self, monkeypatch, values, severity, focus
    ):
        form = _bp_form(monkeypatch, **values)

        form.screen._validate_and_continue()

        assert form.pushed == []
        assert [note[0] for note in form.notes] == [severity]
        form.w[focus].focus.assert_called_once_with()
        assert form.state.category == ""

    def test_fbw_display_replaces_previous_style(self, monkeypatch):
        form = _bp_form(monkeypatch, frequency="10MHz", bandwidth="8MHz")
        display = form.w["#fbw-display"]

        form.screen._update_fbw_display()

        text, style = fractional_bandwidth_feedback("10MHz", "8MHz")
        display.update.assert_called_once_with(text)
        assert [c.args[0] for c in display.remove_class.call_args_list] == [
            "fbw-display",
            "fbw-warning",
            "fbw-danger",
        ]
        display.add_class.assert_called_once_with(style)

    def test_fbw_display_clears_for_unparseable_input(self, monkeypatch):
        form = _bp_form(monkeypatch, frequency="junk")

        form.screen._update_fbw_display()

        form.w["#fbw-display"].update.assert_called_once_with("")
        form.w["#fbw-display"].add_class.assert_not_called()

    def test_reset_restores_defaults_and_back_pops(self, monkeypatch):
        form = _bp_form(monkeypatch, resonator_inductance="1uH", bandwidth="1MHz")

        form.screen.on_button_pressed(Mock(button=Mock(id="reset-btn")))

        expected = {
            "#frequency": "",
            "#bandwidth": "",
            "#impedance": "50",
            "#resonators": "3",
            "#ripple": "0.5",
            "#resonator-impedance": "",
            "#resonator-inductance": "",
        }
        assert {selector: form.w[selector].value for selector in expected} == expected
        form.w["#fbw-display"].update.assert_called_once_with("")
        form.w["#frequency"].focus.assert_called_once_with()

        form.screen.on_button_pressed(Mock(button=Mock(id="next-btn")))
        assert [type(screen) for screen in form.pushed] == [OutputOptionsScreen]

        form.screen.action_back()
        form.app.pop_screen.assert_called_once_with()

    @pytest.mark.parametrize(
        "handler, ripple_visible, focused",
        [
            ("_on_frequency_submitted", False, "#bandwidth"),
            ("_on_bandwidth_submitted", False, "#impedance"),
            ("_on_impedance_submitted", False, "#resonators"),
            ("_on_resonators_submitted", True, "#ripple"),
            ("_on_resonators_submitted", False, "#next-btn"),
            ("_on_ripple_submitted", True, "#next-btn"),
            ("_on_resonator_impedance_submitted", False, "#resonator-inductance"),
            ("_on_resonator_inductance_submitted", False, "#next-btn"),
        ],
    )
    def test_submitting_a_field_advances_focus(self, monkeypatch, handler, ripple_visible, focused):
        form = _bp_form(monkeypatch)
        form.w["#ripple-section"].display = ripple_visible

        getattr(form.screen, handler)(Mock())

        form.w[focused].focus.assert_called_once_with()

    @pytest.mark.parametrize(
        "pressed, ripple_visible, label",
        [
            ("chebyshev", True, "Resonators (Chebyshev: odd only — 3, 5, 7, 9):"),
            ("bessel", False, "Resonators (2-9):"),
        ],
    )
    def test_response_type_toggles_ripple_and_resonator_hint(
        self, monkeypatch, pressed, ripple_visible, label
    ):
        form = _bp_form(monkeypatch)

        form.screen._on_filter_type_changed(Mock(pressed=Mock(id=pressed)))

        assert form.w["#ripple-section"].display is ripple_visible
        form.w["#resonators-label"].update.assert_called_once_with(label)
