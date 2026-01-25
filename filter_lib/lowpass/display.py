"""Display functions for low-pass filters."""
from ..shared.formatting import format_capacitance
from ..shared.display_helpers import format_eseries_match
from ..shared.display_common import (
    format_json_result, format_csv_result, format_quiet_result,
    print_header, print_component_table,
)
from ..shared.plotting import render_ascii_plot
from .transfer import frequency_response, generate_frequency_points


def format_json(result: dict) -> str:
    """Format results as JSON (lowpass: capacitors first)."""
    return format_json_result(result, primary_component='capacitors')


def format_csv(result: dict) -> str:
    """Format results as CSV (lowpass: capacitors first)."""
    return format_csv_result(result, primary_component='capacitors')


def format_quiet(result: dict, raw: bool = False) -> str:
    """Format minimal output (lowpass: capacitors first)."""
    return format_quiet_result(result, raw, primary_component='capacitors')


def _print_pi_topology_diagram(n_capacitors: int, n_inductors: int) -> None:
    """Print dynamic Pi topology ASCII diagram for low-pass filter."""
    main_parts = ["  IN ───┬"]
    for i in range(n_inductors):
        main_parts.append(f"───┤ L{i+1} ├───┬")

    if n_capacitors > n_inductors:
        main_parts.append("─── OUT")
    else:
        main_parts[-1] = main_parts[-1][:-1] + "─── OUT"

    main_line = "".join(main_parts)
    line_len = len(main_line)

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
    print_header(result, topology='Pi', filter_category='Low Pass')

    n_caps = len(result['capacitors'])
    n_inds = len(result['inductors'])

    print("\nTopology:")
    _print_pi_topology_diagram(n_caps, n_inds)

    print_component_table(result, raw=raw, primary_component='capacitors')

    if show_match and not raw:
        print(f"\n{eseries} Standard Capacitor Recommendations")
        print("-" * 45)
        print("(Calculated values with nearest standard matches)")
        print()
        for i, cap in enumerate(result['capacitors']):
            print(f"C{i+1} Calculated: {format_capacitance(cap)}")
            for line in format_eseries_match(cap, eseries, format_capacitance):
                print(line)

    if show_plot:
        freqs = generate_frequency_points(result['freq_hz'])
        ripple = result.get('ripple') or 0.5
        response = frequency_response(result['filter_type'], freqs, result['freq_hz'],
                                       result['order'], ripple)
        print()
        print(render_ascii_plot(freqs, response, result['freq_hz'],
                                filter_type='lowpass'))

    print()
