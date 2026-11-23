"""The single synthesis-plus-analysis path shared by every presentation layer.

Calculators are imported inside the functions, from their package namespaces, so
wizard startup stays cheap and tests can patch ``filter_lib.lowpass.calculate_*``
and ``filter_lib.shared.build_simulation.analyze_build`` at one place.
"""

from __future__ import annotations

from collections.abc import Callable

from ..shared.cancellation import (
    CancellationCheck,
    raise_if_cancelled,
    require_cancellation_check,
)
from ..shared.cli_aliases import DEFAULT_RIPPLE_DB
from .coupling_advice import advise_coupling
from .design_request import DesignRequest
from .design_result import DesignResult
from .part_resolution import resolve_parts


def _ladder_calculator(category: str, filter_type: str) -> Callable:
    if category == "lowpass":
        from .. import lowpass as module
    else:
        from .. import highpass as module
    calculators = {
        "butterworth": module.calculate_butterworth,
        "chebyshev": module.calculate_chebyshev,
        "bessel": module.calculate_bessel,
    }
    if filter_type not in calculators:
        raise ValueError(f"Unknown filter type: {filter_type}")
    return calculators[filter_type]


def _synthesize_ladder(request: DesignRequest) -> dict:
    calculate = _ladder_calculator(request.category, request.filter_type)
    if request.is_chebyshev:
        values = calculate(
            request.frequency_hz,
            request.impedance,
            request.ripple_db,
            request.order,
            topology=request.topology,
        )
    else:
        values = calculate(
            request.frequency_hz, request.impedance, request.order, topology=request.topology
        )
    header = {
        "filter_type": request.filter_type,
        "freq_hz": request.frequency_hz,
        "impedance": request.impedance,
    }
    # The LP->HP transform swaps component roles, so highpass calculators return
    # inductors first; each category keeps its historical dict key order.
    if request.category == "lowpass":
        caps, inds, order = values
        components = {"capacitors": caps, "inductors": inds}
    else:
        inds, caps, order = values
        components = {"inductors": inds, "capacitors": caps}
    return {
        **header,
        **components,
        "order": order,
        # ripple=None tells the display layer to omit the ripple row.
        "ripple": request.ripple_db if request.is_chebyshev else None,
        "topology": request.topology,
    }


def _synthesize_bandpass(
    request: DesignRequest, should_cancel: CancellationCheck | None = None
) -> dict:
    from ..bandpass import calculate_bandpass_filter

    result = calculate_bandpass_filter(
        f0=request.frequency_hz,
        bw=request.bandwidth_hz,
        z0=request.impedance,
        n_resonators=request.order,
        filter_type=request.filter_type,
        coupling=request.topology,
        # Non-Chebyshev types ignore ripple but the parameter must still pass
        # validation, so send the known-good default rather than user input.
        ripple_db=request.ripple_db if request.is_chebyshev else DEFAULT_RIPPLE_DB,
        q_safety=request.q_safety,
        qu=request.qu,
        ql=request.ql,
        qc=request.qc,
        resonator_impedance=request.resonator_impedance,
        resonator_inductance=request.resonator_inductance,
        should_cancel=should_cancel,
    )
    if request.requested_f_low_hz is not None:
        result["requested_parameters"].update(
            {
                "frequency_specification": "edge_frequencies",
                "f_low_hz": request.requested_f_low_hz,
                "f_high_hz": request.requested_f_high_hz,
            }
        )
    return result


def synthesize(request: DesignRequest, should_cancel: CancellationCheck | None = None) -> dict:
    """Return the calculator result dict for ``request`` without parts or build analysis.

    ``should_cancel`` is polled before synthesis and, for band-pass, before each circuit
    evaluation of the calibration and before the response check; it raises
    ``DesignCancelled``. Ladder synthesis is a closed-form calculation and is checked
    only before it starts.
    """
    require_cancellation_check(should_cancel)
    raise_if_cancelled(should_cancel)
    if request.category == "bandpass":
        return _synthesize_bandpass(request, should_cancel)
    return _synthesize_ladder(request)


def design(request: DesignRequest, should_cancel: CancellationCheck | None = None) -> DesignResult:
    """Synthesize ``request``, resolve its parts, and run the build when asked.

    The build simulation runs only when ``request.run_build_analysis`` is set. A
    band-pass design whose coupling capacitors are too small gets its tank-inductance
    advice (``coupling_advice``). ``should_cancel`` is polled by synthesis, part
    resolution, the advice and the build; when it reports true the design stops by raising
    ``DesignCancelled`` (the build raises its subclass ``BuildAnalysisCancelled``).
    """
    result = synthesize(request, should_cancel)
    parts = resolve_parts(request, result, should_cancel)
    advice = advise_coupling(request, result, parts, should_cancel)
    analysis = None
    if request.run_build_analysis:
        from ..shared.build_simulation import analyze_build

        analysis = analyze_build(
            result,
            request.category,
            request.realization,
            parts=parts,
            should_cancel=should_cancel,
        )
    return DesignResult(
        category=request.category,
        result=result,
        request=request,
        parts=parts,
        warnings=tuple(result.get("warnings", ())),
        build_analysis=analysis,
        coupling_advice=advice,
    )
