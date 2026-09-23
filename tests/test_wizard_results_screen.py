"""Results screen: worker publication guards, export preselection, saving, and navigation.

Handlers are called directly with ``Mock(spec=...)`` widgets. The mounted worker
lifecycle is covered by ``test_wizard_build_analysis_pilot.py``,
``test_wizard_design_screen_journeys.py``, and (for a failed calculation)
``test_wizard_failure_surfacing.py``.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock, mock_open

import pytest
from textual.widgets import Button, RadioButton, RadioSet, Static

import filter_lib.wizard.screens.results as results_module
from filter_lib.wizard.filter_type_calculators import calculate_highpass, calculate_lowpass
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.screens.welcome import WelcomeScreen
from filter_lib.wizard.state import CalculationOutcome, FilterState


def _results_screen(monkeypatch, state: FilterState, **widgets) -> SimpleNamespace:
    """ResultsScreen bound to a stub app; ``widgets`` maps ids (``_`` for ``-``) to stubs."""
    screen = ResultsScreen()
    app = Mock(filter_state=state)
    pushed: list = []
    app.push_screen = pushed.append
    monkeypatch.setattr(ResultsScreen, "app", property(lambda _self: app))
    by_selector = {"#" + name.replace("_", "-"): widget for name, widget in widgets.items()}

    def query_one(selector, *_args):
        if selector not in by_selector:
            raise LookupError(selector)
        return by_selector[selector]

    screen.query_one = query_one  # type: ignore[assignment]
    screen.notify = Mock()  # type: ignore[assignment]
    return SimpleNamespace(screen=screen, app=app, pushed=pushed, w=by_selector)


def _running_calculation(monkeypatch, state: FilterState) -> SimpleNamespace:
    """A mounted-equivalent screen whose current worker may publish into ``state``."""
    view = _results_screen(
        monkeypatch,
        state,
        results_text=Mock(spec=Static),
        export_btn=Mock(spec=Button, disabled=True),
    )
    view.worker = Mock()
    view.screen._active_worker = view.worker
    view.screen._calculation_revision = state.begin_calculation()
    view.screen._accept_worker_events = True
    return view


def _worker_event(worker, state_name: str, *, result=None, error=None) -> Mock:
    worker.result = result
    worker.error = error
    return Mock(state=SimpleNamespace(name=state_name), worker=worker)


def _lowpass_success(**overrides) -> FilterState:
    state = FilterState(
        category="lowpass", frequency_hz=10e6, order=3, show_plot=False, eseries="E24"
    )
    state.output_text = "\n".join(calculate_lowpass(state))
    state.calculation_status = "success"
    for field, value in overrides.items():
        setattr(state, field, value)
    return state


def _export_widgets(format_id: str | None) -> dict:
    export_format = Mock(spec=RadioSet)
    export_format.pressed_button = Mock(id=format_id) if format_id else None
    return {"export_format": export_format, "export_section": Mock(display=True)}


def _saving_screen(monkeypatch, tmp_path, state: FilterState, format_id: str | None):
    monkeypatch.chdir(tmp_path)
    view = _results_screen(monkeypatch, state, **_export_widgets(format_id))
    view.screen._result_text = state.output_text
    return view


class TestWorkerPublication:
    def test_success_publishes_text_and_enables_export(self, monkeypatch):
        state = FilterState()
        view = _running_calculation(monkeypatch, state)
        outcome = CalculationOutcome(status="success", output_text="table", result={"ok": 1})

        view.screen.on_worker_state_changed(_worker_event(view.worker, "SUCCESS", result=outcome))

        view.w["#results-text"].update.assert_called_once_with("table")
        assert view.w["#export-btn"].disabled is False
        assert (state.calculation_status, state.output_text, state.result) == (
            "success",
            "table",
            {"ok": 1},
        )
        assert view.screen._result_text == "table"
        assert state.is_exportable

    def test_build_success_publishes_the_same_worker_analysis(self, monkeypatch):
        state = FilterState(build_analysis_enabled=True)
        view = _running_calculation(monkeypatch, state)
        analysis = {"worker": "analysis"}
        outcome = CalculationOutcome(
            status="success", output_text="build", result={"ok": 1}, build_analysis=analysis
        )

        view.screen.on_worker_state_changed(_worker_event(view.worker, "SUCCESS", result=outcome))

        assert state.build_analysis == analysis
        assert state.is_exportable
        assert view.w["#export-btn"].disabled is False

    @pytest.mark.parametrize(
        "state_kwargs, outcome, message",
        [
            (
                {},
                CalculationOutcome(status="error", error="Unknown filter category"),
                "Unknown filter category",
            ),
            (
                {},
                CalculationOutcome(status="success", output_text="  ", result={"ok": 1}),
                "Calculation returned no result",
            ),
            (
                {"build_analysis_enabled": True},
                CalculationOutcome(status="success", output_text="table only", result={"ok": 1}),
                "Calculation returned no realized-build analysis",
            ),
            ({}, "table text instead of an outcome", "Calculation returned an invalid outcome"),
        ],
    )
    def test_unusable_outcome_is_published_as_a_failure(
        self, monkeypatch, state_kwargs, outcome, message
    ):
        state = FilterState(**state_kwargs)
        view = _running_calculation(monkeypatch, state)

        view.screen.on_worker_state_changed(_worker_event(view.worker, "SUCCESS", result=outcome))

        view.w["#results-text"].update.assert_called_once_with(
            f"Calculation failed: {message}\n\nPress Esc to go back."
        )
        assert view.w["#export-btn"].disabled is True
        assert (state.calculation_status, state.calculation_error) == ("error", message)
        assert (state.result, state.build_analysis) == ({}, None)
        assert not state.is_exportable

    @pytest.mark.parametrize(
        "error, message",
        [(RuntimeError("solver exploded"), "solver exploded"), (KeyError(), "KeyError")],
    )
    def test_worker_error_event_renders_the_failure(self, monkeypatch, error, message):
        """The ERROR branch renders the failure Textual delivers for an escaped exception.

        The worker runs with ``exit_on_error=False``, so the app keeps running; the
        mounted journey is ``test_worker_exception_is_rendered_without_exiting_the_app``
        in ``test_wizard_failure_surfacing.py``.
        """
        state = FilterState()
        view = _running_calculation(monkeypatch, state)

        view.screen.on_worker_state_changed(_worker_event(view.worker, "ERROR", error=error))

        view.w["#results-text"].update.assert_called_once_with(
            f"Calculation failed: {message}\n\nPress Esc to go back."
        )
        assert state.calculation_status == "error"
        assert view.w["#export-btn"].disabled is True

    def test_intermediate_worker_states_change_nothing(self, monkeypatch):
        state = FilterState()
        view = _running_calculation(monkeypatch, state)

        view.screen.on_worker_state_changed(_worker_event(view.worker, "RUNNING"))

        assert state.calculation_status == "pending"
        view.w["#results-text"].update.assert_not_called()

    @pytest.mark.parametrize("stale_by", ["newer_revision", "other_worker", "screen_unmounted"])
    def test_stale_events_cannot_publish(self, monkeypatch, stale_by):
        state = FilterState()
        view = _running_calculation(monkeypatch, state)
        worker = view.worker
        if stale_by == "newer_revision":
            state.invalidate_calculation()
        elif stale_by == "other_worker":
            worker = Mock()
        else:
            view.screen.on_unmount()
            view.worker.cancel.assert_called_once_with()
            assert state.calculation_status == "idle"
        status = state.calculation_status
        outcome = CalculationOutcome(
            status="success", output_text="late", result={"late": 1}, build_analysis={"late": 1}
        )

        view.screen.on_worker_state_changed(_worker_event(worker, "SUCCESS", result=outcome))
        view.screen.on_worker_state_changed(_worker_event(worker, "ERROR", error=RuntimeError()))

        assert state.calculation_status == status
        assert (state.result, state.output_text, state.build_analysis) == ({}, "", None)
        view.w["#results-text"].update.assert_not_called()
        assert view.screen._result_text == ""

    def test_unmounting_before_a_calculation_started_changes_nothing(self, monkeypatch):
        state = FilterState(category="lowpass")
        revision = state.begin_calculation()
        view = _results_screen(monkeypatch, state)

        view.screen.on_unmount()

        assert (state.calculation_status, state.calculation_revision) == ("pending", revision)


class TestExportPreselection:
    @pytest.mark.parametrize(
        "state_kwargs, selected, csv_disabled",
        [
            ({"output_format": "table", "export_format": "csv"}, "export-txt", False),
            ({"output_format": "json"}, "export-json", False),
            ({"output_format": "csv", "export_format": "json"}, "export-csv", False),
            ({"output_format": "json", "build_analysis_enabled": True}, "export-json", True),
            # CSV cannot carry a build analysis, so the text export is preselected instead.
            ({"output_format": "csv", "build_analysis_enabled": True}, "export-txt", True),
        ],
    )
    def test_component_format_follows_output_not_response_sidecar(
        self, monkeypatch, state_kwargs, selected, csv_disabled
    ):
        buttons = [
            Mock(spec=RadioButton, id=button_id, value=False, disabled=False)
            for button_id in ("export-txt", "export-json", "export-csv")
        ]
        radio_set = Mock(spec=RadioSet)
        radio_set.query.return_value = buttons
        view = _results_screen(monkeypatch, FilterState(**state_kwargs), export_format=radio_set)

        view.screen._preselect_export_format()

        assert [button.id for button in buttons if button.value] == [selected]
        assert [button.id for button in buttons if button.disabled] == (
            ["export-csv"] if csv_disabled else []
        )

    def test_preselection_is_a_no_op_before_the_format_selector_mounts(self, monkeypatch):
        state = FilterState(output_format="json")
        view = _results_screen(monkeypatch, state)

        view.screen._preselect_export_format()

        assert state.output_format == "json"


class TestNavigationAndExportSection:
    def test_back_quit_and_quit_button(self, monkeypatch):
        view = _results_screen(monkeypatch, FilterState())

        view.screen.action_back()
        view.screen.action_quit()
        view.screen.on_button_pressed(Mock(button=Mock(id="quit-btn")))
        view.screen.on_button_pressed(Mock(button=Mock(id="unknown")))

        view.app.pop_screen.assert_called_once_with()
        assert view.app.exit.call_count == 2

    def test_export_button_reveals_formats_for_the_current_result(self, monkeypatch):
        state = _lowpass_success()
        view = _results_screen(monkeypatch, state, **_export_widgets("export-txt"))
        view.w["#export-section"].display = False
        view.screen._result_text = state.output_text

        view.screen.on_button_pressed(Mock(button=Mock(id="export-btn")))

        assert view.w["#export-section"].display is True
        view.w["#export-format"].focus.assert_called_once_with()

        view.screen.on_button_pressed(Mock(button=Mock(id="cancel-export-btn")))
        assert view.w["#export-section"].display is False

    def test_export_button_without_a_current_result_warns(self, monkeypatch):
        state = _lowpass_success()
        view = _results_screen(monkeypatch, state, **_export_widgets("export-txt"))
        view.w["#export-section"].display = False
        view.screen._result_text = "text from an earlier calculation"

        view.screen.on_button_pressed(Mock(button=Mock(id="export-btn")))

        assert view.w["#export-section"].display is False
        view.screen.notify.assert_called_once_with(
            "No current successful calculation is available to export", severity="warning"
        )

    def test_design_another_resets_state_and_restarts_at_welcome(self, monkeypatch):
        state = _lowpass_success()
        view = _results_screen(monkeypatch, state)
        view.app.screen_stack = ["base", "welcome", "lowpass", "options", "results"]
        view.app.pop_screen.side_effect = view.app.screen_stack.pop

        view.screen.on_button_pressed(Mock(button=Mock(id="another-btn")))

        assert view.app.filter_state is not state
        assert view.app.filter_state == FilterState()
        assert view.app.screen_stack == ["base"]
        assert [type(screen) for screen in view.pushed] == [WelcomeScreen]


class TestSaving:
    def test_text_save_writes_the_displayed_result_and_reports_its_path(
        self, monkeypatch, tmp_path
    ):
        state = _lowpass_success()
        view = _saving_screen(monkeypatch, tmp_path, state, "export-txt")

        view.screen.on_button_pressed(Mock(button=Mock(id="save-btn")))

        [saved] = tmp_path.glob("lowpass-*.txt")
        assert saved.read_text(encoding="utf-8") == state.output_text
        view.screen.notify.assert_called_once_with(
            f"Saved to {os.path.join(str(tmp_path), saved.name)}", severity="information"
        )
        assert view.w["#export-section"].display is False

    def test_missing_selection_falls_back_to_text(self, monkeypatch, tmp_path):
        view = _saving_screen(monkeypatch, tmp_path, _lowpass_success(), None)

        view.screen._save_export()

        assert [path.suffix for path in tmp_path.iterdir()] == [".txt"]

    def test_csv_save_writes_component_rows(self, monkeypatch, tmp_path):
        state = _lowpass_success()
        view = _saving_screen(monkeypatch, tmp_path, state, "export-csv")

        view.screen._save_export()

        [saved] = tmp_path.glob("lowpass-*.csv")
        rows = list(csv.reader(saved.open(encoding="utf-8", newline="")))
        assert [row[0] for row in rows] == ["Component", "C1", "C2", "L1"]

    def test_enter_on_the_format_list_saves_json(self, monkeypatch, tmp_path):
        view = _saving_screen(monkeypatch, tmp_path, _lowpass_success(), "export-json")
        view.w["#export-format"].has_focus = True
        event = Mock(key="enter")

        view.screen.on_key(event)

        [saved] = tmp_path.glob("lowpass-*.json")
        assert json.loads(saved.read_text(encoding="utf-8"))["filter_type"] == "butterworth"
        event.prevent_default.assert_called_once_with()

    @pytest.mark.parametrize("key, focused", [("escape", True), ("enter", False)])
    def test_other_keys_or_unfocused_format_list_do_not_save(
        self, monkeypatch, tmp_path, key, focused
    ):
        view = _saving_screen(monkeypatch, tmp_path, _lowpass_success(), "export-json")
        view.w["#export-format"].has_focus = focused

        view.screen.on_key(Mock(key=key))

        assert list(tmp_path.iterdir()) == []

    def test_enter_before_widgets_are_mounted_is_ignored(self):
        screen = ResultsScreen()
        screen.query_one = Mock(side_effect=LookupError("not mounted"))  # type: ignore[assignment]
        event = Mock(key="enter")

        screen.on_key(event)

        event.prevent_default.assert_not_called()

    @pytest.mark.parametrize("situation", ["never_run", "pending", "failed_after_success"])
    def test_no_file_is_written_without_a_current_success(self, monkeypatch, tmp_path, situation):
        state = _lowpass_success(export_format="json")
        if situation == "never_run":
            state = FilterState(category="lowpass", export_format="json")
        elif situation == "pending":
            state.begin_calculation()
        else:
            state.result = {}
        view = _saving_screen(monkeypatch, tmp_path, state, "export-txt")
        view.screen._result_text = "text from the earlier success"

        view.screen._save_export()

        assert list(tmp_path.iterdir()) == []
        view.screen.notify.assert_called_once_with(
            "No current successful calculation is available to export", severity="warning"
        )
        assert view.w["#export-section"].display is False

    def test_component_csv_is_refused_for_build_analysis(self, monkeypatch, tmp_path):
        state = _lowpass_success(build_analysis_enabled=True, build_analysis={"worker": 1})
        view = _saving_screen(monkeypatch, tmp_path, state, "export-csv")

        view.screen._save_export()

        assert list(tmp_path.iterdir()) == []
        view.screen.notify.assert_called_once_with(
            "Cannot export current result: realized-build analysis is not supported in "
            "component CSV",
            severity="error",
        )

    def test_response_that_cannot_be_computed_blocks_the_save_with_a_message(
        self, monkeypatch, tmp_path
    ):
        # A cutoff at the largest float synthesizes, but no response sweep can span it.
        state = FilterState(
            category="highpass",
            frequency_hz=sys.float_info.max,
            order=3,
            show_plot=False,
            eseries="none",
            export_format="csv",
        )
        state.output_text = "\n".join(calculate_highpass(state))
        state.calculation_status = "success"
        view = _saving_screen(monkeypatch, tmp_path, state, "export-txt")

        view.screen._save_export()

        assert list(tmp_path.iterdir()) == []
        view.screen.notify.assert_called_once_with(
            "Cannot export current result: Requested frequency span must remain positive "
            "and finite",
            severity="error",
        )
        assert view.w["#export-section"].display is False

    def test_write_failure_is_reported_without_claiming_success(self, monkeypatch, tmp_path):
        view = _saving_screen(monkeypatch, tmp_path, _lowpass_success(), "export-txt")
        monkeypatch.setattr(
            results_module, "open", Mock(side_effect=OSError("disk full")), raising=False
        )

        view.screen._save_export()

        [(args, kwargs)] = view.screen.notify.call_args_list
        assert args[0].startswith("Error saving ") and args[0].endswith(": disk full")
        assert kwargs == {"severity": "error"}

    def test_files_are_written_as_utf8_without_newline_translation(self, monkeypatch, tmp_path):
        state = _lowpass_success(output_text="Ω 1 µH ───")
        view = _saving_screen(monkeypatch, tmp_path, state, "export-txt")
        opened = mock_open()
        monkeypatch.setattr(results_module, "open", opened, raising=False)

        view.screen._save_export()

        assert opened.call_args.kwargs == {"encoding": "utf-8", "newline": ""}
        opened().write.assert_called_once_with("Ω 1 µH ───")


class TestResponseSidecar:
    @pytest.mark.parametrize("sidecar", ["json", "csv"])
    def test_selected_sidecar_is_written_beside_the_component_file(
        self, monkeypatch, tmp_path, sidecar
    ):
        view = _saving_screen(
            monkeypatch, tmp_path, _lowpass_success(export_format=sidecar), "export-json"
        )

        view.screen._save_export()

        [component] = tmp_path.glob("lowpass-*[0-9].json")
        [response] = tmp_path.glob(f"lowpass-*-response.{sidecar}")
        assert response.name == component.name.removesuffix(".json") + f"-response.{sidecar}"
        view.screen.notify.assert_called_once_with(
            f"Saved to {tmp_path / component.name} and {tmp_path / response.name}",
            severity="information",
        )
