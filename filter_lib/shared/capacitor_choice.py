"""Choose a standard capacitor by its worst case within tolerance.

Each candidate (a single part or a parallel pair) covers an interval of possible
capacitance: from its nominal value less its tolerance to its nominal value plus its
tolerance, plus, for a pair, the assumed stray across its second part. Its score is the
larger distance from the target to either end of that interval. The best single part
and the best pair are found by exhaustive search over the E-series values the
sourced table lists; the pair is chosen only when its score, in percent of the target, is at
least the policy's margin (0.5 percentage points) better. Ties go to the single part;
between pairs to the smaller part ratio, then the lower nominal value; between singles
to the lower value. Arithmetic is exact (``Fraction`` in pF), so a tie is a real tie.

A part's tolerance is the sourced tolerance of its grade, or, with an override, the
larger of the override percentage and the sourced tolerance (an override can only
loosen a guarantee). A part whose tolerance is not smaller than its value is not
eligible. When the nominal rule's choice uses a part the sourced table does not list, that
choice is kept with status ``tolerance_not_sourced`` and an assumed tolerance.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import replace
from fractions import Fraction
from functools import cache

from .capacitor_grades import ASSUMED_TOLERANCE_PCT, is_made, made_values_pf, sourced_tolerance_pf
from .eseries import (
    _SERIES_HUNDREDTHS,
    TOLERANCE_NOT_SOURCED,
    ESeriesMatch,
    MatchPolicy,
    _error_pct,
)

_PF_PER_F = Fraction(10) ** 12


def _exact(value: float) -> Fraction:
    """The decimal value of a float as written (``1.3e-11`` is exactly 13/10**12)."""
    return Fraction(repr(value))


def part_pf(value_f: float) -> Fraction:
    """A standard part value in exact pF (part values are short decimals)."""
    return _exact(value_f) * _PF_PER_F


def _farads(value_pf: Fraction) -> float:
    """An exact pF value as the nearest float in farads."""
    return float(value_pf / _PF_PER_F)


@cache
def _series_values_pf(series: str) -> tuple[Fraction, ...]:
    """The values of ``series`` that the sourced table lists, ascending, in pF."""
    hundredths = set(_SERIES_HUNDREDTHS[series])
    values = []
    for value in made_values_pf():
        mantissa = value
        while mantissa >= 10:
            mantissa /= 10
        while mantissa < 1:
            mantissa *= 10
        if (mantissa * 100).denominator == 1 and int(mantissa * 100) in hundredths:
            values.append(value)
    return tuple(values)


def part_tolerance_pf(value_pf: Fraction, policy: MatchPolicy) -> Fraction | None:
    """The ± tolerance in pF of a sourced part under ``policy``, or None if not made."""
    sourced = sourced_tolerance_pf(value_pf, policy.grade)
    if sourced is None or policy.tolerance_override_pct is None:
        return sourced
    return max(_exact(policy.tolerance_override_pct) * value_pf / 100, sourced)


def assumed_tolerance_pct(policy: MatchPolicy) -> float:
    """The tolerance assumed for a part the sourced table does not list: the override, or 5%."""
    override = policy.tolerance_override_pct
    return override if override is not None else ASSUMED_TOLERANCE_PCT


def _candidates(policy: MatchPolicy, series: str) -> list[tuple[Fraction, Fraction]]:
    """``(value, tolerance)`` in pF of every eligible part, ascending by value."""
    floor = None if policy.allow_sub_pf else _exact(policy.minimum_capacitance_f) * _PF_PER_F
    candidates = []
    for value in _series_values_pf(series):
        if floor is not None and value < floor:
            continue
        tolerance = part_tolerance_pf(value, policy)
        if tolerance is not None and tolerance < value:
            candidates.append((value, tolerance))
    return candidates


def _not_sourced(nominal: ESeriesMatch, policy: MatchPolicy) -> ESeriesMatch:
    """Keep the nominal choice; each part gets its own tolerance.

    A part the table lists keeps its sourced tolerance (with the override floor); only a
    part the table does not list gets the assumed tolerance.
    """
    assumed = assumed_tolerance_pct(policy) / 100.0
    tolerances, fractions = [], []
    for value in nominal.selected_components or ():
        exact = part_pf(value)
        sourced = part_tolerance_pf(exact, policy)
        if sourced is None:
            tolerances.append(value * assumed)
            fractions.append(assumed)
        else:
            tolerances.append(_farads(sourced))
            fractions.append(float(sourced / exact))
    return replace(
        nominal,
        status=TOLERANCE_NOT_SOURCED,
        part_tolerances_f=tuple(tolerances),
        part_tolerance_fractions=tuple(fractions),
        tolerance_sourced=False,
    )


def choose_capacitor(
    nominal: ESeriesMatch, series: str, ratio_limit: float, policy: MatchPolicy
) -> ESeriesMatch:
    """The worst-case choice for ``nominal.target``, or ``nominal`` if not sourced.

    ``nominal`` is the nominal rule's choice, which has selected parts; it supplies the
    nearest single value for reference and decides whether the target is in the sourced
    series' range.
    """
    selected = nominal.selected_components or ()
    if not all(is_made(part_pf(value)) for value in selected):
        return _not_sourced(nominal, policy)
    candidates = _candidates(policy, series)
    if not candidates:
        return _not_sourced(nominal, policy)

    target = Fraction(nominal.target) * _PF_PER_F
    single_score, single_value, single_tolerance = min(
        (abs(value - target) + tolerance, value, tolerance) for value, tolerance in candidates
    )
    pair = _best_pair(candidates, target, ratio_limit, policy)

    common = {
        "target": nominal.target,
        "nearest_value": nominal.nearest_value,
        "nearest_error_pct": nominal.nearest_error_pct,
        "status": "recommended",
        "warnings": (),
        "policy": policy,
        "tolerance_sourced": True,
    }
    single_f = _farads(single_value)
    improvement = None
    if pair is not None:
        pair_score = pair[0]
        improvement = float((single_score - pair_score) * 100 / target)
        margin = _exact(policy.min_parallel_improvement_pct_points)
        if pair_wins(single_score, pair_score, target, margin):
            _score, _ratio, total, (low, low_tol), (high, high_tol) = pair
            total_f = _farads(total)
            return ESeriesMatch(
                single_value=single_f,
                single_error_pct=_error_pct(single_f, nominal.target),
                parallel=(_farads(low), _farads(high)),
                parallel_value=total_f,
                parallel_error_pct=_error_pct(total_f, nominal.target),
                recommended_kind="parallel",
                recommendation_reason="parallel_worst_case_materially_better",
                raw_parallel_improvement_pct_points=improvement,
                part_tolerances_f=(_farads(low_tol), _farads(high_tol)),
                part_tolerance_fractions=(float(low_tol / low), float(high_tol / high)),
                worst_case_error_f=_farads(pair_score),
                **common,
            )
    return ESeriesMatch(
        single_value=single_f,
        single_error_pct=_error_pct(single_f, nominal.target),
        parallel=None,
        parallel_value=None,
        parallel_error_pct=None,
        recommended_kind="single",
        recommendation_reason=(
            "single_worst_case_is_best"
            if pair is None or pair[0] >= single_score
            else "parallel_worst_case_improvement_below_policy_threshold"
        ),
        raw_parallel_improvement_pct_points=improvement,
        part_tolerances_f=(_farads(single_tolerance),),
        part_tolerance_fractions=(float(single_tolerance / single_value),),
        worst_case_error_f=_farads(single_score),
        **common,
    )


def pair_wins(
    single_score: Fraction, pair_score: Fraction, target: Fraction, margin: Fraction
) -> bool:
    """Whether the pair's score beats the single's by ``margin`` percent of the target.

    The margin is inclusive: an improvement of exactly ``margin`` points chooses the pair.
    An equal score never does, even with a zero margin: ties go to the single part.
    """
    gain = single_score - pair_score
    return gain > 0 and gain * 100 >= margin * target


def _best_pair(
    candidates: list[tuple[Fraction, Fraction]],
    target: Fraction,
    ratio_limit: float,
    policy: MatchPolicy,
):
    """The best pair as ``(score, ratio, total, low part, high part)``, or None.

    A pair's interval contains its nominal total, so a pair whose total is further from the
    target than the best score found so far cannot beat it; only totals within that bound
    are scored, and the bound tightens as better pairs are found.
    """
    values = [value for value, _tolerance in candidates]
    ratio = _exact(float(ratio_limit))
    stray = _exact(policy.stray_capacitance_f) * _PF_PER_F
    best = None
    for index, (low, low_tolerance) in enumerate(candidates):
        start, stop = index, bisect_right(values, low * ratio)
        if best is not None:
            start = bisect_left(values, max(low, target - best[0] - low), lo=index)
            stop = bisect_right(values, min(low * ratio, target + best[0] - low))
        for high, high_tolerance in candidates[start:stop]:
            total = low + high
            tolerance = low_tolerance + high_tolerance
            score = max(abs(total - tolerance - target), abs(total + stray + tolerance - target))
            key = (score, high / low, total, (low, low_tolerance), (high, high_tolerance))
            if best is None or key[:3] < best[:3]:
                best = key
    return best
