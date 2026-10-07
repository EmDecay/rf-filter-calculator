"""Inline SVG frequency-response plot built from ``design.response_series``.

The plot uses the same samples as the ``--plot-data`` export, drawn on a logarithmic
frequency axis with a dB axis and a labelled -3 dB guide. It is a pure function of
numbers: no user text, no external assets, and deterministic output. Colours and
type come from the page stylesheet through the ``plot-*`` classes, and the drawing
scales to its container through ``viewBox``.
"""

from __future__ import annotations

import math

from ..shared.formatting import format_frequency

WIDTH, HEIGHT = 720.0, 300.0
LEFT, RIGHT, TOP, BOTTOM = 52.0, 14.0, 14.0, 36.0
GUIDE_DB = -3.0
LOWEST_DB = -100.0
SOURCES = {
    "lowpass": "analytic transfer function",
    "highpass": "analytic transfer function",
    "bandpass": "simulated synthesized circuit",
}


def _fmt(value: float) -> str:
    """Fixed two-decimal coordinates keep the markup short and reproducible."""
    return f"{value:.2f}"


def _db_range(response_db: list[float]) -> tuple[float, float]:
    """Return ``(bottom, top)`` dB bounds: 0 dB at the top, at most 100 dB of depth."""
    peak = max(response_db)
    # Passive responses peak at 0 dB; rounding residue must not add an empty band.
    top = 0.0 if peak <= 0.5 else math.ceil(peak / 10.0) * 10.0
    bottom = math.floor(min(response_db) / 20.0) * 20.0
    return max(LOWEST_DB, min(bottom, top - 20.0)), top


def _db_ticks(bottom: float, top: float) -> list[float]:
    step = 10.0 if top - bottom <= 60.0 else 20.0
    ticks, value = [], top
    while value >= bottom - 1e-9:
        ticks.append(value)
        value -= step
    return ticks


def _nice_step(span: float) -> float:
    raw = span / 8.0
    magnitude = 10.0 ** math.floor(math.log10(raw))
    for multiple in (1.0, 2.0, 5.0, 10.0):
        if raw <= multiple * magnitude:
            return multiple * magnitude
    return 10.0 * magnitude  # pragma: no cover - the loop always returns


def _frequency_ticks(f_min: float, f_max: float) -> list[float]:
    """1-2-5 decade ticks, or evenly spaced ticks when the span is under a decade."""
    ticks = []
    for exponent in range(math.floor(math.log10(f_min)), math.ceil(math.log10(f_max)) + 1):
        for multiple in (1.0, 2.0, 5.0):
            value = multiple * 10.0**exponent
            if f_min <= value <= f_max:
                ticks.append(value)
    if len(ticks) >= 3:
        return ticks
    step = _nice_step(f_max - f_min)
    first = math.ceil(f_min / step) * step
    count = int(math.floor((f_max - first) / step + 1e-9)) + 1
    return [first + index * step for index in range(count)]


def render_response_svg(freqs: list[float], response_db: list[float], category: str) -> str:
    """Return a self-contained ``<svg>`` element for one response series."""
    if len(freqs) != len(response_db) or len(freqs) < 2:
        raise ValueError("Response plot needs matching frequency and magnitude series")
    f_min, f_max = freqs[0], freqs[-1]
    log_min, log_span = math.log10(f_min), math.log10(f_max) - math.log10(f_min)
    bottom, top = _db_range(response_db)
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM

    def x_at(freq: float) -> float:
        return LEFT + (math.log10(freq) - log_min) / log_span * plot_w

    def y_at(db: float) -> float:
        return TOP + (top - min(top, max(bottom, db))) / (top - bottom) * plot_h

    source = SOURCES.get(category, "response")
    label = (
        f"Frequency response, {source}: magnitude in dB from "
        f"{format_frequency(f_min)} to {format_frequency(f_max)}, {len(freqs)} samples"
    )
    parts = [
        f'<svg class="response-plot" viewBox="0 0 {WIDTH:g} {HEIGHT:g}" role="img" '
        f'aria-label="{label}" data-samples="{len(freqs)}" '
        f'data-f-min="{f_min!r}" data-f-max="{f_max!r}" preserveAspectRatio="xMidYMid meet">',
        f"<title>{label}</title>",
        f'<rect class="plot-frame" x="{_fmt(LEFT)}" y="{_fmt(TOP)}" '
        f'width="{_fmt(plot_w)}" height="{_fmt(plot_h)}"/>',
    ]
    for db in _db_ticks(bottom, top):
        y = _fmt(y_at(db))
        parts.append(
            f'<line class="plot-grid" x1="{_fmt(LEFT)}" y1="{y}" x2="{_fmt(LEFT + plot_w)}" y2="{y}"/>'
        )
        parts.append(
            f'<text class="plot-tick" x="{_fmt(LEFT - 6)}" y="{y}" text-anchor="end" '
            f'dominant-baseline="middle">{db:g}</text>'
        )
    for freq in _frequency_ticks(f_min, f_max):
        x = _fmt(x_at(freq))
        parts.append(
            f'<line class="plot-grid" x1="{x}" y1="{_fmt(TOP)}" x2="{x}" y2="{_fmt(TOP + plot_h)}"/>'
        )
        parts.append(
            f'<text class="plot-tick" x="{x}" y="{_fmt(TOP + plot_h + 16)}" '
            f'text-anchor="middle">{format_frequency(freq)}</text>'
        )
    guide_y = _fmt(y_at(GUIDE_DB))
    parts += [
        f'<line class="plot-guide" x1="{_fmt(LEFT)}" y1="{guide_y}" '
        f'x2="{_fmt(LEFT + plot_w)}" y2="{guide_y}"/>',
        f'<text class="plot-guide-label" x="{_fmt(LEFT + plot_w - 4)}" y="{guide_y}" '
        f'text-anchor="end" dy="-4">−3 dB</text>',
        f'<text class="plot-axis-label" x="{_fmt(LEFT + plot_w / 2)}" y="{_fmt(HEIGHT - 4)}" '
        f'text-anchor="middle">Frequency</text>',
        f'<text class="plot-axis-label" x="12" y="{_fmt(TOP + plot_h / 2)}" text-anchor="middle" '
        f'transform="rotate(-90 12 {_fmt(TOP + plot_h / 2)})">dB</text>',
    ]
    points = " ".join(f"{_fmt(x_at(f))},{_fmt(y_at(db))}" for f, db in zip(freqs, response_db))
    parts.append(f'<polyline class="plot-trace" points="{points}"/>')
    parts.append("</svg>")
    return "\n".join(parts)
