"""Output formatters for bandpass filter results.

Provides JSON, CSV, and quiet text formatting.
"""
from __future__ import annotations
import csv
import io
import json
from typing import Any, Callable

from ..shared.formatting import format_frequency, format_capacitance, format_inductance
from ..shared.display_helpers import format_eseries_match as _shared_format_eseries

# Type alias for filter result dict
FilterResult = dict[str, Any]


def format_eseries_match(value: float, series: str,
                         unit_formatter: Callable[[float], str]) -> list[str]:
    """Format E-series match for a component value.

    Uses additive parallel mode for consistency with lowpass/highpass.

    Args:
        value: Component value
        series: E-series name (E12, E24, E96)
        unit_formatter: Function to format value with units

    Returns:
        List of formatted match strings
    """
    return _shared_format_eseries(value, series, unit_formatter, parallel_mode='additive')


def format_json(result: FilterResult) -> str:
    """Format results as JSON.

    Args:
        result: Dict from calculate_bandpass_filter()

    Returns:
        JSON formatted string
    """
    output = {
        'filter_type': result['filter_type'],
        'coupling': result['coupling'],
        'center_frequency_hz': result['f0'],
        'bandwidth_hz': result['bw'],
        'f_low_hz': result['f_low'],
        'f_high_hz': result['f_high'],
        'fractional_bw': result['fbw'],
        'impedance_ohms': result['z0'],
        'n_resonators': result['n_resonators'],
        'q_min': result['q_min'],
        'components': {
            'tank_capacitors': [{'name': f'Cp{i+1}', 'value_farads': v}
                               for i, v in enumerate(result['c_tank'])],
            'inductors': [{'name': f'L{i+1}', 'value_henries': result['L_resonant']}
                         for i in range(result['n_resonators'])],
            'coupling_capacitors': [{'name': f'Cs{i+1}{i+2}', 'value_farads': v}
                                   for i, v in enumerate(result['c_coupling'])]
        },
        'external_q': {'input': result['qe_in'], 'output': result['qe_out']}
    }
    if result.get('ripple_db') is not None:
        output['ripple_db'] = result['ripple_db']
    return json.dumps(output, indent=2)


def format_csv(result: FilterResult) -> str:
    """Format results as CSV.

    Args:
        result: Dict from calculate_bandpass_filter()

    Returns:
        CSV formatted string
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Component', 'Value', 'Unit'])
    for i, v in enumerate(result['c_tank']):
        formatted = format_capacitance(v)
        val, unit = formatted.rsplit(' ', 1)
        writer.writerow([f'Cp{i+1}', val, unit])
    for i in range(result['n_resonators']):
        formatted = format_inductance(result['L_resonant'])
        val, unit = formatted.rsplit(' ', 1)
        writer.writerow([f'L{i+1}', val, unit])
    for i, v in enumerate(result['c_coupling']):
        formatted = format_capacitance(v)
        val, unit = formatted.rsplit(' ', 1)
        writer.writerow([f'Cs{i+1}{i+2}', val, unit])
    return output.getvalue()


def format_quiet(result: FilterResult, raw: bool = False) -> str:
    """Format results as minimal text (values only).

    Args:
        result: Dict from calculate_bandpass_filter()
        raw: If True, use scientific notation

    Returns:
        Minimal text output
    """
    lines: list[str] = []
    for i, v in enumerate(result['c_tank']):
        if raw:
            lines.append(f"Cp{i+1}: {v:.6e} F")
        else:
            lines.append(f"Cp{i+1}: {format_capacitance(v)}")
    for i in range(result['n_resonators']):
        if raw:
            lines.append(f"L{i+1}: {result['L_resonant']:.6e} H")
        else:
            lines.append(f"L{i+1}: {format_inductance(result['L_resonant'])}")
    for i, v in enumerate(result['c_coupling']):
        if raw:
            lines.append(f"Cs{i+1}{i+2}: {v:.6e} F")
        else:
            lines.append(f"Cs{i+1}{i+2}: {format_capacitance(v)}")
    return '\n'.join(lines)
