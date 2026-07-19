"""E-series component matching for standard resistor/capacitor/inductor values.

Reference: IEC 60063 (Preferred number series for resistors and capacitors)
"""

import math
from dataclasses import dataclass

from .numeric import is_finite_real, positive_float_from_log

# E-series normalized values (1.0-10.0 range), geometric progression
# fmt: off
E_SERIES: dict[str, list[float]] = {
    "E12": [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2],
    "E24": [
        1.0,
        1.1,
        1.2,
        1.3,
        1.5,
        1.6,
        1.8,
        2.0,
        2.2,
        2.4,
        2.7,
        3.0,
        3.3,
        3.6,
        3.9,
        4.3,
        4.7,
        5.1,
        5.6,
        6.2,
        6.8,
        7.5,
        8.2,
        9.1,
    ],
    "E96": [
        1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18,
        1.21, 1.24, 1.27, 1.30, 1.33, 1.37, 1.40, 1.43,
        1.47, 1.50, 1.54, 1.58, 1.62, 1.65, 1.69, 1.74,
        1.78, 1.82, 1.87, 1.91, 1.96, 2.00, 2.05, 2.10,
        2.15, 2.21, 2.26, 2.32, 2.37, 2.43, 2.49, 2.55,
        2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09,
        3.16, 3.24, 3.32, 3.40, 3.48, 3.57, 3.65, 3.74,
        3.83, 3.92, 4.02, 4.12, 4.22, 4.32, 4.42, 4.53,
        4.64, 4.75, 4.87, 4.99, 5.11, 5.23, 5.36, 5.49,
        5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65,
        6.81, 6.98, 7.15, 7.32, 7.50, 7.68, 7.87, 8.06,
        8.25, 8.45, 8.66, 8.87, 9.09, 9.31, 9.53, 9.76,
    ],
}
# fmt: on


def _finite_real(value: object) -> bool:
    return is_finite_real(value)


def _validate_series(series: object) -> str:
    if not isinstance(series, str) or series not in E_SERIES:
        raise ValueError(f"Unknown series {series!r}. Use E12, E24, or E96.")
    return series


@dataclass(frozen=True)
class MatchPolicy:
    """Policy for turning raw preferred-value matches into a build choice.

    The thresholds are calculator policy, not tolerances implied by IEC 60063.
    ``minimum_capacitance_f`` applies only to additive capacitor matching.
    """

    prefer_single_within_pct: float = 1.0
    min_parallel_improvement_pct_points: float = 0.5
    minimum_capacitance_f: float = 1e-12
    allow_sub_pf: bool = False

    def __post_init__(self) -> None:
        if not _finite_real(self.prefer_single_within_pct) or self.prefer_single_within_pct < 0:
            raise ValueError("prefer_single_within_pct must be finite and non-negative")
        if (
            not _finite_real(self.min_parallel_improvement_pct_points)
            or self.min_parallel_improvement_pct_points < 0
        ):
            raise ValueError("min_parallel_improvement_pct_points must be finite and non-negative")
        if not _finite_real(self.minimum_capacitance_f) or self.minimum_capacitance_f <= 0:
            raise ValueError("minimum_capacitance_f must be positive and finite")
        if not isinstance(self.allow_sub_pf, bool):
            raise ValueError("allow_sub_pf must be a boolean")

    def as_dict(self) -> dict[str, float | bool]:
        """JSON-safe policy fields for machine-readable exports."""
        return {
            "prefer_single_within_pct": self.prefer_single_within_pct,
            "min_parallel_improvement_pct_points": (self.min_parallel_improvement_pct_points),
            "minimum_capacitance_f": self.minimum_capacitance_f,
            "allow_sub_pf": self.allow_sub_pf,
        }

    def summary(self) -> str:
        """Compact, deterministic policy description for CSV output."""
        floor_pf = self.minimum_capacitance_f * 1e12
        floor = "disabled" if self.allow_sub_pf else f"{floor_pf:g}pF"
        return (
            f"single<={self.prefer_single_within_pct:g}%;"
            f"parallel-improvement>={self.min_parallel_improvement_pct_points:g}pp;"
            f"minimum-cap={floor}"
        )


DEFAULT_MATCH_POLICY = MatchPolicy()


@dataclass
class ESeriesMatch:
    """Result of E-series component matching."""

    target: float  # Original target value
    single_value: float  # Closest single E-series value
    single_error_pct: float  # Error percentage for single
    parallel: tuple[float, float] | None  # Parallel combo (V1, V2) if better
    parallel_value: float | None  # Resulting parallel value
    parallel_error_pct: float | None  # Error percentage for parallel
    recommended_kind: str = "single"
    recommendation_reason: str = "single_is_preferred"
    status: str = "recommended"
    warnings: tuple[str, ...] = ()
    policy: MatchPolicy = DEFAULT_MATCH_POLICY
    raw_parallel_improvement_pct_points: float | None = None

    @property
    def prefers_parallel(self) -> bool:
        """True only when policy recommends the practical two-part realization."""
        return self.recommended_kind == "parallel"

    @property
    def parallel_improvement_pct_points(self) -> float | None:
        """Absolute-error improvement from the raw pair, in percentage points."""
        return self.raw_parallel_improvement_pct_points

    @property
    def selected_value(self) -> float | None:
        """Realized value selected by policy, or ``None`` when expert input is required."""
        if self.recommended_kind == "parallel":
            return self.parallel_value
        if self.recommended_kind == "single":
            return self.single_value
        return None

    @property
    def selected_components(self) -> tuple[float, ...] | None:
        """Physical part values selected by policy."""
        if self.recommended_kind == "parallel":
            return self.parallel
        if self.recommended_kind == "single":
            return (self.single_value,)
        return None

    @property
    def best_value(self) -> float:
        """Backward-compatible nominal substitution value.

        When policy declines to recommend a sub-pF part, retain the exact
        target rather than silently substituting a disallowed component.
        New realization code should use :attr:`selected_value` and handle
        ``None`` explicitly.
        """
        return self.selected_value if self.selected_value is not None else self.target


def _normalize(value: float) -> tuple[float, int]:
    """Extract mantissa (1.0-10.0) and decade exponent."""
    if not is_finite_real(value) or value <= 0:
        raise ValueError("Value must be positive and finite")
    logarithm = math.log10(value)
    decade = math.floor(logarithm)
    scale = 10.0**decade
    mantissa = value / scale if math.isfinite(scale) and scale > 0 else 10.0 ** (logarithm - decade)
    if mantissa >= 10.0:
        mantissa /= 10
        decade += 1
    elif mantissa < 1.0:
        mantissa *= 10
        decade -= 1
    return mantissa, decade


def _denormalize(mantissa: float, decade: int) -> float:
    """Reconstruct value from mantissa and decade."""
    try:
        scale = 10.0**decade
        value = mantissa * scale
        if math.isfinite(value) and value > 0:
            return value
        log_value = math.log(mantissa) + decade * math.log(10.0)
    except OverflowError as exc:
        raise ValueError("E-series candidate is outside the finite numeric range") from exc
    return positive_float_from_log(log_value, "E-series candidate")


def _finite_candidate(mantissa: float, decade: int) -> float | None:
    """Build a finite positive candidate, skipping out-of-range decades."""
    try:
        return _denormalize(mantissa, decade)
    except ValueError:
        return None


def _error_pct(actual: float, target: float) -> float:
    """Calculate percentage error."""
    return (actual - target) / target * 100


def find_closest_single(target: float, series: str = "E24") -> tuple[float, float]:
    """Find closest single E-series value.

    Args:
        target: Target component value (any unit; matching is decade-free)
        series: E-series name (E12, E24, E96)

    Returns:
        Tuple of (matched_value, error_pct); error_pct is signed
        (positive = matched value above target).

    Raises:
        ValueError: If series is unknown or target is not positive.
    """
    series = _validate_series(series)

    _, decade = _normalize(target)
    series_values = E_SERIES[series]
    best_value: float | None = None
    best_error = float("inf")

    # Check all values in current decade
    for sv in series_values:
        candidate = _finite_candidate(sv, decade)
        if candidate is None:
            continue
        err = abs(_error_pct(candidate, target))
        if err < best_error:
            best_error, best_value = err, candidate

    # Check boundary values in adjacent decades
    adjacent = (
        _finite_candidate(series_values[0], decade + 1),
        _finite_candidate(series_values[-1], decade - 1),
    )
    for candidate in adjacent:
        if candidate is None:
            continue
        err = abs(_error_pct(candidate, target))
        if err < best_error:
            best_error, best_value = err, candidate

    if best_value is None:
        raise ValueError("Target is outside the finite E-series matching range")
    return best_value, _error_pct(best_value, target)


def find_parallel_combo(
    target: float,
    series: str = "E24",
    mode: str | None = None,
    ratio_limit: float = 10.0,
    minimum_value: float | None = None,
) -> tuple[tuple[float, float], float, float] | None:
    """Find parallel combination closest to target.

    Args:
        target: Target component value
        series: E-series name (E12, E24, E96)
        mode: 'additive' for capacitors (C_par = C1 + C2),
              'harmonic' for resistors/inductors (R_par = R1*R2/(R1+R2)).
              Required — the physics of the combination depends on the
              component kind, which cannot be inferred from the value alone.
        ratio_limit: Maximum ratio between component values. Caps the value
            spread so recommendations stay practical to source and so one
            component does not dominate tolerance-wise.
        minimum_value: Optional lower bound for each physical part. Raw search
            remains unbounded by default; builder-facing matching supplies its
            explicit capacitor floor.

    Returns:
        ((V1, V2), parallel_value, error_pct) with V1 <= V2, or None if no
        combination satisfies the ratio limit. error_pct is signed
        (positive = realized value above target).

    Raises:
        ValueError: If series is unknown or mode is not
            'additive'/'harmonic'.
    """
    series = _validate_series(series)

    if mode not in ("additive", "harmonic"):
        raise ValueError(f"Mode is required: use 'additive' or 'harmonic' (got {mode!r}).")
    if not _finite_real(ratio_limit) or ratio_limit < 1:
        raise ValueError("ratio_limit must be finite and >= 1")
    if minimum_value is not None and (not _finite_real(minimum_value) or minimum_value <= 0):
        raise ValueError("minimum_value must be positive and finite")

    _, decade = _normalize(target)
    # Span one decade below through two above the target: additive halves can
    # sit a decade down, while harmonic companions sit above the target (up
    # to ratio_limit times it), which can reach two decades up.
    candidates = [
        candidate
        for d in range(decade - 1, decade + 3)
        for sv in E_SERIES[series]
        if (candidate := _finite_candidate(sv, d)) is not None
    ]

    best_combo, best_value, best_error = None, None, float("inf")

    if mode == "harmonic":
        # Harmonic parallel: R_par = R1*R2/(R1+R2)
        for v1 in candidates:
            if minimum_value is not None and v1 < minimum_value:
                continue
            # R_par < min(R1, R2) always, so every value in a harmonic
            # parallel pair must individually exceed the target; a v1 at or
            # below it can never combine up to the target with any v2.
            if v1 <= target:
                continue
            # Solve R_par = target for the exact companion:
            # V2 = V1*target/(V1-target), positive because v1 > target.
            denominator = 1.0 - target / v1
            if denominator <= 0:
                continue
            v2_needed = target / denominator
            if not math.isfinite(v2_needed):
                continue
            v2, _ = find_closest_single(v2_needed, series)
            if minimum_value is not None and v2 < minimum_value:
                continue
            # Check ratio constraint
            if max(v1, v2) / min(v1, v2) > ratio_limit:
                continue
            parallel_val = 1.0 / (1.0 / v1 + 1.0 / v2)
            err = abs(_error_pct(parallel_val, target))
            if err < best_error:
                best_error = err
                best_value = parallel_val
                best_combo = (min(v1, v2), max(v1, v2))
    else:
        # Additive parallel: C_par = C1 + C2
        for i, v1 in enumerate(candidates):
            if minimum_value is not None and v1 < minimum_value:
                continue
            for v2 in candidates[i:]:
                if minimum_value is not None and v2 < minimum_value:
                    continue
                if max(v1, v2) / min(v1, v2) > ratio_limit:
                    continue
                combined = v1 + v2
                if not math.isfinite(combined):
                    continue
                err = abs(_error_pct(combined, target))
                if err < best_error:
                    best_error = err
                    best_value = combined
                    best_combo = (min(v1, v2), max(v1, v2))

    if best_combo:
        return (best_combo, best_value, _error_pct(best_value, target))
    return None


def match_component(
    target: float,
    series: str = "E24",
    parallel_mode: str | None = None,
    ratio_limit: float = 10.0,
    *,
    policy: MatchPolicy | None = None,
) -> ESeriesMatch:
    """Find best E-series match with optional parallel combination.

    Args:
        target: Target component value
        series: E-series name (E12, E24, E96)
        parallel_mode: 'additive' for capacitors, 'harmonic' for resistors/inductors.
                       Required — see find_parallel_combo.
        ratio_limit: Maximum ratio between parallel component values
        policy: Explicit builder-facing recommendation policy. Defaults to
            :data:`DEFAULT_MATCH_POLICY`.

    Returns:
        ESeriesMatch with single and optional parallel matches
    """
    if policy is not None and not isinstance(policy, MatchPolicy):
        raise ValueError("policy must be a MatchPolicy or None")
    active_policy = DEFAULT_MATCH_POLICY if policy is None else policy
    single_val, single_err = find_closest_single(target, series)
    minimum_value = None
    if parallel_mode == "additive" and not active_policy.allow_sub_pf:
        minimum_value = active_policy.minimum_capacitance_f
    parallel_result = find_parallel_combo(
        target,
        series,
        parallel_mode,
        ratio_limit,
        minimum_value=minimum_value,
    )

    if parallel_result:
        combo, par_val, par_err = parallel_result
    else:
        combo, par_val, par_err = None, None, None

    warnings: list[str] = []
    if (
        parallel_mode == "additive"
        and not active_policy.allow_sub_pf
        and target < active_policy.minimum_capacitance_f
    ):
        floor_pf = active_policy.minimum_capacitance_f * 1e12
        recommended_kind = "none"
        status = "expert_override_required"
        reason = "target_below_automatic_capacitance_floor"
        warnings.append(
            f"Target is below the {floor_pf:g} pF automatic-selection floor; "
            "enable the expert override to select sub-pF parts."
        )
    elif abs(single_err) <= active_policy.prefer_single_within_pct:
        recommended_kind = "single"
        status = "recommended"
        reason = "single_within_preferred_error"
    elif par_err is not None and (
        abs(single_err) - abs(par_err) >= active_policy.min_parallel_improvement_pct_points
    ):
        recommended_kind = "parallel"
        status = "recommended"
        reason = "parallel_materially_improves_error"
    else:
        recommended_kind = "single"
        status = "recommended"
        reason = "parallel_improvement_below_policy_threshold"

    raw_improvement = abs(single_err) - abs(par_err) if par_err is not None else None
    if recommended_kind != "parallel":
        combo, par_val, par_err = None, None, None

    return ESeriesMatch(
        target=target,
        single_value=single_val,
        single_error_pct=single_err,
        parallel=combo,
        parallel_value=par_val,
        parallel_error_pct=par_err,
        recommended_kind=recommended_kind,
        recommendation_reason=reason,
        status=status,
        warnings=tuple(warnings),
        policy=active_policy,
        raw_parallel_improvement_pct_points=raw_improvement,
    )
