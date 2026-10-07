"""Presentation choices for ``render_lines``, plus the realized-build mode rules.

Each surface owns its defaults and maps them here: the CLI from its flags, the wizard
from ``FilterState.to_render_options()``, the web from its form. ``eseries=None``
means no preferred-value matching, which is what ``--no-match`` and the wizard's
"none" choice both select.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..shared.cli_aliases import DEFAULT_ESERIES

OUTPUT_FORMATS = ("table", "json", "csv", "quiet")


@dataclass(frozen=True)
class RenderOptions:
    """How a ``DesignResult`` becomes text.

    ``trailing_blank`` appends the blank line the CLI prints after a table.
    ``build_target_note`` adds the wizard's "Synthesis target" line between the
    table and the realized-build block.
    """

    output_format: str = "table"
    raw: bool = False
    eseries: str | None = DEFAULT_ESERIES
    show_plot: bool = False
    include_toroids: bool = True
    toroid_compact: bool = False
    toroid_full: bool = False
    trailing_blank: bool = True
    build_target_note: bool = False

    def __post_init__(self) -> None:
        if self.output_format not in OUTPUT_FORMATS:
            raise ValueError(f"Unknown output format: {self.output_format}")
        if self.toroid_compact and self.toroid_full:
            raise ValueError("use only one of --toroid-compact or --toroid-full")

    def validate_for_build(self) -> None:
        """Reject output choices that cannot carry a realized-build analysis."""
        if self.output_format == "quiet":
            raise ValueError("Realized-build analysis cannot be combined with quiet output")
        if self.output_format not in {"table", "json"}:
            raise ValueError(
                "Realized-build analysis is supported only with table or JSON component output"
            )
        if self.eseries is None:
            raise ValueError("Realized-build analysis requires an E-series")
