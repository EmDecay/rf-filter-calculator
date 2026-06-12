"""ASCII topology diagrams for bandpass filters.

Generates Top-C (series) and Shunt-C (parallel) coupling diagrams.
"""


def format_top_c_diagram(n: int) -> str:
    """Format Top-C (series coupling) topology diagram as string.

    Shows the series end-coupling capacitors (Ce_in/Ce_out) that realize the
    external Q at source and load, n tanks, and n-1 inter-resonator coupling
    capacitors on the main line. Each tank is a parallel LC circuit to ground.

    Args:
        n: Number of resonators

    Returns:
        Multi-line string with the topology diagram.
    """
    n_coupling = n - 1
    seg_w = 15

    # Main line: end caps couple the source and load into the end tanks
    main_line = "  IN ──┤├──┬" + "──────┤├──────┬" * n_coupling + "──┤├── OUT"
    tank_pos = [11 + i * seg_w for i in range(n)]
    line_len = len(main_line)

    # Coupling capacitor labels above main line
    label_chars = [" "] * line_len
    for i in range(n_coupling):
        mid = (tank_pos[i] + tank_pos[i + 1]) // 2
        label = f"Cs{i + 1}{i + 2}"
        start = mid - len(label) // 2
        for j, ch in enumerate(label):
            if 0 <= start + j < line_len:
                label_chars[start + j] = ch
    for label, mid in (("Ce_in", 8), ("Ce_out", line_len - 8)):
        start = mid - len(label) // 2
        for j, ch in enumerate(label):
            if 0 <= start + j < line_len:
                label_chars[start + j] = ch
    label_line = "".join(label_chars)

    def build_line(elements: list[str]) -> str:
        chars = [" "] * line_len
        for pos, elem in zip(tank_pos, elements):
            start = pos - len(elem) // 2
            for j, ch in enumerate(elem):
                if 0 <= start + j < line_len:
                    chars[start + j] = ch
        return "".join(chars)

    vert_line = build_line(["   │   "] * n)
    tank_top = build_line(["┌──┴──┐"] * n)
    tank_r1 = build_line(["│     │"] * n)
    tank_r2 = build_line([f"Cp{i + 1:<2} L{i + 1}" for i in range(n)])
    tank_r3 = build_line(["│     │"] * n)
    tank_bot = build_line(["└──┬──┘"] * n)
    gnd_wire = build_line(["   │   "] * n)
    gnd_sym = build_line(["  GND  "] * n)

    return "\n".join(
        [
            label_line,
            main_line,
            vert_line,
            tank_top,
            tank_r1,
            tank_r2,
            tank_r3,
            tank_bot,
            gnd_wire,
            gnd_sym,
        ]
    )


def print_top_c_diagram(n: int) -> None:
    """Print Top-C (series coupling) topology diagram.

    Shows n tanks with n-1 coupling capacitors in series on main line.
    Each tank is a parallel LC circuit to ground.

    Args:
        n: Number of resonators
    """
    print(format_top_c_diagram(n))


def format_shunt_c_diagram(n: int) -> str:
    """Format Shunt-C (bottom-coupled) topology diagram as string.

    Coupling capacitors connect bottoms of adjacent tanks horizontally.

    Args:
        n: Number of resonators

    Returns:
        Multi-line string with the topology diagram.
    """
    seg_w = 13

    main_line = "  IN ──────┬" + "────────────┬" * (n - 1) + "────── OUT"
    tank_pos = [11 + i * seg_w for i in range(n)]
    line_len = len(main_line)

    def build_line(elements: list[str]) -> str:
        chars = [" "] * line_len
        for pos, elem in zip(tank_pos, elements):
            start = pos - len(elem) // 2
            for j, ch in enumerate(elem):
                if 0 <= start + j < line_len:
                    chars[start + j] = ch
        return "".join(chars)

    vert1 = build_line(["   │   "] * n)
    tank_top = build_line(["┌──┴──┐"] * n)
    tank_r1 = build_line(["│     │"] * n)
    tank_r2 = build_line([f"Cp{i + 1:<2} L{i + 1}" for i in range(n)])
    tank_r3 = build_line(["│     │"] * n)
    tank_bot = build_line(["└──┬──┘"] * n)
    vert2 = build_line(["   │   "] * n)

    # Bottom coupling rail
    coupling_line_chars = [" "] * line_len
    for i, pos in enumerate(tank_pos):
        if i == 0:
            coupling_line_chars[pos] = "├"
        elif i == n - 1:
            coupling_line_chars[pos] = "┤"
        else:
            coupling_line_chars[pos] = "┼"
        if i < n - 1:
            next_pos = tank_pos[i + 1]
            mid = (pos + next_pos) // 2
            for j in range(pos + 1, next_pos):
                coupling_line_chars[j] = "─"
            label = f"Cs{i + 1}{i + 2}"
            start = mid - len(label) // 2
            for j, ch in enumerate(label):
                if 0 <= start + j < line_len:
                    coupling_line_chars[start + j] = ch
    coupling_line = "".join(coupling_line_chars)

    center_pos = tank_pos[n // 2]
    gnd_wire_chars = [" "] * line_len
    gnd_wire_chars[center_pos] = "│"
    gnd_wire = "".join(gnd_wire_chars)

    gnd_chars = [" "] * line_len
    gnd_label = "GND"
    start = center_pos - len(gnd_label) // 2
    for j, ch in enumerate(gnd_label):
        if 0 <= start + j < line_len:
            gnd_chars[start + j] = ch
    gnd = "".join(gnd_chars)

    return "\n".join(
        [
            main_line,
            vert1,
            tank_top,
            tank_r1,
            tank_r2,
            tank_r3,
            tank_bot,
            vert2,
            coupling_line,
            gnd_wire,
            gnd,
        ]
    )


def print_shunt_c_diagram(n: int) -> None:
    """Print Shunt-C (bottom-coupled) topology diagram.

    Coupling capacitors connect bottoms of adjacent tanks horizontally.

    Args:
        n: Number of resonators
    """
    print(format_shunt_c_diagram(n))
