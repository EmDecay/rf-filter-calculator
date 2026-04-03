"""Zoomed passband plot pair rendering.

Combines full-range and zoomed (0 to -6dB) ASCII plots for frequency response.
Generates 2x resolution frequency data for smoother zoomed views.
"""

import math
from collections.abc import Callable

from .plot_ascii_renderers import render_ascii_plot, render_bandpass_plot


def _compute_zoom_range(ripple_db: float | None) -> float:
    """Compute zoom range in dB for passband detail view.

    Returns max(6.0, 2.0 * ripple_db) for Chebyshev, else 6.0.
    """
    if ripple_db is not None:
        return max(6.0, 2.0 * ripple_db)
    return 6.0


def _generate_zoom_freqs(freqs: list[float], num_points: int) -> list[float]:
    """Generate higher-density frequency points spanning the same range."""
    f_min, f_max = min(freqs), max(freqs)
    log_min, log_max = math.log10(f_min), math.log10(f_max)
    if num_points <= 1:
        return [10**log_min]
    return [10 ** (log_min + (log_max - log_min) * i / (num_points - 1)) for i in range(num_points)]


def render_plot_pair(
    freqs: list[float],
    response_db: list[float],
    cutoff_hz: float,
    filter_type: str = "lowpass",
    ripple_db: float | None = None,
    response_fn: Callable[[float], float] | None = None,
    **kwargs,
) -> str:
    """Render full-range plot + zoomed passband detail for LP/HP filters.

    Args:
        freqs: List of frequencies in Hz
        response_db: List of magnitude responses in dB
        cutoff_hz: Cutoff frequency for labeling
        filter_type: 'lowpass' or 'highpass'
        ripple_db: Chebyshev ripple in dB (affects zoom range)
        response_fn: Callable (freq_hz) -> magnitude_db for 2x zoom resolution
        **kwargs: Passed to render_ascii_plot (width, height, title)

    Returns:
        Combined multi-line string with full plot + zoomed plot
    """
    full = render_ascii_plot(freqs, response_db, cutoff_hz, filter_type=filter_type, **kwargs)

    zoom_db = _compute_zoom_range(ripple_db)

    # Generate 2x points for smoother zoomed view
    if response_fn:
        zoom_freqs = _generate_zoom_freqs(freqs, num_points=len(freqs) * 2)
        zoom_response = [response_fn(f) for f in zoom_freqs]
    else:
        zoom_freqs, zoom_response = freqs, response_db

    # Check if zoomed view has anything to show (not all flat at 0dB)
    in_range = [db for db in zoom_response if db >= -zoom_db]
    if in_range and all(abs(db) < 0.1 for db in in_range):
        return full  # Nothing interesting in passband

    zoomed = render_ascii_plot(
        zoom_freqs,
        zoom_response,
        cutoff_hz,
        filter_type=filter_type,
        db_floor=-zoom_db,
        title=f"Passband Detail (0 to -{zoom_db:.0f} dB)",
        **{k: v for k, v in kwargs.items() if k != "title"},
    )

    return full + "\n\n" + zoomed


def render_bandpass_plot_pair(
    sweep_data: list[tuple[float, float]],
    f0: float,
    bw: float,
    title: str = "Frequency Response",
    ripple_db: float | None = None,
    response_fn: Callable[[float], float] | None = None,
    **kwargs,
) -> str:
    """Render full-range + zoomed passband detail for bandpass filters.

    Args:
        sweep_data: List of (frequency_hz, magnitude_db) tuples
        f0: Center frequency in Hz
        bw: Bandwidth in Hz
        title: Plot title
        ripple_db: Chebyshev ripple in dB (affects zoom range)
        response_fn: Callable (freq_hz) -> magnitude_db for 2x zoom resolution
        **kwargs: Passed to render_bandpass_plot (width, height)

    Returns:
        Combined multi-line string with full plot + zoomed plot
    """
    full = render_bandpass_plot(sweep_data, f0, bw, title=title, **kwargs)

    zoom_db = _compute_zoom_range(ripple_db)

    # Generate 2x points for smoother zoomed view
    if response_fn:
        freqs = [f for f, _ in sweep_data]
        zoom_freqs = _generate_zoom_freqs(freqs, num_points=len(freqs) * 2)
        zoom_sweep = [(f, response_fn(f)) for f in zoom_freqs]
    else:
        zoom_sweep = sweep_data

    # Check if zoomed view has anything to show
    zoom_dbs = [db for _, db in zoom_sweep if db >= -zoom_db]
    if zoom_dbs and all(abs(db) < 0.1 for db in zoom_dbs):
        return full

    zoomed = render_bandpass_plot(
        zoom_sweep,
        f0,
        bw,
        title=f"Passband Detail (0 to -{zoom_db:.0f} dB)",
        db_floor=-zoom_db,
        **kwargs,
    )

    return full + "\n\n" + zoomed
