"""Threshold analysis for frequency response data.

Finds dB crossing frequencies and formats summary tables.
"""

import math


def _find_db_crossing(
    freqs: list[float],
    response_db: list[float],
    threshold_db: float = -3.0,
    direction: str = "falling",
) -> float | None:
    """Find frequency where response crosses a dB threshold.

    Interpolation is linear in log10(frequency), matching the log axis
    the response is plotted on; linear-in-Hz interpolation would bias
    crossings toward the high side of coarse sample spacing.

    Args:
        freqs: List of frequencies in Hz
        response_db: Corresponding magnitude responses in dB
        threshold_db: dB level to find crossing for (e.g. -3, -10, -20)
        direction: 'falling' for LPF (crosses going down), 'rising' for HPF

    Returns:
        Interpolated crossing frequency in Hz (first crossing found
        scanning low to high), or None if the response never crosses
    """
    for i in range(len(response_db) - 1):
        if direction == "falling":
            if response_db[i] >= threshold_db and response_db[i + 1] < threshold_db:
                # The bracketing condition guarantees the two samples differ,
                # so the interpolation denominator is never zero.
                ratio = (threshold_db - response_db[i]) / (response_db[i + 1] - response_db[i])
                log_f1, log_f2 = math.log10(freqs[i]), math.log10(freqs[i + 1])
                return 10 ** (log_f1 + ratio * (log_f2 - log_f1))
        else:
            if response_db[i] < threshold_db and response_db[i + 1] >= threshold_db:
                ratio = (threshold_db - response_db[i]) / (response_db[i + 1] - response_db[i])
                log_f1, log_f2 = math.log10(freqs[i]), math.log10(freqs[i + 1])
                return 10 ** (log_f1 + ratio * (log_f2 - log_f1))
    return None


def _find_3db_frequency(
    freqs: list[float], response_db: list[float], direction: str = "falling"
) -> float | None:
    """Find frequency where response crosses -3dB threshold.

    Backward-compatible wrapper around _find_db_crossing.
    """
    return _find_db_crossing(freqs, response_db, threshold_db=-3.0, direction=direction)


def find_db_thresholds(
    freqs: list[float],
    response_db: list[float],
    levels: list[float] | None = None,
    filter_type: str = "lowpass",
) -> dict[float, list[float | None]]:
    """Find frequencies at multiple dB threshold levels.

    Args:
        freqs: List of frequencies in Hz
        response_db: Corresponding magnitude responses in dB
        levels: dB levels to find (default: [-3, -10, -20])
        filter_type: 'lowpass', 'highpass', or 'bandpass'

    Returns:
        Dict mapping dB level to list of crossing frequencies in Hz.
        LP/HP: single-element list. BP: [f_low, f_high].
        None entries for crossings not found.
    """
    if levels is None:
        levels = [-3, -10, -20]

    result: dict[float, list[float | None]] = {}

    for level in levels:
        if filter_type == "bandpass":
            # BP has two crossings: one rising (lower freq), one falling (upper freq)
            f_rising = _find_db_crossing(freqs, response_db, level, direction="rising")
            f_falling = _find_db_crossing(freqs, response_db, level, direction="falling")
            # Sort so f_low < f_high
            if f_rising is not None and f_falling is not None:
                f_low, f_high = sorted([f_rising, f_falling])
                result[level] = [f_low, f_high]
            else:
                result[level] = [f_rising, f_falling]
        elif filter_type == "highpass":
            f = _find_db_crossing(freqs, response_db, level, direction="rising")
            result[level] = [f]
        else:
            # lowpass (default)
            f = _find_db_crossing(freqs, response_db, level, direction="falling")
            result[level] = [f]

    return result


def format_threshold_table(
    thresholds: dict[float, list[float | None]],
    filter_type: str = "lowpass",
) -> str:
    """Format dB threshold crossings as an ASCII table.

    Args:
        thresholds: Dict from find_db_thresholds()
        filter_type: 'lowpass', 'highpass', or 'bandpass'

    Returns:
        Multi-line formatted table string
    """
    # Deferred import: plot_ascii_renderers imports from this module at
    # top level, so importing it here avoids a circular import.
    from .plot_ascii_renderers import _format_freq_compact

    is_bandpass = filter_type == "bandpass"

    lines = ["", "dB Threshold Summary"]

    if is_bandpass:
        lines.append(f"\u250c{'─' * 8}\u252c{'─' * 14}\u252c{'─' * 14}\u2510")
        lines.append(f"\u2502{'Level':^8}\u2502{'f_low':^14}\u2502{'f_high':^14}\u2502")
        lines.append(f"\u251c{'─' * 8}\u253c{'─' * 14}\u253c{'─' * 14}\u2524")
    else:
        lines.append(f"\u250c{'─' * 8}\u252c{'─' * 14}\u2510")
        lines.append(f"\u2502{'Level':^8}\u2502{'Frequency':^14}\u2502")
        lines.append(f"\u251c{'─' * 8}\u253c{'─' * 14}\u2524")

    arrow = "\u2193" if filter_type == "lowpass" else "\u2191"

    for level in sorted(thresholds.keys(), reverse=True):
        crossings = thresholds[level]
        level_str = f"{int(level):+d} dB" if level == int(level) else f"{level:+.1f} dB"

        if is_bandpass:
            f_low_str = _format_freq_compact(crossings[0]) if crossings[0] is not None else "N/A"
            f_high_str = _format_freq_compact(crossings[1]) if crossings[1] is not None else "N/A"
            lines.append(f"\u2502{level_str:^8}\u2502{f_low_str:^14}\u2502{f_high_str:^14}\u2502")
        else:
            freq = crossings[0]
            freq_str = f"{arrow} {_format_freq_compact(freq)}" if freq is not None else "N/A"
            lines.append(f"\u2502{level_str:^8}\u2502{freq_str:^14}\u2502")

    if is_bandpass:
        lines.append(f"\u2514{'─' * 8}\u2534{'─' * 14}\u2534{'─' * 14}\u2518")
    else:
        lines.append(f"\u2514{'─' * 8}\u2534{'─' * 14}\u2518")

    return "\n".join(lines)
