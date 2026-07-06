"""ASCII rendering functions for frequency response plots.

Provides adaptive ASCII frequency response plots with:
- Logarithmic frequency axis
- Labeled dB and frequency axes
- -3dB reference line with crossing point marker
- Adaptive Y-axis range based on response data
- Support for lowpass, highpass, and bandpass filters
"""

import math

from .plot_threshold_analysis import _find_3db_frequency


def _format_freq_compact(freq_hz: float) -> str:
    """Format a frequency in Hz as a short label like '10M' or '3.5k'.

    Suffix only (no 'Hz') to keep axis labels narrow; 3 significant
    figures is the most that fits under a 60-column plot.
    """
    if freq_hz >= 1e9:
        return f"{freq_hz / 1e9:.3g}G"
    elif freq_hz >= 1e6:
        return f"{freq_hz / 1e6:.3g}M"
    elif freq_hz >= 1e3:
        return f"{freq_hz / 1e3:.3g}k"
    return f"{freq_hz:.3g}"


def render_ascii_plot(
    freqs: list[float],
    response_db: list[float],
    cutoff_hz: float,
    width: int = 60,
    height: int = 12,
    title: str = "Frequency Response (dB)",
    filter_type: str = "lowpass",
    db_floor: float | None = None,
) -> str:
    """Render adaptive ASCII frequency response plot.

    Args:
        freqs: List of frequencies in Hz
        response_db: List of magnitude responses in dB
        cutoff_hz: Cutoff/center frequency for labeling
        width: Plot width in characters (min 40)
        height: Plot height in lines (min 6)
        title: Plot title
        filter_type: 'lowpass', 'highpass', or 'bandpass'
        db_floor: Fixed dB minimum for Y-axis. None = auto-range.

    Returns:
        Multi-line string with ASCII plot

    Raises:
        ValueError: If freqs and response_db have different lengths.
    """
    if len(freqs) != len(response_db):
        raise ValueError("Frequency and response lists must have same length")
    if not freqs:
        return "No data to plot"

    width = max(40, width)
    height = max(6, height)

    # Y-axis: 0 dB always at top; auto floor clamps at -60 dB so deep
    # stopband tails don't flatten the passband into one or two rows.
    # The -5 pad keeps the deepest sample off the bottom border.
    db_max = 0
    if db_floor is not None:
        db_min = db_floor
    else:
        db_min = max(-60, min(response_db) - 5)

    # X-axis is log-frequency. The `or 1.0` fallbacks avoid divide-by-zero
    # for degenerate single-point/flat inputs (renderer must never crash).
    freq_min, freq_max = min(freqs), max(freqs)
    log_min, log_max = math.log10(freq_min), math.log10(freq_max)
    log_range = log_max - log_min or 1.0
    db_range = db_max - db_min or 1.0

    # Grid dimensions (leave room for labels)
    plot_width = width - 8
    plot_height = height - 2
    grid = [[" " for _ in range(plot_width)] for _ in range(plot_height)]

    # Calculate -3dB row position
    db_3db_row = int((db_max - (-3)) / db_range * (plot_height - 1))
    db_3db_row = max(0, min(plot_height - 1, db_3db_row))

    # Find the actual -3dB crossing (interpolated from samples, not fc)
    direction = "rising" if filter_type == "highpass" else "falling"
    f_3db = _find_3db_frequency(freqs, response_db, direction)
    f_3db_col, show_3db_marker = None, False
    if f_3db and f_3db > 0:
        log_f_3db = math.log10(f_3db)
        f_3db_col = int((log_f_3db - log_min) / log_range * (plot_width - 1))
        f_3db_col = max(0, min(plot_width - 1, f_3db_col))
        # Marker only when -3dB deviates >1% from fc. This matters for
        # Chebyshev, where fc is the ripple-band edge and the true -3 dB
        # point sits beyond it; for Butterworth the two coincide and a
        # marker would just be noise.
        show_3db_marker = abs(f_3db - cutoff_hz) / cutoff_hz > 0.01

    # Draw -3dB reference line (dashed) — skip if outside plot range
    if 0 < db_3db_row < plot_height - 1:
        for col in range(plot_width):
            if grid[db_3db_row][col] == " ":
                grid[db_3db_row][col] = "\u00b7" if col % 2 == 0 else " "

    # Plot the response as a filled area (curve down to bottom): solid
    # blocks read better at terminal resolution than a 1-char-thin line,
    # which fragments on steep skirts where adjacent samples skip rows.
    for freq, db in zip(freqs, response_db):
        if freq <= 0:
            continue
        col = int((math.log10(freq) - log_min) / log_range * (plot_width - 1))
        col = max(0, min(plot_width - 1, col))
        row = int((db_max - db) / db_range * (plot_height - 1))
        row = max(0, min(plot_height - 1, row))
        for r in range(row, plot_height):
            grid[r][col] = "\u2588"

    # Mark -3dB crossing point
    if show_3db_marker and f_3db_col is not None and 0 < db_3db_row < plot_height - 1:
        grid[db_3db_row][f_3db_col] = "\u25cf"

    # Build output string
    lines = [title, ""]

    # Add rows with dB labels
    for row_idx in range(plot_height):
        db_val = db_max - (row_idx / (plot_height - 1)) * (db_max - db_min)
        if row_idx == db_3db_row and 0 < db_3db_row < plot_height - 1:
            label = "   -3 \u2502"
        elif row_idx == 0:
            label = f"{db_val:5.0f} \u2502"
        elif row_idx == plot_height - 1:
            label = f"{db_min:5.0f} \u2502"
        elif row_idx == plot_height // 2 and abs(row_idx - db_3db_row) > 1:
            label = f"{(db_max + db_min) / 2:5.0f} \u2502"
        else:
            label = "      \u2502"
        lines.append(label + "".join(grid[row_idx]))

    # X-axis ticks at the 1-2-5 log-scale subdivisions of each decade
    # around fc \u2014 standard graph-paper spacing on a log axis.
    x_axis = list("\u2500" * plot_width)
    tick_multipliers = [1, 2, 5]
    for decade in range(-1, 2):
        for mult in tick_multipliers:
            tick_freq = cutoff_hz * mult * (10**decade)
            if freq_min <= tick_freq <= freq_max:
                log_tick = math.log10(tick_freq)
                tick_col = int((log_tick - log_min) / log_range * (plot_width - 1))
                if 0 <= tick_col < plot_width:
                    x_axis[tick_col] = "\u253c"

    # Add arrow at -3dB crossing
    if show_3db_marker and f_3db_col is not None and 0 <= f_3db_col < plot_width:
        x_axis[f_3db_col] = "\u25b2"
    lines.append("      +" + "".join(x_axis))

    # Frequency labels
    low_label = _format_freq_compact(freq_min)
    high_label = _format_freq_compact(freq_max)
    fc_col = int((math.log10(cutoff_hz) - log_min) / log_range * plot_width)
    fc_label = _format_freq_compact(cutoff_hz) + "(fc)"
    freq_label = " " * 7 + low_label
    freq_label += " " * max(0, fc_col - len(low_label) - len(fc_label) // 2) + fc_label
    freq_label += (
        " " * max(0, plot_width - fc_col - len(fc_label) // 2 - len(high_label)) + high_label
    )
    lines.append(freq_label)

    # Add -3dB frequency label if it differs from cutoff
    if show_3db_marker and f_3db and 0 < db_3db_row < plot_height - 1:
        f3_label = _format_freq_compact(f_3db) + "(-3dB)"
        f3_col = f_3db_col if f_3db_col else plot_width // 2
        lines.append(" " * 7 + " " * f3_col + "\u25b2" + f3_label)

    return "\n".join(lines)


def render_bandpass_plot(
    sweep_data: list[tuple[float, float]],
    f0: float,
    bw: float,
    f_low_hz: float | None = None,
    f_high_hz: float | None = None,
    width: int = 60,
    height: int = 10,
    title: str = "Frequency Response",
    db_floor: float | None = None,
) -> str:
    """Render ASCII frequency response plot for bandpass filters.

    Args:
        sweep_data: List of (frequency_hz, magnitude_db) tuples
        f0: Center frequency in Hz
        bw: Bandwidth in Hz
        f_low_hz: Optional lower band edge for labeling
        f_high_hz: Optional upper band edge for labeling
        width: Plot width in characters
        height: Plot height in lines
        title: Plot title
        db_floor: Fixed dB minimum for Y-axis. None = auto-range.

    Returns:
        Multi-line string with ASCII plot
    """
    if not sweep_data:
        return "No data to plot"

    freqs = [f for f, _ in sweep_data]
    response_db = [db for _, db in sweep_data]

    f_min, f_max = min(freqs), max(freqs)
    db_max = 0
    if db_floor is not None:
        db_min = db_floor
    else:
        db_min = max(-60, min(response_db) - 5)
    db_range = db_max - db_min or 1.0

    log_min = math.log10(f_min) if f_min > 0 else 0
    log_max = math.log10(f_max) if f_max > 0 else 1
    log_range = log_max - log_min or 1.0

    width = max(40, width)
    height = max(6, height)
    grid = [[" " for _ in range(width)] for _ in range(height)]

    # Filled-area rendering, same rationale as render_ascii_plot
    for f, db in sweep_data:
        if f <= 0:
            continue
        log_f = math.log10(f)
        col = int((log_f - log_min) / log_range * (width - 1))
        col = max(0, min(width - 1, col))
        row = int((db_max - db) / db_range * (height - 1))
        row = max(0, min(height - 1, row))
        for r in range(row, height):
            grid[r][col] = "\u2588"

    # Draw -3dB reference line — skip if outside plot range
    row_3db = int((db_max - (-3)) / db_range * (height - 1))
    row_3db = max(0, min(height - 1, row_3db))
    if 0 < row_3db < height - 1:
        for col in range(width):
            if grid[row_3db][col] == " ":
                grid[row_3db][col] = "\u00b7"

    # Vertical f0 marker — only drawn over blank/reference cells so it
    # never erases the response curve itself.
    if f0 > 0:
        log_f0 = math.log10(f0)
        col_f0 = int((log_f0 - log_min) / log_range * (width - 1))
        col_f0 = max(0, min(width - 1, col_f0))
        for row in range(height):
            if grid[row][col_f0] in (" ", "\u00b7"):
                grid[row][col_f0] = "\u2502"
        if 0 < row_3db < height - 1:
            grid[row_3db][col_f0] = "\u253c"

    # Build output
    lines = [title, ""]
    db_labels = {0: 0}
    if 0 < row_3db < height - 1:
        db_labels[row_3db] = -3
    db_labels[height - 1] = int(db_min)

    for row in range(height):
        db_label = db_labels.get(row, None)
        if db_label is not None:
            prefix = f"{db_label:4d} \u2502"
        else:
            prefix = "     \u2502"
        lines.append(prefix + "".join(grid[row]))

    lines.append("     +" + "\u2500" * width)

    # Frequency labels for bandpass — use explicit edges when supplied,
    # otherwise compute the exact quadratic -3 dB edges. For degenerate
    # inputs (f0=0 or bw=0) the quadratic is undefined, so fall back to the
    # arithmetic approximation just to keep the renderer crash-free.
    if f_low_hz is not None and f_high_hz is not None:
        f_low, f_high = f_low_hz, f_high_hz
    elif f0 > 0 and bw > 0:
        from ..bandpass.calculations import compute_bandpass_3db_edges

        f_low, f_high = compute_bandpass_3db_edges(f0, bw)
    else:
        # Degenerate (f0<=0 or bw<=0): fall back to arithmetic so the renderer
        # stays crash-free for pathological test inputs.
        f_low, f_high = f0 - bw / 2, f0 + bw / 2
    label_parts = [
        f"     {_format_freq_compact(f_min):>8}",
        f"{_format_freq_compact(f_low):>10}",
        f"{_format_freq_compact(f0):>8}(f\u2080)",
        f"{_format_freq_compact(f_high):>10}",
        f"{_format_freq_compact(f_max):>8}",
    ]
    # Truncate to the axis width (6-char gutter + plot) so the label row
    # never extends past the plot frame.
    lines.append("  ".join(label_parts)[: 6 + width])

    return "\n".join(lines)
