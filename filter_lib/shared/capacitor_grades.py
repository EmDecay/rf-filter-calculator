"""Sourced tolerance grades and value coverage of the fixed capacitor series.

The packaged ``capacitor_grade_data.json`` records one exact C0G series (Murata
GRM1885C1H…A01, the evidence is in ``docs/component-data-sources.md``): which values it
makes and, for each grade, the guaranteed tolerance of each value range. Values are
exact decimals in pF (``Fraction``) so a value at a range boundary is never misread.

A value the series does not make has no sourced tolerance; capacitor matching then
keeps the legacy nominal rule and labels the choice "tolerance not sourced".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .eseries import E_SERIES
from .packaged_data import (
    QUALIFYING_GUARANTEES,
    load_packaged_json,
    require_finite_number,
    require_guarantee_type,
    require_https_url,
    require_printable_line,
)

GRADE_NAMES = ("standard", "tight")
DEFAULT_GRADE = "standard"
# The tolerance assumed, for the build simulation, for a part the series does not make.
ASSUMED_TOLERANCE_PCT = 5.0

_LABEL = "capacitor grade data"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PART = re.compile(r"^GRM1885C1H[0-9R]{3}[A-Z]A01$")


def _pf(value: object, label: str) -> Fraction:
    """An exact decimal number of pF from the data file."""
    return Fraction(repr(require_finite_number(value, label)))


@dataclass(frozen=True)
class GradeRow:
    """One value range of a grade and its guaranteed tolerance."""

    from_pf: Fraction
    to_pf: Fraction
    code: str
    tolerance_pf: Fraction | None
    tolerance_pct: Fraction | None
    guarantee: str
    tolerance_sheet: str
    range_parts: tuple[str, ...]

    def tolerance_at(self, value_pf: Fraction) -> Fraction:
        """The ± tolerance in pF of a part of ``value_pf`` in this range."""
        if self.tolerance_pf is not None:
            return self.tolerance_pf
        assert self.tolerance_pct is not None
        return value_pf * self.tolerance_pct / 100

    def describe(self) -> str:
        """``±0.25 pF`` or ``±5%``."""
        if self.tolerance_pf is not None:
            return f"±{_number(self.tolerance_pf)} pF"
        assert self.tolerance_pct is not None
        return f"±{_number(self.tolerance_pct)}%"


@dataclass(frozen=True)
class CapacitorGrade:
    """A named tolerance grade: one row per value range of the series."""

    name: str
    label: str
    description: str
    rows: tuple[GradeRow, ...]

    def row_for(self, value_pf: Fraction) -> GradeRow | None:
        return next((row for row in self.rows if row.from_pf <= value_pf <= row.to_pf), None)


@dataclass(frozen=True)
class CapacitorSeries:
    """The exact series the grades belong to."""

    manufacturer: str
    name: str
    description: str
    measurement: str
    temperature_coefficient: str
    guarantee_note: str

    @property
    def title(self) -> str:
        return f"{self.manufacturer} {self.name}"


def _number(value: Fraction) -> str:
    """A tolerance or bound as typed: ``0.25``, ``5``, ``10000``."""
    return f"{float(value):g}"


def _load() -> tuple[CapacitorSeries, dict[str, CapacitorGrade], dict[str, Any]]:
    raw = load_packaged_json(
        __package__, "capacitor_grade_data.json", schema_version=1, label=_LABEL
    )
    series_raw = raw["series"]
    series = CapacitorSeries(
        **{
            key: require_printable_line(series_raw[key], f"Capacitor series {key}")
            for key in (
                "manufacturer",
                "name",
                "description",
                "measurement",
                "temperature_coefficient",
                "guarantee_note",
            )
        }
    )
    sheets = raw["sheets"]
    for part, sheet in sheets.items():
        label = f"Capacitor sheet {part!r}"
        if not _PART.match(part):
            raise RuntimeError(f"{label} is not a GRM1885C1H…A01 part number")
        require_https_url(sheet["url"], label)
        require_printable_line(sheet["as_of"], label)
        if not isinstance(sheet["sha256"], str) or not _SHA256.match(sheet["sha256"]):
            raise RuntimeError(f"{label} needs a SHA-256 of the copy read")
    if tuple(raw["grades"]) != GRADE_NAMES:
        raise RuntimeError(f"Capacitor grades must be {', '.join(GRADE_NAMES)}")
    grades = {}
    for name, grade_raw in raw["grades"].items():
        rows = tuple(_row(name, row, sheets) for row in grade_raw["rows"])
        label = f"Capacitor grade {name}"
        grades[name] = CapacitorGrade(
            name=name,
            label=require_printable_line(grade_raw["label"], label),
            description=require_printable_line(grade_raw["description"], label),
            rows=rows,
        )
    return series, grades, raw["coverage"]


def _row(grade: str, raw: dict[str, Any], sheets: dict[str, Any]) -> GradeRow:
    label = f"Capacitor grade {grade} row {raw.get('code')!r}"
    tolerance_pf = raw.get("tolerance_pf")
    tolerance_pct = raw.get("tolerance_pct")
    if (tolerance_pf is None) == (tolerance_pct is None):
        raise RuntimeError(f"{label} needs exactly one of tolerance_pf and tolerance_pct")
    row = GradeRow(
        from_pf=_pf(raw["from_pf"], label),
        to_pf=_pf(raw["to_pf"], label),
        code=require_printable_line(raw["code"], label),
        tolerance_pf=None if tolerance_pf is None else _pf(tolerance_pf, label),
        tolerance_pct=None if tolerance_pct is None else _pf(tolerance_pct, label),
        guarantee=require_guarantee_type(raw["guarantee"], label),
        tolerance_sheet=raw["tolerance_sheet"],
        range_parts=tuple(raw["range_parts"]),
    )
    if row.guarantee not in QUALIFYING_GUARANTEES:
        raise RuntimeError(f"{label} is not a guaranteed limit")
    if not 0 < row.from_pf <= row.to_pf:
        raise RuntimeError(f"{label} has an invalid value range")
    if min(value for value in (row.tolerance_pf, row.tolerance_pct) if value is not None) <= 0:
        raise RuntimeError(f"{label} has a non-positive tolerance")
    if row.tolerance_sheet not in sheets:
        raise RuntimeError(f"{label} cites a sheet that was not read")
    if not row.range_parts or not all(_PART.match(part) for part in row.range_parts):
        raise RuntimeError(f"{label} needs the part numbers that show its range is made")
    return row


SERIES, GRADES, _COVERAGE = _load()
_FINE = _COVERAGE["fine_step"]
_FINE_FROM, _FINE_TO, _FINE_STEP = (
    _pf(_FINE[key], _LABEL) for key in ("from_pf", "to_pf", "step_pf")
)
_E24_FROM, _E24_TO = (_pf(_COVERAGE["e24"][key], _LABEL) for key in ("from_pf", "to_pf"))
_E24_MANTISSAS = frozenset(Fraction(round(value * 100), 100) for value in E_SERIES["E24"])


def is_made(value_pf: Fraction) -> bool:
    """Whether the series makes a part of exactly ``value_pf`` (an exact ``Fraction``)."""
    if _FINE_FROM <= value_pf <= _FINE_TO:
        return (value_pf / _FINE_STEP).denominator == 1
    if _E24_FROM <= value_pf <= _E24_TO:
        mantissa = value_pf
        while mantissa >= 10:
            mantissa /= 10
        return mantissa in _E24_MANTISSAS
    return False


def made_values_pf() -> tuple[Fraction, ...]:
    """Every value the series makes, ascending."""
    steps = int((_FINE_TO - _FINE_FROM) / _FINE_STEP)
    fine = [_FINE_FROM + index * _FINE_STEP for index in range(steps + 1)]
    e24 = sorted(
        mantissa * 10**exponent
        for exponent in range(1, 5)
        for mantissa in _E24_MANTISSAS
        if _E24_FROM <= mantissa * 10**exponent <= _E24_TO
    )
    return tuple(fine + e24)


def _check_rows_cover_the_series() -> None:
    for grade in GRADES.values():
        for value in made_values_pf():
            matches = [row for row in grade.rows if row.from_pf <= value <= row.to_pf]
            if len(matches) != 1:
                raise RuntimeError(
                    f"Capacitor grade {grade.name} must give one tolerance for {value} pF"
                )


_check_rows_cover_the_series()


def require_grade(name: object) -> CapacitorGrade:
    """The grade called ``name``; the message names the choices."""
    if name not in GRADES:
        raise ValueError(f"Capacitor grade must be {' or '.join(GRADE_NAMES)}")
    return GRADES[name]  # type: ignore[index]


def sourced_tolerance_pf(value_pf: Fraction, grade: str) -> Fraction | None:
    """The guaranteed ± tolerance in pF of the ``value_pf`` part, or None if not made."""
    if not is_made(value_pf):
        return None
    row = require_grade(grade).row_for(value_pf)
    return None if row is None else row.tolerance_at(value_pf)


def tolerance_rule_text(grade: str) -> str:
    """The grade's tolerances by value range, for the output's rule line.

    Consecutive ranges with the same tolerance are joined: the standard grade reads
    ``±0.1 pF (0.5–0.9 pF), ±0.25 pF (1–5 pF), ±0.5 pF (5.1–9.9 pF), ±5% (10–10000 pF)``.
    """
    spans: list[list] = []
    for row in require_grade(grade).rows:
        if spans and spans[-1][0] == row.describe():
            spans[-1][2] = row.to_pf
        else:
            spans.append([row.describe(), row.from_pf, row.to_pf])
    return ", ".join(
        f"{tolerance} ({_number(low)}–{_number(high)} pF)" for tolerance, low, high in spans
    )
