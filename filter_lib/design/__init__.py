"""Shared design orchestration used by the CLI, the Textual wizard, and the web UI.

Surfaces build a ``DesignRequest``, call ``design()``, and pass the ``DesignResult`` to
``render_lines``, ``export_spice``, or ``export_response_data``; none of them calls a
calculator, a category formatter, or the build analysis directly.
"""

from .design_request import DesignRequest, band_from_edges
from .design_result import DesignResult
from .design_service import design, synthesize, with_build_analysis
from .export import export_response_data, export_spice, response_series
from .render import render_lines
from .render_options import RenderOptions

__all__ = [
    "DesignRequest",
    "DesignResult",
    "RenderOptions",
    "band_from_edges",
    "design",
    "export_response_data",
    "export_spice",
    "render_lines",
    "response_series",
    "synthesize",
    "with_build_analysis",
]
