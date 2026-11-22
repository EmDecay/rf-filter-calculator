"""The sourced chip-inductor catalog packaged as ``chip_inductor_data.json``.

Four wirewound families (Coilcraft 0603CS, Murata LQW18AN_00, LQW18AN_80 and LQW15AN_80)
whose datasheets guarantee each part's inductance tolerance, minimum self-resonant
frequency (SRF) and minimum Q, at 10 to 100 nH. The evidence for every row is in
``docs/component-data-sources.md`` (Chip inductors, Recommended catalog); a data change
updates that page in the same change.

A catalog row is one family and inductance value; its part-number pattern carries ``_``
where the tolerance code goes. ``chip_parts()`` lists every orderable variant, one per
offered tolerance code. Only guaranteed limits are packaged: the tolerance is a rated
maximum, the SRF and Q are minimums. The minimum Q is shown, never used for ranking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from typing import Any

from .packaged_data import (
    QUALIFYING_GUARANTEES,
    load_packaged_json,
    require_finite_number,
    require_guarantee_type,
    require_https_url,
    require_printable_line,
)

_LABEL = "chip inductor data"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PAGE = re.compile(r"^p\. \d+(, \d+)*$")
_TOLERANCE_CODE = re.compile(r"^[A-Z]$")


@dataclass(frozen=True)
class ChipSource:
    """The datasheet or specification a family's guarantees come from."""

    source_id: str
    publisher: str
    title: str
    revision: str
    url: str
    sha256: str


@dataclass(frozen=True)
class ChipFamily:
    """One manufacturer's family: its package, source and how it was measured."""

    name: str
    manufacturer: str
    package: str
    source: ChipSource
    measurement: str


@dataclass(frozen=True)
class ChipPart:
    """One orderable chip inductor: a catalog value with one tolerance code.

    ``inductance_h`` is the catalog value at ``test_frequency_hz``; the tolerance is the
    rated ± percent of that value; ``srf_min_hz`` and ``q_min`` are the guaranteed
    minimums (Q at ``q_test_frequency_hz``). ``page`` locates the row in the source.
    """

    part_number: str
    family: ChipFamily
    inductance_h: float
    test_frequency_hz: float
    tolerance_pct: float
    srf_min_hz: float
    q_min: float
    q_test_frequency_hz: float
    page: str


def _positive(value: object, label: str) -> float:
    number = require_finite_number(value, label)
    if number <= 0:
        raise RuntimeError(f"{label} must be positive")
    return float(number)


def _scaled(value: float, exponent: int) -> float:
    """``value × 10**exponent`` as the float nearest the exact decimal (22 nH is 2.2e-08)."""
    return float(Fraction(repr(value)) * Fraction(10) ** exponent)


def _source(source_id: str, raw: dict[str, Any]) -> ChipSource:
    label = f"Chip inductor source {source_id!r}"
    sha256 = raw.get("sha256")
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        raise RuntimeError(f"{label} needs a SHA-256 of the copy read")
    return ChipSource(
        source_id=require_printable_line(source_id, label),
        publisher=require_printable_line(raw.get("publisher"), label),
        title=require_printable_line(raw.get("title"), label),
        revision=require_printable_line(raw.get("revision"), label),
        url=require_https_url(raw.get("url"), label),
        sha256=sha256,
    )


def _family(name: str, raw: dict[str, Any], sources: dict[str, ChipSource]) -> ChipFamily:
    label = f"Chip inductor family {name!r}"
    # A tolerance is a maximum; the SRF and Q are minimums.
    for key, direction in (
        ("tolerance_guarantee", "maximum"),
        ("srf_guarantee", "minimum"),
        ("q_guarantee", "minimum"),
    ):
        guarantee = require_guarantee_type(raw.get(key), label)
        if guarantee not in QUALIFYING_GUARANTEES:
            raise RuntimeError(f"{label} {key.split('_')[0]} is not a guaranteed limit")
        if guarantee != direction:
            raise RuntimeError(f"{label} {key.split('_')[0]} must be a guaranteed {direction}")
    source_id = raw.get("source")
    if source_id not in sources:
        raise RuntimeError(f"{label} cites a source that was not read")
    return ChipFamily(
        name=require_printable_line(name, label),
        manufacturer=require_printable_line(raw.get("manufacturer"), label),
        package=require_printable_line(raw.get("package"), label),
        source=sources[source_id],
        measurement=require_printable_line(raw.get("measurement"), label),
    )


def _tolerance_codes(name: str, raw: object) -> dict[str, float]:
    label = f"Chip inductor family {name!r} tolerance codes"
    if not isinstance(raw, dict) or not raw:
        raise RuntimeError(f"{label} must name each code and its percent")
    codes = {}
    for code, percent in raw.items():
        if not isinstance(code, str) or not _TOLERANCE_CODE.fullmatch(code):
            raise RuntimeError(f"{label} must be single capital letters")
        value = _positive(percent, label)
        if value >= 100:
            raise RuntimeError(f"{label} must be below 100%")
        codes[code] = value
    return codes


def _variants(
    raw: dict[str, Any], families: dict[str, ChipFamily], codes: dict[str, dict[str, float]]
) -> list[ChipPart]:
    label = f"Chip inductor row {raw.get('part_number')!r}"
    pattern = require_printable_line(raw.get("part_number"), label)
    if pattern.count("_") != 1 or any(character.isspace() for character in pattern):
        raise RuntimeError(f"{label} needs one '_' where the tolerance code goes")
    family_name = raw.get("family")
    if family_name not in families:
        raise RuntimeError(f"{label} names an unknown family")
    page = require_printable_line(raw.get("page"), label)
    if not _PAGE.fullmatch(page):
        raise RuntimeError(f"{label} needs the page of its source row")
    offered = raw.get("tolerance_codes")
    family_codes = codes[family_name]
    if (
        not isinstance(offered, list)
        or not offered
        or len(set(offered)) != len(offered)
        or any(code not in family_codes for code in offered)
    ):
        raise RuntimeError(f"{label} offers a tolerance code its family does not define")
    numbers = {
        key: _positive(raw.get(key), f"{label} {key}")
        for key in (
            "inductance_nh",
            "test_frequency_mhz",
            "srf_min_mhz",
            "q_min",
            "q_test_frequency_mhz",
        )
    }
    if numbers["srf_min_mhz"] <= numbers["test_frequency_mhz"]:
        raise RuntimeError(f"{label} has its test frequency at or above its minimum SRF")
    return [
        ChipPart(
            part_number=pattern.replace("_", code),
            family=families[family_name],
            inductance_h=_scaled(numbers["inductance_nh"], -9),
            test_frequency_hz=_scaled(numbers["test_frequency_mhz"], 6),
            tolerance_pct=family_codes[code],
            srf_min_hz=_scaled(numbers["srf_min_mhz"], 6),
            q_min=numbers["q_min"],
            q_test_frequency_hz=_scaled(numbers["q_test_frequency_mhz"], 6),
            page=page,
        )
        for code in offered
    ]


@cache
def chip_parts() -> tuple[ChipPart, ...]:
    """Every orderable chip inductor in the packaged catalog, by part number."""
    raw = load_packaged_json(__package__, "chip_inductor_data.json", schema_version=1, label=_LABEL)
    sources = {key: _source(key, value) for key, value in raw["sources"].items()}
    families = {key: _family(key, value, sources) for key, value in raw["families"].items()}
    codes = {
        key: _tolerance_codes(key, value.get("tolerance_codes"))
        for key, value in raw["families"].items()
    }
    parts = [part for row in raw["parts"] for part in _variants(row, families, codes)]
    numbers = [part.part_number for part in parts]
    if len(numbers) != len(set(numbers)):
        raise RuntimeError(f"Every part number in the {_LABEL} must be listed once")
    return tuple(sorted(parts, key=lambda part: part.part_number))


def catalog_range_h() -> tuple[float, float]:
    """The smallest and largest catalog inductance."""
    values = [part.inductance_h for part in chip_parts()]
    return min(values), max(values)
