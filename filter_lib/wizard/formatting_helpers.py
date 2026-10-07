"""Compatibility helper for rendering a bandpass table from wizard state.

The shared dispatcher renders every wizard table; ``FilterState.to_render_options``
maps the wizard's choices onto it.
"""

from dataclasses import replace

from .state import FilterState


def format_bandpass_table(result: dict, state: FilterState) -> list[str]:
    """Return the CLI's bandpass table lines for ``result`` under the wizard's options."""
    from filter_lib.design import DesignResult, render_lines

    options = replace(state.to_render_options(), output_format="table")
    return render_lines(DesignResult(category="bandpass", result=result), options)
