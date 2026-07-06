"""ASCII topology diagram for Top-C (series capacitive) coupled bandpass filters."""


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
    # Layout constants are tied to the main_line template below: each repeated
    # coupling segment "──────┤├──────┬" is 15 chars wide, and the first tank
    # branch "┬" sits at index 11 of the "  IN ──┤├──┬" prefix. Changing the
    # template requires re-deriving both offsets.
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
    # 8 centers the label over the "┤├" end-cap symbols, which sit a fixed
    # distance from each end of the template regardless of resonator count.
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
