"""The sourced trimmer capacitors packaged as ``trimmer_data.json``.

Only parts whose datasheet states both ends of the range as bounds are packaged: a
guaranteed maximum for the minimum capacitance and a guaranteed minimum for the maximum
(Vishay BFC2 808, Exxelia AT 0300/1300 R2, AT 03HV00 R2, AT 9402G, AT 9410G and AT 23XXG,
and Suntan TSC3S). The evidence for every row is the per-part table of
``docs/component-data-sources.md`` (Trimmer capacitors); a data change updates that page in
the same change.

A row is one range with every part number that has it (for example Vishay's top- and
bottom-adjusted versions). The range is measured at 200 kHz (Vishay) or at a frequency
the maker does not state. A minimum self-resonant frequency (SRF) at the maximum
capacitance is packaged only where the maker guarantees one (most Vishay parts); a
typical SRF is kept as text only.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from typing import Any

from .packaged_data import (
    load_packaged_json,
    require_finite_number,
    require_https_url,
    require_printable_line,
)

_LABEL = "trimmer capacitor data"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PAGE = re.compile(r"^p\. \d+$")
_PF = re.compile(r"^\d+(\.\d+)?$")


@dataclass(frozen=True)
class TrimmerSource:
    """The datasheet a row's bounds come from."""

    source_id: str
    publisher: str
    title: str
    revision: str
    url: str
    sha256: str


@dataclass(frozen=True)
class TrimmerPart:
    """One guaranteed trimmer range and the part numbers that have it.

    ``cmin_max_f`` is the guaranteed maximum of the minimum capacitance and
    ``cmax_min_f`` the guaranteed minimum of the maximum, measured at
    ``range_measured_at_hz`` (``None``: the maker does not state the frequency).
    ``srf_min_at_cmax_hz`` is a guaranteed minimum SRF at the maximum capacitance, or
    ``None`` when the maker guarantees none. The other fields are shown as stated.
    """

    maker: str
    family: str
    part_numbers: tuple[str, ...]
    cmin_max_f: float
    cmax_min_f: float
    range_measured_at_hz: float | None
    srf_min_at_cmax_hz: float | None
    srf_as_stated: str | None
    q_as_stated: str
    dielectric: str
    working_voltage_v: float
    mounting: str
    source: TrimmerSource
    page: str

    @property
    def part_name(self) -> str:
        """The first part number, which names the row."""
        return self.part_numbers[0]

    @property
    def series_inductance_bound_h(self) -> float | None:
        """The bound on the series inductance from the minimum SRF at the maximum.

        ``L <= 1 / ((2 pi SRF_min)^2 Cmax)``: the part's maximum is at least ``Cmax``, so
        its inductance is at most this. ``None`` without a guaranteed SRF.
        """
        if self.srf_min_at_cmax_hz is None:
            return None
        return 1.0 / ((2.0 * math.pi * self.srf_min_at_cmax_hz) ** 2 * self.cmax_min_f)


def _farads(text: object, label: str) -> float:
    """A pF value written as a short decimal string, as the float nearest its farads."""
    if not isinstance(text, str) or not _PF.fullmatch(text):
        raise RuntimeError(f"{label} must be a decimal number of pF written as text")
    value = Fraction(text) / 10**12
    if value <= 0:
        raise RuntimeError(f"{label} must be positive")
    return float(value)


def _positive(value: object, label: str) -> float:
    number = require_finite_number(value, label)
    if number <= 0:
        raise RuntimeError(f"{label} must be positive")
    return float(number)


def _source(source_id: str, raw: dict[str, Any]) -> TrimmerSource:
    label = f"Trimmer source {source_id!r}"
    sha256 = raw.get("sha256")
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        raise RuntimeError(f"{label} needs a SHA-256 of the copy read")
    return TrimmerSource(
        source_id=require_printable_line(source_id, label),
        publisher=require_printable_line(raw.get("publisher"), label),
        title=require_printable_line(raw.get("title"), label),
        revision=require_printable_line(raw.get("revision"), label),
        url=require_https_url(raw.get("url"), label),
        sha256=sha256,
    )


def _part(raw: dict[str, Any], sources: dict[str, TrimmerSource]) -> TrimmerPart:
    numbers = raw.get("part_numbers")
    label = f"Trimmer row {numbers!r}"
    if (
        not isinstance(numbers, list)
        or not numbers
        or len(set(numbers)) != len(numbers)
        or any(not isinstance(number, str) for number in numbers)
    ):
        raise RuntimeError(f"{label} must list its part numbers once each")
    for number in numbers:
        require_printable_line(number, label)
    source_id = raw.get("source")
    if source_id not in sources:
        raise RuntimeError(f"{label} cites a source that was not read")
    page = require_printable_line(raw.get("page"), label)
    if not _PAGE.fullmatch(page):
        raise RuntimeError(f"{label} needs the page of its source row")
    cmin = _farads(raw.get("cmin_max_pf"), f"{label} minimum")
    cmax = _farads(raw.get("cmax_min_pf"), f"{label} maximum")
    if cmin >= cmax:
        raise RuntimeError(f"{label} needs its minimum below its maximum")
    measured = raw.get("range_measured_at_hz")
    srf_mhz = raw.get("srf_min_at_cmax_mhz")
    srf_text = raw.get("srf_as_stated")
    if srf_mhz is not None and srf_text is None:
        raise RuntimeError(f"{label} needs the SRF as stated with its minimum")
    return TrimmerPart(
        maker=require_printable_line(raw.get("maker"), label),
        family=require_printable_line(raw.get("family"), label),
        part_numbers=tuple(numbers),
        cmin_max_f=cmin,
        cmax_min_f=cmax,
        range_measured_at_hz=None if measured is None else _positive(measured, label),
        srf_min_at_cmax_hz=None if srf_mhz is None else _positive(srf_mhz, label) * 1e6,
        srf_as_stated=None if srf_text is None else require_printable_line(srf_text, label),
        q_as_stated=require_printable_line(raw.get("q_as_stated"), label),
        dielectric=require_printable_line(raw.get("dielectric"), label),
        working_voltage_v=_positive(raw.get("working_voltage_v"), label),
        mounting=require_printable_line(raw.get("mounting"), label),
        source=sources[source_id],
        page=page,
    )


@cache
def trimmer_parts() -> tuple[TrimmerPart, ...]:
    """Every packaged trimmer range, in the evidence page's order."""
    raw = load_packaged_json(__package__, "trimmer_data.json", schema_version=1, label=_LABEL)
    sources = {key: _source(key, value) for key, value in raw["sources"].items()}
    parts = tuple(_part(row, sources) for row in raw["trimmers"])
    numbers = [number for part in parts for number in part.part_numbers]
    if len(numbers) != len(set(numbers)):
        raise RuntimeError(f"Every part number in the {_LABEL} must be listed once")
    return parts
