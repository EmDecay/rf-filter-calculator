"""Output Options screen: output/build compatibility, state mapping, and keyboard flow.

Handlers are called directly with ``Mock(spec=...)`` widgets. Mounted keyboard behavior
of the build controls lives in ``test_wizard_build_analysis_pilot.py``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from textual.widgets import Button, Checkbox, Input, RadioSet, SelectionList

from filter_lib.shared.build_types import BuildConfig
from filter_lib.wizard.build_options import BuildOptionError, BuildOptionValues, parse_build_config
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.state import FilterState

DEFAULT_BUILD_INPUTS = {
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


def _radio_set(selected_id: str, focused: bool) -> Mock:
    radio_set = Mock(spec=RadioSet)
    radio_set.pressed_button = Mock(id=selected_id) if selected_id else None
    radio_set.has_focus = focused
    return radio_set


def _screen(
    monkeypatch,
    *,
    focus: str = "",
    eseries: str = "E24",
    output_format: str = "table",
    options: tuple[str, ...] = ("plot",),
    toroid_detail: str = "toroid-full",
    export: str = "no-export",
    build_enabled: bool = False,
    use_toroids: bool = True,
    build_inputs: dict[str, str] | None = None,
) -> SimpleNamespace:
    screen = OutputOptionsScreen()
    app = Mock(filter_state=FilterState(category="lowpass"))
    pushed: list = []
    app.push_screen = pushed.append
    monkeypatch.setattr(OutputOptionsScreen, "app", property(lambda _self: app))

    options_list = Mock(spec=SelectionList)
    options_list.selected = list(options)
    options_list.has_focus = focus == "options-list"
    widgets = {
        "#eseries": _radio_set(eseries, focus == "eseries"),
        "#format": _radio_set(output_format, focus == "format"),
        "#options-list": options_list,
        "#toroid-detail": _radio_set(toroid_detail, focus == "toroid-detail"),
        "#export": _radio_set(export, focus == "export"),
        "#build-analysis-enabled": Mock(spec=Checkbox, value=build_enabled),
        "#build-analysis-options": Mock(display=build_enabled),
        "#build-use-toroids": Mock(spec=Checkbox, value=use_toroids),
        "#results-btn": Mock(spec=Button),
    }
    for selector, value in {**DEFAULT_BUILD_INPUTS, **(build_inputs or {})}.items():
        field = Mock(spec=Input)
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


class TestEnterNavigation:
    @pytest.mark.parametrize(
        "focus, next_focus",
        [
            ("eseries", "#format"),
            ("format", "#options-list"),
            ("options-list", "#toroid-detail"),
            ("toroid-detail", "#export"),
            ("export", "#results-btn"),
        ],
    )
    def test_enter_advances_through_the_output_choices(self, monkeypatch, focus, next_focus):
        form = _screen(monkeypatch, focus=focus)
        event = Mock(key="enter")

        form.screen.on_key(event)

        form.w[next_focus].focus.assert_called_once_with()
        event.prevent_default.assert_called_once_with()
        event.stop.assert_called_once_with()

    def test_other_keys_are_left_alone(self, monkeypatch):
        form = _screen(monkeypatch, focus="eseries")
        event = Mock(key="tab")

        form.screen.on_key(event)

        form.w["#format"].focus.assert_not_called()
        event.prevent_default.assert_not_called()

    def test_enter_before_widgets_are_mounted_is_ignored(self):
        screen = OutputOptionsScreen()
        screen.query_one = Mock(side_effect=LookupError("not mounted"))  # type: ignore[assignment]
        event = Mock(key="enter")

        screen.on_key(event)

        event.prevent_default.assert_not_called()

    def test_last_build_input_hands_focus_to_the_toroid_checkbox(self, monkeypatch):
        form = _screen(monkeypatch, build_enabled=True)

        form.screen._on_build_input_submitted(Mock(input=Mock(id="build-grid-points")))

        form.w["#build-use-toroids"].focus.assert_called_once_with()

    @pytest.mark.parametrize("enabled", [True, False])
    def test_build_toggle_reveals_advanced_controls_only_when_enabled(self, monkeypatch, enabled):
        form = _screen(monkeypatch)

        form.screen._on_build_analysis_changed(Mock(value=enabled))

        assert form.w["#build-analysis-options"].display is enabled
        assert form.w["#build-source-resistance"].focus.called is enabled


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
        "choice, expected", [("toroid-full", "full"), ("toroid-compact", "compact"), ("", "full")]
    )
    def test_toroid_detail_choice(self, monkeypatch, choice, expected):
        form = _screen(monkeypatch, toroid_detail=choice)

        form.screen._show_results()

        assert form.state.toroid_detail == expected

    @pytest.mark.parametrize(
        "export_id, expected", [("export-json", "json"), ("export-csv", "csv"), ("no-export", None)]
    )
    def test_response_sidecar_choice(self, monkeypatch, export_id, expected):
        form = _screen(monkeypatch, export=export_id)

        form.screen._show_results()

        assert form.state.export_format == expected

    @pytest.mark.parametrize(
        "output_format, options, eseries, expected",
        [
            ("table", ("raw",), "none", ("table", True, False, False)),
            ("table", ("raw", "plot"), "none", ("table", True, False, True)),
            ("table", ("quiet",), "none", ("table", False, True, False)),
            ("json", (), "E96", ("json", False, False, False)),
            ("csv", (), "E12", ("csv", False, False, False)),
        ],
    )
    def test_output_flags_are_stored(self, monkeypatch, output_format, options, eseries, expected):
        form = _screen(monkeypatch, eseries=eseries, output_format=output_format, options=options)
        # Stale values from an earlier pass must all be overwritten.
        form.state.show_plot = "plot" not in options
        form.state.output_format = "csv" if output_format == "table" else "table"

        form.screen._show_results()

        state = form.state
        assert form.pushed
        assert (state.output_format, state.raw_units, state.quiet, state.show_plot) == expected
        assert state.eseries == eseries

    def test_complete_resonator_q_is_parsed_into_bandpass_state(self, monkeypatch):
        form = _screen(
            monkeypatch,
            build_enabled=True,
            build_inputs={"#build-resonator-q": "150"},
        )
        form.state.category = "bandpass"

        form.screen._show_results()

        assert form.pushed
        assert form.state.build_resonator_q == 150.0
        assert (form.state.build_inductor_q, form.state.build_capacitor_q) == (None, None)
        assert form.state.make_build_config().resonator_q == 150.0

    def test_default_form_overwrites_stale_build_settings_and_invalidates_result(self, monkeypatch):
        form = _screen(monkeypatch)
        state = form.state
        state.build_analysis_enabled = True
        state.build_inductor_q = 80.0
        state.build_sample_count = 9
        state.build_grid_points = 101
        state.build_use_toroid_candidates = False
        revision = state.begin_calculation()
        state.publish_success(revision, "old", {"old": True}, {"analysis": True})

        form.screen._show_results()

        assert form.pushed
        assert state.build_analysis_enabled is False
        assert state.build_inductor_q is None
        assert (state.build_sample_count, state.build_seed, state.build_grid_points) == (0, 0, 601)
        assert state.build_capacitor_tolerance_pct == 5.0
        assert state.build_inductor_tolerance_pct == 10.0
        assert state.build_use_toroid_candidates is True
        assert state.calculation_revision == revision + 1
        assert (state.result, state.build_analysis) == ({}, None)

    def test_enabled_build_controls_are_parsed_into_state(self, monkeypatch):
        form = _screen(
            monkeypatch,
            eseries="E96",
            build_enabled=True,
            use_toroids=False,
            build_inputs={
                "#build-source-resistance": "25ohm",
                "#build-load-resistance": "1k",
                "#build-capacitor-tolerance": "2.5",
                "#build-inductor-tolerance": "7.5",
                "#build-inductor-q": "120",
                "#build-capacitor-q": "500",
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
        assert (state.build_inductor_q, state.build_capacitor_q, state.build_resonator_q) == (
            120.0,
            500.0,
            None,
        )
        assert (state.build_sample_count, state.build_seed, state.build_grid_points) == (7, 42, 301)
        assert state.build_use_toroid_candidates is False
        assert state.make_build_config().eseries == "E96"

    def test_raw_units_are_allowed_with_build_analysis_because_the_series_is_used(
        self, monkeypatch
    ):
        form = _screen(monkeypatch, eseries="E12", options=("raw",), build_enabled=True)

        form.screen._show_results()

        assert form.pushed
        assert (form.state.raw_units, form.state.eseries) == (True, "E12")
        assert form.state.build_analysis_enabled is True


class TestShowResultsRejections:
    @pytest.mark.parametrize(
        "output_format, options, eseries, message, focus",
        [
            (
                "json",
                ("plot",),
                "E24",
                "the frequency-response plot can be used only",
                "#options-list",
            ),
            ("csv", ("raw",), "E24", "raw units can be used only with table", "#options-list"),
            ("json", ("quiet",), "E24", "quiet mode can be used only with table", "#options-list"),
            ("table", ("quiet", "plot"), "none", "cannot be combined", "#options-list"),
            ("table", ("raw",), "E24", "not represented by raw units", "#eseries"),
            ("table", ("quiet",), "E24", "not represented by quiet mode", "#eseries"),
        ],
    )
    def test_selections_hidden_by_the_output_format_are_rejected(
        self, monkeypatch, output_format, options, eseries, message, focus
    ):
        form = _screen(monkeypatch, output_format=output_format, options=options, eseries=eseries)

        form.screen._show_results()

        _rejected_with(form, message, focus)

    @pytest.mark.parametrize(
        "output_format, options, eseries, message, focus",
        [
            ("csv", (), "E24", "supported only with table or JSON", "#format"),
            ("table", ("quiet",), "none", "cannot be combined with quiet output", "#options-list"),
            ("table", (), "none", "requires an E-series", "#eseries"),
        ],
    )
    def test_build_analysis_rejects_outputs_that_cannot_show_it(
        self, monkeypatch, output_format, options, eseries, message, focus
    ):
        form = _screen(
            monkeypatch,
            output_format=output_format,
            options=options,
            eseries=eseries,
            build_enabled=True,
        )

        form.screen._show_results()

        _rejected_with(form, message, focus)

    def test_custom_build_setting_requires_enabling_analysis(self, monkeypatch):
        form = _screen(monkeypatch, build_inputs={"#build-sample-count": "4"})

        form.screen._show_results()

        _rejected_with(form, "Enable realized-build analysis", "#build-analysis-enabled")

    @pytest.mark.parametrize(
        "build_inputs, message, focus",
        [
            (
                {"#build-source-resistance": "not-ohms"},
                "source resistance",
                "#build-source-resistance",
            ),
            ({"#build-load-resistance": "0"}, "load resistance", "#build-load-resistance"),
            (
                {"#build-capacitor-tolerance": "x"},
                "capacitor tolerance must be a number",
                "#build-capacitor-tolerance",
            ),
            (
                {"#build-capacitor-tolerance": "100"},
                "capacitor_tolerance_pct",
                "#build-capacitor-tolerance",
            ),
            (
                {"#build-inductor-tolerance": "-1"},
                "inductor_tolerance_pct",
                "#build-inductor-tolerance",
            ),
            ({"#build-inductor-q": "abc"}, "inductor Q must be a number", "#build-inductor-q"),
            ({"#build-inductor-q": "0"}, "inductor_q", "#build-inductor-q"),
            ({"#build-capacitor-q": "-5"}, "capacitor_q", "#build-capacitor-q"),
            (
                {"#build-inductor-q": "100", "#build-resonator-q": "200"},
                "mutually exclusive",
                "#build-resonator-q",
            ),
            (
                {"#build-sample-count": "1.5"},
                "sample count must be an integer",
                "#build-sample-count",
            ),
            ({"#build-sample-count": "10001"}, "sample_count", "#build-sample-count"),
            ({"#build-seed": "1.5"}, "seed must be an integer", "#build-seed"),
            ({"#build-grid-points": "50"}, "grid_points", "#build-grid-points"),
            # Hostile text is rejected on its own field rather than raised.
            (
                {"#build-capacitor-tolerance": "nan"},
                "capacitor_tolerance_pct",
                "#build-capacitor-tolerance",
            ),
            (
                {"#build-capacitor-tolerance": ""},
                "capacitor tolerance must be a number",
                "#build-capacitor-tolerance",
            ),
            (
                {"#build-inductor-tolerance": "1e400"},
                "inductor_tolerance_pct",
                "#build-inductor-tolerance",
            ),
            ({"#build-inductor-q": "inf"}, "inductor_q", "#build-inductor-q"),
            ({"#build-capacitor-q": "nan"}, "capacitor_q", "#build-capacitor-q"),
            (
                {"#build-source-resistance": "1e400"},
                "source resistance",
                "#build-source-resistance",
            ),
            ({"#build-load-resistance": "nan"}, "load resistance", "#build-load-resistance"),
            ({"#build-sample-count": "-1"}, "sample_count", "#build-sample-count"),
            # Python 3.11+ refuses the digit count; 3.10 parses it and the range check fails.
            ({"#build-sample-count": "9" * 5000}, "sample", "#build-sample-count"),
            ({"#build-seed": ""}, "seed must be an integer", "#build-seed"),
            (
                {"#build-grid-points": ""},
                "analysis points must be an integer",
                "#build-grid-points",
            ),
            ({"#build-grid-points": "5002"}, "grid_points", "#build-grid-points"),
        ],
    )
    def test_invalid_build_setting_focuses_its_input(
        self, monkeypatch, build_inputs, message, focus
    ):
        form = _screen(monkeypatch, build_enabled=True, build_inputs=build_inputs)

        form.screen._show_results()

        _rejected_with(form, "Invalid realized-build setting: ", focus)
        assert message in form.screen.notify.call_args.args[0]

    @pytest.mark.parametrize(
        "build_inputs, detail, focus",
        [
            # The impedance parser echoes the entry, so an entry naming another field
            # must not steer focus there.
            (
                {"#build-load-resistance": "sourcex"},
                "load resistance: sourcex",
                "#build-load-resistance",
            ),
            (
                {"#build-source-resistance": "loadx"},
                "source resistance: loadx",
                "#build-source-resistance",
            ),
            (
                {"#build-load-resistance": "seed"},
                "load resistance: seed",
                "#build-load-resistance",
            ),
        ],
    )
    def test_echoed_entry_text_cannot_redirect_focus(
        self, monkeypatch, build_inputs, detail, focus
    ):
        form = _screen(monkeypatch, build_enabled=True, build_inputs=build_inputs)

        form.screen._show_results()

        _rejected_with(form, "Invalid realized-build setting: ", focus)
        assert form.screen.notify.call_args.args[0] == f"Invalid realized-build setting: {detail}"
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

        _rejected_with(form, "inductor Q must be a number", "#build-inductor-q")

    def test_a_port_outside_the_design_impedance_range_focuses_that_port(self, monkeypatch):
        """The form checks ports against the design's 50 ohm, not later on Results."""
        form = _screen(
            monkeypatch, build_enabled=True, build_inputs={"#build-load-resistance": "1e9"}
        )

        form.screen._show_results()

        _rejected_with(
            form,
            "Load resistance 1e+09 ohm is outside the supported range 5e-05 to 5e+07 ohm",
            "#build-load-resistance",
        )

    def test_a_rejection_tied_to_no_field_is_reported_without_moving_focus(self, monkeypatch):
        def reject(*_args, **_kwargs):
            raise BuildOptionError("eseries must be E12, E24, or E96", None)

        monkeypatch.setattr("filter_lib.wizard.screens.output_options.parse_build_config", reject)
        form = _screen(monkeypatch, build_enabled=True)

        form.screen._show_results()

        assert form.pushed == []
        form.screen.notify.assert_called_once_with(
            "Invalid realized-build setting: eseries must be E12, E24, or E96", severity="error"
        )
        for widget in form.w.values():
            widget.focus.assert_not_called()


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
            ({"resonator_q": "-1"}, "build-resonator-q"),
            ({"sample_count": "10001"}, "build-sample-count"),
            ({"seed": "s"}, "build-seed"),
            ({"grid_points": "5002"}, "build-grid-points"),
            # The only cross-field rule belongs to the complete resonator Q.
            ({"capacitor_q": "80", "resonator_q": "200"}, "build-resonator-q"),
        ],
    )
    def test_each_rejection_names_the_input_that_caused_it(self, overrides, field_id):
        with pytest.raises(BuildOptionError) as caught:
            parse_build_config("E24", BuildOptionValues(**overrides))

        assert caught.value.field_id == field_id

    @pytest.mark.parametrize(
        "overrides, field_id",
        [
            ({"source_resistance": "1e-5"}, "build-source-resistance"),
            ({"load_resistance": "100M"}, "build-load-resistance"),
            ({"inductor_q": "0.001"}, "build-inductor-q"),
            ({"resonator_q": "2e9"}, "build-resonator-q"),
        ],
    )
    def test_values_outside_the_physical_limits_name_their_input(self, overrides, field_id):
        with pytest.raises(BuildOptionError) as caught:
            parse_build_config("E24", BuildOptionValues(**overrides), design_impedance=50.0)

        assert caught.value.field_id == field_id

    def test_port_range_follows_the_design_impedance(self):
        """100 Mohm is 2e6 times a 50 ohm design but only 1e3 times a 100 kohm one."""
        values = BuildOptionValues(load_resistance="100M")

        config = parse_build_config("E24", values, design_impedance=100e3)

        assert config.load_resistance_ohm == 100e6
        with pytest.raises(BuildOptionError, match="outside the supported range"):
            parse_build_config("E24", values, design_impedance=50.0)

    def test_a_config_level_failure_names_no_input(self):
        with pytest.raises(BuildOptionError, match="eseries") as caught:
            parse_build_config("E6", BuildOptionValues())

        assert caught.value.field_id is None

    def test_valid_values_build_the_shared_config(self):
        config = parse_build_config(
            "E96",
            BuildOptionValues(
                source_resistance="25",
                load_resistance="1k",
                resonator_q="150",
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
            resonator_q=150.0,
            sample_count=8,
            seed=3,
            grid_points=201,
            use_toroid_candidates=False,
        )
