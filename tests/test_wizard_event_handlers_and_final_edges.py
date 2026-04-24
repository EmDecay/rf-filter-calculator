"""Final coverage-gap tests:

- Wizard Input.Submitted / RadioSet.Changed event handlers (LP/HP/BP screens).
- run_wizard() launches the Textual app under mocked conditions.
- Results screen CSV save branch.
- E-series tight-ratio fallthroughs.
- recommend_cores iteration where every candidate winding is None.
- Widget package import for __init__ coverage.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from textual.widgets import Button, Input, RadioSet

from filter_lib.shared.eseries import find_parallel_combo, match_component
from filter_lib.shared.toroid_selection import recommend_cores
from filter_lib.wizard import interactive
from filter_lib.wizard.screens.bandpass import BandpassScreen
from filter_lib.wizard.screens.highpass import HighpassScreen
from filter_lib.wizard.screens.lowpass import LowpassScreen
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.state import FilterState

# ---------------------------------------------------------------------------
# interactive.run_wizard + wizard.widgets coverage
# ---------------------------------------------------------------------------


class TestRunWizardEntryPoint:
    def test_run_wizard_constructs_and_runs_app(self):
        """run_wizard imports FilterWizardApp and calls .run()."""
        with patch("filter_lib.wizard.app.FilterWizardApp") as MockApp:
            interactive.run_wizard()
        MockApp.assert_called_once_with()
        MockApp.return_value.run.assert_called_once_with()


def test_wizard_widgets_package_imports():
    """filter_lib.wizard.widgets must be importable and expose __all__."""
    import filter_lib.wizard.widgets as widgets_pkg

    assert widgets_pkg.__all__ == []


# ---------------------------------------------------------------------------
# LP/HP screen Input.Submitted handlers (focus-advance chain)
# ---------------------------------------------------------------------------


def _lp_hp_widgets(ripple_visible: bool = False):
    freq = Mock(spec=Input)
    imp = Mock(spec=Input)
    order = Mock(spec=Input)
    ripple = Mock(spec=Input)
    btn = Mock(spec=Button)
    ripple_section = Mock()
    ripple_section.display = ripple_visible
    return {
        "#frequency": freq,
        "#impedance": imp,
        "#order": order,
        "#ripple": ripple,
        "#ripple-section": ripple_section,
        "#calculate-btn": btn,
    }


def _install_query_one(screen, widgets):
    def fake_query_one(selector, widget_type=None):
        return widgets[selector]

    screen.query_one = fake_query_one  # type: ignore[assignment]


class TestLowpassHighpassEventHandlers:
    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_frequency_submitted_focuses_impedance(self, cls):
        screen = cls()
        widgets = _lp_hp_widgets()
        _install_query_one(screen, widgets)
        screen._on_frequency_submitted(Mock())
        widgets["#impedance"].focus.assert_called_once()

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_impedance_submitted_focuses_order(self, cls):
        screen = cls()
        widgets = _lp_hp_widgets()
        _install_query_one(screen, widgets)
        screen._on_impedance_submitted(Mock())
        widgets["#order"].focus.assert_called_once()

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_order_submitted_focuses_ripple_when_chebyshev_visible(self, cls):
        screen = cls()
        widgets = _lp_hp_widgets(ripple_visible=True)
        _install_query_one(screen, widgets)
        screen._on_order_submitted(Mock())
        widgets["#ripple"].focus.assert_called_once()

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_order_submitted_focuses_button_when_ripple_hidden(self, cls):
        screen = cls()
        widgets = _lp_hp_widgets(ripple_visible=False)
        _install_query_one(screen, widgets)
        screen._on_order_submitted(Mock())
        widgets["#calculate-btn"].focus.assert_called_once()

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_ripple_submitted_focuses_button(self, cls):
        screen = cls()
        widgets = _lp_hp_widgets()
        _install_query_one(screen, widgets)
        screen._on_ripple_submitted(Mock())
        widgets["#calculate-btn"].focus.assert_called_once()

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_filter_type_changed_shows_ripple_for_chebyshev(self, cls):
        screen = cls()
        ripple_section = Mock()
        _install_query_one(screen, {"#ripple-section": ripple_section})
        event = Mock()
        event.pressed = Mock()
        event.pressed.id = "chebyshev"
        screen._on_filter_type_changed(event)
        assert ripple_section.display is True

    @pytest.mark.parametrize("cls", [LowpassScreen, HighpassScreen])
    def test_filter_type_changed_hides_ripple_for_non_chebyshev(self, cls):
        screen = cls()
        ripple_section = Mock()
        _install_query_one(screen, {"#ripple-section": ripple_section})
        event = Mock()
        event.pressed = Mock()
        event.pressed.id = "butterworth"
        screen._on_filter_type_changed(event)
        assert ripple_section.display is False


# ---------------------------------------------------------------------------
# Bandpass screen Input.Submitted handlers
# ---------------------------------------------------------------------------


def _bp_handler_widgets(ripple_visible: bool = False):
    freq = Mock(spec=Input)
    bw = Mock(spec=Input)
    imp = Mock(spec=Input)
    reson = Mock(spec=Input)
    ripple = Mock(spec=Input)
    btn = Mock(spec=Button)
    ripple_section = Mock()
    ripple_section.display = ripple_visible
    return {
        "#frequency": freq,
        "#bandwidth": bw,
        "#impedance": imp,
        "#resonators": reson,
        "#ripple": ripple,
        "#ripple-section": ripple_section,
        "#calculate-btn": btn,
    }


class TestBandpassEventHandlers:
    def test_frequency_submitted_focuses_bandwidth(self):
        screen = BandpassScreen()
        widgets = _bp_handler_widgets()
        _install_query_one(screen, widgets)
        screen._on_frequency_submitted(Mock())
        widgets["#bandwidth"].focus.assert_called_once()

    def test_bandwidth_submitted_focuses_impedance(self):
        screen = BandpassScreen()
        widgets = _bp_handler_widgets()
        _install_query_one(screen, widgets)
        screen._on_bandwidth_submitted(Mock())
        widgets["#impedance"].focus.assert_called_once()

    def test_impedance_submitted_focuses_resonators(self):
        screen = BandpassScreen()
        widgets = _bp_handler_widgets()
        _install_query_one(screen, widgets)
        screen._on_impedance_submitted(Mock())
        widgets["#resonators"].focus.assert_called_once()

    def test_resonators_submitted_focuses_ripple_when_visible(self):
        screen = BandpassScreen()
        widgets = _bp_handler_widgets(ripple_visible=True)
        _install_query_one(screen, widgets)
        screen._on_resonators_submitted(Mock())
        widgets["#ripple"].focus.assert_called_once()

    def test_resonators_submitted_focuses_button_when_ripple_hidden(self):
        screen = BandpassScreen()
        widgets = _bp_handler_widgets(ripple_visible=False)
        _install_query_one(screen, widgets)
        screen._on_resonators_submitted(Mock())
        widgets["#calculate-btn"].focus.assert_called_once()

    def test_ripple_submitted_focuses_button(self):
        screen = BandpassScreen()
        widgets = _bp_handler_widgets()
        _install_query_one(screen, widgets)
        screen._on_ripple_submitted(Mock())
        widgets["#calculate-btn"].focus.assert_called_once()

    def test_filter_type_changed_shows_ripple_for_chebyshev(self):
        screen = BandpassScreen()
        ripple_section = Mock()
        _install_query_one(screen, {"#ripple-section": ripple_section})
        event = Mock()
        event.pressed = Mock()
        event.pressed.id = "chebyshev"
        screen._on_filter_type_changed(event)
        assert ripple_section.display is True

    def test_filter_type_changed_hides_ripple_for_bessel(self):
        screen = BandpassScreen()
        ripple_section = Mock()
        _install_query_one(screen, {"#ripple-section": ripple_section})
        event = Mock()
        event.pressed = Mock()
        event.pressed.id = "bessel"
        screen._on_filter_type_changed(event)
        assert ripple_section.display is False


# ---------------------------------------------------------------------------
# ResultsScreen: CSV save branch (was previously only exercising txt + json)
# ---------------------------------------------------------------------------


class TestResultsScreenSaveCsv:
    def test_save_export_csv_writes_file(self, tmp_path, monkeypatch):
        screen = ResultsScreen()
        screen._result_text = "ignored"
        state = FilterState()
        state.category = "lowpass"
        state.eseries = "E24"
        state.result = {
            "filter_type": "butterworth",
            "freq_hz": 10e6,
            "impedance": 50.0,
            "order": 3,
            "capacitors": [1e-10, 1e-10],
            "inductors": [1e-6],
            "ripple": None,
            "topology": "pi",
        }
        app = Mock()
        app.filter_state = state
        type(screen).app = property(lambda _self: app)  # type: ignore[misc]

        export_format = Mock(spec=RadioSet)
        btn = Mock()
        btn.id = "export-csv"
        export_format.pressed_button = btn
        section = Mock()
        widgets = {"#export-format": export_format, "#export-section": section}

        screen.query_one = lambda selector, *_a, **_k: widgets[selector]  # type: ignore[assignment]
        screen.notify = Mock()  # type: ignore[assignment]
        monkeypatch.chdir(tmp_path)

        screen._save_export()

        csv_files = list(tmp_path.glob("lowpass-*.csv"))
        assert len(csv_files) == 1
        # The CSV should at minimum contain a header that references components
        content = csv_files[0].read_text()
        assert content  # non-empty


# ---------------------------------------------------------------------------
# E-series: ratio_limit < 1 forces the "no valid combo" branch
# ---------------------------------------------------------------------------


class TestESeriesTightRatioLimit:
    def test_find_parallel_combo_additive_returns_none_with_tight_limit(self):
        """ratio_limit=0.5 filters out every combination in additive mode."""
        result = find_parallel_combo(1e-9, "E24", mode="additive", ratio_limit=0.5)
        assert result is None

    def test_find_parallel_combo_harmonic_returns_none_with_tight_limit(self):
        result = find_parallel_combo(1e-6, "E24", mode="harmonic", ratio_limit=0.5)
        assert result is None

    def test_match_component_returns_none_parallel_when_combo_infeasible(self):
        """Exercises the `parallel_result is None` fallthrough in match_component."""
        match = match_component(47e-12, "E24", parallel_mode="additive", ratio_limit=0.5)
        assert match.parallel is None
        assert match.parallel_value is None
        assert match.parallel_error_pct is None
        assert match.single_value > 0


# ---------------------------------------------------------------------------
# recommend_cores: every candidate winding returns None
# ---------------------------------------------------------------------------


class TestRecommendCoresAllSkipped:
    def test_tiny_target_skips_every_core_returns_empty(self):
        """L so small that every core's solve_winding returns None.

        Covers the `if winding is None: continue` branch in recommend_cores.
        """
        recs = recommend_cores(1e-14, 100e6, top_n=3)
        # Either empty (line 61 hit N times) or tiny recommendations; both
        # exercise the continue branch.
        assert recs == []
