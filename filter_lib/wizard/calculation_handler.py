"""Calculation orchestration for wizard results.

Main entry point that routes to filter-specific calculators.
The actual calculation logic is in filter_type_calculators.py.
Formatting helpers are in formatting_helpers.py.
"""

from copy import deepcopy

from .state import CalculationOutcome, FilterState


def calculate_and_format(state: FilterState) -> CalculationOutcome:
    """Calculate against a detached state snapshot and return its outcome.

    Args:
        state: FilterState with all parameters configured

    Returns:
        Detached success/error outcome. The supplied state is never mutated.
    """
    # Deferred so the wizard UI can start without loading the calculation
    # stack; it's only paid when the user actually reaches the results screen.
    from .filter_type_calculators import calculate_bandpass, calculate_highpass, calculate_lowpass

    # Direct calculator functions retain their legacy state.result side effect
    # for CLI/tests. Running them on a deep copy prevents a canceled or stale
    # worker from mutating the live wizard state.
    snapshot = state.calculation_copy()
    snapshot.result = {}
    snapshot.output_text = ""
    snapshot.build_analysis = None

    if snapshot.build_analysis_enabled:
        if snapshot.output_format not in {"table", "json"}:
            return CalculationOutcome(
                status="error",
                error=(
                    "Realized-build analysis is supported only with table or JSON component output"
                ),
            )
        if snapshot.quiet:
            return CalculationOutcome(
                status="error",
                error="Realized-build analysis cannot be combined with quiet output",
            )
        if snapshot.eseries == "none":
            return CalculationOutcome(
                status="error",
                error="Realized-build analysis requires an E-series",
            )

    try:
        if snapshot.category == "lowpass":
            lines = calculate_lowpass(snapshot)
        elif snapshot.category == "highpass":
            lines = calculate_highpass(snapshot)
        elif snapshot.category == "bandpass":
            lines = calculate_bandpass(snapshot)
        else:
            return CalculationOutcome(status="error", error="Unknown filter category")

        build_analysis = None
        if snapshot.build_analysis_enabled:
            from filter_lib.shared.build_output import format_build_analysis_block
            from filter_lib.shared.build_simulation import analyze_build

            build_analysis = analyze_build(
                snapshot.result,
                snapshot.category,
                snapshot.make_build_config(),
            )
            if snapshot.output_format == "json":
                lines = [_format_build_json(snapshot, build_analysis)]
            else:
                lines.extend(
                    (
                        "",
                        "Synthesis target: requested response and calculated components above.",
                    )
                )
                lines.extend(format_build_analysis_block(build_analysis))
    except Exception as e:
        message = str(e).strip() or type(e).__name__
        return CalculationOutcome(status="error", error=message)

    output_text = "\n".join(lines)
    if not output_text.strip() or not snapshot.result:
        return CalculationOutcome(status="error", error="Calculation returned no usable result")
    return CalculationOutcome(
        status="success",
        output_text=output_text,
        result=deepcopy(snapshot.result),
        build_analysis=deepcopy(build_analysis),
    )


def _format_build_json(state: FilterState, build_analysis) -> str:
    """Format component JSON with the shared realized-build schema attached."""
    eseries = state.eseries
    if state.category == "lowpass":
        from filter_lib.lowpass.display import format_json
    elif state.category == "highpass":
        from filter_lib.highpass.display import format_json
    else:
        from filter_lib.bandpass.formatters import format_json

    return format_json(
        state.result,
        eseries=eseries,
        build_analysis=build_analysis,
    )
