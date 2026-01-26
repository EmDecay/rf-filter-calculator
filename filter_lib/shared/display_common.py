"""Common display formatting functions for lowpass and highpass filters.

Extracts shared logic to reduce code duplication between filter display modules.
Each filter module can import these and customize as needed.
"""
import json

from .formatting import format_capacitance, format_inductance
from .display_helpers import format_component_value, split_value_unit


def format_json_result(result: dict, primary_component: str = 'capacitors') -> str:
    """Format filter results as JSON.

    Args:
        result: Filter result dictionary with capacitors, inductors, etc.
        primary_component: Which component type to list first ('capacitors' or 'inductors')

    Returns:
        JSON string with filter data.
    """
    # Build components dict with specified order
    if primary_component == 'capacitors':
        components = {
            'capacitors': [{'name': f'C{i+1}', 'value_farads': v}
                          for i, v in enumerate(result['capacitors'])],
            'inductors': [{'name': f'L{i+1}', 'value_henries': v}
                         for i, v in enumerate(result['inductors'])]
        }
    else:
        components = {
            'inductors': [{'name': f'L{i+1}', 'value_henries': v}
                         for i, v in enumerate(result['inductors'])],
            'capacitors': [{'name': f'C{i+1}', 'value_farads': v}
                          for i, v in enumerate(result['capacitors'])]
        }

    output = {
        'filter_type': result['filter_type'],
        'cutoff_frequency_hz': result['freq_hz'],
        'impedance_ohms': result['impedance'],
        'order': result['order'],
        'components': components
    }

    if result.get('topology'):
        output['topology'] = result['topology']

    if result.get('ripple'):
        output['ripple_db'] = result['ripple']

    return json.dumps(output, indent=2)


def format_csv_result(result: dict, primary_component: str = 'capacitors') -> str:
    """Format filter results as CSV.

    Args:
        result: Filter result dictionary with capacitors, inductors, etc.
        primary_component: Which component type to list first ('capacitors' or 'inductors')

    Returns:
        CSV string with component data.
    """
    lines = ['Component,Value,Unit']

    if primary_component == 'capacitors':
        # Capacitors first, then inductors
        for i, v in enumerate(result['capacitors']):
            formatted = format_capacitance(v)
            val, unit = split_value_unit(formatted)
            lines.append(f'C{i+1},{val},{unit}')
        for i, v in enumerate(result['inductors']):
            formatted = format_inductance(v)
            val, unit = split_value_unit(formatted)
            lines.append(f'L{i+1},{val},{unit}')
    else:
        # Inductors first, then capacitors
        for i, v in enumerate(result['inductors']):
            formatted = format_inductance(v)
            val, unit = split_value_unit(formatted)
            lines.append(f'L{i+1},{val},{unit}')
        for i, v in enumerate(result['capacitors']):
            formatted = format_capacitance(v)
            val, unit = split_value_unit(formatted)
            lines.append(f'C{i+1},{val},{unit}')

    return '\n'.join(lines)


def format_quiet_result(result: dict, raw: bool = False,
                        primary_component: str = 'capacitors') -> str:
    """Format minimal output with just component values.

    Args:
        result: Filter result dictionary with capacitors, inductors, etc.
        raw: If True, show raw SI values; if False, use engineering notation
        primary_component: Which component type to list first ('capacitors' or 'inductors')

    Returns:
        Minimal string output with component values.
    """
    lines = []

    if primary_component == 'capacitors':
        for i, v in enumerate(result['capacitors']):
            lines.append(format_component_value(f"C{i+1}", v, format_capacitance, raw))
        for i, v in enumerate(result['inductors']):
            lines.append(format_component_value(f"L{i+1}", v, format_inductance, raw))
    else:
        for i, v in enumerate(result['inductors']):
            lines.append(format_component_value(f"L{i+1}", v, format_inductance, raw))
        for i, v in enumerate(result['capacitors']):
            lines.append(format_component_value(f"C{i+1}", v, format_capacitance, raw))

    return '\n'.join(lines)


def print_header(result: dict, topology: str, filter_category: str) -> None:
    """Print common filter header information.

    Args:
        result: Filter result dictionary
        topology: Topology description (e.g., 'Pi', 'T')
        filter_category: Filter category (e.g., 'Low Pass', 'High Pass')
    """
    from .formatting import format_frequency

    title = f"{result['filter_type'].title()} {topology} {filter_category} Filter"
    print(f"\n{title}")
    print("=" * 50)
    print(f"Cutoff Frequency:    {format_frequency(result['freq_hz'])}")
    print(f"Impedance Z0:        {result['impedance']:.4g} Ohm")
    if result.get('ripple') is not None:
        print(f"Ripple:              {result['ripple']} dB")
    print(f"Order:               {result['order']}")
    print("=" * 50)


def print_component_table(result: dict, raw: bool = False,
                          primary_component: str = 'capacitors') -> None:
    """Print component values in a formatted table.

    Args:
        result: Filter result dictionary
        raw: If True, show raw SI values
        primary_component: Which component type in left column ('capacitors' or 'inductors')
    """
    from .formatting import format_capacitance, format_inductance

    col_width = 24

    if primary_component == 'capacitors':
        left_label, right_label = 'Capacitors', 'Inductors'
        left_vals, right_vals = result['capacitors'], result['inductors']
        left_fmt, right_fmt = format_capacitance, format_inductance
        left_prefix, right_prefix = 'C', 'L'
        left_unit, right_unit = 'F', 'H'
    else:
        left_label, right_label = 'Inductors', 'Capacitors'
        left_vals, right_vals = result['inductors'], result['capacitors']
        left_fmt, right_fmt = format_inductance, format_capacitance
        left_prefix, right_prefix = 'L', 'C'
        left_unit, right_unit = 'H', 'F'

    max_rows = max(len(left_vals), len(right_vals))

    print(f"\n{'Component Values':^50}")
    print(f"\u250c{'\u2500' * col_width}\u252c{'\u2500' * col_width}\u2510")
    print(f"\u2502{left_label:^{col_width}}\u2502{right_label:^{col_width}}\u2502")
    print(f"\u251c{'\u2500' * col_width}\u253c{'\u2500' * col_width}\u2524")

    for i in range(max_rows):
        if i < len(left_vals):
            val = left_vals[i]
            left_str = f"{left_prefix}{i+1}: {val:.6e} {left_unit}" if raw else f"{left_prefix}{i+1}: {left_fmt(val)}"
        else:
            left_str = ""
        if i < len(right_vals):
            val = right_vals[i]
            right_str = f"{right_prefix}{i+1}: {val:.6e} {right_unit}" if raw else f"{right_prefix}{i+1}: {right_fmt(val)}"
        else:
            right_str = ""
        print(f"\u2502 {left_str:<{col_width-2}} \u2502 {right_str:<{col_width-2}} \u2502")

    print(f"\u2514{'\u2500' * col_width}\u2534{'\u2500' * col_width}\u2518")
