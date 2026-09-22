"""Wizard export payloads: component JSON/CSV, response sidecars, and file naming."""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import replace
from unittest.mock import Mock

import pytest

from filter_lib.wizard.calculation_handler import calculate_and_format
from filter_lib.wizard.export_formatting import (
    format_component_csv,
    format_component_json,
    format_response_export,
    prepare_export_payloads,
)
from filter_lib.wizard.filter_type_calculators import (
    BANDPASS_WIZARD_RESPONSE_POINTS,
    calculate_bandpass,
    calculate_highpass,
    calculate_lowpass,
)
from filter_lib.wizard.state import FilterState

CALCULATORS = {
    "lowpass": calculate_lowpass,
    "highpass": calculate_highpass,
    "bandpass": calculate_bandpass,
}


def _calculated_state(category: str, **overrides) -> FilterState:
    """Run the wizard calculator so ``state.result`` has the real category shape."""
    values = dict(
        category=category,
        filter_type="butterworth",
        frequency_hz=10e6,
        impedance=50.0,
        order=3,
        topology="pi",
        show_plot=False,
        eseries="E24",
    )
    if category == "bandpass":
        values.update(frequency_hz=14.175e6, bandwidth_hz=350e3, topology="top")
    values.update(overrides)
    state = FilterState(**values)
    state.output_text = "\n".join(CALCULATORS[category](state))
    state.calculation_status = "success"
    return state


@pytest.fixture(scope="module")
def calculated() -> dict[str, FilterState]:
    return {category: _calculated_state(category) for category in CALCULATORS}


def _contains_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


class TestComponentExports:
    @pytest.mark.parametrize(
        "category, capacitor_group, component_groups",
        [
            ("lowpass", "capacitors", {"capacitors", "inductors"}),
            ("highpass", "capacitors", {"capacitors", "inductors"}),
            (
                "bandpass",
                "tank_capacitors",
                {"tank_capacitors", "inductors", "coupling_capacitors", "end_coupling_capacitors"},
            ),
        ],
    )
    def test_json_uses_category_schema_and_honors_the_eseries_choice(
        self, calculated, category, capacitor_group, component_groups
    ):
        state = calculated[category]

        matched = json.loads(format_component_json(state))
        unmatched = json.loads(format_component_json(replace(state, eseries="none")))

        assert set(matched["components"]) == component_groups
        assert matched["components"][capacitor_group][0]["standard_match"]["series"] == "E24"
        assert not _contains_key(unmatched["components"], "standard_match")

    @pytest.mark.parametrize("category", ["lowpass", "highpass", "bandpass"])
    def test_csv_has_one_row_per_component_and_match_columns_only_with_eseries(
        self, calculated, category
    ):
        state = calculated[category]
        result = state.result
        if category == "bandpass":
            n = result["n_resonators"]
            expected = (
                {f"Cp{i}" for i in range(1, n + 1)}
                | {f"L{i}" for i in range(1, n + 1)}
                | {f"Cs{i}{i + 1}" for i in range(1, n)}
                | {"Ce_in", "Ce_out"}
            )
        else:
            expected = {f"C{i}" for i in range(1, len(result["capacitors"]) + 1)} | {
                f"L{i}" for i in range(1, len(result["inductors"]) + 1)
            }

        matched = list(csv.reader(io.StringIO(format_component_csv(state))))
        unmatched = list(
            csv.reader(io.StringIO(format_component_csv(replace(state, eseries="none"))))
        )

        assert {row[0] for row in matched[1:]} == expected
        assert {len(row) for row in matched} == {len(matched[0])}
        assert "NearestStdValue" in matched[0]
        assert "NearestStdValue" not in unmatched[0]

    def test_bandpass_csv_omits_end_caps_absent_from_the_result(self, bandpass_result):
        state = FilterState(category="bandpass", eseries="none", result=bandpass_result)

        rows = list(csv.reader(io.StringIO(format_component_csv(state))))

        assert [row[0] for row in rows[1:]] == [
            "Cp1",
            "Cp2",
            "Cp3",
            "L1",
            "L2",
            "L3",
            "Cs12",
            "Cs23",
        ]

    def test_csv_refuses_to_drop_a_realized_build_analysis(self):
        state = FilterState(category="lowpass", result={"ok": True}, build_analysis_enabled=True)

        with pytest.raises(ValueError, match="not supported in component CSV"):
            format_component_csv(state)

    def test_json_export_reuses_the_worker_build_analysis(self, monkeypatch):
        from filter_lib.shared.build_output import build_analysis_fields

        state = FilterState(
            category="lowpass",
            frequency_hz=10e6,
            order=3,
            show_plot=False,
            eseries="E24",
            build_analysis_enabled=True,
            build_grid_points=51,
            build_use_toroid_candidates=False,
        )
        outcome = calculate_and_format(state)
        revision = state.begin_calculation()
        assert state.publish_success(
            revision, outcome.output_text, outcome.result, outcome.build_analysis
        )
        monkeypatch.setattr(
            "filter_lib.shared.build_simulation.analyze_build",
            Mock(side_effect=AssertionError("export recomputed the analysis")),
        )

        payload = json.loads(format_component_json(state))

        expected = build_analysis_fields(outcome.result, outcome.build_analysis)
        for key in ("target", "simulated", "nominal_build", "tolerance_analysis"):
            assert payload[key] == expected[key]


class TestResponseExport:
    @pytest.mark.parametrize("category, rising", [("lowpass", False), ("highpass", True)])
    def test_lp_hp_response_follows_the_category_transfer_function(
        self, calculated, category, rising
    ):
        payload = json.loads(format_response_export(calculated[category], "json"))

        assert payload["filter"]["category"] == category
        assert payload["filter"]["cutoff_hz"] == 10e6
        magnitudes = [point["magnitude_db"] for point in payload["data"]]
        low_end, high_end = magnitudes[0], magnitudes[-1]
        passband, stopband = (high_end, low_end) if rising else (low_end, high_end)
        assert passband == pytest.approx(0.0, abs=0.01)
        assert stopband < -40.0

    def test_csv_response_has_header_and_one_row_per_json_point(self, calculated):
        state = calculated["lowpass"]

        rows = list(csv.reader(io.StringIO(format_response_export(state, "csv"))))
        points = json.loads(format_response_export(state, "json"))["data"]

        assert rows[0] == ["frequency_hz", "magnitude_db"]
        assert len(rows) - 1 == len(points)

    def test_bandpass_response_is_the_simulated_wizard_sweep(self, calculated):
        state = calculated["bandpass"]

        payload = json.loads(format_response_export(state, "json"))

        assert payload["filter"]["category"] == "bandpass"
        assert len(payload["data"]) == BANDPASS_WIZARD_RESPONSE_POINTS
        peak = max(payload["data"], key=lambda point: point["magnitude_db"])
        assert abs(peak["frequency_hz"] - 14.175e6) < 350e3 / 2


class TestPrepareExportPayloads:
    def test_text_payload_and_optional_sidecar_are_named_in_the_working_directory(
        self, calculated, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        state = replace(calculated["highpass"], export_format="csv")

        files = prepare_export_payloads(state, "export-txt")

        (component_path, component), (response_path, response) = files
        assert os.path.dirname(component_path) == str(tmp_path)
        name = os.path.basename(component_path)
        assert name.startswith("highpass-") and name.endswith(".txt")
        assert os.path.basename(response_path) == name.removesuffix(".txt") + "-response.csv"
        assert component == state.output_text
        assert response.startswith("frequency_hz,magnitude_db")

    def test_without_sidecar_only_the_component_payload_is_prepared(self, calculated):
        files = prepare_export_payloads(calculated["lowpass"], "export-json")

        assert len(files) == 1
        assert files[0][0].endswith(".json")
        assert json.loads(files[0][1])["filter_type"] == "butterworth"
