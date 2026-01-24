"""ASCII plotting utilities and data export for frequency response.

Provides adaptive ASCII frequency response plots with:
- Logarithmic frequency axis
- Labeled dB and frequency axes
- -3dB reference line with crossing point marker
- Adaptive Y-axis range based on response data
- Support for lowpass, highpass, and bandpass filters
"""
import json
import math


def _format_freq_compact(freq_hz: float) -> str:
    """Format frequency compactly for plot labels."""
    if freq_hz >= 1e9:
        return f"{freq_hz/1e9:.3g}G"
    elif freq_hz >= 1e6:
        return f"{freq_hz/1e6:.3g}M"
    elif freq_hz >= 1e3:
        return f"{freq_hz/1e3:.3g}k"
    return f"{freq_hz:.3g}"


def _find_3db_frequency(freqs: list[float], response_db: list[float],
                        direction: str = 'falling') -> float | None:
    """Find frequency where response crosses -3dB threshold.

    Args:
        freqs: List of frequencies in Hz
        response_db: Corresponding magnitude responses in dB
        direction: 'falling' for LPF (crosses going down), 'rising' for HPF

    Returns:
        Interpolated -3dB frequency, or None if not found
    """
    for i in range(len(response_db) - 1):
        if direction == 'falling':
            # LPF: look for crossing from above -3dB to below
            if response_db[i] >= -3 and response_db[i + 1] < -3:
                if response_db[i] == response_db[i + 1]:
                    return freqs[i]
                ratio = (-3 - response_db[i]) / (response_db[i + 1] - response_db[i])
                log_f1, log_f2 = math.log10(freqs[i]), math.log10(freqs[i + 1])
                return 10 ** (log_f1 + ratio * (log_f2 - log_f1))
        else:
            # HPF: look for crossing from below -3dB to above
            if response_db[i] < -3 and response_db[i + 1] >= -3:
                if response_db[i] == response_db[i + 1]:
                    return freqs[i + 1]
                ratio = (-3 - response_db[i]) / (response_db[i + 1] - response_db[i])
                log_f1, log_f2 = math.log10(freqs[i]), math.log10(freqs[i + 1])
                return 10 ** (log_f1 + ratio * (log_f2 - log_f1))
    return None


def render_ascii_plot(freqs: list[float], response_db: list[float],
                      cutoff_hz: float, width: int = 60, height: int = 12,
                      title: str = "Frequency Response (dB)",
                      filter_type: str = 'lowpass') -> str:
    """Render adaptive ASCII frequency response plot.

    Automatically adjusts Y-axis range based on response data. Shows -3dB
    reference line and marks the -3dB crossing point when it differs from
    the specified cutoff frequency.

    Args:
        freqs: List of frequencies in Hz
        response_db: List of magnitude responses in dB
        cutoff_hz: Cutoff/center frequency for labeling
        width: Plot width in characters (min 40)
        height: Plot height in lines (min 6)
        title: Plot title
        filter_type: 'lowpass', 'highpass', or 'bandpass'

    Returns:
        Multi-line string with ASCII plot
    """
    if len(freqs) != len(response_db):
        raise ValueError("Frequency and response lists must have same length")
    if not freqs:
        return "No data to plot"

    width = max(40, width)
    height = max(6, height)

    # Adaptive dB range based on actual response
    db_max = 0
    db_min = max(-60, min(response_db) - 5)

    # Frequency range in log space
    freq_min, freq_max = min(freqs), max(freqs)
    log_min, log_max = math.log10(freq_min), math.log10(freq_max)
    log_range = log_max - log_min or 1.0
    db_range = db_max - db_min or 1.0

    # Grid dimensions (leave room for labels)
    plot_width = width - 8
    plot_height = height - 2
    grid = [[' ' for _ in range(plot_width)] for _ in range(plot_height)]

    # Calculate -3dB row position
    db_3db_row = int((db_max - (-3)) / db_range * (plot_height - 1))
    db_3db_row = max(0, min(plot_height - 1, db_3db_row))

    # Find actual -3dB crossing point
    direction = 'rising' if filter_type == 'highpass' else 'falling'
    f_3db = _find_3db_frequency(freqs, response_db, direction)
    f_3db_col, show_3db_marker = None, False
    if f_3db and f_3db > 0:
        log_f_3db = math.log10(f_3db)
        f_3db_col = int((log_f_3db - log_min) / log_range * (plot_width - 1))
        f_3db_col = max(0, min(plot_width - 1, f_3db_col))
        # Only show marker if -3dB differs significantly from cutoff (>1%)
        show_3db_marker = abs(f_3db - cutoff_hz) / cutoff_hz > 0.01

    # Draw -3dB reference line (dashed)
    for col in range(plot_width):
        if grid[db_3db_row][col] == ' ':
            grid[db_3db_row][col] = '·' if col % 2 == 0 else ' '

    # Plot the response curve - fill from curve down to bottom
    for freq, db in zip(freqs, response_db):
        if freq <= 0:
            continue
        col = int((math.log10(freq) - log_min) / log_range * (plot_width - 1))
        col = max(0, min(plot_width - 1, col))
        row = int((db_max - db) / db_range * (plot_height - 1))
        row = max(0, min(plot_height - 1, row))
        # Fill from curve down to show attenuation region
        for r in range(row, plot_height):
            grid[r][col] = '█'

    # Mark -3dB crossing point
    if show_3db_marker and f_3db_col is not None:
        grid[db_3db_row][f_3db_col] = '●'

    # Build output string
    lines = [title, ""]

    # Add rows with dB labels
    for row_idx in range(plot_height):
        db_val = db_max - (row_idx / (plot_height - 1)) * (db_max - db_min)
        if row_idx == db_3db_row:
            label = "   -3 │"
        elif row_idx == 0:
            label = f"{db_val:5.0f} │"
        elif row_idx == plot_height - 1:
            label = f"{db_min:5.0f} │"
        elif row_idx == plot_height // 2 and abs(row_idx - db_3db_row) > 1:
            label = f"{(db_max + db_min) / 2:5.0f} │"
        else:
            label = "      │"
        lines.append(label + ''.join(grid[row_idx]))

    # X-axis with tick marks at decade subdivisions
    x_axis = list("─" * plot_width)
    tick_multipliers = [1, 2, 5]
    for decade in range(-1, 2):
        for mult in tick_multipliers:
            tick_freq = cutoff_hz * mult * (10 ** decade)
            if freq_min <= tick_freq <= freq_max:
                log_tick = math.log10(tick_freq)
                tick_col = int((log_tick - log_min) / log_range * (plot_width - 1))
                if 0 <= tick_col < plot_width:
                    x_axis[tick_col] = '┼'

    # Add arrow at -3dB crossing
    if show_3db_marker and f_3db_col is not None and 0 <= f_3db_col < plot_width:
        x_axis[f_3db_col] = '▲'
    lines.append("      +" + ''.join(x_axis))

    # Frequency labels
    low_label = _format_freq_compact(freq_min)
    high_label = _format_freq_compact(freq_max)
    fc_col = int((math.log10(cutoff_hz) - log_min) / log_range * plot_width)
    fc_label = _format_freq_compact(cutoff_hz) + "(fc)"
    freq_label = " " * 7 + low_label
    freq_label += " " * max(0, fc_col - len(low_label) - len(fc_label) // 2) + fc_label
    freq_label += " " * max(0, plot_width - fc_col - len(fc_label) // 2 - len(high_label)) + high_label
    lines.append(freq_label)

    # Add -3dB frequency label if it differs from cutoff
    if show_3db_marker and f_3db:
        f3_label = _format_freq_compact(f_3db) + "(-3dB)"
        f3_col = f_3db_col if f_3db_col else plot_width // 2
        lines.append(" " * 7 + " " * f3_col + "▲" + f3_label)

    return '\n'.join(lines)


def render_bandpass_plot(sweep_data: list[tuple[float, float]], f0: float,
                         bw: float, width: int = 60, height: int = 10,
                         title: str = "Frequency Response") -> str:
    """Render ASCII frequency response plot for bandpass filters.

    Args:
        sweep_data: List of (frequency_hz, magnitude_db) tuples
        f0: Center frequency in Hz
        bw: Bandwidth in Hz
        width: Plot width in characters
        height: Plot height in lines
        title: Plot title

    Returns:
        Multi-line string with ASCII plot
    """
    if not sweep_data:
        return "No data to plot"

    freqs = [f for f, _ in sweep_data]
    response_db = [db for _, db in sweep_data]

    f_min, f_max = min(freqs), max(freqs)
    db_max = 0
    db_min = max(-60, min(response_db) - 5)
    db_range = db_max - db_min or 1.0

    log_min = math.log10(f_min) if f_min > 0 else 0
    log_max = math.log10(f_max) if f_max > 0 else 1
    log_range = log_max - log_min or 1.0

    width = max(40, width)
    height = max(6, height)
    grid = [[' ' for _ in range(width)] for _ in range(height)]

    # Plot response - fill from curve down
    for f, db in sweep_data:
        if f <= 0:
            continue
        log_f = math.log10(f)
        col = int((log_f - log_min) / log_range * (width - 1))
        col = max(0, min(width - 1, col))
        row = int((db_max - db) / db_range * (height - 1))
        row = max(0, min(height - 1, row))
        for r in range(row, height):
            grid[r][col] = '█'

    # Draw -3dB reference line
    row_3db = int((db_max - (-3)) / db_range * (height - 1))
    row_3db = max(0, min(height - 1, row_3db))
    for col in range(width):
        if grid[row_3db][col] == ' ':
            grid[row_3db][col] = '·'

    # Mark center frequency
    if f0 > 0:
        log_f0 = math.log10(f0)
        col_f0 = int((log_f0 - log_min) / log_range * (width - 1))
        col_f0 = max(0, min(width - 1, col_f0))
        for row in range(height):
            if grid[row][col_f0] in (' ', '·'):
                grid[row][col_f0] = '│'
        grid[row_3db][col_f0] = '┼'

    # Build output
    lines = [title, ""]
    db_labels = {row_3db: -3, height - 1: int(db_min), 0: 0}

    for row in range(height):
        db_label = db_labels.get(row, None)
        if db_label is not None:
            prefix = f"{db_label:4d} │"
        else:
            prefix = "     │"
        lines.append(prefix + ''.join(grid[row]))

    lines.append("     +" + "─" * width)

    # Frequency labels for bandpass
    f_low = f0 - bw / 2
    f_high = f0 + bw / 2
    label_parts = [
        f"     {_format_freq_compact(f_min):>8}",
        f"{_format_freq_compact(f_low):>10}",
        f"{_format_freq_compact(f0):>8}(f₀)",
        f"{_format_freq_compact(f_high):>10}",
        f"{_format_freq_compact(f_max):>8}"
    ]
    lines.append("  ".join(label_parts)[:6 + width])

    return '\n'.join(lines)


def generate_frequency_points(f0: float, decades: float = 2.0,
                              points_per_decade: int = 20) -> list[float]:
    """Generate logarithmically spaced frequency points around f0.

    Args:
        f0: Center frequency in Hz
        decades: Number of decades to span (total)
        points_per_decade: Points per decade

    Returns:
        List of frequencies in Hz
    """
    total_points = int(decades * points_per_decade)
    start_exp = math.log10(f0) - decades / 2
    return [10 ** (start_exp + i * decades / total_points)
            for i in range(total_points + 1)]


def export_json(sweep_data: list[tuple[float, float]], f0: float, bw: float,
                filter_type: str, order: int, ripple_db: float | None = None) -> str:
    """Export sweep data as JSON string.

    Args:
        sweep_data: List of (frequency_hz, magnitude_db) tuples
        f0: Center frequency in Hz
        bw: Bandwidth in Hz
        filter_type: Filter type name
        order: Filter order
        ripple_db: Chebyshev ripple (optional)

    Returns:
        JSON formatted string
    """
    data = {
        "filter_type": filter_type,
        "f0_hz": f0,
        "bandwidth_hz": bw,
        "order": order,
        "data": [{"frequency_hz": f, "magnitude_db": round(db, 2)} for f, db in sweep_data]
    }
    if ripple_db is not None:
        data["ripple_db"] = ripple_db
    return json.dumps(data, indent=2)


def export_csv(sweep_data: list[tuple[float, float]]) -> str:
    """Export sweep data as CSV string.

    Args:
        sweep_data: List of (frequency_hz, magnitude_db) tuples

    Returns:
        CSV formatted string
    """
    lines = ["frequency_hz,magnitude_db"]
    for f, db in sweep_data:
        lines.append(f"{f},{db:.2f}")
    return '\n'.join(lines)
