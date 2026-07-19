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

from collections.abc import Mapping, Sequence

from .numeric import is_finite_real, require_finite_real, require_positive_finite
from .strict_json import dumps_strict, validate_finite_tree

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
_CATEGORIES = {"lowpass", "highpass", "bandpass"}
_RESPONSE_TYPES = {"butterworth", "chebyshev", "bessel"}


def _validate_meta(meta: object) -> Mapping:
    """Validate the documented unified response-metadata schema."""
    if not isinstance(meta, Mapping):
        raise ValueError("meta must be a mapping")
    category = meta.get("category")
    if not isinstance(category, str) or category not in _CATEGORIES:
        raise ValueError("meta.category must be 'lowpass', 'highpass', or 'bandpass'")
    response_type = meta.get("response_type")
    if not isinstance(response_type, str) or response_type not in _RESPONSE_TYPES:
        raise ValueError("meta.response_type must be 'butterworth', 'chebyshev', or 'bessel'")
    order = meta.get("order")
    if (
        isinstance(order, bool)
        or not isinstance(order, int)
        or order < 1
        or not is_finite_real(order)
    ):
        raise ValueError("meta.order must be a positive finite integer")

    if category == "bandpass":
        require_positive_finite(meta.get("f0_hz"), "meta.f0_hz")
        require_positive_finite(meta.get("bw_hz"), "meta.bw_hz")
        if meta.get("cutoff_hz") is not None or meta.get("topology") is not None:
            raise ValueError("bandpass metadata cannot contain cutoff_hz or topology")
        coupling = meta.get("coupling")
        if coupling is not None and (not isinstance(coupling, str) or coupling != "top"):
            raise ValueError("meta.coupling must be 'top' when supplied")
    else:
        require_positive_finite(meta.get("cutoff_hz"), "meta.cutoff_hz")
        if any(meta.get(key) is not None for key in ("f0_hz", "bw_hz", "coupling")):
            raise ValueError("lowpass/highpass metadata cannot contain f0_hz, bw_hz, or coupling")
        topology = meta.get("topology")
        if topology is not None and (not isinstance(topology, str) or topology not in {"pi", "t"}):
            raise ValueError("meta.topology must be 'pi' or 't' when supplied")

    ripple_db = meta.get("ripple_db")
    if response_type == "chebyshev":
        require_positive_finite(ripple_db, "meta.ripple_db")
        if ripple_db > 3.0:
            raise ValueError("meta.ripple_db must be at most 3.0 dB")
    elif ripple_db is not None:
        raise ValueError("meta.ripple_db is valid only for a Chebyshev response")
    return meta


def response_meta(category: str, result: dict) -> dict:
    """Build export metadata from a filter result dict (CLI/wizard shape).

    Args:
        category: 'lowpass', 'highpass', or 'bandpass'
        result: Result dict — LP/HP shape (freq_hz/order/ripple/topology) or
            bandpass shape (f0/bw/n_resonators/ripple_db/coupling)

    Returns:
        Metadata dict for export_response_json
    """
    if not isinstance(category, str) or category not in _CATEGORIES:
        raise ValueError("category must be 'lowpass', 'highpass', or 'bandpass'")
    if not isinstance(result, Mapping):
        raise ValueError("result must be a mapping")
    if category == "bandpass":
        meta = {
            "category": "bandpass",
            "response_type": result.get("filter_type"),
            "order": result.get("n_resonators"),
            "f0_hz": result.get("f0"),
            "bw_hz": result.get("bw"),
            "ripple_db": result.get("ripple_db"),
            "coupling": result.get("coupling"),
        }
    else:
        meta = {
            "category": category,
            "response_type": result.get("filter_type"),
            "order": result.get("order"),
            "cutoff_hz": result.get("freq_hz"),
            "ripple_db": result.get("ripple"),
            "topology": result.get("topology"),
        }
    _validate_meta(meta)
    return meta


def export_response_json(freqs: list[float], response_db: list[float], meta: dict) -> str:
    """Export a frequency response as JSON in the unified schema.

    Args:
        freqs: Frequency points in Hz
        response_db: Magnitudes in dB
        meta: Metadata dict (see response_meta); None values are omitted

    Returns:
        JSON string
    """
    _validate_response_arrays(freqs, response_db)
    if not isinstance(meta, Mapping):
        raise ValueError("meta must be a mapping")
    validate_finite_tree({"filter": dict(meta)})
    _validate_meta(meta)
    filter_block = {k: meta[k] for k in _FILTER_KEYS if meta.get(k) is not None}
    payload = {
        "filter": filter_block,
        "data": [
            {"frequency_hz": f, "magnitude_db": round(db, 2)} for f, db in zip(freqs, response_db)
        ],
    }
    return dumps_strict(payload, indent=2)


def export_response_csv(freqs: list[float], response_db: list[float]) -> str:
    """Export a frequency response as CSV (header: frequency_hz,magnitude_db)."""
    _validate_response_arrays(freqs, response_db)
    validate_finite_tree({"frequency_hz": freqs, "magnitude_db": response_db})
    lines = ["frequency_hz,magnitude_db"]
    lines.extend(f"{f:.6g},{db:.2f}" for f, db in zip(freqs, response_db))
    return "\n".join(lines)


def _validate_response_arrays(freqs: list[float], response_db: list[float]) -> None:
    """Validate parallel numeric arrays before JSON or CSV serialization."""
    if (
        not isinstance(freqs, Sequence)
        or isinstance(freqs, (str, bytes))
        or not isinstance(response_db, Sequence)
        or isinstance(response_db, (str, bytes))
    ):
        raise ValueError("freqs and response_db must be numeric sequences")
    if len(freqs) != len(response_db):
        raise ValueError(
            "freqs and response_db must have the same length "
            f"(got {len(freqs)} and {len(response_db)})"
        )
    for index, frequency in enumerate(freqs):
        require_positive_finite(frequency, f"$.data[{index}].frequency_hz")
    for index, magnitude_db in enumerate(response_db):
        require_finite_real(magnitude_db, f"$.data[{index}].magnitude_db")
