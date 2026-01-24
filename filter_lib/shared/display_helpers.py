"""Shared display formatting helpers for filter results.

Provides E-series matching display, component formatting, and output formatters.
"""
from __future__ import annotations
from typing import Callable

from .eseries import match_component


def format_eseries_match(value: float, series: str,
                         unit_formatter: Callable[[float], str],
                         parallel_mode: str = 'additive') -> list[str]:
    """Format E-series match for display.

    Args:
        value: Component value to match
        series: E-series name (E12, E24, E96)
        unit_formatter: Function to format value with units (e.g., format_capacitance)
        parallel_mode: Parallel matching mode ('additive' recommended)

    Returns:
        List of formatted lines showing nearest standard and parallel match
    """
    match = match_component(value, series, parallel_mode=parallel_mode)
    lines: list[str] = []
    formatted = unit_formatter(match.single_value)
    error_sign = '+' if match.single_error_pct > 0 else ''
    lines.append(f"  Nearest Std:  {formatted} ({error_sign}{match.single_error_pct:.1f}%)")

    if match.parallel and match.parallel_error_pct is not None:
        if abs(match.parallel_error_pct) < abs(match.single_error_pct):
            p1, p2 = match.parallel
            p1_fmt = unit_formatter(p1).split()[0]
            p2_fmt = unit_formatter(p2)
            err_sign = '+' if match.parallel_error_pct > 0 else ''
            lines.append(f"  Parallel Std: {p1_fmt} || {p2_fmt} ({err_sign}{match.parallel_error_pct:.1f}%)")
    return lines


def format_component_value(name: str, value: float,
                           unit_formatter: Callable[[float], str],
                           raw: bool = False) -> str:
    """Format a component value with optional raw mode.

    Args:
        name: Component name (e.g., 'C1', 'L2')
        value: Component value in base units (F or H)
        unit_formatter: Function to format value (format_capacitance or format_inductance)
        raw: If True, use scientific notation

    Returns:
        Formatted string like "C1: 150 pF" or "C1: 1.50e-10 F"
    """
    if raw:
        unit = 'F' if 'capacit' in unit_formatter.__name__.lower() else 'H'
        return f"{name}: {value:.6e} {unit}"
    return f"{name}: {unit_formatter(value)}"


def split_value_unit(formatted_string: str) -> tuple[str, str]:
    """Split a formatted value string into (value, unit) tuple.

    Args:
        formatted_string: String like "150 pF" or "1.5 uH"

    Returns:
        Tuple of (value_str, unit_str), e.g., ("150", "pF")
    """
    return tuple(formatted_string.rsplit(' ', 1))
