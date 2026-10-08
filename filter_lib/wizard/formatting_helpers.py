"""Compatibility helper for rendering a bandpass table from wizard state.

The shared dispatcher renders every wizard table; ``FilterState.to_render_options``
maps the wizard's choices onto it.
"""

from dataclasses import replace

from .state import FilterState


def format_bandpass_table(result: dict, state: FilterState) -> list[str]:
    """Return the CLI's bandpass table lines for ``result`` under the wizard's options.

    The wizard's sub-pF switch is carried too, so the E-series rows match the real path.
    """
    from filter_lib.design import DesignResult, render_lines

    options = replace(state.to_render_options(), output_format="table")
    outcome = DesignResult(category="bandpass", result=result, allow_sub_pf=state.allow_sub_pf)
    return render_lines(outcome, options)
