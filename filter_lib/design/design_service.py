"""The single synthesis-plus-analysis path shared by every presentation layer.

Calculators are imported inside the functions, from their package namespaces, so
wizard startup stays cheap and tests can patch ``filter_lib.lowpass.calculate_*``
and ``filter_lib.shared.build_simulation.analyze_build`` at one place.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from ..shared.cli_aliases import DEFAULT_RIPPLE_DB
from ..shared.eseries import DEFAULT_MATCH_POLICY, MatchPolicy
from .design_request import DesignRequest
from .design_result import DesignResult


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


def _synthesize_bandpass(request: DesignRequest) -> dict:
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


def synthesize(request: DesignRequest) -> dict:
    """Return the calculator result dict for ``request`` without build analysis."""
    if request.category == "bandpass":
        return _synthesize_bandpass(request)
    return _synthesize_ladder(request)


def resolve_match_policy(request: DesignRequest) -> MatchPolicy:
    """The capacitor match policy for ``request``; ``design()`` is its only caller."""
    return replace(DEFAULT_MATCH_POLICY, allow_sub_pf=request.allow_sub_pf)


def design(request: DesignRequest, should_cancel: Callable[[], bool] | None = None) -> DesignResult:
    """Synthesize ``request``, resolve its part policy, and run the build when asked.

    The build simulation runs only when ``request.run_build_analysis`` is set;
    ``should_cancel`` is polled by it, which raises ``BuildAnalysisCancelled`` when the
    check reports true.
    """
    result = synthesize(request)
    policy = resolve_match_policy(request)
    analysis = None
    if request.run_build_analysis:
        from ..shared.build_simulation import analyze_build

        analysis = analyze_build(
            result,
            request.category,
            request.realization,
            eseries=request.eseries,
            policy=policy,
            should_cancel=should_cancel,
        )
    return DesignResult(
        category=request.category,
        result=result,
        request=request,
        match_policy=policy,
        warnings=tuple(result.get("warnings", ())),
        build_analysis=analysis,
    )
