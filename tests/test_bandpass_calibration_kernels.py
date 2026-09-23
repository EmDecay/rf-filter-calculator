"""Numeric kernels behind Top-C calibration: grid, measurement guards, and the Newton solver.

The solver helpers are exercised with plain deterministic residual functions whose
exact Jacobians and roots are known, so the expected values do not repeat the
implementation's algebra.
"""

import copy
import math

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.bandpass.model_diagnostics import model_diagnostics
from filter_lib.bandpass.passband_measurement import _deviation_grid, measure_netlist_passband
from filter_lib.bandpass.top_c_calibration import (
    _jacobian_columns,
    _newton_step,
    _reducing_step,
)
from filter_lib.shared.transfer_functions import MAX_FREQUENCY_POINTS


def _frequency_at_deviation(delta: float, f0: float, bw: float) -> float:
    """Positive root of f^2 - delta*bw*f - f0^2 = 0."""
    half = delta * bw / 2
    return half + math.sqrt(half * half + f0 * f0)


@pytest.fixture(scope="module")
def butterworth_design():
    return calculate_bandpass_filter(10e6, 0.5e6, 50, 3, "butterworth", "top")


class TestDeviationGrid:
    """The calibration grid is uniform in normalized deviation from -span to +span."""

    @pytest.mark.parametrize("f0, bw", [(10e6, 0.5e6), (1.0, 0.9)])
    def test_grid_samples_exact_symmetric_deviations(self, f0, bw):
        grid = _deviation_grid(f0, bw, 5)

        expected = [_frequency_at_deviation(delta, f0, bw) for delta in (-4, -2, 0, 2, 4)]
        assert grid == pytest.approx(expected, rel=1e-12, abs=0)
        # delta(f0^2/f) = -delta(f): mirrored samples are geometric reflections about f0.
        for low, high in zip(grid, reversed(grid)):
            assert low * high == pytest.approx(f0 * f0, rel=1e-12, abs=0)

    def test_smallest_grid_is_the_span_ends_and_center(self):
        f0, bw = 10e6, 0.5e6
        grid = _deviation_grid(f0, bw, 3, span=1.0)

        assert grid == pytest.approx(
            [_frequency_at_deviation(-1.0, f0, bw), f0, _frequency_at_deviation(1.0, f0, bw)],
            rel=1e-12,
            abs=0,
        )

    @pytest.mark.parametrize("points", [True, 2, 3.0, "401", MAX_FREQUENCY_POINTS + 1])
    def test_rejects_invalid_point_counts(self, points):
        with pytest.raises(ValueError, match="points must be an integer between 3 and"):
            _deviation_grid(10e6, 0.5e6, points)

    @pytest.mark.parametrize("span", [0.0, -1.0, math.nan, math.inf, True, "4"])
    def test_rejects_invalid_span(self, span):
        with pytest.raises(ValueError, match="span must be positive and finite"):
            _deviation_grid(10e6, 0.5e6, 5, span=span)


class TestPassbandMeasurementGuards:
    @pytest.mark.parametrize(
        "target_f0, target_bw",
        [(10e6, 0.05e6), (10e6, 0.1e6), (30e6, 0.5e6), (9.1e6, 0.5e6), (10.9e6, 0.5e6)],
        ids=[
            "grid-narrower-than-passband",
            "grid-at-passband",
            "grid-off-passband",
            "only-upper-skirt-beyond-grid",
            "only-lower-skirt-beyond-grid",
        ],
    )
    def test_skirts_beyond_the_grid_are_not_reported_as_edges(
        self, butterworth_design, target_f0, target_bw
    ):
        with pytest.raises(ValueError, match="skirts are outside the calibration grid"):
            measure_netlist_passband(butterworth_design, target_f0, target_bw)

    def test_underflowing_transmission_has_no_passband_peak(self, butterworth_design):
        isolated = copy.deepcopy(butterworth_design)
        isolated["c_coupling"] = [value * 1e-200 for value in isolated["c_coupling"]]

        with pytest.raises(ValueError, match="no finite passband peak"):
            measure_netlist_passband(isolated, 10e6, 0.5e6)

    def test_model_diagnostics_report_underflow_instead_of_failing(self, butterworth_design):
        isolated = copy.deepcopy(butterworth_design)
        isolated["c_coupling"] = [value * 1e-200 for value in isolated["c_coupling"]]

        diagnostics = model_diagnostics(isolated)

        for sample in diagnostics["harmonic_response"]["samples"]:
            assert sample["status"] == "outside_numeric_range"
            assert sample["transducer_gain_db"] is None
            assert sample["frequency_hz"] == 10e6 * sample["multiple"]
        comparisons = diagnostics["loss_estimate_validation"]["comparisons"]
        assert set(comparisons) == {"100", "250"}
        for record in comparisons.values():
            assert record["status"] == "outside_numeric_range"
            assert "circuit_added_center_loss_db" not in record


def _linear_evaluator(matrix, *, infeasible_above=None):
    """Residual r = J @ (x, y); optionally raise when x exceeds a feasibility bound."""
    (a, b), (c, d) = matrix
    calls = []

    def evaluate(x: float, y: float):
        calls.append((x, y))
        if infeasible_above is not None and x > infeasible_above:
            raise ValueError("infeasible trial")
        return {"x": x, "y": y}, (a * x + b * y, c * x + d * y)

    return evaluate, calls


class TestCalibrationNewtonKernels:
    @pytest.mark.parametrize("infeasible_above", [None, 0.3])
    def test_jacobian_columns_recover_a_linear_map(self, infeasible_above):
        """A forward step that is infeasible falls back to an exact backward difference."""
        matrix = ((2.0, 3.0), (-1.0, 5.0))
        evaluate, calls = _linear_evaluator(matrix, infeasible_above=infeasible_above)
        coordinates = [0.3, -0.2]
        _candidate, residual = evaluate(*coordinates)

        columns = _jacobian_columns(evaluate, coordinates, residual)

        assert columns[0] == pytest.approx((2.0, -1.0), rel=1e-9)
        assert columns[1] == pytest.approx((3.0, 5.0), rel=1e-9)
        assert calls[1][0] == pytest.approx(0.301)  # the forward trial is always attempted
        if infeasible_above is not None:
            assert calls[2][0] == pytest.approx(0.299)

    def test_newton_step_solves_the_linearized_system(self):
        columns = [(2.0, -1.0), (3.0, 5.0)]  # J = [[2, 3], [-1, 5]]
        residual = (0.05, -0.12)

        step = _newton_step(columns, residual)

        # J @ step = -residual, checked by direct multiplication.
        assert 2.0 * step[0] + 3.0 * step[1] == pytest.approx(-residual[0], rel=1e-12)
        assert -1.0 * step[0] + 5.0 * step[1] == pytest.approx(-residual[1], rel=1e-12)

    def test_newton_step_is_bounded_in_log_coordinates(self):
        step = _newton_step([(1.0, 0.0), (0.0, 1.0)], (3.0, -0.4))

        assert step == [-0.25, 0.25]

    @pytest.mark.parametrize(
        "columns",
        [[(1.0, 2.0), (2.0, 4.0)], [(1e-5, 0.0), (0.0, 1e-5)], [(math.inf, 0.0), (0.0, 1.0)]],
        ids=["rank-deficient", "near-singular", "non-finite"],
    )
    def test_singular_jacobian_is_rejected(self, columns):
        with pytest.raises(ValueError, match="Jacobian is singular"):
            _newton_step(columns, (0.1, 0.1))

    def test_reducing_step_halves_an_overshooting_step(self):
        # One-dimensional residual x - 1 from x = 0; a step of 3 overshoots to 2.
        evaluate, calls = _linear_evaluator(((1.0, 0.0), (0.0, 0.0)))

        def shifted(x, y):
            candidate, (value, other) = evaluate(x, y)
            return candidate, (value - 1.0, other)

        coordinates, candidate, residual = _reducing_step(
            shifted, [0.0, 0.0], (-1.0, 0.0), [3.0, 0.0]
        )

        assert coordinates == [1.5, 0.0]
        assert candidate == {"x": 1.5, "y": 0.0}
        assert residual == (0.5, 0.0)
        assert [x for x, _ in calls] == [3.0, 1.5]

    def test_reducing_step_skips_infeasible_trials(self):
        evaluate, calls = _linear_evaluator(((1.0, 0.0), (0.0, 0.0)), infeasible_above=1.0)

        def shifted(x, y):
            candidate, (value, other) = evaluate(x, y)
            return candidate, (value - 1.0, other)

        coordinates, _candidate, residual = _reducing_step(
            shifted, [0.0, 0.0], (-1.0, 0.0), [4.0, 0.0]
        )

        assert [x for x, _ in calls] == [4.0, 2.0, 1.0]
        assert coordinates == [1.0, 0.0]
        assert residual == (0.0, 0.0)

    def test_reducing_step_requires_strict_decrease(self):
        """A step that only mirrors the residual (|x - 1| stays 1) is not progress."""
        evaluate, calls = _linear_evaluator(((1.0, 0.0), (0.0, 0.0)))

        coordinates, _candidate, residual = _reducing_step(
            lambda x, y: (evaluate(x, y)[0], (x - 1.0, 0.0)), [0.0, 0.0], (-1.0, 0.0), [2.0, 0.0]
        )

        assert [x for x, _ in calls] == [2.0, 1.0]
        assert coordinates == [1.0, 0.0]
        assert residual == (0.0, 0.0)

    def test_reducing_step_gives_up_after_nine_halvings(self):
        evaluate, calls = _linear_evaluator(((1.0, 0.0), (0.0, 0.0)))

        with pytest.raises(ValueError, match="could not find a reducing bounded step"):
            # Moving away from the root never reduces |x - 1|.
            _reducing_step(
                lambda x, y: (evaluate(x, y)[0], (x - 1.0, 0.0)),
                [0.0, 0.0],
                (-1.0, 0.0),
                [-1.0, 0.0],
            )
        assert [x for x, _ in calls] == [-(0.5**attempt) for attempt in range(9)]
