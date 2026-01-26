"""ASCII topology diagram rendering for Pi and T filter topologies.

Shared by lowpass and highpass display modules.
"""


def _build_line(positions: list[int], elements: list[str], line_len: int) -> str:
    """Build a line with elements centered at given positions.

    Args:
        positions: Column positions for each element
        elements: Text elements to place
        line_len: Total line length
    """
    chars = [' '] * line_len
    for pos, elem in zip(positions, elements):
        start = pos - len(elem) // 2
        for j, ch in enumerate(elem):
            if 0 <= start + j < line_len:
                chars[start + j] = ch
    return ''.join(chars)


def print_pi_topology_diagram(n_shunt: int, n_series: int,
                              series_label: str = 'L',
                              shunt_label: str = 'C') -> None:
    """Print Pi topology ASCII diagram: shunt - series - shunt pattern.

    Args:
        n_shunt: Number of shunt elements (odd positions)
        n_series: Number of series elements (even positions)
        series_label: Label prefix for series elements (default 'L')
        shunt_label: Label prefix for shunt elements (default 'C')
    """
    main_parts = ["  IN ───┬"]
    for i in range(n_series):
        main_parts.append(f"───┤ {series_label}{i+1} ├───┬")

    if n_shunt > n_series:
        main_parts.append("─── OUT")
    else:
        main_parts[-1] = main_parts[-1][:-1] + "─── OUT"

    main_line = "".join(main_parts)
    line_len = len(main_line)

    shunt_positions = []
    pos = main_line.find('┬')
    while pos != -1:
        shunt_positions.append(pos)
        pos = main_line.find('┬', pos + 1)

    vert_line = _build_line(shunt_positions, ['│'] * n_shunt, line_len)
    cap_sym = _build_line(shunt_positions, ['==='] * n_shunt, line_len)
    shunt_labels = [f"{shunt_label}{i+1}" for i in range(n_shunt)]
    label_line = _build_line(shunt_positions, shunt_labels, line_len)
    gnd_wire = _build_line(shunt_positions, ['│'] * n_shunt, line_len)
    gnd_sym = _build_line(shunt_positions, ['GND'] * n_shunt, line_len)

    print(main_line)
    print(vert_line)
    print(cap_sym)
    print(label_line)
    print(gnd_wire)
    print(gnd_sym)


def print_t_topology_diagram(n_series: int, n_shunt: int,
                             series_label: str = 'L',
                             shunt_label: str = 'C') -> None:
    """Print T topology ASCII diagram: series - shunt - series pattern.

    Args:
        n_series: Number of series elements (odd positions, in signal path)
        n_shunt: Number of shunt elements (even positions, to ground)
        series_label: Label prefix for series elements (default 'L')
        shunt_label: Label prefix for shunt elements (default 'C')
    """
    main_parts = ["  IN ───"]
    for i in range(n_series):
        if i > 0:
            main_parts.append("───")
        main_parts.append(f"┤{series_label}{i+1}├")
        if i < n_shunt:
            main_parts.append("───┬")

    if n_series > n_shunt:
        main_parts.append("─── OUT")
    else:
        main_parts[-1] = "───┬─── OUT"

    main_line = "".join(main_parts)
    line_len = len(main_line)

    shunt_positions = []
    pos = main_line.find('┬')
    while pos != -1:
        shunt_positions.append(pos)
        pos = main_line.find('┬', pos + 1)

    vert_line = _build_line(shunt_positions, ['│'] * n_shunt, line_len)
    shunt_sym = _build_line(shunt_positions, ['==='] * n_shunt, line_len)
    shunt_labels = [f"{shunt_label}{i+1}" for i in range(n_shunt)]
    label_line = _build_line(shunt_positions, shunt_labels, line_len)
    gnd_wire = _build_line(shunt_positions, ['│'] * n_shunt, line_len)
    gnd_sym = _build_line(shunt_positions, ['GND'] * n_shunt, line_len)

    print(main_line)
    print(vert_line)
    print(shunt_sym)
    print(label_line)
    print(gnd_wire)
    print(gnd_sym)
