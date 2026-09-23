"""Formatting helpers for wizard calculation output.

The wizard renders band-pass tables with the CLI's renderer,
``bandpass.display.format_table_lines``; this module only maps the wizard
state onto its options. LP/HP rendering goes through shared.lp_hp_display.
"""

from .state import FilterState


def format_bandpass_table(result: dict, state: FilterState) -> list[str]:
    """Format bandpass filter results as the CLI's table lines.

    Args:
        result: Bandpass result dict from calculate_bandpass_filter
        state: Wizard state supplying raw units, E-series, plot, and toroid detail

    Returns:
        Display lines: design header, warnings, Q figures, topology diagram,
        component tables, preferred values, toroid windings, and the optional
        plot, exactly as ``filter-calc bandpass`` prints them.
    """
    from filter_lib.bandpass.display import format_table_lines

    return format_table_lines(
        result,
        raw=state.raw_units,
        eseries=None if state.eseries == "none" else state.eseries,
        show_plot=state.show_plot,
        # The wizard always shows windings; its detail choice maps onto the CLI flags.
        include_toroids=True,
        toroid_compact=state.toroid_detail == "compact",
        toroid_full=state.toroid_detail == "full",
    )
