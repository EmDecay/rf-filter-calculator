"""Display functions for high-pass filters."""
from ..shared.formatting import format_inductance, format_capacitance
from ..shared.display_helpers import format_eseries_match
from ..shared.display_common import (
    format_json_result, format_csv_result, format_quiet_result,
    print_header, print_component_table,
)
from ..shared.topology_diagrams import print_pi_topology_diagram, print_t_topology_diagram
from ..shared.plotting import render_ascii_plot
from .transfer import frequency_response, generate_frequency_points


def _primary_component(result: dict) -> str:
    """Return primary component type based on topology.

    HPF T: caps at series (odd) positions = primary.
    HPF Pi: inds at shunt (odd) positions = primary.
    """
    return 'inductors' if result.get('topology', 't') == 'pi' else 'capacitors'


def format_json(result: dict) -> str:
    """Format results as JSON."""
    return format_json_result(result, primary_component=_primary_component(result))


def format_csv(result: dict) -> str:
    """Format results as CSV."""
    return format_csv_result(result, primary_component=_primary_component(result))


def format_quiet(result: dict, raw: bool = False) -> str:
    """Format minimal output."""
    return format_quiet_result(result, raw, primary_component=_primary_component(result))


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

    topology = result.get('topology', 't')
    primary = _primary_component(result)

    # Use shared header and table printing
    print_header(result, topology=topology.upper(), filter_category='High Pass')

    n_inds = len(result['inductors'])
    n_caps = len(result['capacitors'])

    print("\nTopology:")
    # HPF swaps component types: series C + shunt L
    if topology == 't':
        print_t_topology_diagram(n_caps, n_inds, series_label='C', shunt_label='L')
    else:
        print_pi_topology_diagram(n_inds, n_caps, series_label='C', shunt_label='L')

    print_component_table(result, raw=raw, primary_component=primary)

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
                                filter_type='highpass'))

    print()
