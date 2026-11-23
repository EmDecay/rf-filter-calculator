"""Calculation orchestration for wizard results.

Main entry point that routes to filter-specific calculators.
The actual calculation logic is in filter_type_calculators.py, which calls the shared
``filter_lib.design`` service and renderer.
"""

from collections.abc import Callable
from copy import deepcopy

from .state import (
    CALCULATION_STOPPED_MESSAGE,
    INTERNAL_NO_RESULT_MESSAGE,
    CalculationOutcome,
    FilterState,
)


def calculate_and_format(
    state: FilterState, should_cancel: Callable[[], bool] | None = None
) -> CalculationOutcome:
    """Calculate against a detached state snapshot and return its outcome.

    Args:
        state: FilterState with all parameters configured
        should_cancel: Optional zero-argument check passed to the build
            simulation, the only step whose run time the user controls. The Results
            worker passes its own cancellation flag so leaving the screen or quitting
            stops the analysis instead of leaving a thread running.

    Returns:
        Detached success/error outcome. The supplied state is never mutated.
    """
    # Deferred so the wizard UI can start without loading the calculation
    # stack; it's only paid when the user actually reaches the results screen.
    from filter_lib.design import render_lines
    from filter_lib.shared.build_types import BuildAnalysisCancelled

    from .filter_type_calculators import (
        calculate_bandpass,
        calculate_highpass,
        calculate_lowpass,
        design_from_state,
    )

    # The calculators store their design result on the state they are given. Running
    # them on a deep copy prevents a canceled or stale worker from mutating the live
    # wizard state.
    snapshot = state.calculation_copy()
    snapshot.result = {}
    snapshot.output_text = ""
    snapshot.build_analysis = None
    snapshot.design_outcome = None
    snapshot.document_designs = {}

    # Options the shown output cannot apply are left out here (the shared rule), so
    # every remaining combination is one the CLI accepts.
    try:
        options = snapshot.to_render_options()
    except ValueError as e:
        return CalculationOutcome(status="error", error=str(e))

    calculators = {
        "lowpass": calculate_lowpass,
        "highpass": calculate_highpass,
        "bandpass": calculate_bandpass,
    }
    if snapshot.category not in calculators:
        return CalculationOutcome(status="error", error="Unknown filter category")

    # Only the result shown is calculated here. A disabled build or resonator Q never
    # runs for it; a saved JSON that uses one is calculated when it is saved.
    try:
        if snapshot.runs_build:
            # The build is part of the request; only it polls the cancellation check.
            lines = render_lines(design_from_state(snapshot, should_cancel), options)
        else:
            lines = calculators[snapshot.category](snapshot)
    except BuildAnalysisCancelled:
        # Only a cancelled worker sees this, and its revision can no longer publish.
        return CalculationOutcome(status="error", error=CALCULATION_STOPPED_MESSAGE)
    except Exception as e:
        message = str(e).strip() or type(e).__name__
        return CalculationOutcome(status="error", error=message)

    output_text = "\n".join(lines)
    if not output_text.strip() or not snapshot.result:
        return CalculationOutcome(status="error", error=INTERNAL_NO_RESULT_MESSAGE)
    # One detached copy: the result and the build analysis are the design result's own.
    detached = deepcopy(snapshot.design_outcome)
    if detached is None:
        return CalculationOutcome(
            status="success", output_text=output_text, result=deepcopy(snapshot.result)
        )
    return CalculationOutcome(
        status="success",
        output_text=output_text,
        result=detached.result,
        build_analysis=detached.build_analysis,
        design=detached,
    )
