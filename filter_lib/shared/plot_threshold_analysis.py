"""Threshold analysis for frequency response data.

Finds dB crossing frequencies and formats summary tables.
"""

import math
from dataclasses import dataclass

from .numeric import is_finite_real


@dataclass(frozen=True)
class ThresholdRegion:
    """One connected run whose sampled response is at or above a threshold.

    ``f_low`` or ``f_high`` is ``None`` when that skirt lies outside the
    supplied frequency grid. The sample indexes remain useful to callers
    that need to inspect ripple holes or select a region around a known
    passband center.
    """

    f_low: float | None
    f_high: float | None
    start_index: int
    end_index: int
    peak_db: float


def _interpolate_log_crossing(
    f1: float, db1: float, f2: float, db2: float, threshold_db: float
) -> float:
    """Interpolate one threshold crossing on the logarithmic frequency axis."""
    if db1 == threshold_db:
        return f1
    if db2 == threshold_db:
        return f2
    ratio = (threshold_db - db1) / (db2 - db1)
    return 10 ** (math.log10(f1) + ratio * (math.log10(f2) - math.log10(f1)))


def find_threshold_regions(
    freqs: list[float], response_db: list[float], threshold_db: float
) -> list[ThresholdRegion]:
    """Return every connected response region at or above ``threshold_db``.

    Frequencies must form a positive, strictly increasing grid. Exact
    threshold samples are inside a region, which makes plateaus deterministic
    and prevents a crossing from disappearing because of equality rounding.

    Args:
        freqs: Positive, strictly increasing frequencies in Hz.
        response_db: Magnitude response in dB, one value per frequency.
        threshold_db: Absolute threshold in dB.

    Returns:
        Connected regions in ascending-frequency order.

    Raises:
        ValueError: If lengths differ, the grid is invalid, or values are not
            finite.
    """
    if len(freqs) != len(response_db):
        raise ValueError("freqs and response_db must have the same length")
    if not is_finite_real(threshold_db):
        raise ValueError("threshold_db must be finite")
    if any(not is_finite_real(f) or f <= 0 for f in freqs):
        raise ValueError("frequencies must be positive and finite")
    if any(right <= left for left, right in zip(freqs, freqs[1:])):
        raise ValueError("frequencies must be strictly increasing")
    if any(not is_finite_real(db) for db in response_db):
        raise ValueError("response_db values must be finite")

    regions: list[ThresholdRegion] = []
    i = 0
    while i < len(response_db):
        if response_db[i] < threshold_db:
            i += 1
            continue

        start = i
        while i + 1 < len(response_db) and response_db[i + 1] >= threshold_db:
            i += 1
        end = i

        f_low = None
        if start > 0:
            f_low = _interpolate_log_crossing(
                freqs[start - 1],
                response_db[start - 1],
                freqs[start],
                response_db[start],
                threshold_db,
            )
        f_high = None
        if end + 1 < len(response_db):
            f_high = _interpolate_log_crossing(
                freqs[end],
                response_db[end],
                freqs[end + 1],
                response_db[end + 1],
                threshold_db,
            )
        regions.append(
            ThresholdRegion(
                f_low=f_low,
                f_high=f_high,
                start_index=start,
                end_index=end,
                peak_db=max(response_db[start : end + 1]),
            )
        )
        i += 1
    return regions


def _select_threshold_region(
    regions: list[ThresholdRegion],
    freqs: list[float],
    filter_type: str,
    reference_frequency: float | None,
) -> ThresholdRegion | None:
    """Select the passband region appropriate for a filter category."""
    if not regions:
        return None
    if filter_type == "lowpass":
        return next((region for region in regions if region.start_index == 0), None)
    if filter_type == "highpass":
        last = len(freqs) - 1
        return next((region for region in reversed(regions) if region.end_index == last), None)
    if reference_frequency is None:
        return max(regions, key=lambda region: (region.peak_db, -region.start_index))
    if not is_finite_real(reference_frequency) or reference_frequency <= 0:
        raise ValueError("reference_frequency must be positive and finite")

    log_reference = math.log(reference_frequency)

    def distance(region: ThresholdRegion) -> tuple[float, float]:
        start = freqs[region.start_index]
        end = freqs[region.end_index]
        if start <= reference_frequency <= end:
            return 0.0, -region.peak_db
        nearest = start if reference_frequency < start else end
        return abs(math.log(nearest) - log_reference), -region.peak_db

    return min(regions, key=distance)


def _has_region_compatible_grid(freqs: list[float], response_db: list[float]) -> bool:
    """Whether strict connected-region analysis can safely consume this grid."""
    return (
        len(freqs) == len(response_db)
        and all(is_finite_real(f) and f > 0 for f in freqs)
        and all(right > left for left, right in zip(freqs, freqs[1:]))
        and all(is_finite_real(db) for db in response_db)
    )


def _reference_passband_peak_db(
    freqs: list[float], response_db: list[float], reference_frequency: float
) -> float:
    """Return the local response peak nearest a requested passband center.

    Using the global maximum would let an unrelated spur re-baseline a lossy
    intended passband. Local maxima are determined from neighboring samples;
    a flat plateau is deterministic and equally suitable as the reference.
    """
    if not is_finite_real(reference_frequency) or reference_frequency <= 0:
        raise ValueError("reference_frequency must be positive and finite")
    local_maxima = [
        i
        for i, value in enumerate(response_db)
        if (i == 0 or value >= response_db[i - 1])
        and (i == len(response_db) - 1 or value >= response_db[i + 1])
    ]
    if not local_maxima:
        return max(response_db)
    log_reference = math.log(reference_frequency)
    peak_index = min(
        local_maxima,
        key=lambda index: (
            abs(math.log(freqs[index]) - log_reference),
            -response_db[index],
        ),
    )
    return response_db[peak_index]


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
    *,
    reference_frequency: float | None = None,
    relative_to_peak: bool = False,
) -> dict[float, list[float | None]]:
    """Find frequencies at multiple dB threshold levels.

    Args:
        freqs: List of frequencies in Hz
        response_db: Corresponding magnitude responses in dB
        levels: dB levels to find (default: [-3, -10, -20])
        filter_type: 'lowpass', 'highpass', or 'bandpass'
        reference_frequency: Intended bandpass center used to reject unrelated
            disconnected lobes. When omitted, the highest region is selected.
        relative_to_peak: Interpret each level relative to the sampled peak.

    Returns:
        Dict mapping dB level to list of crossing frequencies in Hz.
        LP/HP: single-element list. BP: [f_low, f_high].
        None entries for crossings not found.
    """
    if levels is None:
        levels = [-3, -10, -20]

    result: dict[float, list[float | None]] = {}

    for level in levels:
        effective_level = level
        if relative_to_peak and response_db:
            if filter_type == "bandpass" and reference_frequency is not None:
                reference_peak = _reference_passband_peak_db(
                    freqs, response_db, reference_frequency
                )
            else:
                reference_peak = max(response_db)
            effective_level = reference_peak + level

        if _has_region_compatible_grid(freqs, response_db):
            regions = find_threshold_regions(freqs, response_db, effective_level)
            selected = _select_threshold_region(regions, freqs, filter_type, reference_frequency)
            if filter_type == "bandpass":
                result[level] = (
                    [selected.f_low, selected.f_high] if selected is not None else [None, None]
                )
            elif filter_type == "highpass":
                result[level] = [selected.f_low if selected is not None else None]
            else:
                result[level] = [selected.f_high if selected is not None else None]
            continue

        # Preserve the permissive behavior of the legacy wrapper for malformed
        # grids. New callers that need deterministic diagnostics should call
        # find_threshold_regions directly and receive strict validation.
        if filter_type == "bandpass":
            # BP has two crossings: one rising (lower freq), one falling (upper freq)
            f_rising = _find_db_crossing(freqs, response_db, effective_level, direction="rising")
            f_falling = _find_db_crossing(freqs, response_db, effective_level, direction="falling")
            # Sort so f_low < f_high
            if f_rising is not None and f_falling is not None:
                f_low, f_high = sorted([f_rising, f_falling])
                result[level] = [f_low, f_high]
            else:
                result[level] = [f_rising, f_falling]
        elif filter_type == "highpass":
            f = _find_db_crossing(freqs, response_db, effective_level, direction="rising")
            result[level] = [f]
        else:
            # lowpass (default)
            f = _find_db_crossing(freqs, response_db, effective_level, direction="falling")
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
