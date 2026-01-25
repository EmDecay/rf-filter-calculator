"""Display functions for high-pass filters with T-topology."""
from ..shared.formatting import format_inductance
from ..shared.display_helpers import format_eseries_match
from ..shared.display_common import (
    format_json_result, format_csv_result, format_quiet_result,
    print_header, print_component_table,
)
from ..shared.plotting import render_ascii_plot
from .transfer import frequency_response, generate_frequency_points


def format_json(result: dict) -> str:
    """Format results as JSON (highpass: inductors first)."""
    return format_json_result(result, primary_component='inductors')


def format_csv(result: dict) -> str:
    """Format results as CSV (highpass: inductors first)."""
    return format_csv_result(result, primary_component='inductors')


def format_quiet(result: dict, raw: bool = False) -> str:
    """Format minimal output (highpass: inductors first)."""
    return format_quiet_result(result, raw, primary_component='inductors')


def _print_t_topology_diagram(n_inductors: int, n_capacitors: int) -> None:
    """Print dynamic T topology ASCII diagram for high-pass filter.

    T topology: IN ───┤L1├───┬───┤L2├───┬─── OUT
                              │           │
                             ===         ===
                             C1          C2
                              │           │
                             GND         GND
    """
    # Build main signal line with series inductors
    main_parts = ["  IN ───"]
    for i in range(n_inductors):
        if i > 0:
            main_parts.append("───")
        main_parts.append(f"┤L{i+1}├")
        if i < n_capacitors:  # Add branch point for capacitor
            main_parts.append("───┬")

    # Close the line
    if n_inductors > n_capacitors:
        main_parts.append("─── OUT")
    else:
        main_parts[-1] = "───┬─── OUT"

    main_line = "".join(main_parts)
    line_len = len(main_line)

    # Find positions of branch points (┬)
    cap_positions = []
    pos = main_line.find('┬')
    while pos != -1:
        cap_positions.append(pos)
        pos = main_line.find('┬', pos + 1)

    def build_line(positions: list[int], elements: list[str]) -> str:
        chars = [' '] * line_len
        for pos, elem in zip(positions, elements):
            start = pos - len(elem) // 2
            for j, ch in enumerate(elem):
                if 0 <= start + j < line_len:
                    chars[start + j] = ch
        return ''.join(chars)

    # Build capacitor lines
    vert_line = build_line(cap_positions, ['│'] * n_capacitors)
    cap_sym = build_line(cap_positions, ['==='] * n_capacitors)
    cap_labels = [f"C{i+1}" for i in range(n_capacitors)]
    label_line = build_line(cap_positions, cap_labels)
    gnd_wire = build_line(cap_positions, ['│'] * n_capacitors)
    gnd_sym = build_line(cap_positions, ['GND'] * n_capacitors)

    print(main_line)
    print(vert_line)
    print(cap_sym)
    print(label_line)
    print(gnd_wire)
    print(gnd_sym)




def display_results(result: dict, raw: bool = False,
                    output_format: str = 'table', quiet: bool = False,
                    eseries: str = 'E24', show_match: bool = True,
                    show_plot: bool = False) -> None:
    """Display calculated filter component values."""
    if output_format == 'json':
        print(format_json(result))
        return
    if output_format == 'csv':
        print(format_csv(result), end='')
        return
    if quiet:
        print(format_quiet(result, raw))
        return

    # Use shared header and table printing
    print_header(result, topology='T', filter_category='High Pass')

    n_inds = len(result['inductors'])
    n_caps = len(result['capacitors'])

    print("\nTopology:")
    _print_t_topology_diagram(n_inds, n_caps)

    print_component_table(result, raw=raw, primary_component='inductors')

    if show_match and not raw:
        print(f"\n{eseries} Standard Inductor Recommendations")
        print("-" * 45)
        print("(Calculated values with nearest standard matches)")
        print()
        for i, ind in enumerate(result['inductors']):
            print(f"L{i+1} Calculated: {format_inductance(ind)}")
            for line in format_eseries_match(ind, eseries, format_inductance):
                print(line)

    if show_plot:
        freqs = generate_frequency_points(result['freq_hz'])
        ripple = result.get('ripple') or 0.5
        response = frequency_response(result['filter_type'], freqs, result['freq_hz'],
                                       result['order'], ripple)
        print()
        print(render_ascii_plot(freqs, response, result['freq_hz'],
                                filter_type='highpass'))

    print()
