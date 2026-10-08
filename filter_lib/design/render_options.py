"""Presentation choices for ``render_lines``, plus the build-simulation mode rules.

Each surface owns its defaults and maps them here: the CLI from its flags, the wizard
from ``FilterState.to_render_options()``, the web from its form. ``eseries=None``
means no standard capacitor values are chosen, which is what ``--no-match`` and the
wizard's and web's "None" choice all select.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..shared.cli_aliases import DEFAULT_ESERIES
from ..shared.eseries import SUB_PF_OPTION_LABEL

OUTPUT_FORMATS = ("table", "json", "csv", "quiet")


def needs_eseries_message(subject: str) -> str:
    """The one wording for "``subject`` cannot work without standard capacitor values"."""
    return f"{subject} needs an E-series (E12, E24, or E96) to choose standard capacitor values"


# Rules every surface enforces; the wizard and web reuse these texts.
BUILD_NEEDS_ESERIES_MESSAGE = needs_eseries_message("Build simulation")
BUILD_NEEDS_TABLE_OR_JSON_MESSAGE = "Build simulation needs table or JSON output"
BUILD_NOT_WITH_VALUES_ONLY_MESSAGE = "Build simulation cannot be used with values-only output"
SUB_PF_NEEDS_ESERIES_MESSAGE = needs_eseries_message(f'"{SUB_PF_OPTION_LABEL}"')


def shows_design_warnings(output_format: str) -> bool:
    """True when the output is the component table, which lists the design warnings itself.

    Every other output (values only, JSON, CSV, SPICE, response data) leaves them out,
    so a surface shows them once next to that output instead.
    """
    return output_format == "table"


@dataclass(frozen=True)
class RenderOptions:
    """How a ``DesignResult`` becomes text.

    ``trailing_blank`` appends the blank line the CLI prints after a table.
    ``build_target_note`` adds the wizard's line that tells the ideal design above
    from the build simulation below (``render.BUILD_TARGET_NOTE``).
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
            raise ValueError("Choose either compact or full toroid detail, not both")

    @property
    def shows_design_warnings(self) -> bool:
        """True when this output lists the design warnings itself (see the function)."""
        return shows_design_warnings(self.output_format)

    def validate_for_build(self) -> None:
        """Reject output choices that cannot carry a build simulation."""
        if self.output_format == "quiet":
            raise ValueError(BUILD_NOT_WITH_VALUES_ONLY_MESSAGE)
        if self.output_format not in {"table", "json"}:
            raise ValueError(BUILD_NEEDS_TABLE_OR_JSON_MESSAGE)
        if self.eseries is None:
            raise ValueError(BUILD_NEEDS_ESERIES_MESSAGE)

    def validate_for_sub_pf(self) -> None:
        """Reject choosing sub-pF capacitors when no standard values are chosen at all."""
        if self.eseries is None:
            raise ValueError(SUB_PF_NEEDS_ESERIES_MESSAGE)
