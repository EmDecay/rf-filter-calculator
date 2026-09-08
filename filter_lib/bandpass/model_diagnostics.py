"""Informational checks of Top-C rejection and small-loss approximations."""

import math
from dataclasses import replace

from ..shared.build_loss_models import _with_loss
from ..shared.circuit_builders import build_named_circuit
from ..shared.nodal_solver import solve_transducer_power_gain

# An explicitly chosen reporting threshold, not a synthesis acceptance gate.
COHN_COMPARISON_TOLERANCE_DB = 0.5


def _gain_db(circuit, z0: float, frequency: float) -> float:
    gain = solve_transducer_power_gain(
        circuit.n_nodes,
        circuit.branches(),
        z0,
        z0,
        circuit.in_node,
        circuit.out_node,
        [frequency],
    )[0]
    if gain <= 0:
        raise ValueError("gain is below the finite numeric range")
    return 10 * math.log10(gain)


def model_diagnostics(result: dict) -> dict:
    """Compare model predictions without changing calibrated design validity.

    Cohn uses complete resonator Q. Its comparison uses a single equivalent
    inductor loss per tank, exact component values and equal synthesis ports.
    It does not predict a rounded build or certify physical component Q.
    """
    circuit = build_named_circuit(result, "bandpass")
    f0, z0 = result["f0"], result["z0"]
    harmonic_samples = []
    for multiple in (2, 3):
        frequency = f0 * multiple
        try:
            gain = _gain_db(circuit, z0, frequency)
            harmonic_samples.append(
                {
                    "multiple": multiple,
                    "frequency_hz": frequency,
                    "transducer_gain_db": gain,
                    "status": "evaluated",
                }
            )
        except ValueError:
            harmonic_samples.append(
                {
                    "multiple": multiple,
                    "frequency_hz": frequency if math.isfinite(frequency) else None,
                    "transducer_gain_db": None,
                    "status": "outside_numeric_range",
                }
            )

    comparisons = {}
    for key, estimate in result["il_estimates"].items():
        q = float(key)
        record = {"resonator_qu": q, "cohn_estimate_db": estimate}
        try:
            lossy = replace(
                circuit,
                elements=tuple(
                    _with_loss(element, q if element.kind == "L" else None, f0)
                    for element in circuit.elements
                ),
            )
            lossless_gain = _gain_db(circuit, z0, f0)
            lossy_gain = _gain_db(lossy, z0, f0)
            added_loss = lossless_gain - lossy_gain
            error = estimate - added_loss
            record.update(
                {
                    "lossless_center_gain_db": lossless_gain,
                    "lossy_center_gain_db": lossy_gain,
                    "circuit_added_center_loss_db": added_loss,
                    "estimate_minus_circuit_db": error,
                    "status": "agrees_at_center"
                    if abs(error) <= COHN_COMPARISON_TOLERANCE_DB
                    else "poor_approximation_at_center",
                }
            )
        except ValueError:
            record["status"] = "outside_numeric_range"
        comparisons[key] = record

    return {
        "harmonic_response": {
            "model": "exact_lossless_top_c_circuit_equal_synthesis_ports",
            "informational_only": True,
            "acceptance_mask_applied": False,
            "samples": harmonic_samples,
        },
        "loss_estimate_validation": {
            "method": "cohn_small_loss_vs_exact_component_center_loss",
            "loss_model": "one_equivalent_inductor_series_loss_per_resonator",
            "reference_frequency_hz": f0,
            "comparison_tolerance_db": COHN_COMPARISON_TOLERANCE_DB,
            "tolerance_is_reporting_policy_not_design_gate": True,
            "scope": "center_frequency_model_comparison_not_hardware_or_full_passband_accuracy",
            "comparisons": comparisons,
        },
    }
