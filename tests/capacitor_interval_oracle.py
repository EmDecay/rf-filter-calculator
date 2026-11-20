"""Independent statement of the worst-case capacitor rule, for tests.

Written from ``docs/component-data-sources.md`` (Fixed capacitors) and the rule in plain
words, without calling production code: the rows below are typed from the evidence page,
and the search is a plain brute force over every single part and every pair. Production
code (``filter_lib.shared.capacitor_choice``) prunes its search; this does not.

Assumed rows (Murata GRM1885C1H…A01, values in pF):

- made values: 0.5 to 9.9 in 0.1 steps; E24 values from 10 to 10000;
- standard grade: ±0.1 (0.5–0.9), ±0.25 (1–5), ±0.5 (5.1–9.9), ±5% (10–10000);
- tight grade: ±0.05 (0.5–0.9), ±0.1 (1–5), ±0.25 (5.1–9.9), ±2% (10–910),
  ±5% (1000–10000).
"""

from __future__ import annotations

from fractions import Fraction

E24 = (
    10,
    11,
    12,
    13,
    15,
    16,
    18,
    20,
    22,
    24,
    27,
    30,
    33,
    36,
    39,
    43,
    47,
    51,
    56,
    62,
    68,
    75,
    82,
    91,
)
E12 = (10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82)


def _made(value: Fraction) -> bool:
    if Fraction(1, 2) <= value <= Fraction(99, 10):
        return (value * 10).denominator == 1
    if 10 <= value <= 10000:
        while value >= 100:
            value /= 10
        return value.denominator == 1 and int(value) in E24
    return False


def tolerance(value: Fraction, grade: str) -> Fraction:
    """The ± tolerance in pF of a made part of ``value`` pF."""
    if value <= Fraction(9, 10):
        return Fraction(1, 10) if grade == "standard" else Fraction(1, 20)
    if value <= 5:
        return Fraction(1, 4) if grade == "standard" else Fraction(1, 10)
    if value < 10:
        return Fraction(1, 2) if grade == "standard" else Fraction(1, 4)
    if grade == "tight" and value <= 910:
        return value * 2 / 100
    return value * 5 / 100


def series_values(series: str) -> list[Fraction]:
    """Values of ``series`` (E12 or E24) from 1 pF to 10 nF that the series makes."""
    mantissas = E12 if series == "E12" else E24
    values = [Fraction(m, 10) * 10**decade for decade in range(4) for m in mantissas]
    values.append(Fraction(10000))
    return sorted(value for value in values if _made(value))


def best_choice(
    target_pf: Fraction,
    series: str = "E24",
    grade: str = "standard",
    stray_pf: Fraction = Fraction(1, 5),
    override_pct: Fraction | None = None,
    margin_pp: Fraction = Fraction(1, 2),
) -> tuple[tuple[Fraction, ...], Fraction]:
    """``(parts, score)`` of the rule's choice for ``target_pf``, by brute force."""

    def tol(value: Fraction) -> Fraction:
        sourced = tolerance(value, grade)
        return sourced if override_pct is None else max(override_pct * value / 100, sourced)

    values = [value for value in series_values(series) if tol(value) < value]
    singles = []
    for value in values:
        low, high = value - tol(value), value + tol(value)
        singles.append((max(abs(low - target_pf), abs(high - target_pf)), value))
    single_score, single = min(singles)
    pairs = []
    for first in values:
        for second in values:
            if second < first or second > 10 * first:
                continue
            total = first + second
            spread = tol(first) + tol(second)
            low, high = total - spread, total + stray_pf + spread
            score = max(abs(low - target_pf), abs(high - target_pf))
            pairs.append((score, second / first, total, first, second))
    pair = min(pairs)
    gain = single_score - pair[0]
    if gain > 0 and gain * 100 >= margin_pp * target_pf:
        return (pair[3], pair[4]), pair[0]
    return (single,), single_score
