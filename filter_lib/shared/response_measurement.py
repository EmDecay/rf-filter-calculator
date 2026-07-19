"""Frequency-grid and response-landmark measurements for simulated circuits."""

import math

from .numeric import is_finite_real
from .transfer_functions import MAX_FREQUENCY_POINTS


def _is_real(value: object) -> bool:
    return is_finite_real(value)


def _validate_response_arrays(freqs: list[float], mags: list[float]) -> None:
    if len(freqs) != len(mags):
        raise ValueError("freqs and mags must have the same length")
    if any(not _is_real(frequency) or frequency <= 0 for frequency in freqs):
        raise ValueError("frequencies must be positive and finite")
    if any(not _is_real(magnitude) or magnitude < 0 for magnitude in mags):
        raise ValueError("magnitudes must be finite and non-negative")


def _peak_index(freqs: list[float], mags: list[float], reference: float | None) -> int:
    if reference is None:
        return max(range(len(mags)), key=mags.__getitem__)
    local_maxima = [
        index
        for index, value in enumerate(mags)
        if (index == 0 or value >= mags[index - 1])
        and (index == len(mags) - 1 or value >= mags[index + 1])
    ]
    return min(
        local_maxima,
        key=lambda index: (abs(freqs[index] - reference), -mags[index]),
    )


def _threshold_runs(mags: list[float], threshold: float) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(mags):
        if mags[index] < threshold:
            index += 1
            continue
        start = index
        while index + 1 < len(mags) and mags[index + 1] >= threshold:
            index += 1
        runs.append((start, index))
        index += 1
    return runs


def _selected_run(
    freqs: list[float],
    mags: list[float],
    runs: list[tuple[int, int]],
    peak_index: int,
    threshold: float,
    reference: float | None,
) -> tuple[int, int]:
    anchor_index = peak_index
    if reference is not None:
        nearest = min(range(len(freqs)), key=lambda index: abs(freqs[index] - reference))
        if mags[nearest] >= threshold:
            anchor_index = nearest
    selected = next(
        ((start, end) for start, end in runs if start <= anchor_index <= end),
        None,
    )
    if selected is not None:
        return selected
    return min(
        runs,
        key=lambda run: min(abs(anchor_index - run[0]), abs(anchor_index - run[1])),
    )


def _interpolate_crossing(
    freqs: list[float], mags: list[float], threshold: float, outside: int, inside: int
) -> float:
    m1, m2 = mags[outside], mags[inside]
    f1, f2 = freqs[outside], freqs[inside]
    if m2 == m1:
        return f1
    return f1 + (threshold - m1) / (m2 - m1) * (f2 - f1)


def find_3db_edges(
    freqs: list[float],
    mags: list[float],
    reference_frequency: float | None = None,
) -> tuple[float | None, float | None]:
    """Find the connected -3 dB band around the intended response peak."""
    if reference_frequency is not None and (
        not is_finite_real(reference_frequency) or reference_frequency <= 0
    ):
        raise ValueError("reference_frequency must be positive and finite")
    _validate_response_arrays(freqs, mags)
    if not freqs:
        return None, None
    if any(right <= left for left, right in zip(freqs, freqs[1:])):
        raise ValueError("frequencies must be strictly increasing")

    peak_index = _peak_index(freqs, mags, reference_frequency)
    peak = mags[peak_index]
    if not math.isfinite(peak) or peak <= 0:
        return None, None
    threshold = peak / math.sqrt(2)
    runs = _threshold_runs(mags, threshold)
    if not runs:
        return None, None
    lo_index, hi_index = _selected_run(
        freqs,
        mags,
        runs,
        peak_index,
        threshold,
        reference_frequency,
    )
    f_low = (
        _interpolate_crossing(freqs, mags, threshold, lo_index - 1, lo_index)
        if lo_index > 0
        else freqs[0]
    )
    f_high = (
        _interpolate_crossing(freqs, mags, threshold, hi_index + 1, hi_index)
        if hi_index < len(mags) - 1
        else freqs[-1]
    )
    return f_low, f_high


def passband_ripple_db(
    freqs: list[float], mags: list[float], f_limit: float
) -> tuple[float, float]:
    """Return absolute (maximum dB, minimum dB) over ``freqs <= f_limit``."""
    if not is_finite_real(f_limit) or f_limit <= 0:
        raise ValueError("f_limit must be positive and finite")
    _validate_response_arrays(freqs, mags)
    in_band = [magnitude for frequency, magnitude in zip(freqs, mags) if frequency <= f_limit]
    if not in_band:
        raise ValueError("No frequency points at or below f_limit")
    db = [20 * math.log10(magnitude) if magnitude > 0 else -math.inf for magnitude in in_band]
    return max(db), min(db)


def logspace(start_exp: float, stop_exp: float, points: int) -> list[float]:
    """Log-spaced grid from 10**start_exp to 10**stop_exp inclusive."""
    if not _is_real(start_exp) or not _is_real(stop_exp):
        raise ValueError("logspace exponents must be finite real numbers")
    if (
        isinstance(points, bool)
        or not isinstance(points, int)
        or not 2 <= points <= MAX_FREQUENCY_POINTS
    ):
        raise ValueError(
            f"points must be >= 2 and <= {MAX_FREQUENCY_POINTS:,}, and must be an integer"
        )
    step = (stop_exp - start_exp) / (points - 1)
    try:
        result = [10 ** (start_exp + index * step) for index in range(points)]
    except OverflowError as error:
        raise ValueError("logspace values must be positive and finite") from error
    if any(not math.isfinite(value) or value <= 0 for value in result):
        raise ValueError("logspace values must be positive and finite")
    return result
