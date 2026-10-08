"""Output Options screen: live applicability, state mapping, build fields, keyboard flow.

Handlers are called directly with ``Mock(spec=...)`` widgets. Mounted behavior (widget
ids, real disabling, focus) lives in ``test_wizard_output_option_journeys.py`` and
``test_wizard_build_analysis_pilot.py``.
"""

from __future__ import annotations

from itertools import product
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from textual.widgets import Button, Checkbox, Input, RadioButton, RadioSet, Static

from filter_lib.design.option_applicability import (
    ALLOW_SUB_PF,
    BUILD,
    ESERIES,
    ESERIES_VALUES_ONLY_MESSAGE,
    LOSS_Q,
    LOSS_Q_DISABLED_MESSAGE,
    TOROID_DETAIL,
    OutputChoices,
    inapplicable_options,
)
from filter_lib.design.render_options import (
    BUILD_NEEDS_ESERIES_MESSAGE,
    BUILD_NEEDS_TABLE_OR_JSON_MESSAGE,
    SUB_PF_NEEDS_ESERIES_MESSAGE,
)
from filter_lib.shared.build_types import (
    RESONATOR_AND_COMPONENT_Q_MESSAGE,
    SEED_NEEDS_SAMPLES_MESSAGE,
    BuildConfig,
)
from filter_lib.wizard.build_options import (
    BUILD_INPUT_FLOW,
    BuildOptionError,
    BuildOptionValues,
    build_field_values,
    parse_build_config,
)
from filter_lib.wizard.screens.output_options import (
    OPTION_WIDGETS,
    OutputOptionsScreen,
    reason_id,
)
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.state import FilterState

DEFAULT_BUILD_INPUTS = {
    "#build-capacitor-tolerance": "5",
    "#build-inductor-tolerance": "10",
    "#build-inductor-q": "",
    "#build-capacitor-q": "",
    "#build-reference-frequency": "",
    "#build-source-resistance": "",
    "#build-load-resistance": "",
    "#build-sample-count": "0",
    "#build-seed": "0",
    "#build-grid-points": "601",
}


def _radio_set(selected_id: str, focused: bool) -> Mock:
    radio_set = Mock(spec=RadioSet)
    radio_set.pressed_button = Mock(id=selected_id) if selected_id else None
    radio_set.has_focus = focused
    radio_set.disabled = False
    return radio_set


def _checkbox(widget_id: str, value: bool, focus: str) -> Mock:
    return Mock(
        spec=Checkbox, id=widget_id, value=value, has_focus=focus == widget_id, disabled=False
    )


def _screen(
    monkeypatch,
    *,
    focus: str = "",
    eseries: str = "E24",
    output_format: str = "table",
    toroid_detail: str = "toroid-best",
    export: str = "no-export",
    plot: bool = False,
    raw: bool = False,
    build_enabled: bool = False,
    use_toroids: bool = True,
    allow_sub_pf: bool = False,
    build_inputs: dict[str, str] | None = None,
    state: FilterState | None = None,
) -> SimpleNamespace:
    screen = OutputOptionsScreen()
    app = Mock(filter_state=state or FilterState(category="lowpass"))
    pushed: list = []
    app.push_screen = pushed.append
    monkeypatch.setattr(OutputOptionsScreen, "app", property(lambda _self: app))

    widgets = {
        "#format": _radio_set(output_format, focus == "format"),
        "#eseries": _radio_set(eseries, focus == "eseries"),
        "#toroid-detail": _radio_set(toroid_detail, focus == "toroid-detail"),
        "#export": _radio_set(export, focus == "export"),
        "#allow-sub-pf": _checkbox("allow-sub-pf", allow_sub_pf, focus),
        "#plot": _checkbox("plot", plot, focus),
        "#raw": _checkbox("raw", raw, focus),
        "#build-analysis-enabled": _checkbox("build-analysis-enabled", build_enabled, focus),
        "#build-use-toroids": _checkbox("build-use-toroids", use_toroids, focus),
        "#build-analysis-options": Mock(display=build_enabled, disabled=False),
        "#results-btn": Mock(spec=Button, disabled=False),
    }
    for button_id in ("#toroid-full", "#toroid-compact", "#export-json", "#export-csv"):
        widgets[button_id] = Mock(spec=RadioButton, disabled=False)
    for option in (*OPTION_WIDGETS, LOSS_Q):
        widgets[reason_id(option)] = Mock(spec=Static, display=False)
    for selector, value in {**DEFAULT_BUILD_INPUTS, **(build_inputs or {})}.items():
        field = Mock(spec=Input, disabled=False, has_focus=focus == selector[1:])
        field.value = value
        widgets[selector] = field

    def query_one(selector, *_args):
        if selector not in widgets:
            raise LookupError(selector)
        return widgets[selector]

    screen.query_one = query_one  # type: ignore[assignment]
    screen.notify = Mock()  # type: ignore[assignment]
    return SimpleNamespace(screen=screen, app=app, state=app.filter_state, pushed=pushed, w=widgets)


def _rejected_with(form: SimpleNamespace, message: str, focus: str) -> None:
    assert form.pushed == []
    form.screen.notify.assert_called_once()
    assert message in form.screen.notify.call_args.args[0]
    assert form.screen.notify.call_args.kwargs == {"severity": "error"}
    form.w[focus].focus.assert_called_once_with()


def _shown_reason(form: SimpleNamespace, selector: str) -> str | None:
    static = form.w[selector]
    return static.update.call_args.args[0] if static.display else None


class TestEnterNavigation:
    """Enter walks the controls in the web form's order (D15), skipping unavailable ones."""

    @pytest.mark.parametrize(
        "focus, next_focus",
        [
            ("format", "#eseries"),
            ("eseries", "#allow-sub-pf"),
            ("allow-sub-pf", "#toroid-detail"),
            ("toroid-detail", "#plot"),
            ("plot", "#raw"),
            ("raw", "#export"),
            ("export", "#build-analysis-enabled"),
            # The build fields are hidden while the build is unticked.
            ("build-analysis-enabled", "#results-btn"),
            ("build-use-toroids", "#results-btn"),
        ],
    )
    def test_enter_advances_through_every_control(self, monkeypatch, focus, next_focus):
        form = _screen(monkeypatch, focus=focus)
        form.screen._refresh_options()
        event = Mock(key="enter")

        form.screen.on_key(event)

        form.w[next_focus].focus.assert_called_once_with()
        event.prevent_default.assert_called_once_with()
        event.stop.assert_called_once_with()

    @pytest.mark.parametrize(
        "output_format, focus, next_focus",
        [
            # Values only disables the standard values and the sub-pF box.
            ("quiet", "format", "#toroid-detail"),
            # JSON disables the text plot and raw units.
            ("json", "toroid-detail", "#export"),
        ],
    )
    def test_enter_skips_disabled_controls(self, monkeypatch, output_format, focus, next_focus):
        form = _screen(monkeypatch, output_format=output_format, focus=focus)
        form.screen._refresh_options()

        form.screen.on_key(Mock(key="enter"))

        form.w[next_focus].focus.assert_called_once_with()

    def test_enter_on_a_ticked_build_reaches_its_first_field(self, monkeypatch):
        form = _screen(monkeypatch, build_enabled=True, focus="build-analysis-enabled")
        form.screen._refresh_options()

        form.screen.on_key(Mock(key="enter"))

        form.w[f"#{BUILD_INPUT_FLOW[0]}"].focus.assert_called_once_with()

    def test_build_fields_advance_in_form_order_then_reach_the_toroid_box(self, monkeypatch):
        form = _screen(monkeypatch, build_enabled=True)
        form.screen._refresh_options()

        for current, following in zip(BUILD_INPUT_FLOW, BUILD_INPUT_FLOW[1:]):
            form.screen._on_build_input_submitted(Mock(input=Mock(id=current)))
            form.w[f"#{following}"].focus.assert_called_once_with()
        form.screen._on_build_input_submitted(Mock(input=Mock(id=BUILD_INPUT_FLOW[-1])))

        form.w["#build-use-toroids"].focus.assert_called_once_with()

    def test_other_keys_are_left_alone(self, monkeypatch):
        form = _screen(monkeypatch, focus="eseries")
        event = Mock(key="tab")

        form.screen.on_key(event)

        form.w["#allow-sub-pf"].focus.assert_not_called()
        event.prevent_default.assert_not_called()

    def test_enter_before_widgets_are_mounted_is_ignored(self):
        screen = OutputOptionsScreen()
        screen.query_one = Mock(side_effect=LookupError("not mounted"))  # type: ignore[assignment]
        event = Mock(key="enter")

        screen.on_key(event)

        event.prevent_default.assert_not_called()

    @pytest.mark.parametrize(
        "enabled, output_format, shown",
        [(True, "table", True), (False, "table", False), (True, "csv", False)],
    )
    def test_build_fields_show_only_while_the_build_applies(
        self, monkeypatch, enabled, output_format, shown
    ):
        form = _screen(monkeypatch, build_enabled=enabled, output_format=output_format)

        form.screen._on_choice_changed(
            Mock(checkbox=form.w["#build-analysis-enabled"], value=enabled)
        )

        assert form.w["#build-analysis-options"].display is shown
        assert form.w[f"#{BUILD_INPUT_FLOW[0]}"].focus.called is shown


FORMATS = ("table", "quiet", "json", "csv")


class TestLiveApplicability:
    """Controls are disabled, with the shared rule's reason, exactly when it says so (D7)."""

    @pytest.mark.parametrize(
        "output_format, eseries, raw, build, toroids",
        list(product(FORMATS, ("E24", "none"), (False, True), (False, True), ("best", "none"))),
    )
    def test_disabled_controls_and_reasons_follow_the_shared_rule(
        self, monkeypatch, output_format, eseries, raw, build, toroids
    ):
        form = _screen(
            monkeypatch,
            output_format=output_format,
            eseries=eseries,
            raw=raw,
            build_enabled=build,
            toroid_detail=f"toroid-{toroids}",
        )

        form.screen._refresh_options()

        reasons = inapplicable_options(
            OutputChoices(
                output_format=output_format,
                eseries=None if eseries == "none" else eseries,
                raw=raw,
                build=build,
                include_toroids=toroids != "none",
            )
        )
        for option, selectors in OPTION_WIDGETS.items():
            for selector in selectors:
                assert form.w[selector].disabled is (option in reasons), (option, selector)
            assert _shown_reason(form, reason_id(option)) == reasons.get(option)
        # Resonator Q is not entered, so its reason never shows on this screen.
        assert _shown_reason(form, reason_id(LOSS_Q)) is None
        assert form.w["#build-analysis-options"].display is (build and BUILD not in reasons)

    def test_values_only_no_longer_needs_the_eseries_changed_first(self, monkeypatch):
        """C-3: Values only with the default E24 shows results; the series is disabled."""
        form = _screen(monkeypatch, output_format="quiet")
        form.screen._refresh_options()

        form.screen._show_results()

        assert [type(screen) for screen in form.pushed] == [ResultsScreen]
        form.screen.notify.assert_not_called()
        assert form.w["#eseries"].disabled is True
        assert _shown_reason(form, reason_id(ESERIES)) == ESERIES_VALUES_ONLY_MESSAGE
        state = form.state
        assert (state.output_format, state.eseries) == ("quiet", "E24")
        assert ESERIES not in state.applied_options()

    def test_toroid_detail_disables_only_its_table_choices(self, monkeypatch):
        form = _screen(monkeypatch, output_format="json", toroid_detail="toroid-full")

        form.screen._refresh_options()

        assert form.w["#toroid-full"].disabled is True
        assert form.w["#toroid-compact"].disabled is True
        assert form.w["#toroid-detail"].disabled is False
        assert form.state.toroid_detail == "full"
        assert TOROID_DETAIL not in form.state.applied_options()

    @pytest.mark.parametrize(
        "output_format, shown", [("table", None), ("json", None), ("quiet", True), ("csv", True)]
    )
    def test_resonator_q_from_the_bandpass_screen_says_when_it_is_left_out(
        self, monkeypatch, output_format, shown
    ):
        state = FilterState(category="bandpass", qu=200.0)
        form = _screen(monkeypatch, output_format=output_format, state=state)

        form.screen._refresh_options()

        expected = LOSS_Q_DISABLED_MESSAGE if shown else None
        assert _shown_reason(form, reason_id(LOSS_Q)) == expected

    @pytest.mark.parametrize("output_format", ["table", "json", "csv"])
    def test_response_data_file_stays_available_with_resonator_q(self, monkeypatch, output_format):
        """Like the web's response downloads, the file leaves resonator Q out."""
        state = FilterState(category="bandpass", ql=150.0)
        form = _screen(monkeypatch, output_format=output_format, state=state, export="export-json")

        form.screen._refresh_options()
        form.screen._show_results()

        for selector in ("#export-json", "#export-csv"):
            assert form.w[selector].disabled is False
        assert form.state.export_format == "json"
        assert LOSS_Q not in form.state.document_options("response-json")

    def test_choices_reach_state_live_for_the_bandpass_screen(self, monkeypatch):
        form = _screen(monkeypatch, output_format="csv")

        form.screen._on_choice_changed(Mock(spec=["pressed"]))

        assert form.state.output_format == "csv"


class TestButtons:
    def test_show_results_opens_results_and_back_pops(self, monkeypatch):
        form = _screen(monkeypatch)

        form.screen.on_button_pressed(Mock(button=Mock(id="unknown")))
        assert form.pushed == []
        form.app.pop_screen.assert_not_called()

        form.screen.on_button_pressed(Mock(button=Mock(id="results-btn")))
        assert [type(screen) for screen in form.pushed] == [ResultsScreen]

        form.screen.on_button_pressed(Mock(button=Mock(id="back-btn")))
        form.screen.action_back()
        assert form.app.pop_screen.call_count == 2


class TestShowResultsStateMapping:
    @pytest.mark.parametrize(
        "eseries_id, expected", [("none", "none"), ("E12", "E12"), ("E96", "E96"), ("", "E24")]
    )
    def test_eseries_choice_is_preserved_and_none_disables_matching(
        self, monkeypatch, eseries_id, expected
    ):
        form = _screen(monkeypatch, eseries=eseries_id)

        form.screen._show_results()

        assert form.pushed
        assert form.state.eseries == expected

    @pytest.mark.parametrize(
        "choice, expected",
        [
            ("toroid-best", "best"),
            ("toroid-full", "full"),
            ("toroid-compact", "compact"),
            ("toroid-none", "none"),
            ("", "best"),
        ],
    )
    def test_toroid_detail_choice(self, monkeypatch, choice, expected):
        form = _screen(monkeypatch, toroid_detail=choice)

        form.screen._show_results()

        assert form.state.toroid_detail == expected
        assert form.state.include_toroids is (expected != "none")

    @pytest.mark.parametrize(
        "export_id, expected", [("export-json", "json"), ("export-csv", "csv"), ("no-export", None)]
    )
    def test_response_sidecar_choice(self, monkeypatch, export_id, expected):
        form = _screen(monkeypatch, export=export_id)

        form.screen._show_results()

        assert form.state.export_format == expected

    @pytest.mark.parametrize(
        "output_format, raw, plot, eseries",
        [
            ("table", True, False, "none"),
            ("table", True, True, "E24"),
            ("quiet", False, False, "none"),
            ("json", False, False, "E96"),
            ("csv", False, False, "E12"),
        ],
    )
    def test_output_choices_are_stored_as_shown(
        self, monkeypatch, output_format, raw, plot, eseries
    ):
        form = _screen(
            monkeypatch, eseries=eseries, output_format=output_format, raw=raw, plot=plot
        )
        # Stale values from an earlier pass must all be overwritten.
        form.state.show_plot = not plot
        form.state.output_format = "csv" if output_format == "table" else "table"

        form.screen._show_results()

        state = form.state
        assert form.pushed
        assert (state.output_format, state.raw_units, state.show_plot) == (
            output_format,
            raw,
            plot,
        )
        assert state.quiet is (output_format == "quiet")
        assert state.eseries == eseries

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"output_format": "json", "plot": True},
            {"output_format": "csv", "raw": True},
            {"output_format": "table", "raw": True},
            {"output_format": "csv", "build_enabled": True},
            {"output_format": "quiet", "build_enabled": True},
            {"output_format": "table", "eseries": "none", "build_enabled": True},
            {"output_format": "table", "eseries": "none", "allow_sub_pf": True},
        ],
    )
    def test_choices_that_cannot_apply_are_no_longer_refused(self, monkeypatch, kwargs):
        """These used to fail on Show results; now they are disabled and left out."""
        form = _screen(monkeypatch, **kwargs)

        form.screen._show_results()

        form.screen.notify.assert_not_called()
        assert [type(screen) for screen in form.pushed] == [ResultsScreen]
        assert form.state.applied_options() <= form.state.set_options()
        assert not form.state.applied_options() & set(form.state.option_reasons())

    def test_default_form_overwrites_stale_build_settings_and_invalidates_result(self, monkeypatch):
        form = _screen(monkeypatch)
        state = form.state
        state.build_analysis_enabled = True
        state.build_inductor_q = 80.0
        state.build_reference_frequency_hz = 5e6
        state.build_sample_count = 9
        state.build_grid_points = 101
        revision = state.begin_calculation()
        state.publish_success(revision, "old", {"old": True}, {"analysis": True})

        form.screen._show_results()

        defaults = BuildConfig()
        assert form.pushed
        assert state.build_analysis_enabled is False
        assert (state.build_inductor_q, state.build_reference_frequency_hz) == (None, None)
        assert (state.build_sample_count, state.build_seed, state.build_grid_points) == (
            defaults.sample_count,
            defaults.seed,
            defaults.grid_points,
        )
        assert state.build_capacitor_tolerance_pct == defaults.capacitor_tolerance_pct
        assert state.build_inductor_tolerance_pct == defaults.inductor_tolerance_pct
        assert state.build_use_toroid_candidates is True
        assert state.calculation_revision == revision + 1
        assert (state.result, state.build_analysis) == ({}, None)

    def test_unticked_build_ignores_its_hidden_fields_as_the_web_does(self, monkeypatch):
        form = _screen(monkeypatch, build_inputs={"#build-sample-count": "x"})

        form.screen._show_results()

        form.screen.notify.assert_not_called()
        assert form.pushed
        assert form.state.build_sample_count == BuildConfig().sample_count

    def test_enabled_build_controls_are_parsed_into_state(self, monkeypatch):
        form = _screen(
            monkeypatch,
            eseries="E96",
            build_enabled=True,
            use_toroids=False,
            build_inputs={
                "#build-capacitor-tolerance": "2.5",
                "#build-inductor-tolerance": "7.5",
                "#build-inductor-q": "120",
                "#build-capacitor-q": "500",
                "#build-reference-frequency": "7MHz",
                "#build-source-resistance": "25ohm",
                "#build-load-resistance": "1k",
                "#build-sample-count": "7",
                "#build-seed": "42",
                "#build-grid-points": "301",
            },
        )

        form.screen._show_results()

        state = form.state
        assert form.pushed
        assert state.build_analysis_enabled is True
        assert (state.build_source_resistance_ohm, state.build_load_resistance_ohm) == (
            25.0,
            1000.0,
        )
        assert (state.build_capacitor_tolerance_pct, state.build_inductor_tolerance_pct) == (
            2.5,
            7.5,
        )
        assert (state.build_inductor_q, state.build_capacitor_q) == (120.0, 500.0)
        assert state.build_reference_frequency_hz == 7e6
        assert (state.build_sample_count, state.build_seed, state.build_grid_points) == (7, 42, 301)
        assert state.build_use_toroid_candidates is False
        config = state.make_build_config()
        assert (config.eseries, config.reference_frequency_hz) == ("E96", 7e6)

    def test_raw_units_are_allowed_with_build_analysis_because_the_series_is_used(
        self, monkeypatch
    ):
        form = _screen(monkeypatch, eseries="E12", raw=True, build_enabled=True)

        form.screen._show_results()

        assert form.pushed
        assert (form.state.raw_units, form.state.eseries) == (True, "E12")
        assert form.state.runs_build is True

    def test_toroid_none_simulates_calculated_inductances(self, monkeypatch):
        """--no-toroids also means --no-toroid-build: the box is disabled and left out."""
        form = _screen(monkeypatch, toroid_detail="toroid-none", build_enabled=True)
        form.screen._refresh_options()

        form.screen._show_results()

        assert form.w["#build-use-toroids"].disabled is True
        assert form.state.build_use_toroid_candidates is True
        assert form.state.make_build_config().use_toroid_candidates is False


class TestSubPicofaradOption:
    """ "Allow capacitors below 1 pF" maps onto state and needs a capacitor series."""

    @pytest.mark.parametrize("allow", [True, False])
    def test_choice_is_stored_with_a_series(self, monkeypatch, allow):
        form = _screen(monkeypatch, eseries="E96", allow_sub_pf=allow)
        form.state.allow_sub_pf = not allow  # a stale value must be overwritten

        form.screen._show_results()

        assert form.pushed
        assert (form.state.allow_sub_pf, form.state.eseries) == (allow, "E96")
        assert form.state.to_design_request(include_build=False).allow_sub_pf is allow

    def test_without_a_series_it_is_disabled_with_the_shared_message(self, monkeypatch):
        form = _screen(monkeypatch, eseries="none", allow_sub_pf=True)
        form.screen._refresh_options()

        form.screen._show_results()

        assert form.pushed
        assert form.w["#allow-sub-pf"].disabled is True
        assert _shown_reason(form, reason_id(ALLOW_SUB_PF)) == SUB_PF_NEEDS_ESERIES_MESSAGE
        assert form.state.allow_sub_pf is True
        assert form.state.to_design_request(include_build=False).allow_sub_pf is False

    def test_raw_units_with_the_build_simulation_keep_the_option(self, monkeypatch):
        form = _screen(monkeypatch, raw=True, build_enabled=True, allow_sub_pf=True)

        form.screen._show_results()

        assert form.pushed
        assert form.state.to_design_request(include_build=False).allow_sub_pf is True


class TestShowResultsRejections:
    """Only the build fields' own values (and resonator Q with part Q) can be refused."""

    @pytest.mark.parametrize(
        "build_inputs, message, focus",
        [
            (
                {"#build-source-resistance": "not-ohms"},
                "Invalid simulation source resistance: not-ohms",
                "#build-source-resistance",
            ),
            (
                {"#build-load-resistance": "0"},
                "Simulation load resistance must be positive: 0",
                "#build-load-resistance",
            ),
            (
                {"#build-capacitor-tolerance": "x"},
                "Capacitor tolerance must be a number",
                "#build-capacitor-tolerance",
            ),
            (
                {"#build-capacitor-tolerance": "100"},
                "Capacitor tolerance must be at least 0% and less than 100%",
                "#build-capacitor-tolerance",
            ),
            (
                {"#build-inductor-tolerance": "-1"},
                "Inductor tolerance must be at least 0% and less than 100%",
                "#build-inductor-tolerance",
            ),
            ({"#build-inductor-q": "abc"}, "Inductor Q must be a number", "#build-inductor-q"),
            (
                {"#build-inductor-q": "0"},
                "Inductor Q must be between 0.01 and 1e9",
                "#build-inductor-q",
            ),
            (
                {"#build-capacitor-q": "-5"},
                "Capacitor Q must be between 0.01 and 1e9",
                "#build-capacitor-q",
            ),
            (
                {"#build-reference-frequency": "abc"},
                "Invalid frequency at which the Q values apply: abc",
                "#build-reference-frequency",
            ),
            (
                {"#build-reference-frequency": "-5MHz"},
                "Frequency at which the Q values apply must be positive: -5MHz",
                "#build-reference-frequency",
            ),
            (
                {"#build-sample-count": "1.5"},
                "Extra random tolerance cases must be a whole number",
                "#build-sample-count",
            ),
            (
                {"#build-sample-count": "10001"},
                "extra random tolerance cases must be a whole number from 0 to 10000",
                "#build-sample-count",
            ),
            ({"#build-seed": "1.5"}, "Random seed must be a whole number", "#build-seed"),
            (
                {"#build-grid-points": "50"},
                "Frequency points must be a whole number from 51 to 5001",
                "#build-grid-points",
            ),
            # Hostile text is rejected on its own field rather than raised.
            (
                {"#build-capacitor-tolerance": "nan"},
                "Capacitor tolerance must be at least 0% and less than 100%",
                "#build-capacitor-tolerance",
            ),
            (
                {"#build-inductor-tolerance": "1e400"},
                "Inductor tolerance must be at least 0% and less than 100%",
                "#build-inductor-tolerance",
            ),
            (
                {"#build-inductor-q": "inf"},
                "Inductor Q must be between 0.01 and 1e9",
                "#build-inductor-q",
            ),
            (
                {"#build-capacitor-q": "nan"},
                "Capacitor Q must be between 0.01 and 1e9",
                "#build-capacitor-q",
            ),
            (
                {"#build-source-resistance": "1e400"},
                "Simulation source resistance must be positive and finite: 1e400",
                "#build-source-resistance",
            ),
            (
                {"#build-load-resistance": "nan"},
                "Simulation load resistance must be positive: nan",
                "#build-load-resistance",
            ),
            (
                {"#build-sample-count": "-1"},
                "extra random tolerance cases must be a whole number from 0 to 10000",
                "#build-sample-count",
            ),
            # Python 3.11+ refuses the digit count; 3.10 parses it and the range check fails.
            (
                {"#build-sample-count": "9" * 5000},
                "random tolerance cases must be a whole number",
                "#build-sample-count",
            ),
            (
                {"#build-grid-points": "5002"},
                "Frequency points must be a whole number from 51 to 5001",
                "#build-grid-points",
            ),
        ],
    )
    def test_invalid_build_setting_focuses_its_input(
        self, monkeypatch, build_inputs, message, focus
    ):
        form = _screen(monkeypatch, build_enabled=True, build_inputs=build_inputs)

        form.screen._show_results()

        _rejected_with(form, "Build simulation: ", focus)
        assert message in form.screen.notify.call_args.args[0]

    def test_blank_build_fields_take_the_cli_defaults_as_the_help_says(self, monkeypatch):
        blanks = {selector: "" for selector in DEFAULT_BUILD_INPUTS}
        form = _screen(monkeypatch, build_enabled=True, build_inputs=blanks)

        form.screen._show_results()

        form.screen.notify.assert_not_called()
        assert form.pushed
        defaults = BuildConfig()
        state = form.state
        assert (
            state.build_capacitor_tolerance_pct,
            state.build_inductor_tolerance_pct,
            state.build_sample_count,
            state.build_seed,
            state.build_grid_points,
        ) == (
            defaults.capacitor_tolerance_pct,
            defaults.inductor_tolerance_pct,
            defaults.sample_count,
            defaults.seed,
            defaults.grid_points,
        )

    @pytest.mark.parametrize(
        "build_inputs, focus",
        [
            ({"#build-inductor-q": "100"}, "#build-inductor-q"),
            ({"#build-capacitor-q": "300"}, "#build-capacitor-q"),
        ],
    )
    def test_resonator_q_and_part_q_together_are_refused_with_the_shared_message(
        self, monkeypatch, build_inputs, focus
    ):
        state = FilterState(category="bandpass", qu=200.0)
        form = _screen(monkeypatch, build_enabled=True, build_inputs=build_inputs, state=state)

        form.screen._show_results()

        _rejected_with(form, RESONATOR_AND_COMPONENT_Q_MESSAGE, focus)

    @pytest.mark.parametrize(
        "build_inputs, detail, focus",
        [
            # The impedance parser echoes the entry, so an entry naming another field
            # must not steer focus there.
            (
                {"#build-load-resistance": "sourcex"},
                "Invalid simulation load resistance: sourcex (use a number of ohms with an optional k or M suffix, e.g. 50 or 1k)",
                "#build-load-resistance",
            ),
            (
                {"#build-source-resistance": "loadx"},
                "Invalid simulation source resistance: loadx (use a number of ohms with an optional k or M suffix, e.g. 50 or 1k)",
                "#build-source-resistance",
            ),
            (
                {"#build-load-resistance": "seed"},
                "Invalid simulation load resistance: seed (use a number of ohms with an optional k or M suffix, e.g. 50 or 1k)",
                "#build-load-resistance",
            ),
        ],
    )
    def test_echoed_entry_text_cannot_redirect_focus(
        self, monkeypatch, build_inputs, detail, focus
    ):
        form = _screen(monkeypatch, build_enabled=True, build_inputs=build_inputs)

        form.screen._show_results()

        _rejected_with(form, "Build simulation: ", focus)
        assert form.screen.notify.call_args.args[0] == f"Build simulation: {detail}"
        for selector, widget in form.w.items():
            if selector != focus:
                widget.focus.assert_not_called()

    def test_first_invalid_field_in_form_order_is_reported(self, monkeypatch):
        form = _screen(
            monkeypatch,
            build_enabled=True,
            build_inputs={"#build-grid-points": "50", "#build-inductor-q": "abc"},
        )

        form.screen._show_results()

        _rejected_with(form, "Inductor Q must be a number", "#build-inductor-q")

    def test_a_port_outside_the_design_impedance_range_focuses_that_port(self, monkeypatch):
        """The form checks ports against the design's 50 ohm, not later on Results."""
        form = _screen(
            monkeypatch, build_enabled=True, build_inputs={"#build-load-resistance": "1e9"}
        )

        form.screen._show_results()

        _rejected_with(
            form,
            "Simulation load resistance 1e+09 ohm is outside the supported range 5e-05 to 5e+07 ohm",
            "#build-load-resistance",
        )

    def test_a_rejection_tied_to_no_field_is_reported_without_moving_focus(self, monkeypatch):
        def reject(*_args, **_kwargs):
            raise BuildOptionError("E-series must be E12, E24, or E96", None)

        monkeypatch.setattr("filter_lib.wizard.screens.output_options.parse_build_config", reject)
        form = _screen(monkeypatch, build_enabled=True)

        form.screen._show_results()

        assert form.pushed == []
        form.screen.notify.assert_called_once_with(
            "Build simulation: E-series must be E12, E24, or E96", severity="error"
        )
        for widget in form.w.values():
            widget.focus.assert_not_called()

    @pytest.mark.parametrize("output_format", ["csv", "quiet"])
    def test_a_disabled_build_is_not_checked_for_the_result_nor_focused(
        self, monkeypatch, output_format
    ):
        """Its fields are hidden: the result opens, and a saved JSON reports the problem."""
        form = _screen(
            monkeypatch,
            output_format=output_format,
            build_enabled=True,
            build_inputs={"#build-capacitor-tolerance": "abc"},
        )
        # The rule hides the fields of a build the output cannot show.
        form.screen._refresh_options()
        assert form.w["#build-analysis-options"].display is False

        form.screen._show_results()

        assert len(form.pushed) == 1 and isinstance(form.pushed[0], ResultsScreen)
        form.screen.notify.assert_not_called()
        for selector in DEFAULT_BUILD_INPUTS:
            form.w[selector].focus.assert_not_called()
        message = "Build simulation: Capacitor tolerance must be a number"
        assert form.state.build_input_error == message
        with pytest.raises(ValueError, match=message):
            form.state.json_design_request()

    def test_disabled_resonator_q_with_hidden_part_q_does_not_block_the_result(self, monkeypatch):
        """CSV uses neither Qu nor the build; the saved JSON (which uses both) refuses."""
        state = FilterState(category="bandpass", qu=200.0)
        form = _screen(
            monkeypatch,
            output_format="csv",
            build_enabled=True,
            build_inputs={"#build-inductor-q": "100"},
            state=state,
        )

        form.screen._show_results()

        assert len(form.pushed) == 1
        form.screen.notify.assert_not_called()
        assert form.state.build_input_error == (
            f"Build simulation: {RESONATOR_AND_COMPONENT_Q_MESSAGE}"
        )

    def test_an_unticked_build_keeps_its_typed_values_unchecked(self, monkeypatch):
        """Unticked, the fields are ignored but kept, as on the web; Back shows them again."""
        form = _screen(
            monkeypatch,
            build_enabled=False,
            build_inputs={"#build-capacitor-tolerance": "2.50", "#build-seed": "x"},
        )

        form.screen._show_results()

        assert len(form.pushed) == 1
        form.screen.notify.assert_not_called()
        shown = build_field_values(form.state)
        assert shown["build-capacitor-tolerance"] == "2.50"
        assert shown["build-seed"] == "x"
        assert form.state.build_analysis_enabled is False

    def test_valid_typed_values_reach_the_state_while_unticked(self, monkeypatch):
        form = _screen(
            monkeypatch,
            build_enabled=False,
            build_inputs={"#build-capacitor-tolerance": "2.5", "#build-grid-points": "201"},
        )

        form.screen._show_results()

        assert form.state.build_capacitor_tolerance_pct == 2.5
        assert form.state.build_grid_points == 201
        assert form.state.build_input_error is None

    def test_a_seed_without_extra_random_cases_is_refused_like_the_cli(self, monkeypatch):
        form = _screen(monkeypatch, build_enabled=True, build_inputs={"#build-seed": "5"})

        form.screen._show_results()

        _rejected_with(form, SEED_NEEDS_SAMPLES_MESSAGE, "#build-seed")


class TestParseBuildConfig:
    @pytest.mark.parametrize(
        "overrides, field_id",
        [
            ({"source_resistance": "sourcex"}, "build-source-resistance"),
            ({"load_resistance": "sourcex"}, "build-load-resistance"),
            ({"capacitor_tolerance": "100"}, "build-capacitor-tolerance"),
            ({"inductor_tolerance": "x"}, "build-inductor-tolerance"),
            ({"inductor_q": "0"}, "build-inductor-q"),
            ({"capacitor_q": "q"}, "build-capacitor-q"),
            ({"reference_frequency": "0"}, "build-reference-frequency"),
            ({"sample_count": "10001"}, "build-sample-count"),
            ({"seed": "s"}, "build-seed"),
            ({"grid_points": "5002"}, "build-grid-points"),
        ],
    )
    def test_each_rejection_names_the_input_that_caused_it(self, overrides, field_id):
        with pytest.raises(BuildOptionError) as caught:
            parse_build_config("E24", BuildOptionValues(**overrides))

        assert caught.value.field_id == field_id

    @pytest.mark.parametrize(
        "sample_count, seed, refused",
        [("0", "0", False), ("0", "", False), ("0", "5", True), ("3", "5", False)],
    )
    def test_a_nonzero_seed_needs_extra_random_cases(self, sample_count, seed, refused):
        values = BuildOptionValues(sample_count=sample_count, seed=seed)
        if not refused:
            parse_build_config("E24", values)
            return
        with pytest.raises(BuildOptionError) as caught:
            parse_build_config("E24", values)

        assert str(caught.value) == SEED_NEEDS_SAMPLES_MESSAGE
        assert caught.value.field_id == "build-seed"

    @pytest.mark.parametrize(
        "overrides, field_id",
        [
            ({"source_resistance": "1e-5"}, "build-source-resistance"),
            ({"load_resistance": "100M"}, "build-load-resistance"),
            ({"inductor_q": "0.001"}, "build-inductor-q"),
            ({"capacitor_q": "2e9"}, "build-capacitor-q"),
        ],
    )
    def test_values_outside_the_physical_limits_name_their_input(self, overrides, field_id):
        with pytest.raises(BuildOptionError) as caught:
            parse_build_config("E24", BuildOptionValues(**overrides), design_impedance=50.0)

        assert caught.value.field_id == field_id

    def test_resonator_q_refuses_part_q_on_the_first_part_q_given(self):
        values = BuildOptionValues(inductor_q="100", capacitor_q="300")

        with pytest.raises(BuildOptionError, match=RESONATOR_AND_COMPONENT_Q_MESSAGE) as caught:
            parse_build_config("E24", values, resonator_q_supplied=True)

        assert caught.value.field_id == "build-inductor-q"
        assert parse_build_config("E24", values).inductor_q == 100.0

    def test_port_range_follows_the_design_impedance(self):
        """100 Mohm is 2e6 times a 50 ohm design but only 1e3 times a 100 kohm one."""
        values = BuildOptionValues(load_resistance="100M")

        config = parse_build_config("E24", values, design_impedance=100e3)

        assert config.load_resistance_ohm == 100e6
        with pytest.raises(BuildOptionError, match="outside the supported range"):
            parse_build_config("E24", values, design_impedance=50.0)

    def test_a_config_level_failure_names_no_input(self):
        with pytest.raises(BuildOptionError, match="^E-series must be E12, E24, or E96$") as caught:
            parse_build_config("E6", BuildOptionValues())

        assert caught.value.field_id is None

    def test_default_values_are_the_cli_defaults(self):
        assert parse_build_config("E24", BuildOptionValues()) == BuildConfig()

    def test_valid_values_build_the_shared_config(self):
        config = parse_build_config(
            "E96",
            BuildOptionValues(
                source_resistance="25",
                load_resistance="1k",
                reference_frequency="10MHz",
                sample_count="8",
                seed="3",
                grid_points="201",
                use_toroid_candidates=False,
            ),
        )

        assert config == BuildConfig(
            eseries="E96",
            source_resistance_ohm=25.0,
            load_resistance_ohm=1000.0,
            reference_frequency_hz=10e6,
            sample_count=8,
            seed=3,
            grid_points=201,
            use_toroid_candidates=False,
        )


def test_build_reasons_are_the_render_options_messages():
    """The build reasons are the texts ``RenderOptions`` raises for the same request."""
    reasons = inapplicable_options(OutputChoices(output_format="csv"))
    assert reasons[BUILD] == BUILD_NEEDS_TABLE_OR_JSON_MESSAGE
    reasons = inapplicable_options(OutputChoices(eseries=None, build=True))
    assert reasons[BUILD] == BUILD_NEEDS_ESERIES_MESSAGE
