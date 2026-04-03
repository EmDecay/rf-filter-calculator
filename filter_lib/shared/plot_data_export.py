"""Data export functions for frequency response data.

Supports JSON and CSV export of sweep data.
"""

import json


def export_json(
    sweep_data: list[tuple[float, float]],
    f0: float,
    bw: float,
    filter_type: str,
    order: int,
    ripple_db: float | None = None,
) -> str:
    """Export sweep data as JSON string.

    Args:
        sweep_data: List of (frequency_hz, magnitude_db) tuples
        f0: Center frequency in Hz
        bw: Bandwidth in Hz
        filter_type: Filter type name
        order: Filter order
        ripple_db: Chebyshev ripple (optional)

    Returns:
        JSON formatted string
    """
    data = {
        "filter_type": filter_type,
        "f0_hz": f0,
        "bandwidth_hz": bw,
        "order": order,
        "data": [{"frequency_hz": f, "magnitude_db": round(db, 2)} for f, db in sweep_data],
    }
    if ripple_db is not None:
        data["ripple_db"] = ripple_db
    return json.dumps(data, indent=2)


def export_csv(sweep_data: list[tuple[float, float]]) -> str:
    """Export sweep data as CSV string.

    Args:
        sweep_data: List of (frequency_hz, magnitude_db) tuples

    Returns:
        CSV formatted string
    """
    lines = ["frequency_hz,magnitude_db"]
    for f, db in sweep_data:
        lines.append(f"{f},{db:.2f}")
    return "\n".join(lines)
