"""Filter-specific calculation entry points for the wizard.

Contract shared by all three calculators: design the filter from the FilterState the
screens populated through the shared ``filter_lib.design`` service, stash the design
result on the state (the results screen's export paths re-format it later), and return
display lines rendered by the shared dispatcher.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from filter_lib.design.export import BANDPASS_RESPONSE_POINTS

from .state import FilterState

if TYPE_CHECKING:
    from filter_lib.design import DesignResult

# Kept for callers that size the wizard's response export; the shared export owns it.
BANDPASS_WIZARD_RESPONSE_POINTS = BANDPASS_RESPONSE_POINTS


def design_from_state(
    state: FilterState, should_cancel: Callable[[], bool] | None = None
) -> DesignResult:
    """Design the result shown (with its build simulation, if any) and store it on ``state``.

    The design result is kept so the results screen can save JSON, CSV, and response
    data later without designing again when their request is the same.
    """
    from filter_lib.design import design

    outcome = design(state.to_design_request(), should_cancel=should_cancel)
    state.result = outcome.result
    state.build_analysis = outcome.build_analysis
    state.design_outcome = outcome
    return outcome


def _calculate(state: FilterState, should_cancel: Callable[[], bool] | None) -> list[str]:
    """Design the result shown, store it, and render it."""
    from filter_lib.design import render_lines

    return render_lines(design_from_state(state, should_cancel), state.to_render_options())


def calculate_lowpass(
    state: FilterState, should_cancel: Callable[[], bool] | None = None
) -> list[str]:
    """Calculate a lowpass filter and return output lines for `state.output_format`."""
    return _calculate(state, should_cancel)


def calculate_highpass(
    state: FilterState, should_cancel: Callable[[], bool] | None = None
) -> list[str]:
    """Calculate a highpass filter and return output lines for `state.output_format`."""
    return _calculate(state, should_cancel)


def calculate_bandpass(
    state: FilterState, should_cancel: Callable[[], bool] | None = None
) -> list[str]:
    """Calculate a bandpass filter and return output lines for `state.output_format`.

    `state.topology` carries the coupling id ("top") and `state.order` the resonator
    count.
    """
    return _calculate(state, should_cancel)
