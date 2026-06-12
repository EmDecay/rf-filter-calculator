"""Unified frequency-response export for LP/HP/BP across CLI and wizard.

One JSON schema and one CSV header replace the three divergent
implementations that previously lived in ``shared/transfer_functions.py``,
``bandpass/transfer.py``, and ``shared/plot_data_export.py``.

JSON schema::

    {
      "filter": {
        "category":      "lowpass" | "highpass" | "bandpass",
        "response_type": "butterworth" | "chebyshev" | "bessel",
        "order":         <int>,
        "cutoff_hz":     <float>,         # lowpass/highpass only
        "topology":      "pi" | "t",      # lowpass/highpass (optional)
        "f0_hz":         <float>,         # bandpass only
        "bw_hz":         <float>,         # bandpass only
        "coupling":      "top",           # bandpass (optional)
        "ripple_db":     <float>          # chebyshev only
      },
      "data": [
        {"frequency_hz": <float>, "magnitude_db": <float>},  # rounded 0.01 dB
        ...
      ]
    }

CSV format: header ``frequency_hz,magnitude_db``, one row per point,
frequency in %.6g, magnitude rounded to 0.01 dB.
"""

import json

# Key order defines the JSON "filter" block layout; absent/None keys are omitted
_FILTER_KEYS = (
    "category",
    "response_type",
    "order",
    "cutoff_hz",
    "f0_hz",
    "bw_hz",
    "ripple_db",
    "topology",
    "coupling",
)


def response_meta(category: str, result: dict) -> dict:
    """Build export metadata from a filter result dict (CLI/wizard shape).

    Args:
        category: 'lowpass', 'highpass', or 'bandpass'
        result: Result dict — LP/HP shape (freq_hz/order/ripple/topology) or
            bandpass shape (f0/bw/n_resonators/ripple_db/coupling)

    Returns:
        Metadata dict for export_response_json
    """
    if category == "bandpass":
        return {
            "category": "bandpass",
            "response_type": result["filter_type"],
            "order": result["n_resonators"],
            "f0_hz": result["f0"],
            "bw_hz": result["bw"],
            "ripple_db": result.get("ripple_db"),
            "coupling": result.get("coupling"),
        }
    return {
        "category": category,
        "response_type": result["filter_type"],
        "order": result["order"],
        "cutoff_hz": result["freq_hz"],
        "ripple_db": result.get("ripple"),
        "topology": result.get("topology"),
    }


def export_response_json(freqs: list[float], response_db: list[float], meta: dict) -> str:
    """Export a frequency response as JSON in the unified schema.

    Args:
        freqs: Frequency points in Hz
        response_db: Magnitudes in dB
        meta: Metadata dict (see response_meta); None values are omitted

    Returns:
        JSON string
    """
    filter_block = {k: meta[k] for k in _FILTER_KEYS if meta.get(k) is not None}
    payload = {
        "filter": filter_block,
        "data": [
            {"frequency_hz": f, "magnitude_db": round(db, 2)} for f, db in zip(freqs, response_db)
        ],
    }
    return json.dumps(payload, indent=2)


def export_response_csv(freqs: list[float], response_db: list[float]) -> str:
    """Export a frequency response as CSV (header: frequency_hz,magnitude_db)."""
    lines = ["frequency_hz,magnitude_db"]
    lines.extend(f"{f:.6g},{db:.2f}" for f, db in zip(freqs, response_db))
    return "\n".join(lines)
