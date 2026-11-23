"""Loading and checking the JSON data files packaged with ``filter_lib``.

Every packaged data file goes through ``load_packaged_json``, which rejects NaN,
Infinity and overflowing number literals and checks the file's schema version. The
field guards below give each data module the same checks for its source URLs,
guarantee types and display strings, with errors that name the data set.
"""

from __future__ import annotations

import json
import math
from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit

from .numeric import is_finite_real

# How a source states a value: a specification limit (minimum or maximum), a
# characteristic value (typical), or a figure printed for information only.
GUARANTEE_TYPES = ("minimum", "maximum", "typical", "reference_only")
# Only a specification limit may qualify a part.
QUALIFYING_GUARANTEES = frozenset({"minimum", "maximum"})


def load_packaged_json(
    package: str, filename: str, *, schema_version: int, label: str
) -> dict[str, Any]:
    """Return the packaged JSON object ``filename`` of ``package``.

    ``label`` names the data set in errors ("toroid core data"). The file must hold an
    object whose ``schema_version`` equals ``schema_version``; non-finite numbers are
    refused while parsing.
    """

    def reject_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON constant {value!r} in {label}")

    def finite_float(text: str) -> float:
        value = float(text)
        if not math.isfinite(value):
            raise ValueError(f"Non-finite JSON number {text!r} in {label}")
        return value

    data_path = files(package).joinpath(filename)
    with data_path.open("r", encoding="utf-8") as data_file:
        raw = json.load(data_file, parse_constant=reject_constant, parse_float=finite_float)
    version = raw.get("schema_version") if isinstance(raw, dict) else None
    # ``type(...) is int``: JSON ``true`` loads as a bool, which equals 1.
    if type(version) is not int or version != schema_version:
        raise RuntimeError(f"Unsupported {label} schema; expected version {schema_version}")
    return raw


def require_https_url(url: object, label: str) -> str:
    """Return ``url`` when it is a printable HTTPS URL; ``label`` names its owner."""
    if not isinstance(url, str) or not url.startswith("https://") or not urlsplit(url).hostname:
        raise RuntimeError(f"{label} must use an HTTPS URL")
    return require_printable_line(url, label)


def require_printable_line(text: object, label: str) -> str:
    """Return ``text`` when it is a non-empty, printable, single-line string."""
    if not isinstance(text, str) or not text.strip() or not text.isprintable():
        raise RuntimeError(f"{label} must be a non-empty single line of printable text")
    return text


def require_guarantee_type(value: object, label: str) -> str:
    """Return ``value`` when it is one of ``GUARANTEE_TYPES``."""
    if value not in GUARANTEE_TYPES:
        raise RuntimeError(f"{label} has an unknown guarantee type {value!r}")
    return value  # type: ignore[return-value]


def require_finite_number(value: object, label: str) -> float:
    """Return ``value`` when it is a finite real number (booleans refused)."""
    if not is_finite_real(value):
        raise RuntimeError(f"{label} must be a finite number")
    return value  # type: ignore[return-value]
