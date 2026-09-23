"""Wizard calculators, band-pass table rendering, and the detached calculation outcome.

Reference component values come from the Butterworth prototype g = (1, 2, 1):
at 10 MHz and 50 Ohm, a unit-g capacitor is 1/(2*pi*f*Z) = 318.31 pF and a unit-g
inductor is Z/(2*pi*f) = 795.77 nH.
"""

from __future__ import annotations

import json
from importlib import import_module
from unittest.mock import Mock

import pytest
from textual.widgets import RadioSet

from filter_lib.bandpass.display import format_eseries_lines
from filter_lib.wizard.calculation_handler import calculate_and_format
from filter_lib.wizard.export_formatting import format_component_csv, format_component_json
from filter_lib.wizard.filter_type_calculators import (
    BANDPASS_WIZARD_RESPONSE_POINTS,
    calculate_bandpass,
    calculate_highpass,
    calculate_lowpass,
)
from filter_lib.wizard.formatting_helpers import format_bandpass_table
from filter_lib.wizard.radio_button_helpers import get_selected_radio
from filter_lib.wizard.state import FilterState

LP_HP = {"lowpass": calculate_lowpass, "highpass": calculate_highpass}
CALCULATORS = {**LP_HP, "bandpass": calculate_bandpass}


def _state(category: str, **overrides) -> FilterState:
    values = dict(
        category=category,
        filter_type="butterworth",
        frequency_hz=10e6,
        impedance=50.0,
        order=3,
        topology="pi",
        show_plot=False,
        eseries="none",
    )
    if category == "bandpass":
        values.update(frequency_hz=14.175e6, bandwidth_hz=350e3, topology="top")
    values.update(overrides)
    return FilterState(**values)


def _render(category: str, **overrides) -> tuple[FilterState, str]:
    state = _state(category, **overrides)
    return state, "\n".join(CALCULATORS[category](state))


# ---------------------------------------------------------------------------
# Low-pass / high-pass calculators
# ---------------------------------------------------------------------------


class TestLowpassHighpassCalculators:
    @pytest.mark.parametrize("category", ["lowpass", "highpass"])
    @pytest.mark.parametrize("filter_type", ["butterworth", "chebyshev", "bessel"])
    def test_result_records_the_public_synthesis_for_the_chosen_response(
        self, category, filter_type
    ):
        state = _state(
            category,
            filter_type=filter_type,
            frequency_hz=7e6,
            impedance=75.0,
            order=5,
            ripple_db=0.25,
            topology="t",
            output_format="json",
        )

        LP_HP[category](state)

        synthesize = getattr(import_module(f"filter_lib.{category}"), f"calculate_{filter_type}")
        if filter_type == "chebyshev":
            first, second, order = synthesize(7e6, 75.0, 0.25, 5, "t")
        else:
            first, second, order = synthesize(7e6, 75.0, 5, "t")
        # High-pass synthesis returns inductors first; the stored result must not swap them.
        capacitors, inductors = (first, second) if category == "lowpass" else (second, first)
        assert state.result == {
            "filter_type": filter_type,
            "freq_hz": 7e6,
            "impedance": 75.0,
            "capacitors": capacitors,
            "inductors": inductors,
            "order": order,
            "ripple": 0.25 if filter_type == "chebyshev" else None,
            "topology": "t",
        }

    @pytest.mark.parametrize(
        "category, raw, expected",
        [
            ("lowpass", True, "C1: 3.183099e-10 F\nC2: 3.183099e-10 F\nL1: 1.591549e-06 H"),
            ("lowpass", False, "C1: 318.31 pF\nC2: 318.31 pF\nL1: 1.59 µH"),
            ("highpass", True, "L1: 7.957747e-07 H\nL2: 7.957747e-07 H\nC1: 1.591549e-10 F"),
            ("highpass", False, "L1: 795.77 nH\nL2: 795.77 nH\nC1: 159.15 pF"),
        ],
    )
    def test_quiet_output_is_one_value_per_component(self, category, raw, expected):
        state = _state(category, quiet=True, raw_units=raw)

        assert LP_HP[category](state) == [expected]

    @pytest.mark.parametrize(
        "category, topology, title, first_column",
        [
            ("lowpass", "pi", "Butterworth PI Low Pass Filter", "Capacitors"),
            ("lowpass", "t", "Butterworth T Low Pass Filter", "Inductors"),
            ("highpass", "pi", "Butterworth PI High Pass Filter", "Inductors"),
            ("highpass", "t", "Butterworth T High Pass Filter", "Capacitors"),
        ],
    )
    def test_table_lists_the_first_ladder_element_first(
        self, category, topology, title, first_column
    ):
        _, output = _render(category, topology=topology)

        lines = output.splitlines()
        assert title in lines
        assert "Topology:" in lines
        header = next(line for line in lines if "Capacitors" in line and "Inductors" in line)
        assert header.index(first_column) < header.index(
            "Inductors" if first_column == "Capacitors" else "Capacitors"
        )

    def test_raw_units_table_prints_si_values(self):
        _, output = _render("lowpass", raw_units=True)

        assert "│ C1: 3.183099e-10 F" in output
        assert "│ L1: 1.591549e-06 H" in output
        assert "318.31 pF" not in output

    @pytest.mark.parametrize("category", ["lowpass", "highpass"])
    def test_eseries_selection_covers_capacitors_and_inductors_are_wound(self, category):
        _, matched = _render(category, eseries="E12")
        _, unmatched = _render(category, eseries="none")

        assert "E12 Preferred-Value Capacitor Selection" in matched
        assert "Preferred-Value Inductor Selection" not in matched
        assert "Inductors: wind to value (see toroid recommendations)" in matched
        assert "Preferred-Value" not in unmatched

    @pytest.mark.parametrize("category", ["lowpass", "highpass"])
    def test_plot_and_threshold_summary_follow_the_plot_option(self, category):
        _, with_plot = _render(category, show_plot=True)
        _, without_plot = _render(category, show_plot=False)

        for heading in ("Frequency Response (dB)", "dB Threshold Summary"):
            assert heading in with_plot
            assert heading not in without_plot

    @pytest.mark.parametrize("category", ["lowpass", "highpass"])
    def test_chebyshev_table_states_its_ripple(self, category):
        _, chebyshev = _render(category, filter_type="chebyshev", ripple_db=0.5)
        _, butterworth = _render(category)

        assert "Ripple:              0.5 dB" in chebyshev.splitlines()
        assert "Ripple:" not in butterworth


@pytest.mark.parametrize("category", ["lowpass", "highpass", "bandpass"])
@pytest.mark.parametrize("output_format", ["json", "csv"])
def test_machine_output_is_the_same_document_the_export_saves(category, output_format):
    state = _state(category, output_format=output_format, eseries="E24")

    lines = CALCULATORS[category](state)

    export = format_component_json if output_format == "json" else format_component_csv
    # A saved file ends with one LF, as the CLI's printed CSV and JSON do.
    assert [line + "\n" for line in lines] == [export(state)]


# ---------------------------------------------------------------------------
# Band-pass calculator and table
# ---------------------------------------------------------------------------


class TestBandpassCalculator:
    def test_table_reports_validation_and_capacitor_selection(self):
        state, output = _render("bandpass", eseries="E24")

        assert (state.result["f0"], state.result["bw"], state.result["z0"]) == (
            14.175e6,
            350e3,
            50.0,
        )
        assert state.result["n_resonators"] == 3
        lines = output.splitlines()
        assert "Butterworth Coupled Resonator Bandpass Filter" in lines
        assert "Response validation: Passed synthesized-response checks" in lines
        assert "E24 Preferred-Value Capacitor Selection" in lines
        for label in ("Cp1", "Cp3", "Ce_in", "Cs12", "Cs23", "Ce_out"):
            assert any(line.startswith(f"{label} Calculated: ") for line in lines)

    def test_raw_units_hide_preferred_value_selection(self):
        _, output = _render("bandpass", eseries="E24", raw_units=True)

        assert "Preferred-Value Capacitor Selection" not in output
        assert "│ Cp1: " in output and " F " in output

    def test_chebyshev_table_states_its_ripple(self):
        state, output = _render("bandpass", filter_type="chebyshev", ripple_db=0.5)

        assert state.result["ripple_db"] == 0.5
        assert "Ripple:              0.5 dB" in output.splitlines()

    def test_quiet_output_lists_every_named_component(self):
        state = _state("bandpass", quiet=True)

        [text] = calculate_bandpass(state)

        names = [line.split(":")[0] for line in text.splitlines()]
        assert names == ["Cp1", "Cp2", "Cp3", "L1", "L2", "L3", "Cs12", "Cs23", "Ce_in", "Ce_out"]

    def test_one_percent_plot_finds_both_threshold_skirts(self):
        _, output = _render("bandpass", frequency_hz=10e6, bandwidth_hz=100e3, show_plot=True)

        assert "Butterworth 3-pole Response" in output
        threshold_row = next(line for line in output.splitlines() if "│ -3 dB" in line)
        assert BANDPASS_WIZARD_RESPONSE_POINTS >= 601
        assert "N/A" not in threshold_row
        assert threshold_row.count("│") >= 3

    def test_fixed_tank_inductance_reaches_the_synthesis(self):
        state = _state("bandpass", resonator_inductance=1e-6)

        calculate_bandpass(state)

        assert state.result["L_resonant"] == 1e-6
        assert state.result["resonator_selection"] == "fixed_inductance"


def test_bandpass_recommendations_require_expert_action_below_one_picofarad():
    result = {"c_tank": [1e-15], "c_coupling": [], "c_end_in": None, "c_end_out": None}

    output = "\n".join(format_eseries_lines(result, "E24"))

    assert "policy selects at most one realization; expert action may be required" in output
    assert "Nearest Std (reference only)" in output
    assert "EXPERT ACTION REQUIRED; no part selected" in output
    assert "below the 1 pF automatic-selection floor" in output


class TestFormatBandpassTable:
    def test_top_c_table_lists_every_section(self, bandpass_result):
        state = FilterState(raw_units=False, show_plot=False)

        output = "\n".join(format_bandpass_table(bandpass_result, state))

        for text in (
            "Butterworth Coupled Resonator Bandpass Filter",
            "Center Frequency f₀: 14.175 MHz",
            "Lower Cutoff fₗ:     14.00108 MHz",
            "Upper Cutoff fₕ:     14.35108 MHz",
            "Bandwidth BW:        350 kHz",
            "Fractional BW:       2.47%",
            "Resonators:          3",
            "Tank Capacitors",
            "Coupling Capacitors",
            "│ Cp1: 100.00 pF",
            "│ L1: 1.00 µH",
            "│ Cs12: 10.00 pF",
            "External Q (input):  50.00",
            "complete-resonator unloaded Q",
        ):
            assert text in output
        for absent in ("Shunt", "Minimum usable Q", "Q safety factor", "Ripple:"):
            assert absent not in output

    def test_raw_units_print_si_values(self, bandpass_result):
        state = FilterState(raw_units=True, show_plot=False)

        output = "\n".join(format_bandpass_table(bandpass_result, state))

        assert "│ Cp1: 1.000000e-10 F" in output
        assert "│ L1: 1.000000e-06 H" in output
        assert "│ Cs12: 1.000000e-11 F" in output
        assert "100.00 pF" not in output

    def test_outside_envelope_status_and_warnings_are_shown(self, bandpass_result):
        result = {
            **bandpass_result,
            "response_validation_status": "outside_validated_envelope",
            "warnings": ["Bandwidth too large", "Q values may be unrealistic"],
        }

        lines = format_bandpass_table(result, FilterState(show_plot=False))

        assert "Response validation: Outside validated envelope; see warnings" in lines
        assert lines[lines.index("\nWarnings:") + 1 :][:2] == [
            "  ⚠ Bandwidth too large",
            "  ⚠ Q values may be unrealistic",
        ]

    def test_chebyshev_ripple_row(self, bandpass_result):
        result = {**bandpass_result, "filter_type": "chebyshev", "ripple_db": 0.5}

        output = "\n".join(format_bandpass_table(result, FilterState(show_plot=False)))

        assert "Chebyshev Coupled Resonator Bandpass Filter" in output
        assert "Ripple:              0.5 dB" in output


# ---------------------------------------------------------------------------
# Detached calculation outcome used by the Results worker
# ---------------------------------------------------------------------------


class TestCalculateAndFormat:
    @pytest.mark.parametrize(
        "category, title",
        [
            ("lowpass", "Low Pass"),
            ("highpass", "High Pass"),
            ("bandpass", "Bandpass"),
        ],
    )
    def test_success_is_detached_from_the_live_state(self, category, title):
        state = _state(category)

        outcome = calculate_and_format(state)

        assert outcome.succeeded
        assert title in outcome.output_text
        assert outcome.result["filter_type"] == "butterworth"
        assert (state.result, state.output_text, state.build_analysis) == ({}, "", None)

    def test_unknown_category_is_an_error_outcome(self):
        outcome = calculate_and_format(FilterState(category="bandstop"))

        assert (outcome.status, outcome.error, outcome.result) == (
            "error",
            "Unknown filter category",
            {},
        )

    def test_synthesis_error_becomes_an_error_outcome(self):
        state = _state("lowpass", frequency_hz=-1.0)

        outcome = calculate_and_format(state)

        assert outcome.status == "error"
        assert outcome.error == "Cutoff frequency must be positive and finite"
        assert not outcome.succeeded
        assert state.result == {}

    def test_table_build_analysis_is_appended_to_the_outcome(self):
        state = _state(
            "lowpass",
            eseries="E24",
            build_analysis_enabled=True,
            build_grid_points=51,
            build_use_toroid_candidates=False,
        )

        outcome = calculate_and_format(state)

        assert outcome.succeeded
        assert outcome.build_analysis.config.grid_points == 51
        for heading in (
            "Synthesis target",
            "Calculated exact values",
            "Selected nominal build",
            "Tolerance screening",
            "simulation, not a measurement",
        ):
            assert heading in outcome.output_text
        assert (state.result, state.build_analysis) == ({}, None)

    def test_cancelled_build_analysis_is_an_error_outcome_without_a_result(self):
        state = _state(
            "lowpass",
            eseries="E24",
            build_analysis_enabled=True,
            build_grid_points=51,
            build_use_toroid_candidates=False,
        )

        outcome = calculate_and_format(state, should_cancel=lambda: True)

        assert (outcome.status, outcome.error) == ("error", "Calculation cancelled")
        assert (outcome.output_text, outcome.result, outcome.build_analysis) == ("", {}, None)
        assert not outcome.succeeded

    @pytest.mark.parametrize("category", ["lowpass", "highpass"])
    def test_json_build_analysis_uses_the_shared_four_block_schema(self, category):
        state = _state(
            category,
            output_format="json",
            eseries="E24",
            build_analysis_enabled=True,
            build_grid_points=51,
            build_use_toroid_candidates=False,
        )

        outcome = calculate_and_format(state)
        payload = json.loads(outcome.output_text)

        assert outcome.succeeded
        assert payload["target"]["category"] == category
        assert payload["simulated"]["realization"] == "calculated_exact_values"
        assert (
            payload["nominal_build"]["realization"]
            == "selected_nominal_parts_and_calculated_exact_fallbacks"
        )
        assert payload["tolerance_analysis"]["grid_points"] == 51

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"output_format": "csv"}, "supported only with table or JSON component output"),
            ({"quiet": True}, "cannot be combined with quiet output"),
            ({"eseries": "none"}, "requires an E-series"),
        ],
    )
    def test_build_analysis_rejects_modes_that_cannot_show_it(self, overrides, expected):
        values = {"eseries": "E24", "build_analysis_enabled": True, **overrides}

        outcome = calculate_and_format(_state("lowpass", **values))

        assert outcome.status == "error"
        assert expected in outcome.error
        assert outcome.build_analysis is None


class TestGetSelectedRadio:
    def test_returns_the_pressed_button_id(self):
        screen = Mock()
        screen.query_one.return_value = Mock(pressed_button=Mock(id="option_a"))

        assert get_selected_radio(screen, "my-radio-set") == "option_a"
        screen.query_one.assert_called_once_with("#my-radio-set", RadioSet)

    def test_returns_empty_string_when_nothing_is_pressed(self):
        screen = Mock()
        screen.query_one.return_value = Mock(pressed_button=None)

        assert get_selected_radio(screen, "my-radio-set") == ""
