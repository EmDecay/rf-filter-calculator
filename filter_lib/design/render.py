"""Single text renderer for design results: table, quiet, JSON, and CSV.

The category formatters below stay the source of truth for each format; this module
only selects them and places the realized-build analysis, so the CLI, wizard, and web
emit the same bytes for the same options.
"""

from __future__ import annotations

from types import ModuleType

from .design_result import DesignResult
from .render_options import RenderOptions

BUILD_TARGET_NOTE = (
    "Above: the ideal design. Below: a simulation of building it with the chosen parts."
)


def _formatters(category: str) -> ModuleType:
    """Return the module providing ``format_json``/``format_csv``/``format_quiet``."""
    if category == "lowpass":
        from ..lowpass import display
    elif category == "highpass":
        from ..highpass import display
    elif category == "bandpass":
        from ..bandpass import formatters as display
    else:
        raise ValueError("Unknown filter category")
    return display


def _table_lines(outcome: DesignResult, options: RenderOptions) -> list[str]:
    if outcome.category == "bandpass":
        from ..bandpass.display import format_table_lines

        return format_table_lines(
            outcome.result, outcome.parts, raw=options.raw, show_plot=options.show_plot
        )

    from ..shared.lp_hp_display import CAPACITOR_MATCH, LpHpRenderOptions, render_results_lines

    display = _formatters(outcome.category)
    config = (
        display.LOWPASS_DISPLAY_CONFIG
        if outcome.category == "lowpass"
        else display.HIGHPASS_DISPLAY_CONFIG
    )
    return render_results_lines(
        outcome.result,
        LpHpRenderOptions(
            config=config,
            parts=outcome.parts,
            raw=options.raw,
            show_plot=options.show_plot,
            match=CAPACITOR_MATCH,
            trailing_blank=False,
        ),
    )


def render_lines(outcome: DesignResult, options: RenderOptions) -> list[str]:
    """Render ``outcome`` as output lines; join with ``\\n`` to get the document.

    Machine formats return one element without a trailing newline. Table output
    appends the realized-build block when the outcome carries one. Every format reads
    the outcome's resolved parts; how much of the inductor suggestions the table shows
    is the request's ``inductor_suggestions``.
    """
    build_analysis = outcome.build_analysis
    if build_analysis is not None:
        options.validate_for_build()
    display = _formatters(outcome.category)
    result = outcome.result

    if options.output_format == "json":
        return [display.format_json(result, outcome.parts, build_analysis=build_analysis)]
    if options.output_format == "csv":
        return [display.format_csv(result, outcome.parts)]
    if options.output_format == "quiet":
        return [display.format_quiet(result, options.raw)]

    lines = _table_lines(outcome, options)
    if options.trailing_blank:
        lines.append("")
    if build_analysis is not None:
        from ..shared.build_output import format_build_analysis_block

        if options.build_target_note:
            lines.extend(("", BUILD_TARGET_NOTE))
        lines.extend(format_build_analysis_block(build_analysis))
    return lines
