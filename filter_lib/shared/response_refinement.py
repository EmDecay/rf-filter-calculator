"""Bounded, evaluated response landmarks shared by build and plot reporting.

Mesh doubling detects missed structure; local optimization and bisection avoid
making measurements depend on how closely a grid happens to hit an extremum.
Convergence is numerical evidence on the finite window, not an interval proof.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, replace

from .numeric import is_finite_real
from .plot_threshold_analysis import find_threshold_regions

GAIN_TOLERANCE_DB = 0.001
FREQUENCY_TOLERANCE_FRACTION = 1e-5
MAX_REFINEMENT_PASSES = 4


@dataclass(frozen=True)
class RefinedResponse:
    """Evaluated landmarks and their convergence evidence."""

    frequencies: tuple[float, ...]
    response_db: tuple[float, ...]
    peak_db: float
    worst_db: float
    reference_frequency: float
    reference_db: float
    regions: tuple[tuple[float | None, float | None], ...]
    selected_region: int | None
    converged: bool
    evaluations: int


def refine_crossing(
    response_fn: Callable[[float], float],
    low: float,
    high: float,
    threshold: float,
    tolerance_hz: float,
) -> float:
    """Bisect a bracket using evaluated dB, with a finite iteration budget."""
    if (
        not all(is_finite_real(f) and f > 0 for f in (low, high, tolerance_hz))
        or high <= low
        or not is_finite_real(threshold)
    ):
        raise ValueError("crossing bracket, threshold and tolerance must be finite and ordered")
    low_db = response_fn(low)
    high_db = response_fn(high)
    if not all(is_finite_real(value) for value in (low_db, high_db)):
        raise ValueError("crossing response must be finite")
    if low_db == threshold:
        return low
    if high_db == threshold:
        return high
    if (low_db >= threshold) == (high_db >= threshold):
        raise ValueError("evaluated response does not bracket the requested threshold")
    for _ in range(64):
        middle = low + (high - low) / 2
        if high - low <= tolerance_hz or middle in (low, high):
            return middle
        value = response_fn(middle)
        if not is_finite_real(value):
            raise ValueError("crossing response must be finite")
        if (value >= threshold) == (low_db >= threshold):
            low, low_db = middle, value
        else:
            high = middle
    return low + (high - low) / 2


def _extremum(fn: Callable[[float], float], low: float, high: float, sign: int, tol: float):
    """Golden-section search within one sampled local-extremum bracket."""
    ratio = (math.sqrt(5) - 1) / 2
    left, right = high - ratio * (high - low), low + ratio * (high - low)
    yl, yr = sign * fn(left), sign * fn(right)
    for _ in range(48):
        if high - low <= tol:
            break
        if yl < yr:
            low, left, yl = left, right, yr
            right = low + ratio * (high - low)
            yr = sign * fn(right)
        else:
            high, right, yr = right, left, yl
            left = high - ratio * (high - low)
            yl = sign * fn(left)
    return left if yl >= yr else right


def _landmarks(fn, grid, passband, reference, scale, drop_db):
    values = [fn(f) for f in grid]
    extra = []
    for i in range(1, len(grid) - 1):
        value, left, right = values[i], values[i - 1], values[i + 1]
        for sign in (1, -1):
            # Ignore numerical ripple on an essentially flat response.
            if sign * value >= max(sign * left, sign * right) and (
                sign * value - min(sign * left, sign * right) > 1e-7
            ):
                extra.append(_extremum(fn, grid[i - 1], grid[i + 1], sign, scale * 1e-7))
    grid = sorted(set(grid + extra))
    values = [fn(f) for f in grid]
    peaks = [
        i
        for i, value in enumerate(values)
        if (i == 0 or value >= values[i - 1]) and (i == len(grid) - 1 or value >= values[i + 1])
    ]
    peak_index = (
        min(peaks, key=lambda i: (abs(grid[i] - reference), -values[i]))
        if reference is not None
        else max(range(len(grid)), key=values.__getitem__)
    )
    threshold = values[peak_index] - drop_db
    sampled_regions = find_threshold_regions(grid, values, threshold)
    regions = []
    selected = None
    for index, region in enumerate(sampled_regions):
        start, end = region.start_index, region.end_index
        low = (
            None
            if start == 0
            else refine_crossing(fn, grid[start - 1], grid[start], threshold, scale * 1e-7)
        )
        high = (
            None
            if end == len(grid) - 1
            else refine_crossing(fn, grid[end], grid[end + 1], threshold, scale * 1e-7)
        )
        regions.append((low, high))
        if start <= peak_index <= end:
            selected = index
    return RefinedResponse(
        tuple(grid),
        tuple(values),
        max(values),
        min(value for f, value in zip(grid, values) if passband[0] <= f <= passband[1]),
        grid[peak_index],
        values[peak_index],
        tuple(regions),
        selected,
        False,
        0,
    )


def _agrees(previous: RefinedResponse, current: RefinedResponse, scale: float) -> bool:
    if previous.selected_region != current.selected_region or len(previous.regions) != len(
        current.regions
    ):
        return False
    for a, b in zip(
        (previous.peak_db, previous.worst_db, previous.reference_db),
        (current.peak_db, current.worst_db, current.reference_db),
    ):
        if abs(a - b) > GAIN_TOLERANCE_DB:
            return False
    for previous_pair, current_pair in zip(previous.regions, current.regions):
        for a, b in zip(previous_pair, current_pair):
            if a is None or b is None:
                if a != b:
                    return False
            elif abs(a - b) > scale * FREQUENCY_TOLERANCE_FRACTION:
                return False
    return True


def refine_response(
    response_fn: Callable[[float], float],
    freqs: list[float],
    passband: tuple[float, float],
    *,
    reference_frequency: float | None = None,
    frequency_scale: float,
    drop_db: float = 10 * math.log10(2),
    max_passes: int = MAX_REFINEMENT_PASSES,
) -> RefinedResponse:
    """Refine landmarks until consecutive meshes agree or the budget expires.

    Frequencies and passband must be finite, positive, and ordered. The scale
    is requested bandwidth for BP, cutoff for LP/HP. Each pass bisects every
    initial-grid interval (at most four passes); extrema/crossings are further
    evaluated locally. Exact passband boundaries are always included.
    """
    if (
        not isinstance(max_passes, int)
        or isinstance(max_passes, bool)
        or not 1 <= max_passes <= MAX_REFINEMENT_PASSES
    ):
        raise ValueError(f"max_passes must be an integer in [1, {MAX_REFINEMENT_PASSES}]")
    if not is_finite_real(frequency_scale) or frequency_scale <= 0:
        raise ValueError("frequency_scale must be positive and finite")
    if not is_finite_real(drop_db) or drop_db <= 0:
        raise ValueError("drop_db must be positive and finite")
    if (
        not isinstance(freqs, (list, tuple))
        or len(freqs) < 2
        or any(not is_finite_real(f) or f <= 0 for f in freqs)
        or any(b <= a for a, b in zip(freqs, freqs[1:]))
    ):
        raise ValueError("frequencies must be positive, finite and strictly increasing")
    if (
        not isinstance(passband, (list, tuple))
        or len(passband) != 2
        or not all(is_finite_real(f) and f > 0 for f in passband)
        or passband[1] <= passband[0]
    ):
        raise ValueError("passband must have positive finite ordered boundaries")
    if reference_frequency is not None and (
        not is_finite_real(reference_frequency) or reference_frequency <= 0
    ):
        raise ValueError("reference_frequency must be positive and finite")

    cache: dict[float, float] = {}

    def evaluate(frequency: float) -> float:
        if frequency not in cache:
            value = response_fn(frequency)
            if not is_finite_real(value):
                raise ValueError("response refinement requires finite dB values")
            cache[frequency] = value
        return cache[frequency]

    grid = sorted(
        set(list(freqs) + list(passband) + ([reference_frequency] if reference_frequency else []))
    )
    previous = None
    for _ in range(max_passes):
        current = _landmarks(
            evaluate, grid, passband, reference_frequency, frequency_scale, drop_db
        )
        if previous is not None and _agrees(previous, current, frequency_scale):
            return replace(current, converged=True, evaluations=len(cache))
        previous = current
        grid = sorted(
            grid + [a + (b - a) / 2 for a, b in zip(grid, grid[1:]) if a < a + (b - a) / 2 < b]
        )
    return replace(current, evaluations=len(cache))
