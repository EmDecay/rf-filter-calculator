"""Screen-level regression tests for wizard bugs found during review.

Covers:
- Output options "None" E-series must propagate to state (not silently become E24)
- Bandpass screen must offer Bessel as a filter-type option
- Highpass screen topology labels must match the rendered schematic shape
- HP/LP wizards must reject even-order Chebyshev designs
"""

from __future__ import annotations

import inspect
from unittest.mock import Mock

import pytest
from textual.widgets import RadioSet, SelectionList

from filter_lib.wizard.screens import bandpass as bandpass_screen_mod
from filter_lib.wizard.screens import highpass as highpass_screen_mod
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.state import FilterState

# ---------------------------------------------------------------------------
# Output options: "None" E-series must survive _show_results
# ---------------------------------------------------------------------------


def _make_output_options_screen_with_selections(
    eseries_id: str,
    format_id: str = "table",
    export_id: str = "no-export",
    options_selected: tuple[str, ...] = (),
) -> tuple[OutputOptionsScreen, FilterState]:
    """Build an OutputOptionsScreen with stubbed widget queries for _show_results."""
    screen = OutputOptionsScreen()
    state = FilterState()
    app = Mock()
    app.filter_state = state

    def _radio_set(selected_id: str) -> Mock:
        rs = Mock(spec=RadioSet)
        btn = Mock()
        btn.id = selected_id
        rs.pressed_button = btn
        return rs

    def _selection_list(selected: tuple[str, ...]) -> Mock:
        sl = Mock(spec=SelectionList)
        sl.selected = list(selected)
        return sl

    def fake_query_one(selector: str, widget_type=None):
        if selector == "#eseries":
            return _radio_set(eseries_id)
        if selector == "#format":
            return _radio_set(format_id)
        if selector == "#options-list":
            return _selection_list(options_selected)
        if selector == "#export":
            return _radio_set(export_id)
        raise AssertionError(f"unexpected selector {selector!r}")

    screen.query_one = fake_query_one  # type: ignore[assignment]
    # bypass Screen.app property which requires a mounted app
    type(screen).app = property(lambda _self: app)  # type: ignore[misc]
    return screen, state


def test_output_options_preserves_none_eseries():
    """Selecting 'None' must stay 'none' so downstream matching is disabled."""
    screen, state = _make_output_options_screen_with_selections("none")
    screen._show_results()
    assert state.eseries == "none"


@pytest.mark.parametrize("eseries_id", ["E12", "E24", "E96"])
def test_output_options_preserves_explicit_eseries(eseries_id):
    screen, state = _make_output_options_screen_with_selections(eseries_id)
    screen._show_results()
    assert state.eseries == eseries_id


# ---------------------------------------------------------------------------
# Bandpass wizard must offer a Bessel radio option
# ---------------------------------------------------------------------------


def test_bandpass_wizard_exposes_bessel_radio_button():
    """The bandpass screen compose source must include a Bessel filter-type option."""
    source = inspect.getsource(bandpass_screen_mod)
    assert 'id="bessel"' in source, "bandpass screen is missing the Bessel RadioButton"
    assert "Bessel" in source


# ---------------------------------------------------------------------------
# Highpass wizard topology labels must match the rendered schematic
# ---------------------------------------------------------------------------


def test_highpass_wizard_topology_labels_match_schematic():
    """T highpass is C-L-C (series-C-first); Pi highpass is L-C-L (shunt-L-first)."""
    source = inspect.getsource(highpass_screen_mod)
    # T topology for highpass = series C + shunt L + series C = C-L-C
    assert "T (C-L-C)" in source, "T label must say (C-L-C) for highpass"
    # Pi topology for highpass = shunt L + series C + shunt L = L-C-L
    assert "Pi (L-C-L)" in source, "Pi label must say (L-C-L) for highpass"
    # The previous (swapped) labels must not exist
    assert "T (L-C-L)" not in source
    assert "Pi (C-L-C)" not in source


# ---------------------------------------------------------------------------
# HP/LP wizard must reject even-order Chebyshev at input time
# ---------------------------------------------------------------------------


def _make_lp_hp_screen_with_inputs(screen_cls, *, order: int, filter_type: str):
    """Build an LP or HP screen with stubbed Input / RadioSet queries."""
    screen = screen_cls()
    state = FilterState()
    app = Mock()
    app.filter_state = state
    notifications: list[tuple[str, str]] = []

    def _input(value: str) -> Mock:
        inp = Mock()
        inp.value = value
        inp.placeholder = ""
        inp.strip = value.strip
        inp.focus = Mock()
        return inp

    def _radio_set(selected_id: str) -> Mock:
        rs = Mock(spec=RadioSet)
        btn = Mock()
        btn.id = selected_id
        rs.pressed_button = btn
        return rs

    widget_map: dict[str, Mock] = {
        "#frequency": _input("10MHz"),
        "#impedance": _input("50"),
        "#order": _input(str(order)),
        "#ripple": _input("0.5"),
        "#filter-type": _radio_set(filter_type),
        "#topology": _radio_set("pi"),
    }

    def fake_query_one(selector: str, widget_type=None):
        return widget_map[selector]

    screen.query_one = fake_query_one  # type: ignore[assignment]
    type(screen).app = property(lambda _self: app)  # type: ignore[misc]
    screen.notify = lambda msg, severity="information": notifications.append((severity, msg))  # type: ignore[assignment]

    # Stub push_screen so we know whether validation blocked navigation
    pushed: list = []
    app.push_screen = pushed.append

    return screen, state, notifications, pushed


def test_highpass_wizard_rejects_even_chebyshev():
    from filter_lib.wizard.screens.highpass import HighpassScreen

    screen, state, notifications, pushed = _make_lp_hp_screen_with_inputs(
        HighpassScreen, order=4, filter_type="chebyshev"
    )
    screen._calculate()

    assert pushed == [], "navigation should be blocked for even Chebyshev"
    assert any("odd order" in msg for _sev, msg in notifications)


def test_lowpass_wizard_rejects_even_chebyshev():
    from filter_lib.wizard.screens.lowpass import LowpassScreen

    screen, state, notifications, pushed = _make_lp_hp_screen_with_inputs(
        LowpassScreen, order=4, filter_type="chebyshev"
    )
    screen._calculate()

    assert pushed == [], "navigation should be blocked for even Chebyshev"
    assert any("odd order" in msg for _sev, msg in notifications)


def test_highpass_wizard_allows_odd_chebyshev():
    from filter_lib.wizard.screens.highpass import HighpassScreen

    screen, state, notifications, pushed = _make_lp_hp_screen_with_inputs(
        HighpassScreen, order=5, filter_type="chebyshev"
    )
    screen._calculate()

    assert pushed, "odd Chebyshev should advance past validation"


# ---------------------------------------------------------------------------
# Bandpass wizard must block shunt-C coupling while it is disabled
# ---------------------------------------------------------------------------


def _make_bandpass_screen_with_coupling(coupling: str):
    """Build a BandpassScreen with stubbed Input / RadioSet queries."""
    from filter_lib.wizard.screens.bandpass import BandpassScreen

    screen = BandpassScreen()
    state = FilterState()
    app = Mock()
    app.filter_state = state
    notifications: list[tuple[str, str]] = []

    def _input(value: str) -> Mock:
        inp = Mock()
        inp.value = value
        inp.placeholder = ""
        inp.focus = Mock()
        return inp

    def _radio_set(selected_id: str) -> Mock:
        rs = Mock(spec=RadioSet)
        btn = Mock()
        btn.id = selected_id
        rs.pressed_button = btn
        rs.focus = Mock()
        return rs

    widget_map: dict[str, Mock] = {
        "#frequency": _input("14.175MHz"),
        "#bandwidth": _input("350kHz"),
        "#impedance": _input("50"),
        "#resonators": _input("3"),
        "#ripple": _input("0.5"),
        "#filter-type": _radio_set("butterworth"),
        "#coupling": _radio_set(coupling),
    }

    def fake_query_one(selector: str, widget_type=None):
        return widget_map[selector]

    screen.query_one = fake_query_one  # type: ignore[assignment]
    type(screen).app = property(lambda _self: app)  # type: ignore[misc]
    screen.notify = lambda msg, severity="information": notifications.append((severity, msg))  # type: ignore[assignment]

    pushed: list = []
    app.push_screen = pushed.append

    return screen, state, notifications, pushed, widget_map


def test_bandpass_wizard_blocks_shunt_coupling_while_disabled():
    screen, state, notifications, pushed, widgets = _make_bandpass_screen_with_coupling("shunt")
    screen._calculate()

    assert pushed == [], "navigation should be blocked while shunt-C is disabled"
    assert any(sev == "error" and "temporarily disabled" in msg for sev, msg in notifications), (
        notifications
    )
    widgets["#coupling"].focus.assert_called_once()
    assert state.category == "", "state must not be mutated when the gate blocks"


def test_bandpass_wizard_allows_top_coupling():
    screen, state, notifications, pushed, _widgets = _make_bandpass_screen_with_coupling("top")
    screen._calculate()

    assert pushed, "Top-C should advance past validation"
    assert state.topology == "top"
