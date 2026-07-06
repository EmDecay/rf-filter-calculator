"""ASCII topology diagram rendering for Pi and T filter topologies.

Shared by lowpass and highpass display modules.
"""


def _build_line(positions: list[int], elements: list[str], line_len: int) -> str:
    """Build a line with elements centered at given positions.

    Characters falling outside [0, line_len) are silently clipped so a
    label near the line edge cannot raise.

    Args:
        positions: Column positions for each element (element is centered here)
        elements: Text elements to place
        line_len: Total line length

    Returns:
        Fixed-width string of length line_len.
    """
    chars = [" "] * line_len
    for pos, elem in zip(positions, elements):
        start = pos - len(elem) // 2
        for j, ch in enumerate(elem):
            if 0 <= start + j < line_len:
                chars[start + j] = ch
    return "".join(chars)


def format_pi_topology_diagram(
    n_shunt: int, n_series: int, series_label: str = "L", shunt_label: str = "C"
) -> str:
    """Format Pi topology ASCII diagram as string.

    Args:
        n_shunt: Number of shunt elements (odd positions)
        n_series: Number of series elements (even positions)
        series_label: Label prefix for series elements (default 'L')
        shunt_label: Label prefix for shunt elements (default 'C')

    Returns:
        Multi-line string with the topology diagram.
    """
    # Pi pattern: shunt at input, then series/shunt alternating. Every "┬"
    # in the main line is a shunt tap point; the lines below are aligned by
    # scanning for those characters rather than recomputing positions.
    main_parts = ["  IN ───┬"]
    for i in range(n_series):
        main_parts.append(f"───┤ {series_label}{i + 1} ├───┬")

    if n_shunt > n_series:
        main_parts.append("─── OUT")
    else:
        # Even orders end on a series element: drop the trailing "┬" so no
        # phantom shunt tap is drawn after the last series component.
        main_parts[-1] = main_parts[-1][:-1] + "─── OUT"

    main_line = "".join(main_parts)
    line_len = len(main_line)

    shunt_positions = []
    pos = main_line.find("┬")
    while pos != -1:
        shunt_positions.append(pos)
        pos = main_line.find("┬", pos + 1)

    vert_line = _build_line(shunt_positions, ["│"] * n_shunt, line_len)
    cap_sym = _build_line(shunt_positions, ["==="] * n_shunt, line_len)
    shunt_labels = [f"{shunt_label}{i + 1}" for i in range(n_shunt)]
    label_line = _build_line(shunt_positions, shunt_labels, line_len)
    gnd_wire = _build_line(shunt_positions, ["│"] * n_shunt, line_len)
    gnd_sym = _build_line(shunt_positions, ["GND"] * n_shunt, line_len)

    return "\n".join([main_line, vert_line, cap_sym, label_line, gnd_wire, gnd_sym])


def print_pi_topology_diagram(
    n_shunt: int, n_series: int, series_label: str = "L", shunt_label: str = "C"
) -> None:
    """Print Pi topology ASCII diagram: shunt - series - shunt pattern.

    Args:
        n_shunt: Number of shunt elements (odd positions)
        n_series: Number of series elements (even positions)
        series_label: Label prefix for series elements (default 'L')
        shunt_label: Label prefix for shunt elements (default 'C')
    """
    print(format_pi_topology_diagram(n_shunt, n_series, series_label, shunt_label))


def format_t_topology_diagram(
    n_series: int, n_shunt: int, series_label: str = "L", shunt_label: str = "C"
) -> str:
    """Format T topology ASCII diagram as string.

    Args:
        n_series: Number of series elements (odd positions, in signal path)
        n_shunt: Number of shunt elements (even positions, to ground)
        series_label: Label prefix for series elements (default 'L')
        shunt_label: Label prefix for shunt elements (default 'C')

    Returns:
        Multi-line string with the topology diagram.
    """
    # T pattern: series at input, shunt taps between series elements.
    # As in the Pi renderer, "┬" characters mark shunt taps and drive the
    # alignment of the label/ground lines below.
    main_parts = ["  IN ───"]
    for i in range(n_series):
        if i > 0:
            main_parts.append("───")
        main_parts.append(f"┤{series_label}{i + 1}├")
        if i < n_shunt:
            main_parts.append("───┬")

    if n_series > n_shunt:
        main_parts.append("─── OUT")
    else:
        # Even orders end on a shunt element: keep the final tap and run
        # the line straight out from it.
        main_parts[-1] = "───┬─── OUT"

    main_line = "".join(main_parts)
    line_len = len(main_line)

    shunt_positions = []
    pos = main_line.find("┬")
    while pos != -1:
        shunt_positions.append(pos)
        pos = main_line.find("┬", pos + 1)

    vert_line = _build_line(shunt_positions, ["│"] * n_shunt, line_len)
    shunt_sym = _build_line(shunt_positions, ["==="] * n_shunt, line_len)
    shunt_labels = [f"{shunt_label}{i + 1}" for i in range(n_shunt)]
    label_line = _build_line(shunt_positions, shunt_labels, line_len)
    gnd_wire = _build_line(shunt_positions, ["│"] * n_shunt, line_len)
    gnd_sym = _build_line(shunt_positions, ["GND"] * n_shunt, line_len)

    return "\n".join([main_line, vert_line, shunt_sym, label_line, gnd_wire, gnd_sym])


def print_t_topology_diagram(
    n_series: int, n_shunt: int, series_label: str = "L", shunt_label: str = "C"
) -> None:
    """Print T topology ASCII diagram: series - shunt - series pattern.

    Args:
        n_series: Number of series elements (odd positions, in signal path)
        n_shunt: Number of shunt elements (even positions, to ground)
        series_label: Label prefix for series elements (default 'L')
        shunt_label: Label prefix for shunt elements (default 'C')
    """
    print(format_t_topology_diagram(n_series, n_shunt, series_label, shunt_label))
