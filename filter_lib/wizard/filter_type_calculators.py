"""Filter-specific calculation entry points for the wizard.

Contract shared by all three calculators: design the filter from the FilterState the
screens populated through the shared ``filter_lib.design`` service, stash the raw
result dict on `state.result` (the results screen's export paths re-format it later),
and return display lines rendered by the shared dispatcher.
"""

from filter_lib.design.export import BANDPASS_RESPONSE_POINTS

from .state import FilterState

# Kept for callers that size the wizard's response export; the shared export owns it.
BANDPASS_WIZARD_RESPONSE_POINTS = BANDPASS_RESPONSE_POINTS


def _calculate(state: FilterState) -> list[str]:
    """Synthesize without build analysis, store the result, and render it."""
    from filter_lib.design import design, render_lines

    outcome = design(state.to_design_request(include_build=False))
    # Keep the raw result so the results screen can export JSON/CSV/response
    # data later without re-running the synthesis.
    state.result = outcome.result
    return render_lines(outcome, state.to_render_options())


def calculate_lowpass(state: FilterState) -> list[str]:
    """Calculate a lowpass filter and return output lines for `state.output_format`."""
    return _calculate(state)


def calculate_highpass(state: FilterState) -> list[str]:
    """Calculate a highpass filter and return output lines for `state.output_format`."""
    return _calculate(state)


def calculate_bandpass(state: FilterState) -> list[str]:
    """Calculate a bandpass filter and return output lines for `state.output_format`.

    `state.topology` carries the coupling id ("top") and `state.order` the resonator
    count.
    """
    return _calculate(state)
