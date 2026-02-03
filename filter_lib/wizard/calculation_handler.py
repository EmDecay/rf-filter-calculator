"""Calculation and formatting logic for wizard results."""
from .state import FilterState


def calculate_and_format(state: FilterState) -> str:
    """Perform filter calculation and return formatted output text.

    Args:
        state: FilterState with all parameters configured

    Returns:
        Formatted output string for display
    """
    try:
        if state.category == "lowpass":
            lines = _calculate_lowpass(state)
        elif state.category == "highpass":
            lines = _calculate_highpass(state)
        elif state.category == "bandpass":
            lines = _calculate_bandpass(state)
        else:
            lines = ["Unknown filter category"]
    except Exception as e:
        lines = [f"Calculation error: {e}"]

    return '\n'.join(lines)


def _calculate_lowpass(state: FilterState) -> list[str]:
    """Calculate lowpass filter and return formatted output lines."""
    from filter_lib.lowpass import (
        calculate_butterworth, calculate_chebyshev, calculate_bessel
    )
    from filter_lib.lowpass.display import format_json, format_csv, format_quiet
    from filter_lib.lowpass.transfer import frequency_response, generate_frequency_points
    from filter_lib.shared.formatting import format_capacitance
    from filter_lib.shared.display_helpers import format_eseries_match
    from filter_lib.shared.plotting import render_ascii_plot

    # Calculate component values
    if state.filter_type == "butterworth":
        caps, inds, order = calculate_butterworth(
            state.frequency_hz, state.impedance, state.order, state.topology
        )
        ripple = None
    elif state.filter_type == "chebyshev":
        caps, inds, order = calculate_chebyshev(
            state.frequency_hz, state.impedance, state.ripple_db,
            state.order, state.topology
        )
        ripple = state.ripple_db
    else:  # bessel
        caps, inds, order = calculate_bessel(
            state.frequency_hz, state.impedance, state.order, state.topology
        )
        ripple = None

    result = {
        'filter_type': state.filter_type,
        'freq_hz': state.frequency_hz,
        'impedance': state.impedance,
        'capacitors': caps,
        'inductors': inds,
        'order': order,
        'ripple': ripple,
        'topology': state.topology,
    }
    state.result = result

    if state.output_format == 'json':
        return [format_json(result)]
    if state.output_format == 'csv':
        return [format_csv(result)]
    if state.quiet:
        return [format_quiet(result, state.raw_units)]

    lines = _format_lp_hp_table(result, state, 'Low Pass')

    if state.eseries != "none" and not state.raw_units:
        lines.extend(_format_eseries_recs(
            result['capacitors'], 'C', 'Capacitor',
            state.eseries, format_capacitance
        ))

    if state.show_plot:
        freqs = generate_frequency_points(result['freq_hz'])
        ripple_val = result.get('ripple') or 0.5
        response = frequency_response(
            result['filter_type'], freqs, result['freq_hz'],
            result['order'], ripple_val
        )
        lines.append("")
        lines.append(render_ascii_plot(freqs, response, result['freq_hz'],
                                       filter_type='lowpass'))
    return lines


def _calculate_highpass(state: FilterState) -> list[str]:
    """Calculate highpass filter and return formatted output lines."""
    from filter_lib.highpass import (
        calculate_butterworth, calculate_chebyshev, calculate_bessel
    )
    from filter_lib.highpass.display import format_json, format_csv, format_quiet
    from filter_lib.highpass.transfer import frequency_response, generate_frequency_points
    from filter_lib.shared.formatting import format_inductance
    from filter_lib.shared.display_helpers import format_eseries_match
    from filter_lib.shared.plotting import render_ascii_plot

    if state.filter_type == "butterworth":
        inds, caps, order = calculate_butterworth(
            state.frequency_hz, state.impedance, state.order, state.topology
        )
        ripple = None
    elif state.filter_type == "chebyshev":
        inds, caps, order = calculate_chebyshev(
            state.frequency_hz, state.impedance, state.ripple_db,
            state.order, state.topology
        )
        ripple = state.ripple_db
    else:  # bessel
        inds, caps, order = calculate_bessel(
            state.frequency_hz, state.impedance, state.order, state.topology
        )
        ripple = None

    result = {
        'filter_type': state.filter_type,
        'freq_hz': state.frequency_hz,
        'impedance': state.impedance,
        'inductors': inds,
        'capacitors': caps,
        'order': order,
        'ripple': ripple,
        'topology': state.topology,
    }
    state.result = result

    if state.output_format == 'json':
        return [format_json(result)]
    if state.output_format == 'csv':
        return [format_csv(result)]
    if state.quiet:
        return [format_quiet(result, state.raw_units)]

    lines = _format_lp_hp_table(result, state, 'High Pass')

    if state.eseries != "none" and not state.raw_units:
        lines.extend(_format_eseries_recs(
            result['inductors'], 'L', 'Inductor',
            state.eseries, format_inductance
        ))

    if state.show_plot:
        freqs = generate_frequency_points(result['freq_hz'])
        ripple_val = result.get('ripple') or 0.5
        response = frequency_response(
            result['filter_type'], freqs, result['freq_hz'],
            result['order'], ripple_val
        )
        lines.append("")
        lines.append(render_ascii_plot(freqs, response, result['freq_hz'],
                                       filter_type='highpass'))
    return lines


def _calculate_bandpass(state: FilterState) -> list[str]:
    """Calculate bandpass filter and return formatted output lines."""
    from filter_lib.bandpass import calculate_bandpass_filter
    from filter_lib.bandpass.formatters import format_json, format_csv, format_quiet
    from filter_lib.bandpass.transfer import frequency_sweep
    from filter_lib.shared.plotting import render_bandpass_plot

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

    if state.output_format == 'json':
        return [format_json(result)]
    if state.output_format == 'csv':
        return [format_csv(result)]
    if state.quiet:
        return [format_quiet(result, state.raw_units)]

    lines = _format_bandpass_table(result, state)

    if state.show_plot:
        sweep = frequency_sweep(
            result['f0'], result['bw'], result['n_resonators'],
            result['filter_type'],
            ripple_db=result.get('ripple_db') or 0.5,
            points=61
        )
        title = f"{result['filter_type'].title()} {result['n_resonators']}-pole Response"
        lines.append("")
        lines.append(render_bandpass_plot(sweep, result['f0'], result['bw'], title=title))

    return lines


def _format_lp_hp_table(result: dict, state: FilterState, category: str) -> list[str]:
    """Format table output for lowpass/highpass filters."""
    from filter_lib.shared.formatting import (
        format_frequency, format_capacitance, format_inductance
    )
    from filter_lib.shared.topology_diagrams import (
        format_pi_topology_diagram, format_t_topology_diagram
    )

    lines = []
    topology = result.get('topology', 'pi')
    title = f"{result['filter_type'].title()} {topology.upper()} {category} Filter"
    lines.append(f"\n{title}")
    lines.append("=" * 50)
    lines.append(f"Cutoff Frequency:    {format_frequency(result['freq_hz'])}")
    lines.append(f"Impedance Z0:        {result['impedance']:.4g} Ohm")
    if result.get('ripple') is not None:
        lines.append(f"Ripple:              {result['ripple']} dB")
    lines.append(f"Order:               {result['order']}")
    lines.append("=" * 50)

    n_caps = len(result['capacitors'])
    n_inds = len(result['inductors'])
    lines.append("\nTopology:")
    if topology == 'pi':
        lines.append(format_pi_topology_diagram(n_caps, n_inds))
    else:
        lines.append(format_t_topology_diagram(n_inds, n_caps))

    lines.append(_format_component_table(result, state.raw_units))
    return lines


def _format_component_table(result: dict, raw: bool) -> str:
    """Format component values as a table."""
    from filter_lib.shared.formatting import format_capacitance, format_inductance

    col_width = 24
    caps = result['capacitors']
    inds = result['inductors']
    max_rows = max(len(caps), len(inds))

    lines = []
    lines.append(f"\n{'Component Values':^50}")
    lines.append(f"\u250c{'\u2500' * col_width}\u252c{'\u2500' * col_width}\u2510")
    lines.append(f"\u2502{'Capacitors':^{col_width}}\u2502{'Inductors':^{col_width}}\u2502")
    lines.append(f"\u251c{'\u2500' * col_width}\u253c{'\u2500' * col_width}\u2524")

    for i in range(max_rows):
        cap_str = ""
        ind_str = ""
        if i < len(caps):
            val = caps[i]
            cap_str = f"C{i+1}: {val:.6e} F" if raw else f"C{i+1}: {format_capacitance(val)}"
        if i < len(inds):
            val = inds[i]
            ind_str = f"L{i+1}: {val:.6e} H" if raw else f"L{i+1}: {format_inductance(val)}"
        lines.append(f"\u2502 {cap_str:<{col_width-2}} \u2502 {ind_str:<{col_width-2}} \u2502")

    lines.append(f"\u2514{'\u2500' * col_width}\u2534{'\u2500' * col_width}\u2518")
    return '\n'.join(lines)


def _format_eseries_recs(components: list, prefix: str, name: str,
                         eseries: str, formatter) -> list[str]:
    """Format E-series recommendations for components."""
    from filter_lib.shared.display_helpers import format_eseries_match

    lines = []
    lines.append(f"\n{eseries} Standard {name} Recommendations")
    lines.append("-" * 45)
    lines.append("(Calculated values with nearest standard matches)")
    lines.append("")
    for i, val in enumerate(components):
        lines.append(f"{prefix}{i+1} Calculated: {formatter(val)}")
        for line in format_eseries_match(val, eseries, formatter):
            lines.append(line)
    return lines


def _format_bandpass_table(result: dict, state: FilterState) -> list[str]:
    """Format bandpass filter results as table."""
    from filter_lib.shared.formatting import format_frequency, format_capacitance, format_inductance
    from filter_lib.bandpass.diagrams import format_top_c_diagram, format_shunt_c_diagram

    lines = []
    coupling = result.get('coupling', 'top')
    coupling_name = "Top-C Coupled" if coupling == 'top' else "Shunt-C Coupled"
    title = f"{result['filter_type'].title()} {coupling_name} Band-Pass Filter"
    lines.append(f"\n{title}")
    lines.append("=" * 60)
    lines.append(f"Center Frequency:    {format_frequency(result['f0'])}")
    lines.append(f"Bandwidth:           {format_frequency(result['bw'])}")
    lines.append(f"Fractional BW:       {result['fbw']*100:.2f}%")
    lines.append(f"Impedance Z0:        {result['z0']:.4g} Ohm")
    lines.append(f"Resonators:          {result['n_resonators']}")
    if result.get('ripple_db'):
        lines.append(f"Ripple:              {result['ripple_db']} dB")
    lines.append("=" * 60)

    if result.get('warnings'):
        lines.append("\nWarnings:")
        for w in result['warnings']:
            lines.append(f"  ! {w}")

    lines.append(f"\nMinimum Component Q: {result['q_min']:.0f}")
    lines.append(f"  (Q safety factor: {result['q_safety']})")

    lines.append("\nTopology:")
    if coupling == 'top':
        lines.append(format_top_c_diagram(result['n_resonators']))
    else:
        lines.append(format_shunt_c_diagram(result['n_resonators']))

    n = result['n_resonators']
    lines.append(f"\n{'Component Values':^50}")
    lines.append(f"\u250c{'\u2500' * 24}\u252c{'\u2500' * 24}\u2510")
    lines.append(f"\u2502{'Tank Capacitors':^24}\u2502{'Inductors':^24}\u2502")
    lines.append(f"\u251c{'\u2500' * 24}\u253c{'\u2500' * 24}\u2524")

    for i in range(n):
        if state.raw_units:
            cap_str = f"Cp{i+1}: {result['c_tank'][i]:.6e} F"
            ind_str = f"L{i+1}: {result['L_resonant']:.6e} H"
        else:
            cap_str = f"Cp{i+1}: {format_capacitance(result['c_tank'][i])}"
            ind_str = f"L{i+1}: {format_inductance(result['L_resonant'])}"
        lines.append(f"\u2502 {cap_str:<22} \u2502 {ind_str:<22} \u2502")

    lines.append(f"\u2514{'\u2500' * 24}\u2534{'\u2500' * 24}\u2518")

    lines.append(f"\n\u250c{'\u2500' * 24}\u2510")
    lines.append(f"\u2502{'Coupling Capacitors':^24}\u2502")
    lines.append(f"\u251c{'\u2500' * 24}\u2524")

    for i, cs in enumerate(result['c_coupling']):
        if state.raw_units:
            cs_str = f"Cs{i+1}{i+2}: {cs:.6e} F"
        else:
            cs_str = f"Cs{i+1}{i+2}: {format_capacitance(cs)}"
        lines.append(f"\u2502 {cs_str:<22} \u2502")

    lines.append(f"\u2514{'\u2500' * 24}\u2518")

    lines.append(f"\nExternal Q (input):  {result['qe_in']:.2f}")
    lines.append(f"External Q (output): {result['qe_out']:.2f}")

    return lines
