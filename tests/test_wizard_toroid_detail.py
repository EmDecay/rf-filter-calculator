"""Wizard table output carries the screened toroid section at the chosen detail level.

"best" is the CLI default (the best candidate, detailed); "full" mirrors the CLI's
--toroid-full (up to three multi-line candidates); "compact" mirrors --toroid-compact
(one line for the best candidate); "none" is --no-toroids. JSON and CSV keep their own
fixed candidate contracts regardless of the table choice.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import replace

import pytest
from textual.widgets import RadioSet

from filter_lib.bandpass.display import format_toroid_block_lines
from filter_lib.shared.toroid_selection import recommend_cores
from filter_lib.wizard.app import FilterWizardApp
from filter_lib.wizard.filter_type_calculators import (
    calculate_bandpass,
    calculate_highpass,
    calculate_lowpass,
)
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.state import FilterState, ToroidDetail

TOROID_HEADER = "Toroid Winding Suggestions (iron-powder T-series)"
ACCURACY_NOTE = "L range: the same turns across the core's ±5% A_L tolerance."
NOT_ASSESSED_NOTE = (
    "Not checked: RF Q, core loss, SRF, saturation, heating, power handling. Measure before use."
)
INDUCTOR_NOTE = (
    "Inductors: no standard values; wind to the calculated value (see Toroid Winding Suggestions)."
)
# Ranked candidate rows in both detail levels start "  1. ", "  2. ", ...
CANDIDATE_ROW = re.compile(r"^  \d\. ")

LP_HP_CALCULATORS = {"lowpass": calculate_lowpass, "highpass": calculate_highpass}


def _lp_hp_state(category: str, toroid_detail: ToroidDetail = "full", **overrides) -> FilterState:
    state = FilterState(
        category=category,
        filter_type="butterworth",
        frequency_hz=10e6,
        impedance=50.0,
        order=5,
        topology="pi",
        output_format="table",
        eseries="E24",
        show_plot=False,
        toroid_detail=toroid_detail,
    )
    return replace(state, **overrides)


def _bp_state(toroid_detail: ToroidDetail = "full", **overrides) -> FilterState:
    state = FilterState(
        category="bandpass",
        filter_type="butterworth",
        topology="top",
        frequency_hz=10e6,
        bandwidth_hz=500e3,
        impedance=50.0,
        order=3,
        output_format="table",
        eseries="E24",
        show_plot=False,
        toroid_detail=toroid_detail,
    )
    return replace(state, **overrides)


def _candidate_rows(lines: list[str]) -> list[str]:
    return [line for line in "\n".join(lines).splitlines() if CANDIDATE_ROW.match(line)]


@pytest.mark.parametrize("category", ["lowpass", "highpass"])
def test_lp_hp_full_detail_lists_up_to_three_candidates_per_inductor(category):
    state = _lp_hp_state(category)
    lines = LP_HP_CALCULATORS[category](state)
    output = "\n".join(lines)

    inductors = state.result["inductors"]
    expected = sum(len(recommend_cores(value, 10e6, top_n=3)) for value in inductors)
    assert expected > len(inductors), "fixture must exercise more than one candidate"
    assert TOROID_HEADER in output
    assert ACCURACY_NOTE in output
    assert output.count(NOT_ASSESSED_NOTE) == 1
    assert INDUCTOR_NOTE in output
    for index in range(len(inductors)):
        assert f"L{index + 1} target:" in output
    assert len(_candidate_rows(lines)) == expected
    assert output.count("     Wire: ") == expected


@pytest.mark.parametrize("category", ["lowpass", "highpass"])
def test_lp_hp_compact_detail_is_one_line_for_best_candidate(category):
    state = _lp_hp_state(category, toroid_detail="compact")
    lines = LP_HP_CALCULATORS[category](state)
    output = "\n".join(lines)

    inductors = state.result["inductors"]
    expected = sum(len(recommend_cores(value, 10e6, top_n=1)) for value in inductors)
    assert expected == len(inductors)
    assert TOROID_HEADER in output
    assert ACCURACY_NOTE not in output
    assert output.count(NOT_ASSESSED_NOTE) == 1
    assert "     Wire: " not in output
    rows = _candidate_rows(lines)
    assert len(rows) == expected
    assert all(row.startswith("  1. ") and " turns AWG " in row for row in rows)


@pytest.mark.parametrize(("toroid_detail", "top_n"), [("full", 3), ("compact", 1)])
def test_bandpass_table_includes_cli_toroid_block_at_selected_detail(
    toroid_detail: ToroidDetail, top_n: int
):
    state = _bp_state(toroid_detail)
    lines = calculate_bandpass(state)

    compact = toroid_detail == "compact"
    # Same lines the CLI prints, minus the section's trailing blank.
    block = format_toroid_block_lines(state.result, compact, top_n)[:-1]
    start = lines.index(block[1]) - 1
    assert lines[start : start + len(block)] == block
    assert any("L1–L3 (all equal) target:" in line for line in block)
    expected = len(recommend_cores(state.result["L_resonant"], state.result["f0"], top_n=top_n))
    assert expected >= 1
    assert len(_candidate_rows(lines)) == expected
    assert INDUCTOR_NOTE in lines


def test_bandpass_toroid_block_sits_between_eseries_section_and_plot():
    lines = calculate_bandpass(_bp_state(show_plot=True))
    output = "\n".join(lines)

    eseries_at = output.index("E24 Standard Capacitor Values")
    toroid_at = output.index(TOROID_HEADER)
    plot_at = output.index("Simulated Response, ideal parts (dB): Butterworth, 3 resonators")
    assert eseries_at < toroid_at < plot_at


def test_bandpass_json_keeps_up_to_three_candidates_regardless_of_table_detail():
    state = _bp_state("compact", output_format="json")
    payload = json.loads(calculate_bandpass(state)[0])

    expected = recommend_cores(state.result["L_resonant"], state.result["f0"], top_n=3)
    assert len(payload["resonator_toroid_candidates"]) == len(expected)


def test_toroid_detail_choice_flows_from_output_options_to_results():
    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = _lp_hp_state("lowpass")
        async with app.run_test(size=(120, 80)) as pilot:
            await pilot.pause()
            app.push_screen(OutputOptionsScreen())
            await pilot.pause()

            detail = app.screen.query_one("#toroid-detail", RadioSet)
            assert detail.pressed_button is not None
            assert detail.pressed_button.id == "toroid-full"

            # Keyboard path: Enter from the sub-pF box lands on the toroid choice,
            # arrow keys move within it, and space selects.
            app.screen.query_one("#allow-sub-pf").focus()
            await pilot.press("enter")
            assert detail.has_focus
            await pilot.press("down", "space")
            await pilot.pause()
            assert detail.pressed_button.id == "toroid-compact"
            await pilot.press("enter")
            assert app.screen.query_one("#plot").has_focus

            app.screen.query_one("#results-btn").focus()
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            state = app.filter_state
            assert state.toroid_detail == "compact"
            assert state.calculation_status == "success"
            assert TOROID_HEADER in state.output_text
            assert ACCURACY_NOTE not in state.output_text
            assert "     Wire: " not in state.output_text

    asyncio.run(exercise())
