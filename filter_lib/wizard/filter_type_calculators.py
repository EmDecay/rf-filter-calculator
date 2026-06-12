"""Filter-specific calculation and formatting logic.

Separated from calculation_handler.py for better organization.
Contains lowpass, highpass, and bandpass calculation implementations.
"""

from .state import FilterState


def calculate_lowpass(state: FilterState) -> list[str]:
    """Calculate lowpass filter and return formatted output lines."""
    from filter_lib.lowpass import calculate_bessel, calculate_butterworth, calculate_chebyshev
    from filter_lib.lowpass.display import (
        LOWPASS_DISPLAY_CONFIG,
        LP_WIZARD_MATCH,
        format_csv,
        format_json,
        format_quiet,
    )
    from filter_lib.shared.lp_hp_display import LpHpRenderOptions, render_results_lines

    # Calculate component values
    if state.filter_type == "butterworth":
        caps, inds, order = calculate_butterworth(
            state.frequency_hz, state.impedance, state.order, state.topology
        )
        ripple = None
    elif state.filter_type == "chebyshev":
        caps, inds, order = calculate_chebyshev(
            state.frequency_hz, state.impedance, state.ripple_db, state.order, state.topology
        )
        ripple = state.ripple_db
    else:  # bessel
        caps, inds, order = calculate_bessel(
            state.frequency_hz, state.impedance, state.order, state.topology
        )
        ripple = None

    result = {
        "filter_type": state.filter_type,
        "freq_hz": state.frequency_hz,
        "impedance": state.impedance,
        "capacitors": caps,
        "inductors": inds,
        "order": order,
        "ripple": ripple,
        "topology": state.topology,
    }
    state.result = result

    eseries = None if state.eseries == "none" else state.eseries

    if state.output_format == "json":
        return [format_json(result, eseries=eseries)]
    if state.output_format == "csv":
        return [format_csv(result, eseries=eseries)]
    if state.quiet:
        return [format_quiet(result, state.raw_units)]

    return render_results_lines(
        result,
        LpHpRenderOptions(
            config=LOWPASS_DISPLAY_CONFIG,
            raw=state.raw_units,
            eseries=eseries,
            show_match=eseries is not None,
            show_plot=state.show_plot,
            include_toroids=False,
            match=LP_WIZARD_MATCH,
            trailing_blank=False,
        ),
    )


def calculate_highpass(state: FilterState) -> list[str]:
    """Calculate highpass filter and return formatted output lines."""
    from filter_lib.highpass import calculate_bessel, calculate_butterworth, calculate_chebyshev
    from filter_lib.highpass.display import (
        HIGHPASS_DISPLAY_CONFIG,
        HP_WIZARD_MATCH,
        format_csv,
        format_json,
        format_quiet,
    )
    from filter_lib.shared.lp_hp_display import LpHpRenderOptions, render_results_lines

    if state.filter_type == "butterworth":
        inds, caps, order = calculate_butterworth(
            state.frequency_hz, state.impedance, state.order, state.topology
        )
        ripple = None
    elif state.filter_type == "chebyshev":
        inds, caps, order = calculate_chebyshev(
            state.frequency_hz, state.impedance, state.ripple_db, state.order, state.topology
        )
        ripple = state.ripple_db
    else:  # bessel
        inds, caps, order = calculate_bessel(
            state.frequency_hz, state.impedance, state.order, state.topology
        )
        ripple = None

    result = {
        "filter_type": state.filter_type,
        "freq_hz": state.frequency_hz,
        "impedance": state.impedance,
        "inductors": inds,
        "capacitors": caps,
        "order": order,
        "ripple": ripple,
        "topology": state.topology,
    }
    state.result = result

    eseries = None if state.eseries == "none" else state.eseries

    if state.output_format == "json":
        return [format_json(result, eseries=eseries)]
    if state.output_format == "csv":
        return [format_csv(result, eseries=eseries)]
    if state.quiet:
        return [format_quiet(result, state.raw_units)]

    return render_results_lines(
        result,
        LpHpRenderOptions(
            config=HIGHPASS_DISPLAY_CONFIG,
            raw=state.raw_units,
            eseries=eseries,
            show_match=eseries is not None,
            show_plot=state.show_plot,
            include_toroids=False,
            match=HP_WIZARD_MATCH,
            trailing_blank=False,
        ),
    )


def calculate_bandpass(state: FilterState) -> list[str]:
    """Calculate bandpass filter and return formatted output lines."""
    from filter_lib.bandpass import calculate_bandpass_filter
    from filter_lib.bandpass.formatters import format_csv, format_json, format_quiet
    from filter_lib.bandpass.transfer import netlist_frequency_sweep
    from filter_lib.shared.plotting import (
        find_db_thresholds,
        format_threshold_table,
        render_bandpass_plot_pair,
    )

    from .formatting_helpers import format_bandpass_eseries_recs, format_bandpass_table

    result = calculate_bandpass_filter(
        f0=state.frequency_hz,
        bw=state.bandwidth_hz,
        z0=state.impedance,
        n_resonators=state.order,
        filter_type=state.filter_type,
        coupling=state.topology,
        ripple_db=state.ripple_db,
    )
    state.result = result

    eseries = None if state.eseries == "none" else state.eseries

    if state.output_format == "json":
        return [format_json(result, eseries=eseries)]
    if state.output_format == "csv":
        return [format_csv(result, eseries=eseries)]
    if state.quiet:
        return [format_quiet(result, state.raw_units)]

    lines = format_bandpass_table(result, state)

    if state.eseries != "none" and not state.raw_units:
        lines.extend(format_bandpass_eseries_recs(result, state.eseries))

    if state.show_plot:
        from filter_lib.shared.transfer_response_dispatch import make_bp_netlist_response_db

        ripple_val = result.get("ripple_db") or 0.5
        sweep = netlist_frequency_sweep(result, points=61)
        title = f"{result['filter_type'].title()} {result['n_resonators']}-pole Response"
        response_fn = make_bp_netlist_response_db(result)
        lines.append("")
        lines.append(
            render_bandpass_plot_pair(
                sweep,
                result["f0"],
                result["bw"],
                f_low_hz=result["f_low"],
                f_high_hz=result["f_high"],
                title=title,
                ripple_db=ripple_val,
                response_fn=response_fn,
            )
        )
        freqs = [f for f, _ in sweep]
        dbs = [db for _, db in sweep]
        thresholds = find_db_thresholds(freqs, dbs, filter_type="bandpass")
        lines.append(format_threshold_table(thresholds, filter_type="bandpass"))

    return lines
