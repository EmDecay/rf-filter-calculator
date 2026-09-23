"""Designs the forms accept but the math cannot realize fail visibly, never by crashing.

The forms accept any positive finite value, so the calculation path must turn numerically
extreme designs and unexpected exceptions into an error outcome. The Results worker also
runs with ``exit_on_error=False``, so an exception that still escaped ``calculate_and_format``
is rendered on the screen instead of exiting the app.
"""

from __future__ import annotations

import asyncio
import json
import math
import sys

import pytest
from textual.widgets import Button, Static

from filter_lib.wizard.app import FilterWizardApp
from filter_lib.wizard.calculation_handler import calculate_and_format
from filter_lib.wizard.export_formatting import format_component_csv, format_component_json
from filter_lib.wizard.screens.output_options import OutputOptionsScreen
from filter_lib.wizard.screens.results import ResultsScreen
from filter_lib.wizard.state import FilterState

MAX_FLOAT = sys.float_info.max
MIN_SUBNORMAL = 5e-324
NOT_FINITE = "Inputs do not produce finite positive component values"


def _state(category: str, **overrides) -> FilterState:
    values = dict(
        category=category,
        filter_type="butterworth",
        frequency_hz=10e6,
        impedance=50.0,
        order=3,
        topology="top" if category == "bandpass" else "pi",
        show_plot=False,
        eseries="none",
    )
    if category == "bandpass":
        values["bandwidth_hz"] = 500e3
    values.update(overrides)
    return FilterState(**values)


@pytest.mark.parametrize(
    "category, overrides, message",
    [
        ("lowpass", {"frequency_hz": MIN_SUBNORMAL}, NOT_FINITE),
        (
            "highpass",
            {"impedance": MIN_SUBNORMAL, "filter_type": "chebyshev", "ripple_db": MIN_SUBNORMAL},
            NOT_FINITE,
        ),
        # The default plot cannot span a sweep above the largest float.
        (
            "lowpass",
            {"frequency_hz": MAX_FLOAT, "show_plot": True},
            "Requested frequency span must remain positive and finite",
        ),
        (
            "bandpass",
            {"frequency_hz": MAX_FLOAT, "bandwidth_hz": MAX_FLOAT / 10},
            "f0 and bw must produce positive finite band edges",
        ),
        (
            "bandpass",
            {"resonator_inductance": MAX_FLOAT},
            "resonator impedance is outside the positive finite numeric range",
        ),
        (
            "bandpass",
            {"bandwidth_hz": 9.99e6, "order": 9},
            "Bandwidth too wide to realize: derived tank capacitances must be positive and finite",
        ),
        # A subnormal bandwidth is rejected before synthesis with a message naming the
        # bandwidth and its limit; with build analysis enabled it is still an outcome.
        (
            "bandpass",
            {
                "bandwidth_hz": MIN_SUBNORMAL,
                "eseries": "E24",
                "build_analysis_enabled": True,
                "build_grid_points": 51,
            },
            "Bandwidth 4.94e-324 Hz is too narrow relative to the 1e+07 Hz center frequency "
            "to synthesize at double precision; use a fractional bandwidth of at least "
            "3.6e-12 (a bandwidth of at least 3.6e-05 Hz)",
        ),
    ],
)
def test_form_valid_extremes_become_error_outcomes(category, overrides, message):
    outcome = calculate_and_format(_state(category, **overrides))

    assert outcome.status == "error"
    assert not outcome.succeeded
    if message is None:
        assert outcome.error.strip()
    else:
        assert outcome.error == message
    assert (outcome.output_text, outcome.result, outcome.build_analysis) == ("", {}, None)


def _finite_json(text: str):
    """Parse strict JSON; ``NaN``/``Infinity`` literals are rejected."""

    def reject(constant: str):
        raise ValueError(f"non-finite JSON literal {constant}")

    return json.loads(text, parse_constant=reject)


def _component_values(node) -> list[float]:
    """Every ``value_farads``/``value_henries`` number, including preferred-value parts."""
    if isinstance(node, list):
        return [value for item in node for value in _component_values(item)]
    if not isinstance(node, dict):
        return []
    values = [value for key, value in node.items() if key.startswith("value_")]
    return values + [value for item in node.values() for value in _component_values(item)]


@pytest.mark.parametrize(
    "category, overrides",
    [
        ("lowpass", {"frequency_hz": 1e-300}),
        ("highpass", {"impedance": MAX_FLOAT}),
        ("lowpass", {"filter_type": "chebyshev", "ripple_db": MIN_SUBNORMAL, "order": 9}),
        ("bandpass", {"impedance": MAX_FLOAT}),
    ],
)
def test_realizable_extremes_export_only_finite_positive_values(category, overrides):
    state = _state(category, eseries="E24", **overrides)
    outcome = calculate_and_format(state)
    assert outcome.succeeded, outcome.error
    revision = state.begin_calculation()
    assert state.publish_success(revision, outcome.output_text, outcome.result)

    payload = _finite_json(format_component_json(state))
    format_component_csv(state)

    values = _component_values(payload["components"])
    assert len(values) >= 3
    assert all(math.isfinite(value) and value > 0 for value in values)


@pytest.mark.parametrize(
    "error, message",
    [
        (ZeroDivisionError("float division by zero"), "float division by zero"),
        (OverflowError("math range error"), "math range error"),
        (RuntimeError("   "), "RuntimeError"),
        (KeyError(), "KeyError"),
    ],
)
@pytest.mark.parametrize(
    "category, target",
    [
        ("lowpass", "filter_lib.lowpass.calculate_butterworth"),
        ("highpass", "filter_lib.highpass.calculate_butterworth"),
        ("bandpass", "filter_lib.bandpass.calculate_bandpass_filter"),
    ],
)
def test_any_synthesis_exception_becomes_an_error_outcome(
    monkeypatch, category, target, error, message
):
    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(target, fail)

    outcome = calculate_and_format(_state(category))

    assert (outcome.status, outcome.error, outcome.result) == ("error", message, {})


def test_realized_build_exception_becomes_an_error_outcome(monkeypatch):
    def fail(*_args, **_kwargs):
        raise ArithmeticError("nominal circuit diverged")

    monkeypatch.setattr("filter_lib.shared.build_simulation.analyze_build", fail)
    state = _state("lowpass", eseries="E24", build_analysis_enabled=True, build_grid_points=51)

    outcome = calculate_and_format(state)

    assert (outcome.status, outcome.error) == ("error", "nominal circuit diverged")
    assert (outcome.output_text, outcome.result, outcome.build_analysis) == ("", {}, None)


def test_calculator_that_stores_no_result_is_an_error_outcome(monkeypatch):
    monkeypatch.setattr(
        "filter_lib.wizard.filter_type_calculators.calculate_highpass",
        lambda _state: ["a table with no stored result"],
    )

    outcome = calculate_and_format(_state("highpass"))

    assert (outcome.status, outcome.error) == ("error", "Calculation returned no usable result")
    assert outcome.output_text == ""


def test_unrealizable_design_shows_its_error_in_the_running_app() -> None:
    """A worker failure is rendered on Results; the app keeps running and Esc goes back."""

    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = _state("lowpass", frequency_hz=MIN_SUBNORMAL)
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            app.push_screen(OutputOptionsScreen())
            await pilot.pause()
            app.screen.query_one("#results-btn", Button).press()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            results = app.screen
            assert isinstance(results, ResultsScreen)
            assert str(results.query_one("#results-text", Static).render()) == (
                f"Calculation failed: {NOT_FINITE}\n\nPress Esc to go back."
            )
            state = app.filter_state
            assert (state.calculation_status, state.calculation_error) == ("error", NOT_FINITE)
            assert results.query_one("#export-btn", Button).disabled is True
            assert app.return_code is None

            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, OutputOptionsScreen)
            assert state.calculation_status == "error"

    asyncio.run(exercise())


def test_worker_exception_is_rendered_without_exiting_the_app(monkeypatch) -> None:
    def fail(_snapshot, *_args, **_kwargs):
        raise RuntimeError("solver exploded")

    monkeypatch.setattr("filter_lib.wizard.screens.results.calculate_and_format", fail)

    async def exercise() -> None:
        app = FilterWizardApp()
        app.filter_state = _state("lowpass")
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            app.push_screen(ResultsScreen())
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert app.return_code is None
            assert str(app.screen.query_one("#results-text", Static).render()) == (
                "Calculation failed: solver exploded\n\nPress Esc to go back."
            )
            assert app.filter_state.calculation_status == "error"
            assert app.screen.query_one("#export-btn", Button).disabled is True

    asyncio.run(exercise())
