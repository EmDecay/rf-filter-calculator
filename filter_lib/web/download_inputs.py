"""The inputs a download uses: what the user sees, applied to that download's document.

The page disables a control that cannot apply to the output shown (for example the
E-series with Values only). A disabled control is not submitted, so the result shown is
the CLI command without that flag. The page also sends the control's visible value as
``visible.<name>`` and the result keeps it with its inputs. A download is a different
document: it uses each visible value that applies to it, judged by the shared rule, so
Values only with E-series "None" downloads JSON as ``--format json --no-match``, never
with a substituted E24. Display-only choices (raw units, text plot, toroid detail) never
reach a download, as before.
"""

from __future__ import annotations

from ..design.option_applicability import (
    ALLOW_SUB_PF,
    BUILD,
    DOCUMENT_FORMATS,
    ESERIES,
    LOSS_Q,
    RAW_UNITS,
    TEXT_PLOT,
    TOROID_BUILD,
    TOROID_DETAIL,
    OutputChoices,
    document_options,
)
from ..shared.cli_aliases import DEFAULT_ESERIES
from .form_values import FormData, flag, text

VISIBLE_PREFIX = "visible."
# Form field -> the shared rule's option it belongs to.
FIELD_OPTIONS = {
    "eseries": ESERIES,
    "allow_sub_pf": ALLOW_SUB_PF,
    "toroids": TOROID_DETAIL,
    "plot": TEXT_PLOT,
    "raw": RAW_UNITS,
    "sim_build": BUILD,
    "toroid_build": TOROID_BUILD,
    "qu": LOSS_Q,
    "ql": LOSS_Q,
    "qc": LOSS_Q,
}
# Each download kind follows the rules of ``DOCUMENT_FORMATS[kind]`` (shared with the
# wizard's saved files): the design JSON and the chosen-parts deck carry the build and
# the loss model; the others carry neither.
__all__ = ["DOCUMENT_FORMATS", "FIELD_OPTIONS", "VISIBLE_PREFIX", "download_fields"]


def _choices(fields: FormData) -> OutputChoices:
    eseries = text(fields, "eseries", DEFAULT_ESERIES)
    return OutputChoices(
        eseries=None if eseries == "none" else eseries,
        raw=flag(fields, "raw"),
        build=flag(fields, "sim_build"),
        include_toroids=text(fields, "toroids") != "none",
    )


def download_fields(fields: FormData, kind: str) -> dict[str, str]:
    """Return the fields the ``kind`` download is calculated from.

    Fields sent normally are kept as they are. Each ``visible.<name>`` value is added
    as ``<name>`` when its option applies to the download's document.
    """
    shown = {name: value for name, value in fields.items() if not name.startswith(VISIBLE_PREFIX)}
    visible = {
        name.removeprefix(VISIBLE_PREFIX): value
        for name, value in fields.items()
        if name.startswith(VISIBLE_PREFIX) and name.removeprefix(VISIBLE_PREFIX) in FIELD_OPTIONS
    }
    used = document_options(
        _choices({**shown, **visible}), kind, visible=[FIELD_OPTIONS[name] for name in visible]
    )
    return {
        **shown,
        **{name: value for name, value in visible.items() if FIELD_OPTIONS[name] in used},
    }
