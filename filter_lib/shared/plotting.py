"""Facade re-exporting plotting utilities for backward compatibility.

All implementation lives in:
- plot_ascii_renderers.py — render functions + freq formatting
- plot_zoom_pairs.py — zoomed passband plot pairs + zoom helpers
- plot_threshold_analysis.py — dB crossing detection + summary tables
- plot_data_export.py — JSON/CSV export
"""

from .plot_ascii_renderers import (  # noqa: F401
    _format_freq_compact,
    render_ascii_plot,
    render_bandpass_plot,
)
from .plot_data_export import export_csv, export_json  # noqa: F401
from .plot_threshold_analysis import (  # noqa: F401
    _find_3db_frequency,
    find_db_thresholds,
    format_threshold_table,
)
from .plot_zoom_pairs import (  # noqa: F401
    _compute_zoom_range,
    _generate_zoom_freqs,
    render_bandpass_plot_pair,
    render_plot_pair,
)
