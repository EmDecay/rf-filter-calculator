"""Display functions for low-pass filters."""
import json

from ..shared.formatting import format_frequency, format_capacitance, format_inductance
from ..shared.display_helpers import format_eseries_match, format_component_value, split_value_unit
from ..shared.plotting import render_ascii_plot
from .transfer import frequency_response, generate_frequency_points


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




def format_json(result: dict) -> str:
    """Format results as JSON."""
    output = {
        'filter_type': result['filter_type'],
        'cutoff_frequency_hz': result['freq_hz'],
        'impedance_ohms': result['impedance'],
        'order': result['order'],
        'components': {
            'capacitors': [{'name': f'C{i+1}', 'value_farads': v}
                          for i, v in enumerate(result['capacitors'])],
            'inductors': [{'name': f'L{i+1}', 'value_henries': v}
                         for i, v in enumerate(result['inductors'])]
        }
    }
    if result.get('ripple'):
        output['ripple_db'] = result['ripple']
    return json.dumps(output, indent=2)


def format_csv(result: dict) -> str:
    """Format results as CSV."""
    lines = ['Component,Value,Unit']
    for i, v in enumerate(result['capacitors']):
        formatted = format_capacitance(v)
        val, unit = split_value_unit(formatted)
        lines.append(f'C{i+1},{val},{unit}')
    for i, v in enumerate(result['inductors']):
        formatted = format_inductance(v)
        val, unit = split_value_unit(formatted)
        lines.append(f'L{i+1},{val},{unit}')
    return '\n'.join(lines)


def format_quiet(result: dict, raw: bool = False) -> str:
    """Format minimal output."""
    lines = []
    for i, v in enumerate(result['capacitors']):
        lines.append(format_component_value(f"C{i+1}", v, format_capacitance, raw))
    for i, v in enumerate(result['inductors']):
        lines.append(format_component_value(f"L{i+1}", v, format_inductance, raw))
    return '\n'.join(lines)


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

    title = f"{result['filter_type'].title()} Pi Low Pass Filter"
    print(f"\n{title}")
    print("=" * 50)
    print(f"Cutoff Frequency:    {format_frequency(result['freq_hz'])}")
    print(f"Impedance Z0:        {result['impedance']:.4g} Ohm")
    if result.get('ripple') is not None:
        print(f"Ripple:              {result['ripple']} dB")
    print(f"Order:               {result['order']}")
    print("=" * 50)

    n_caps = len(result['capacitors'])
    n_inds = len(result['inductors'])

    print("\nTopology:")
    _print_pi_topology_diagram(n_caps, n_inds)

    max_rows = max(n_caps, n_inds)
    col_width = 24

    print(f"\n{'Component Values':^50}")
    print(f"┌{'─' * col_width}┬{'─' * col_width}┐")
    print(f"│{'Capacitors':^{col_width}}│{'Inductors':^{col_width}}│")
    print(f"├{'─' * col_width}┼{'─' * col_width}┤")

    for i in range(max_rows):
        if i < n_caps:
            val = result['capacitors'][i]
            cap_str = f"C{i+1}: {val:.6e} F" if raw else f"C{i+1}: {format_capacitance(val)}"
        else:
            cap_str = ""
        if i < n_inds:
            val = result['inductors'][i]
            ind_str = f"L{i+1}: {val:.6e} H" if raw else f"L{i+1}: {format_inductance(val)}"
        else:
            ind_str = ""
        print(f"│ {cap_str:<{col_width-2}} │ {ind_str:<{col_width-2}} │")

    print(f"└{'─' * col_width}┴{'─' * col_width}┘")

    if show_match and not raw:
        print(f"\n{eseries} Standard Capacitor Recommendations")
        print("─" * 45)
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
