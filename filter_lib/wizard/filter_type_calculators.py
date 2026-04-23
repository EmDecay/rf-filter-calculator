"""Filter-specific calculation and formatting logic.

Separated from calculation_handler.py for better organization.
Contains lowpass, highpass, and bandpass calculation implementations.
"""

from .state import FilterState


def calculate_lowpass(state: FilterState) -> list[str]:
    """Calculate lowpass filter and return formatted output lines."""
    from filter_lib.lowpass import calculate_bessel, calculate_butterworth, calculate_chebyshev
    from filter_lib.lowpass.display import format_csv, format_json, format_quiet
    from filter_lib.lowpass.transfer import frequency_response, generate_frequency_points
    from filter_lib.shared.formatting import format_capacitance
    from filter_lib.shared.plotting import (
        find_db_thresholds,
        format_threshold_table,
        render_plot_pair,
    )

    from .formatting_helpers import format_eseries_recs, format_lp_hp_table

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

    lines = format_lp_hp_table(result, state, "Low Pass")

    if state.eseries != "none" and not state.raw_units:
        lines.extend(
            format_eseries_recs(
                result["capacitors"], "C", "Capacitor", state.eseries, format_capacitance
            )
        )

    if state.show_plot:
        from filter_lib.shared.transfer_response_dispatch import make_lp_response_db

        freqs = generate_frequency_points(result["freq_hz"])
        ripple_val = result.get("ripple") or 0.5
        response = frequency_response(
            result["filter_type"], freqs, result["freq_hz"], result["order"], ripple_val
        )
        cutoff = result["freq_hz"]
        response_fn = make_lp_response_db(
            result["filter_type"], cutoff, result["order"], ripple_val
        )
        lines.append("")
        lines.append(
            render_plot_pair(
                freqs,
                response,
                cutoff,
                filter_type="lowpass",
                ripple_db=ripple_val,
                response_fn=response_fn,
            )
        )
        thresholds = find_db_thresholds(freqs, response, filter_type="lowpass")
        lines.append(format_threshold_table(thresholds, filter_type="lowpass"))
    return lines


def calculate_highpass(state: FilterState) -> list[str]:
    """Calculate highpass filter and return formatted output lines."""
    from filter_lib.highpass import calculate_bessel, calculate_butterworth, calculate_chebyshev
    from filter_lib.highpass.display import format_csv, format_json, format_quiet
    from filter_lib.highpass.transfer import frequency_response, generate_frequency_points
    from filter_lib.shared.formatting import format_inductance
    from filter_lib.shared.plotting import (
        find_db_thresholds,
        format_threshold_table,
        render_plot_pair,
    )

    from .formatting_helpers import format_eseries_recs, format_lp_hp_table

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

    lines = format_lp_hp_table(result, state, "High Pass")

    if state.eseries != "none" and not state.raw_units:
        lines.extend(
            format_eseries_recs(
                result["inductors"], "L", "Inductor", state.eseries, format_inductance
            )
        )

    if state.show_plot:
        from filter_lib.shared.transfer_response_dispatch import make_hp_response_db

        freqs = generate_frequency_points(result["freq_hz"])
        ripple_val = result.get("ripple") or 0.5
        response = frequency_response(
            result["filter_type"], freqs, result["freq_hz"], result["order"], ripple_val
        )
        cutoff = result["freq_hz"]
        response_fn = make_hp_response_db(
            result["filter_type"], cutoff, result["order"], ripple_val
        )
        lines.append("")
        lines.append(
            render_plot_pair(
                freqs,
                response,
                cutoff,
                filter_type="highpass",
                ripple_db=ripple_val,
                response_fn=response_fn,
            )
        )
        thresholds = find_db_thresholds(freqs, response, filter_type="highpass")
        lines.append(format_threshold_table(thresholds, filter_type="highpass"))
    return lines


def calculate_bandpass(state: FilterState) -> list[str]:
    """Calculate bandpass filter and return formatted output lines."""
    from filter_lib.bandpass import calculate_bandpass_filter
    from filter_lib.bandpass.formatters import format_csv, format_json, format_quiet
    from filter_lib.bandpass.transfer import frequency_sweep
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
        from filter_lib.shared.transfer_response_dispatch import make_bp_response_db

        ripple_val = result.get("ripple_db") or 0.5
        sweep = frequency_sweep(
            result["f0"],
            result["bw"],
            result["n_resonators"],
            result["filter_type"],
            ripple_db=ripple_val,
            points=61,
        )
        title = f"{result['filter_type'].title()} {result['n_resonators']}-pole Response"
        response_fn = make_bp_response_db(
            result["f0"],
            result["bw"],
            result["n_resonators"],
            result["filter_type"],
            ripple_val,
        )
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
