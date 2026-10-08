"""Low-pass, high-pass, and band-pass design-form behavior without a running app.

Handlers are called directly on screens whose ``query_one`` returns ``Mock(spec=...)``
widgets. Widget-id wiring and real key handling are covered by the mounted journeys in
``test_wizard_design_screen_journeys.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from textual.widgets import Button, Input, RadioButton, RadioSet, Static

from filter_lib.bandpass.input_validation import fbw_impractical_warning, fbw_untested_warning
from filter_lib.design import band_from_edges
from filter_lib.design.option_applicability import LOSS_Q_DISABLED_MESSAGE
from filter_lib.shared.cli_aliases import (
    COMPONENT_COUNT_MESSAGE,
    RIPPLE_RANGE_MESSAGE,
    chebyshev_odd_count_message,
)
from filter_lib.wizard.bandpass_form import (
    BandpassFormError,
    BandpassFormValues,
    edge_bandwidth_feedback,
    fractional_bandwidth_feedback,
    parse_bandpass_form,
)
from filter_lib.wizard.design_field_validation import CUTOFF_LABELS
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
    FOCUS_FLOW = ("filter-type", "topology", "frequency", "next-btn")

    def __init__(self, widgets: dict) -> None:
        self._widgets = widgets

    def query_one(self, selector: str, widget_type=None):
        if selector not in self._widgets:
            raise LookupError(selector)
        return self._widgets[selector]


def _nav_widgets(focus: str = "") -> dict[str, Mock]:
    widgets = {
        "#filter-type": _radio_set("a", has_focus=focus == "filter-type"),
        "#topology": _radio_set("b", has_focus=focus == "topology"),
        "#frequency": _input(),
        "#next-btn": Mock(spec=Button),
    }
    for widget in widgets.values():
        widget.disabled = False
    return widgets


class TestRadioSetEnterNavigation:
    def test_enter_on_first_radio_set_focuses_the_next_and_consumes_the_key(self):
        widgets = _nav_widgets("filter-type")
        event = _key("enter")

        _NavScreen(widgets).on_key(event)

        widgets["#topology"].focus.assert_called_once_with()
        event.prevent_default.assert_called_once_with()
        event.stop.assert_called_once_with()

    def test_enter_on_last_radio_set_focuses_the_first_input(self):
        widgets = _nav_widgets("topology")

        _NavScreen(widgets).on_key(_key("enter"))

        widgets["#frequency"].focus.assert_called_once_with()

    def test_disabled_controls_are_skipped(self):
        widgets = _nav_widgets("topology")
        widgets["#frequency"].disabled = True

        _NavScreen(widgets).on_key(_key("enter"))

        widgets["#frequency"].focus.assert_not_called()
        widgets["#next-btn"].focus.assert_called_once_with()

    def test_submitting_an_input_in_the_flow_advances_and_others_are_ignored(self):
        widgets = _nav_widgets()
        screen = _NavScreen(widgets)

        screen.on_input_submitted(Mock(input=Mock(id="frequency")))
        screen.on_input_submitted(Mock(input=Mock(id="not-in-flow")))

        widgets["#next-btn"].focus.assert_called_once_with()

    @pytest.mark.parametrize("key, focused", [("tab", True), ("enter", False)])
    def test_other_keys_or_unfocused_radio_sets_are_left_alone(self, key, focused):
        widgets = _nav_widgets("filter-type" if focused else "")
        event = _key(key)

        _NavScreen(widgets).on_key(event)

        widgets["#topology"].focus.assert_not_called()
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
        "#frequency-label": Mock(spec=Static),
        "#next-btn": Mock(spec=Button),
    }
    return _mount(monkeypatch, screen_cls(), widgets)


LP_HP_REJECTIONS = [
    ({"frequency": "notafreq"}, "error", "Invalid cutoff frequency", "#frequency"),
    ({"impedance": "abc"}, "error", "Invalid impedance", "#impedance"),
    ({"impedance": "0"}, "error", "Impedance must be positive", "#impedance"),
    ({"order": "1"}, "error", COMPONENT_COUNT_MESSAGE, "#order"),
    ({"order": "10"}, "error", COMPONENT_COUNT_MESSAGE, "#order"),
    ({"order": "xyz"}, "error", COMPONENT_COUNT_MESSAGE, "#order"),
    (
        {"filter_type": "chebyshev", "order": "4"},
        "warning",
        chebyshev_odd_count_message("components"),
        "#order",
    ),
    ({"filter_type": "chebyshev", "ripple": "0"}, "error", RIPPLE_RANGE_MESSAGE, "#ripple"),
    ({"filter_type": "chebyshev", "ripple": "-0.1"}, "error", RIPPLE_RANGE_MESSAGE, "#ripple"),
    ({"filter_type": "chebyshev", "ripple": "nope"}, "error", RIPPLE_RANGE_MESSAGE, "#ripple"),
    ({"filter_type": "chebyshev", "ripple": "nan"}, "error", RIPPLE_RANGE_MESSAGE, "#ripple"),
    ({"filter_type": "chebyshev", "ripple": "inf"}, "error", RIPPLE_RANGE_MESSAGE, "#ripple"),
    ({"filter_type": "chebyshev", "ripple": "3.1"}, "error", RIPPLE_RANGE_MESSAGE, "#ripple"),
    # Hostile text: every field is rejected with a message on that field, never raised.
    ({"frequency": "10XHz"}, "error", "Invalid cutoff frequency", "#frequency"),
    ({"frequency": "-5MHz"}, "error", "Cutoff frequency must be positive", "#frequency"),
    ({"frequency": "0"}, "error", "Cutoff frequency must be positive", "#frequency"),
    ({"frequency": "nan"}, "error", "Cutoff frequency must be positive", "#frequency"),
    ({"frequency": "inf"}, "error", "Cutoff frequency must be positive", "#frequency"),
    (
        {"frequency": "1e400"},
        "error",
        "Cutoff frequency must be positive and finite",
        "#frequency",
    ),
    (
        {"frequency": "1e-400"},
        "error",
        "Cutoff frequency must be positive and finite",
        "#frequency",
    ),
    ({"frequency": "1e999999999MHz"}, "error", "must be positive and finite", "#frequency"),
    (
        {"frequency": "9" * 5000},
        "error",
        "Cutoff frequency must be positive and finite",
        "#frequency",
    ),
    ({"impedance": "nan"}, "error", "Impedance must be positive", "#impedance"),
    ({"impedance": "-50"}, "error", "Impedance must be positive", "#impedance"),
    ({"impedance": "1e400"}, "error", "Impedance must be positive and finite", "#impedance"),
    ({"order": ""}, "error", COMPONENT_COUNT_MESSAGE, "#order"),
    ({"order": "3.5"}, "error", COMPONENT_COUNT_MESSAGE, "#order"),
    ({"order": "0"}, "error", COMPONENT_COUNT_MESSAGE, "#order"),
    ({"order": "1e1"}, "error", COMPONENT_COUNT_MESSAGE, "#order"),
    ({"order": "9" * 5000}, "error", COMPONENT_COUNT_MESSAGE, "#order"),
    ({"filter_type": "chebyshev", "ripple": ""}, "error", RIPPLE_RANGE_MESSAGE, "#ripple"),
    ({"filter_type": "chebyshev", "ripple": "3.0001"}, "error", RIPPLE_RANGE_MESSAGE, "#ripple"),
    ({"filter_type": "chebyshev", "ripple": "1e400"}, "error", RIPPLE_RANGE_MESSAGE, "#ripple"),
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

    @pytest.mark.parametrize("screen_cls", LP_HP_SCREENS)
    @pytest.mark.parametrize(
        "overrides, message, focus",
        [
            (
                {"frequency": "10XHz"},
                "Invalid cutoff frequency: 10XHz (use a number with an optional k, M, or G suffix, e.g. 14.2MHz)",
                "#frequency",
            ),
            (
                {"frequency": "-5MHz"},
                "Cutoff frequency must be positive: -5MHz",
                "#frequency",
            ),
            (
                {"impedance": "abc"},
                "Invalid impedance: abc (use a number of ohms with an optional k or M suffix, e.g. 50 or 1k)",
                "#impedance",
            ),
            ({"impedance": "0"}, "Impedance must be positive: 0", "#impedance"),
        ],
    )
    def test_parser_rejections_name_the_field_once(
        self, monkeypatch, screen_cls, overrides, message, focus
    ):
        form = _lp_hp_form(monkeypatch, screen_cls, **overrides)

        form.screen._validate_and_continue()

        assert form.notes == [("error", message)]
        form.w[focus].focus.assert_called_once_with()

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
            # Unusual but unambiguous text is parsed to the value it names.
            ({"frequency": "１０MHz"}, {"frequency_hz": 10e6}),
            ({"frequency": " 7.1 mhz "}, {"frequency_hz": 7.1e6}),
            ({"frequency": "   "}, {"frequency_hz": 10e6}),
            ({"impedance": "50k"}, {"impedance": 50000.0}),
            ({"impedance": " 75Ω "}, {"impedance": 75.0}),
            ({"order": " 5 "}, {"order": 5}),
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
        "submitted, ripple_visible, focused",
        # The web form's order: frequency, number of components, impedance.
        [
            ("ripple", True, "#frequency"),
            ("frequency", False, "#order"),
            ("order", False, "#impedance"),
            ("impedance", False, "#next-btn"),
        ],
    )
    def test_submitting_a_field_advances_focus(
        self, monkeypatch, screen_cls, submitted, ripple_visible, focused
    ):
        form = _lp_hp_form(monkeypatch, screen_cls)
        form.w["#ripple-section"].display = ripple_visible

        form.screen.on_input_submitted(Mock(input=Mock(id=submitted)))

        form.w[focused].focus.assert_called_once_with()

    @pytest.mark.parametrize("screen_cls", LP_HP_SCREENS)
    @pytest.mark.parametrize("ripple_visible, focused", [(True, "#ripple"), (False, "#frequency")])
    def test_enter_on_topology_reaches_ripple_only_for_chebyshev(
        self, monkeypatch, screen_cls, ripple_visible, focused
    ):
        form = _lp_hp_form(monkeypatch, screen_cls)
        form.w["#ripple-section"].display = ripple_visible
        form.w["#topology"].has_focus = True

        form.screen.on_key(_key("enter"))

        form.w[focused].focus.assert_called_once_with()

    @pytest.mark.parametrize("screen_cls", LP_HP_SCREENS)
    @pytest.mark.parametrize(
        "pressed, ripple_visible, label",
        [
            ("chebyshev", True, "Number of components (Chebyshev: odd only — 3, 5, 7, 9):"),
            ("butterworth", False, "Number of components (2-9):"),
            ("bessel", False, "Number of components (2-9):"),
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
        form.w["#frequency-label"].update.assert_called_once_with(CUTOFF_LABELS[ripple_visible])
        assert ("ripple-band edge" in CUTOFF_LABELS[ripple_visible]) is ripple_visible
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
            ({"impedance": "0"}, "Impedance must be positive", "impedance", "error"),
            (
                {"resonator_impedance": "75", "resonator_inductance": "1uH"},
                "Set either the resonator impedance or the resonator inductance, not both",
                "resonator-inductance",
                "error",
            ),
            (
                {"resonator_impedance": "abc"},
                "(?i)resonator impedance",
                "resonator-impedance",
                "error",
            ),
            (
                {"resonator_inductance": "not-an-inductor"},
                "(?i)resonator inductance",
                "resonator-inductance",
                "error",
            ),
            (
                {"resonators": "1"},
                "Number of resonators must be from 2 to 9",
                "resonators",
                "error",
            ),
            (
                {"resonators": "xxx"},
                "Number of resonators must be from 2 to 9",
                "resonators",
                "error",
            ),
            (
                {"filter_type": "chebyshev", "resonators": "4"},
                "Chebyshev needs an odd number of resonators",
                "resonators",
                "warning",
            ),
            (
                {"filter_type": "chebyshev", "ripple": "-0.1"},
                RIPPLE_RANGE_MESSAGE,
                "ripple",
                "error",
            ),
            (
                {"filter_type": "chebyshev", "ripple": "nan"},
                RIPPLE_RANGE_MESSAGE,
                "ripple",
                "error",
            ),
            (
                {"filter_type": "chebyshev", "ripple": "3.1"},
                RIPPLE_RANGE_MESSAGE,
                "ripple",
                "error",
            ),
            # Hostile text: each field is reported as a form error on that field.
            ({"frequency": ""}, "Invalid center frequency", "frequency", "error"),
            ({"frequency": "nan"}, "Center frequency must be positive", "frequency", "error"),
            ({"frequency": "-5MHz"}, "Center frequency must be positive", "frequency", "error"),
            (
                {"frequency": "1e400"},
                "Center frequency must be positive and finite",
                "frequency",
                "error",
            ),
            ({"bandwidth": "0"}, "Bandwidth must be positive", "bandwidth", "error"),
            ({"bandwidth": "inf"}, "Bandwidth must be positive", "bandwidth", "error"),
            ({"bandwidth": "10XHz"}, "Invalid bandwidth", "bandwidth", "error"),
            (
                {"frequency": "１０MHz", "bandwidth": "１０MHz"},
                "Bandwidth must be less than center frequency",
                "bandwidth",
                "error",
            ),
            ({"impedance": "nan"}, "Impedance must be positive", "impedance", "error"),
            ({"impedance": "1e400"}, "Impedance must be positive and finite", "impedance", "error"),
            (
                {"resonator_impedance": "0"},
                "(?i)resonator impedance",
                "resonator-impedance",
                "error",
            ),
            (
                {"resonator_inductance": "-1uH"},
                "(?i)resonator inductance",
                "resonator-inductance",
                "error",
            ),
            (
                {"resonator_inductance": "1e400H"},
                "(?i)resonator inductance",
                "resonator-inductance",
                "error",
            ),
            (
                {"resonators": ""},
                "Number of resonators must be from 2 to 9",
                "resonators",
                "error",
            ),
            (
                {"resonators": "3.5"},
                "Number of resonators must be from 2 to 9",
                "resonators",
                "error",
            ),
            (
                {"resonators": "10"},
                "Number of resonators must be from 2 to 9",
                "resonators",
                "error",
            ),
            # The range comes before the Chebyshev odd-count rule, as in the CLI and web.
            (
                {"filter_type": "chebyshev", "resonators": "10"},
                "Number of resonators must be from 2 to 9",
                "resonators",
                "error",
            ),
            (
                {"resonators": "9" * 5000},
                "Number of resonators must be from 2 to 9",
                "resonators",
                "error",
            ),
            ({"filter_type": "chebyshev", "ripple": ""}, RIPPLE_RANGE_MESSAGE, "ripple", "error"),
            ({"filter_type": "chebyshev", "ripple": "0"}, RIPPLE_RANGE_MESSAGE, "ripple", "error"),
            (
                {"filter_type": "chebyshev", "ripple": "3.0001"},
                RIPPLE_RANGE_MESSAGE,
                "ripple",
                "error",
            ),
        ],
    )
    def test_invalid_values_name_the_field_to_focus(self, overrides, message, field_id, severity):
        with pytest.raises(BandpassFormError, match=message) as caught:
            parse_bandpass_form(_bp_values(**overrides))

        assert caught.value.field_id == field_id
        assert caught.value.severity == severity

    @pytest.mark.parametrize(
        "overrides, message",
        [
            (
                {"frequency": "10XHz"},
                "Invalid center frequency: 10XHz (use a number with an optional k, M, or G suffix, e.g. 14.2MHz)",
            ),
            (
                {"bandwidth": "10XHz"},
                "Invalid bandwidth: 10XHz (use a number with an optional k, M, or G suffix, e.g. 14.2MHz)",
            ),
            (
                {"impedance": "abc"},
                "Invalid impedance: abc (use a number of ohms with an optional k or M suffix, e.g. 50 or 1k)",
            ),
            (
                {"resonator_impedance": "abc"},
                "Invalid resonator impedance: abc (use a number of ohms with an optional k or M suffix, e.g. 50 or 1k)",
            ),
            (
                {"resonator_inductance": "not-an-inductor"},
                "Invalid resonator inductance: not-an-inductor (use a number with H, mH, uH, or nH, e.g. 1.2uH)",
            ),
            (
                {"frequency": "-5MHz"},
                "Center frequency must be positive: -5MHz",
            ),
        ],
    )
    def test_parser_rejections_name_the_field_once(self, overrides, message):
        with pytest.raises(BandpassFormError) as caught:
            parse_bandpass_form(_bp_values(**overrides))

        assert str(caught.value) == message


class TestParseBandEdgesAndResonatorQ:
    """The web's band-edge entry (D4) and resonator Q on the design form (D5)."""

    def test_edges_give_the_cli_center_and_width_and_are_kept(self):
        design = parse_bandpass_form(
            _bp_values(band_spec="edges", f_low="14MHz", f_high="14.35MHz")
        )

        assert (design.frequency_hz, design.bandwidth_hz) == band_from_edges(14e6, 14.35e6)
        assert (design.requested_f_low_hz, design.requested_f_high_hz) == (14e6, 14.35e6)

    def test_center_entry_ignores_the_hidden_edge_fields(self):
        design = parse_bandpass_form(_bp_values(f_low="junk", f_high="junk"))

        assert (design.requested_f_low_hz, design.requested_f_high_hz) == (None, None)

    @pytest.mark.parametrize(
        "overrides, message, field_id",
        [
            ({"f_low": "junk", "f_high": "14MHz"}, "Invalid lower cutoff frequency", "f-low"),
            (
                {"f_low": "14MHz", "f_high": "-1"},
                "Upper cutoff frequency must be positive",
                "f-high",
            ),
            (
                {"f_low": "15MHz", "f_high": "14MHz"},
                "Lower cutoff frequency must be below the upper cutoff frequency",
                "f-high",
            ),
            (
                {"f_low": "1MHz", "f_high": "10MHz"},
                "Bandwidth must be less than center frequency",
                "f-high",
            ),
        ],
    )
    def test_invalid_edges_name_their_field(self, overrides, message, field_id):
        with pytest.raises(BandpassFormError, match=message) as caught:
            parse_bandpass_form(_bp_values(band_spec="edges", **overrides))

        assert caught.value.field_id == field_id

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"qu": "200"}, (200.0, None, None)),
            ({"ql": "150", "qc": "900"}, (None, 150.0, 900.0)),
            ({"qc": "1e9"}, (None, None, 1e9)),
        ],
    )
    def test_resonator_q_values(self, overrides, expected):
        design = parse_bandpass_form(_bp_values(**overrides))

        assert (design.qu, design.ql, design.qc) == expected

    @pytest.mark.parametrize(
        "overrides, message, field_id",
        [
            ({"qu": "abc"}, "^Qu must be a number$", "qu"),
            ({"qc": "x"}, "^QC must be a number$", "qc"),
            # The shared calculator's mutual-exclusion message, on the field that conflicts.
            ({"qu": "200", "ql": "150"}, "^Give either Qu or QL/QC, not both$", "ql"),
            ({"qu": "200", "qc": "900"}, "^Give either Qu or QL/QC, not both$", "qc"),
            ({"qu": "0"}, "^Qu must be between 0.01 and 1e9$", "qu"),
            ({"ql": "nan"}, "^QL must be between 0.01 and 1e9$", "ql"),
            ({"qc": "2e9"}, "^QC must be between 0.01 and 1e9$", "qc"),
        ],
    )
    def test_invalid_resonator_q_names_its_field(self, overrides, message, field_id):
        with pytest.raises(BandpassFormError, match=message) as caught:
            parse_bandpass_form(_bp_values(**overrides))

        assert caught.value.field_id == field_id

    @pytest.mark.parametrize(
        "f_low, f_high, expected",
        [
            ("14MHz", "14.35MHz", "within the 10%"),
            ("14MHz", "13MHz", "Lower cutoff frequency must be below the upper cutoff frequency"),
            ("1MHz", "10MHz", "Bandwidth must be less than center frequency"),
            ("junk", "14MHz", None),
        ],
    )
    def test_edge_feedback(self, f_low, f_high, expected):
        feedback = edge_bandwidth_feedback(f_low, f_high)

        if expected is None:
            assert feedback is None
        else:
            assert expected in feedback[0]


class TestFractionalBandwidthFeedback:
    @pytest.mark.parametrize(
        "frequency, bandwidth, percent, style, wording",
        [
            (
                "14.175MHz",
                "350kHz",
                "2.5%",
                "fbw-display",
                "is within the 10% this design method was tested up to",
            ),
            (
                "10MHz",
                "1MHz",
                "10.0%",
                "fbw-display",
                "is within the 10% this design method was tested up to",
            ),
            ("10MHz", "2MHz", "20.0%", "fbw-warning", fbw_untested_warning(0.2)),
            ("10MHz", "4MHz", "40.0%", "fbw-warning", fbw_untested_warning(0.4)),
            ("10MHz", "4.01MHz", "40.1%", "fbw-danger", fbw_impractical_warning(0.401)),
        ],
    )
    def test_threshold_bands_defer_final_validation(
        self, frequency, bandwidth, percent, style, wording
    ):
        text, class_name = fractional_bandwidth_feedback(frequency, bandwidth)

        assert class_name == style
        assert text.startswith(f"Fractional bandwidth {percent} ")
        assert wording in text
        # The wording of the result's design warnings, not the retired method names.
        for retired in ("transmission-line", "studied", "edge-calibration", "validated"):
            assert retired not in text.lower()
        if style == "fbw-danger":
            assert "high-pass filter followed by a low-pass filter" in text

    @pytest.mark.parametrize(
        "frequency, bandwidth", [("junk", "1MHz"), ("10MHz", ""), ("0MHz", "1MHz")]
    )
    def test_partial_or_zero_input_gives_no_feedback(self, frequency, bandwidth):
        assert fractional_bandwidth_feedback(frequency, bandwidth) is None

    @pytest.mark.parametrize(
        "frequency, bandwidth",
        [
            # A subnormal center frequency: bandwidth / center overflows to infinity.
            ("1e-330GHz", "1MHz"),
            ("1e-330GHz", "1e-330GHz"),
            ("10MHz", "10MHz"),
            ("10MHz", "11MHz"),
        ],
    )
    def test_bandwidth_not_below_center_shows_the_rejection_instead_of_a_percentage(
        self, frequency, bandwidth
    ):
        feedback = fractional_bandwidth_feedback(frequency, bandwidth)

        assert feedback == ("Bandwidth must be less than center frequency", "fbw-danger")
        with pytest.raises(BandpassFormError, match=feedback[0]):
            parse_bandpass_form(_bp_values(frequency=frequency, bandwidth=bandwidth))

    @pytest.mark.parametrize(
        "frequency, bandwidth, percent",
        [("1e-330GHz", "1e-331GHz", "9.9%"), ("1e290GHz", "1e-300Hz", "0.0%")],
    )
    def test_extreme_scales_below_center_still_show_a_finite_percentage(
        self, frequency, bandwidth, percent
    ):
        text, _style = fractional_bandwidth_feedback(frequency, bandwidth)

        assert text.startswith(f"Fractional bandwidth {percent} ")


def _bp_form(
    monkeypatch, filter_type: str = "butterworth", band_spec: str = "center", **inputs: str
) -> SimpleNamespace:
    """Band-pass screen stub; ``inputs`` use field names with ``_`` for ``-`` in widget ids."""
    values = {
        "frequency": "14.175MHz",
        "bandwidth": "350kHz",
        "impedance": "50",
        "resonators": "3",
        "ripple": "0.5",
        "resonator_impedance": "",
        "resonator_inductance": "",
        "f_low": "",
        "f_high": "",
        "qu": "",
        "ql": "",
        "qc": "",
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
            "#band-spec": _radio_set(band_spec),
            "#center": Mock(spec=RadioButton),
            "#center-fields": Mock(display=band_spec == "center"),
            "#edge-fields": Mock(display=band_spec == "edges"),
            "#ripple-section": Mock(display=filter_type == "chebyshev"),
            "#resonators-label": Mock(spec=Static),
            "#fbw-display": Mock(spec=Static),
            "#reason-loss_q": Mock(spec=Static, display=False),
            "#next-btn": Mock(spec=Button),
        }
    )
    for name in ("qu", "ql", "qc"):
        widgets[f"#{name}"].disabled = False
    return _mount(monkeypatch, BandpassScreen(), widgets)


class TestBandpassScreen:
    def test_valid_design_is_stored_and_opens_output_options(self, monkeypatch):
        form = _bp_form(
            monkeypatch,
            filter_type="chebyshev",
            frequency="",
            bandwidth="500kHz",
            impedance="75ohm",
            resonators="5",
            ripple="0.1",
            resonator_impedance="100ohm",
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
        # Port impedance and resonator count differ from the FilterState defaults (50, 3),
        # so a dropped assignment cannot pass by leaving the default in place.
        assert (state.impedance, state.order, state.ripple_db) == (75.0, 5, 0.1)
        assert (state.resonator_impedance, state.resonator_inductance) == (100.0, None)

    def test_accepting_a_design_invalidates_the_previous_result(self, monkeypatch):
        form = _bp_form(monkeypatch)
        revision = form.state.begin_calculation()
        form.state.publish_success(revision, "old table", {"old": True})

        form.screen._validate_and_continue()

        assert form.pushed
        assert form.state.calculation_revision == revision + 1
        assert (form.state.calculation_status, form.state.result) == ("idle", {})

    def test_clearing_the_tank_inductance_replaces_the_stale_value(self, monkeypatch):
        form = _bp_form(monkeypatch)
        form.state.resonator_inductance = 1e-6  # from an earlier pass through this form

        form.screen._validate_and_continue()

        assert (form.state.resonator_impedance, form.state.resonator_inductance) == (None, None)

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

    def test_fbw_display_for_a_subnormal_center_shows_the_rejection(self, monkeypatch):
        form = _bp_form(monkeypatch, frequency="1e-330GHz", bandwidth="1MHz")
        display = form.w["#fbw-display"]

        form.screen._update_fbw_display()

        display.update.assert_called_once_with("Bandwidth must be less than center frequency")
        display.add_class.assert_called_once_with("fbw-danger")

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
        "submitted, band_spec, focused",
        # The web form's order: band, number of resonators, impedance, resonator size, Q.
        [
            ("ripple", "center", "#band-spec"),
            ("frequency", "center", "#bandwidth"),
            ("bandwidth", "center", "#resonators"),
            ("f-low", "edges", "#f-high"),
            ("f-high", "edges", "#resonators"),
            ("resonators", "center", "#impedance"),
            ("impedance", "center", "#resonator-impedance"),
            ("resonator-impedance", "center", "#resonator-inductance"),
            ("resonator-inductance", "center", "#qu"),
            ("qu", "center", "#ql"),
            ("ql", "center", "#qc"),
            ("qc", "center", "#next-btn"),
        ],
    )
    def test_submitting_a_field_advances_focus(self, monkeypatch, submitted, band_spec, focused):
        form = _bp_form(monkeypatch, band_spec=band_spec)

        form.screen.on_input_submitted(Mock(input=Mock(id=submitted)))

        form.w[focused].focus.assert_called_once_with()

    @pytest.mark.parametrize("band_spec, focused", [("center", "#frequency"), ("edges", "#f-low")])
    def test_enter_on_the_band_choice_reaches_its_first_field(
        self, monkeypatch, band_spec, focused
    ):
        form = _bp_form(monkeypatch, band_spec=band_spec)
        form.w["#band-spec"].has_focus = True

        form.screen.on_key(_key("enter"))

        form.w[focused].focus.assert_called_once_with()

    def test_disabled_resonator_q_fields_are_skipped(self, monkeypatch):
        form = _bp_form(monkeypatch)
        form.app.filter_state.output_format = "csv"
        form.screen._refresh_resonator_q()

        form.screen.on_input_submitted(Mock(input=Mock(id="resonator-inductance")))

        form.w["#next-btn"].focus.assert_called_once_with()

    @pytest.mark.parametrize(
        "output_format, disabled",
        [("table", False), ("json", False), ("quiet", True), ("csv", True)],
    )
    def test_resonator_q_is_disabled_with_the_shared_reason_when_the_output_cannot_use_it(
        self, monkeypatch, output_format, disabled
    ):
        """D5/D7: the format chosen on Output options decides; going back shows why."""
        form = _bp_form(monkeypatch, qu="200")
        form.app.filter_state.output_format = output_format

        form.screen.on_screen_resume()

        for name in ("qu", "ql", "qc"):
            assert form.w[f"#{name}"].disabled is disabled
        reason = form.w["#reason-loss_q"]
        assert reason.display is disabled
        reason.update.assert_called_once_with(LOSS_Q_DISABLED_MESSAGE if disabled else "")
        # The value stays: a saved JSON file still uses it.
        assert form.w["#qu"].value == "200"

    @pytest.mark.parametrize("band_spec", ["center", "edges"])
    def test_band_choice_shows_its_fields(self, monkeypatch, band_spec):
        form = _bp_form(monkeypatch, f_low="14MHz", f_high="14.35MHz")
        form.w["#band-spec"].pressed_button = Mock(id=band_spec)

        form.screen._on_band_spec_changed(Mock(pressed=Mock(id=band_spec)))

        assert form.w["#center-fields"].display is (band_spec == "center")
        assert form.w["#edge-fields"].display is (band_spec == "edges")
        expected = (
            edge_bandwidth_feedback("14MHz", "14.35MHz")
            if band_spec == "edges"
            else fractional_bandwidth_feedback("14.175MHz", "350kHz")
        )
        form.w["#fbw-display"].update.assert_called_once_with(expected[0])

    def test_band_edges_are_stored_with_the_center_and_width_they_give(self, monkeypatch):
        form = _bp_form(monkeypatch, band_spec="edges", f_low="7MHz", f_high="")

        form.screen._validate_and_continue()

        assert [type(screen) for screen in form.pushed] == [OutputOptionsScreen]
        state = form.state
        center, width = band_from_edges(7e6, 14.35e6)  # blank upper edge = 14.35MHz
        assert (state.frequency_hz, state.bandwidth_hz) == (center, width)
        assert (state.requested_f_low_hz, state.requested_f_high_hz) == (7e6, 14.35e6)
        request = state.to_design_request(include_build=False)
        assert (request.requested_f_low_hz, request.requested_f_high_hz) == (7e6, 14.35e6)

    def test_center_entry_clears_edges_from_an_earlier_pass(self, monkeypatch):
        form = _bp_form(monkeypatch)
        form.state.requested_f_low_hz, form.state.requested_f_high_hz = 7e6, 8e6

        form.screen._validate_and_continue()

        assert (form.state.requested_f_low_hz, form.state.requested_f_high_hz) == (None, None)

    def test_resonator_q_is_stored_and_reaches_the_design_request(self, monkeypatch):
        form = _bp_form(monkeypatch, ql="150", qc="900")
        form.state.qu = 50.0  # stale value from an earlier pass

        form.screen._validate_and_continue()

        assert (form.state.qu, form.state.ql, form.state.qc) == (None, 150.0, 900.0)
        request = form.state.to_design_request(include_build=False)
        assert (request.qu, request.ql, request.qc) == (None, 150.0, 900.0)

    @pytest.mark.parametrize(
        "pressed, ripple_visible, label",
        [
            ("chebyshev", True, "Number of resonators (Chebyshev: odd only — 3, 5, 7, 9):"),
            ("bessel", False, "Number of resonators (2-9):"),
        ],
    )
    def test_response_type_toggles_ripple_and_resonator_hint(
        self, monkeypatch, pressed, ripple_visible, label
    ):
        form = _bp_form(monkeypatch)

        form.screen._on_filter_type_changed(Mock(pressed=Mock(id=pressed)))

        assert form.w["#ripple-section"].display is ripple_visible
        form.w["#resonators-label"].update.assert_called_once_with(label)


# ---------------------------------------------------------------------------
# Stale-result invalidation (shared by the three design screens)
# ---------------------------------------------------------------------------

DESIGN_SCREENS = [LowpassScreen, HighpassScreen, BandpassScreen]


class TestPreviousResultInvalidation:
    @pytest.mark.parametrize("screen_cls", DESIGN_SCREENS)
    def test_invalidating_before_mount_is_a_no_op(self, screen_cls):
        assert screen_cls()._invalidate_previous_result() is None

    @pytest.mark.parametrize("screen_cls", DESIGN_SCREENS)
    def test_invalidating_with_an_app_missing_filter_state_raises(self, monkeypatch, screen_cls):
        monkeypatch.setattr(screen_cls, "app", property(lambda _self: SimpleNamespace()))

        with pytest.raises(AttributeError):
            screen_cls()._invalidate_previous_result()

    @pytest.mark.parametrize(
        "screen_cls, handler",
        [
            (LowpassScreen, "_on_topology_changed"),
            (HighpassScreen, "_on_topology_changed"),
            (HighpassScreen, "_on_design_input_changed"),
            (BandpassScreen, "_on_coupling_changed"),
            (BandpassScreen, "_on_design_input_changed"),
        ],
    )
    def test_changing_a_design_choice_clears_the_previous_result(
        self, monkeypatch, screen_cls, handler
    ):
        app = Mock(filter_state=FilterState())
        monkeypatch.setattr(screen_cls, "app", property(lambda _self: app))
        state = app.filter_state
        revision = state.begin_calculation()
        state.publish_success(revision, "old table", {"old": True})

        getattr(screen_cls(), handler)(Mock())

        assert state.calculation_revision == revision + 1
        assert (state.calculation_status, state.result, state.output_text) == ("idle", {}, "")
        assert not state.is_exportable
