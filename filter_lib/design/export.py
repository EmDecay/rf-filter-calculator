"""SPICE and frequency-response exports for design results.

``response_series`` is the one frequency sweep behind ``--plot-data``, the wizard's
response export, and the web UI's SVG plot: LP/HP use the analytic transfer
function, bandpass simulates the synthesized circuit.
"""

from __future__ import annotations

from ..shared.cli_aliases import DEFAULT_RIPPLE_DB
from .design_result import DesignResult
from .render_options import needs_eseries_message

# Dense enough to resolve both skirts of narrow band-pass designs; equals
# ``bandpass.display.PLOT_POINTS`` so the export matches the on-screen plot.
BANDPASS_RESPONSE_POINTS = 601
RESPONSE_FORMATS = ("json", "csv")
NOMINAL_SPICE_NEEDS_ESERIES_MESSAGE = needs_eseries_message("A chosen-parts SPICE deck")


def response_series(outcome: DesignResult) -> tuple[list[float], list[float]]:
    """Return ``(frequencies_hz, magnitudes_db)`` for the design's response."""
    result = outcome.result
    if outcome.category == "bandpass":
        from ..bandpass.transfer import netlist_frequency_sweep

        sweep = netlist_frequency_sweep(result, points=BANDPASS_RESPONSE_POINTS)
        return [frequency for frequency, _ in sweep], [magnitude for _, magnitude in sweep]

    if outcome.category == "lowpass":
        from ..lowpass.transfer import frequency_response, generate_frequency_points
    elif outcome.category == "highpass":
        from ..highpass.transfer import frequency_response, generate_frequency_points
    else:
        raise ValueError("Unknown filter category")
    freqs = generate_frequency_points(result["freq_hz"])
    # Ripple only shapes Chebyshev responses; the others ignore the argument.
    response_db = frequency_response(
        result["filter_type"],
        freqs,
        result["freq_hz"],
        result["order"],
        result.get("ripple") or DEFAULT_RIPPLE_DB,
    )
    return freqs, response_db


def export_response_data(outcome: DesignResult, fmt: str) -> str:
    """Return the response document (``--plot-data`` schema) without a final newline."""
    from ..shared.response_export import export_response_csv, export_response_json, response_meta

    if fmt not in RESPONSE_FORMATS:
        raise ValueError(f"Unknown response data format: {fmt}")
    freqs, response_db = response_series(outcome)
    if fmt == "json":
        return export_response_json(
            freqs, response_db, response_meta(outcome.category, outcome.result)
        )
    return export_response_csv(freqs, response_db)


def export_spice(outcome: DesignResult, realization: str) -> str:
    """Return the SPICE deck for ``realization`` (``exact`` or ``nominal_build``).

    The deck ends with its own newline, so callers write it unchanged. The chosen-parts
    deck uses the outcome's resolved parts and build settings, so it has the same
    capacitors and inductors as every other output; it never runs the build
    simulation's tolerance cases.
    """
    from ..shared.spice_export import export_spice_deck

    if realization == "nominal_build" and outcome.eseries is None:
        raise ValueError(NOMINAL_SPICE_NEEDS_ESERIES_MESSAGE)
    return export_spice_deck(
        outcome.result,
        outcome.category,
        realization=realization,
        config=outcome.realization,
        parts=outcome.parts,
    )
