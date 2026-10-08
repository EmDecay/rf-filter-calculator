"""Main display function for bandpass filter results.

Orchestrates output formatting, topology diagrams, and E-series matching.
``format_table_lines`` is the single bandpass table renderer; the CLI prints
it and the wizard shows it, so the two cannot drift apart.
"""

import textwrap
from typing import Any

from ..shared.display_helpers import eseries_section_lines
from ..shared.eseries import MatchPolicy
from ..shared.formatting import (
    band_edge_digits,
    format_capacitance,
    format_fixed,
    format_frequency,
    format_inductance,
    format_restated_frequency,
    format_restated_value,
)
from ..shared.plotting import (
    find_db_thresholds,
    format_threshold_table,
    render_bandpass_plot_pair,
)
from ..shared.response_export import export_response_csv, export_response_json, response_meta
from ..shared.toroid_display import (
    format_winding_candidate_section,
    has_winding_suggestion,
    inductor_note_line,
)
from .diagrams import format_top_c_diagram
from .formatters import (
    coupling_capacitor_rows,
    format_csv,
    format_eseries_match,
    format_json,
    format_quiet,
)
from .transfer import netlist_frequency_sweep

# Type alias for filter result dict
BandpassResult = dict[str, Any]

# A 1% FBW design spans only a small part of the minimum 0.1-decade plot
# window. 601 points keeps both skirts represented while the renderer still
# compresses the samples to terminal width.
PLOT_POINTS = 601

# Warning lines wrap at the width the build-simulation bullets use.
WARNING_WRAP_WIDTH = 96

# Status from response_verification.validate_netlist_shape: "validated" means both
# -3 dB edges, the passband shape, Chebyshev ripple, and the points just outside the
# passband are within the tool's limits, in one -3 dB region, at up to 10% FBW.
_VALIDATION_STATUS_TEXT = {
    "validated": "Passed (simulated circuit matches the requested response)",
    "outside_validated_envelope": "Not confirmed; see warnings below",
}


def display_results(
    result: BandpassResult,
    raw: bool = False,
    output_format: str = "table",
    quiet: bool = False,
    eseries: str | None = "E24",
    show_plot: bool = False,
    plot_data: str | None = None,
    include_toroids: bool = True,
    toroid_compact: bool = False,
    toroid_full: bool = False,
    matched_sim: dict[str, Any] | None = None,
    build_analysis=None,
) -> None:
    """Display calculated filter component values.

    Args:
        result: Dict from calculate_bandpass_filter()
        raw: If True, display values in scientific notation
        output_format: 'table', 'json', or 'csv'
        quiet: If True, output only component values
        eseries: E-series for matching (None to disable)
        show_plot: Show ASCII frequency response
        plot_data: Export plot data as 'json' or 'csv'
        include_toroids: Include toroid recommendations in output
        toroid_compact: Use compact 1-line-per-rec text format
        toroid_full: Show up to three qualified cores in table output (default top-1;
            JSON carries up to three and CSV the best available)
        matched_sim: Optional matched-value simulation summary attached to
            JSON output as an additive ``matched_sim`` key
        build_analysis: Optional realized-build analysis result attached to
            JSON output; table rendering is handled by the command/wizard
    """
    # Handle plot data export (simulated from the synthesized circuit)
    if plot_data:
        sweep = netlist_frequency_sweep(result, points=PLOT_POINTS)
        freqs = [f for f, _ in sweep]
        response_db = [db for _, db in sweep]
        if plot_data == "json":
            print(export_response_json(freqs, response_db, response_meta("bandpass", result)))
        else:
            print(export_response_csv(freqs, response_db))
        return

    if output_format == "json":
        print(
            format_json(
                result,
                eseries=eseries,
                include_toroids=include_toroids,
                matched_sim=matched_sim,
                build_analysis=build_analysis,
            )
        )
        return
    if output_format == "csv":
        print(format_csv(result, eseries=eseries, include_toroids=include_toroids))
        return
    if quiet:
        print(format_quiet(result, raw))
        return

    _print_table_output(
        result, raw, eseries, show_plot, include_toroids, toroid_compact, toroid_full
    )


def _print_table_output(
    result: BandpassResult,
    raw: bool,
    eseries: str | None,
    show_plot: bool,
    include_toroids: bool = True,
    toroid_compact: bool = False,
    toroid_full: bool = False,
) -> None:
    """Print full table output with diagram and component values."""
    lines = format_table_lines(
        result,
        raw=raw,
        eseries=eseries,
        show_plot=show_plot,
        include_toroids=include_toroids,
        toroid_compact=toroid_compact,
        toroid_full=toroid_full,
    )
    print("\n".join(lines))
    print()


def format_table_lines(
    result: BandpassResult,
    *,
    raw: bool = False,
    eseries: str | None = "E24",
    show_plot: bool = False,
    include_toroids: bool = True,
    toroid_compact: bool = False,
    toroid_full: bool = False,
    match_policy: MatchPolicy | None = None,
) -> list[str]:
    """Render the bandpass table output as lines, for the CLI and the wizard.

    Args:
        result: Dict from calculate_bandpass_filter()
        raw: Print SI values in scientific notation and skip preferred values
        eseries: E-series for the preferred-value section (None to omit it)
        show_plot: Append the simulated response plot and threshold table
        include_toroids: Append the shared-inductance winding candidates
        toroid_compact: One line per winding candidate
        toroid_full: Up to three candidates instead of the best one
        match_policy: E-series match policy (None selects the default policy)
    """
    lines = format_header_lines(result)

    if result["warnings"]:
        lines.append("\nWarnings:")
        for warning in result["warnings"]:
            lines.extend(
                textwrap.wrap(
                    warning,
                    width=WARNING_WRAP_WIDTH,
                    initial_indent="  ⚠ ",
                    subsequent_indent="    ",
                    break_on_hyphens=False,
                )
            )

    lines.extend(format_q_model_lines(result))
    il_text = format_insertion_loss_line(result)
    if il_text:
        lines.append(il_text)
    lines.extend(format_validation_scope_lines(result))

    lines.extend(["\nTopology:", format_top_c_diagram(result["n_resonators"])])
    lines.extend(_component_table_lines(result, raw, mention_toroids=include_toroids))
    lines.extend(_external_q_lines(result))

    if eseries and not raw:
        lines.extend(format_eseries_lines(result, eseries, match_policy))

    if include_toroids:
        lines.extend(format_toroid_block_lines(result, toroid_compact, 3 if toroid_full else 1))

    if show_plot:
        lines.extend(_frequency_response_lines(result))
    return lines


def format_header_lines(result: BandpassResult) -> list[str]:
    """Design header restating the request; band edges resolve the printed bandwidth.

    Center, bandwidth, and impedance repeat the typed values exactly. The edges are
    computed, so they carry enough significant digits that their difference restates
    the bandwidth to four figures even for a 0.1% band (not 99.95 / 100.1 MHz beside
    100 kHz).
    """
    edge_digits = band_edge_digits(result["f_high"], result["bw"])
    lines = [
        f"\n{result['filter_type'].title()} Coupled-Resonator Band-Pass Filter",
        "=" * 50,
        f"Center Frequency f₀: {format_restated_frequency(result['f0'])}",
        f"Lower -3 dB Edge fₗ: {format_restated_frequency(result['f_low'], edge_digits)}",
        f"Upper -3 dB Edge fₕ: {format_restated_frequency(result['f_high'], edge_digits)}",
        f"-3 dB Bandwidth:     {format_restated_frequency(result['bw'])}",
        f"Fractional BW:       {result['fbw'] * 100:.2f}%",
        f"Impedance Z₀:        {format_restated_value(result['z0'])} Ω",
    ]
    if result["ripple_db"] is not None:
        lines.append(f"Ripple:              {result['ripple_db']} dB")
    lines.append(f"Resonators:          {result['n_resonators']}")
    lines.append("Coupling:            Top-C (series capacitors)")
    status_text = _VALIDATION_STATUS_TEXT.get(result.get("response_validation_status"))
    if status_text:
        lines.append(f"Response Check:      {status_text}")
    lines.append("=" * 50)
    return lines


def format_insertion_loss_line(result: BandpassResult) -> str:
    """Loss added at f₀ by resonator losses, Cohn estimate beside the circuit result, e.g.

    ``Added loss at f₀ for resonator Qu (inductor and capacitor losses together):``
    ``  Qu=100:  Cohn estimate 3.46 dB, circuit simulation 3.46 dB``

    The circuit value is the center-frequency gain of the exact circuit, lossless minus
    with one series loss per resonator inductor for that Qu. Returns an empty string
    when the result carries no il_estimates (older result dicts).
    """
    il_estimates = result.get("il_estimates")
    if not il_estimates:
        return ""
    labels = _qu_labels(il_estimates)
    width = max(len(label) for label in labels.values()) + len("Qu=:")
    validation = result.get("loss_estimate_validation") or {}
    comparisons = validation.get("comparisons", {})
    tolerance = validation.get("comparison_tolerance_db")
    lines = ["Added loss at f₀ for resonator Qu (inductor and capacitor losses together):"]
    for key, estimate in il_estimates.items():
        row = f"  {f'Qu={labels[key]}:':<{width}}  Cohn estimate {format_fixed(estimate, 2)} dB"
        check = comparisons.get(key)
        if check is not None:
            loss = check.get("circuit_added_center_loss_db")
            if loss is None:
                row += ", circuit simulation not available (outside numeric range)"
            else:
                row += f", circuit simulation {format_fixed(loss, 2)} dB"
                if check.get("status") == "poor_approximation_at_center":
                    row += (
                        f"\n  {'':<{width}}  (estimate off by more than {tolerance:g} dB; "
                        "use the simulated value)"
                    )
        lines.append(row)
    return "\n".join(lines)


def _qu_label(value: float, extra_digits: int = 0) -> str:
    """Display text for one Q value without printing a precise value at full precision.

    A compact value that ``:g`` reproduces (``100``, ``12345``, ``1e+06``) prints as is.
    A precise value such as 132.3529411764706 keeps four significant digits, or all of
    its integer digits, plus ``extra_digits`` (``132.4``, ``123457``).
    """
    compact = f"{value:g}"
    if float(compact) == value:
        return compact
    digits = max(4, len(f"{abs(value):.0f}")) + extra_digits
    return f"{value:.{min(17, digits)}g}"


def _qu_labels(qu_keys) -> dict[str, str]:
    """Map Qu keys to :func:`_qu_label` text, widened only as far as needed to stay distinct.

    A user Qu of 100.00001 therefore still prints apart from the standard ``100``.
    """
    keys = list(qu_keys)
    # 17 significant digits always separate distinct binary64 values.
    for extra_digits in range(14):
        labels = {key: _qu_label(float(key), extra_digits) for key in keys}
        if len(set(labels.values())) == len(labels):
            break
    return labels


def format_validation_scope_lines(result: BandpassResult) -> list[str]:
    """Say what the response check covers, then the attenuation at 2×f₀ and 3×f₀.

    The harmonic samples are the transducer gain of the exact lossless circuit between
    equal source and load impedance, so the attenuation is exactly minus that gain.
    """
    if "harmonic_response" not in result:
        return []
    lines = [
        "Response check covers the -3 dB edges, passband shape, and points just outside the "
        "passband.",
        f"Farther out, Top-C rejection can differ from the ideal "
        f"{result['filter_type'].title()} response and is not checked.",
    ]
    parts = []
    for sample in result["harmonic_response"]["samples"]:
        gain = sample["transducer_gain_db"]
        value = f"{format_fixed(-gain, 2)} dB" if gain is not None else "too large to compute"
        parts.append(f"{sample['multiple']}×f₀: {value}")
    if parts:
        lines.append(f"  Attenuation at {'; at '.join(parts)} (ideal lossless parts)")
    return lines


def format_q_model_lines(result: BandpassResult) -> list[str]:
    """A blank separator, plus the resonator Qu the user gave and what it came from."""
    q_model = result.get("q_model", {})
    resonator_qu = q_model.get("resonator_qu")
    if resonator_qu is None:
        return [""]

    # Reuse the insertion-loss label so a widened Qu reads the same on both lines.
    il_labels = _qu_labels(result.get("il_estimates") or {})
    qu_text = next(
        (label for key, label in il_labels.items() if float(key) == resonator_qu),
        _qu_label(resonator_qu),
    )
    component_parts = []
    if q_model.get("inductor_ql") is not None:
        component_parts.append(f"QL={_qu_label(q_model['inductor_ql'])}")
    if q_model.get("capacitor_qc") is not None:
        component_parts.append(f"QC={_qu_label(q_model['capacitor_qc'])}")
    source = f" (from {' and '.join(component_parts)} at f₀)" if component_parts else ""
    return ["", f"Your Qu: {qu_text}{source}"]


def format_toroid_block_lines(
    result: BandpassResult, compact: bool = False, top_n: int = 1
) -> list[str]:
    """Shared-L_resonant toroid section as lines for the CLI and wizard.

    Every resonator uses the same inductance, so one block labelled for
    L1…Ln replaces per-inductor repetition.
    """
    label = f"L1–L{result['n_resonators']} (all equal)"
    return format_winding_candidate_section(
        [(label, result["L_resonant"])], result["f0"], compact, top_n
    )


def _component_table_lines(result: BandpassResult, raw: bool, mention_toroids: bool) -> list[str]:
    """Tank capacitor / inductor table followed by the coupling capacitor table.

    Rules are 24 box-drawing characters; each cell is padded to 22 characters plus
    one space on each side, so changing one width without the other breaks borders.
    """
    rule = "─" * 24
    lines = [
        f"\n{'Component Values':^50}",
        f"┌{rule}┬{rule}┐",
        f"│{'Tank Capacitors':^24}│{'Inductors':^24}│",
        f"├{rule}┼{rule}┤",
    ]
    for i, c_tank in enumerate(result["c_tank"]):
        if raw:
            cap_str = f"Cp{i + 1}: {c_tank:.6e} F"
            ind_str = f"L{i + 1}: {result['L_resonant']:.6e} H"
        else:
            cap_str = f"Cp{i + 1}: {format_capacitance(c_tank)}"
            ind_str = f"L{i + 1}: {format_inductance(result['L_resonant'])}"
        lines.append(f"│ {cap_str:<22} │ {ind_str:<22} │")
    lines.append(f"└{rule}┴{rule}┘")
    lines.append(
        inductor_note_line(
            mention_toroids and has_winding_suggestion([result["L_resonant"]], result["f0"])
        )
    )

    lines += [f"\n┌{rule}┐", f"│{'Coupling Capacitors':^24}│", f"├{rule}┤"]
    for label, value in coupling_capacitor_rows(result):
        cs_str = f"{label}: {value:.6e} F" if raw else f"{label}: {format_capacitance(value)}"
        lines.append(f"│ {cs_str:<22} │")
    lines.append(f"└{rule}┘")
    return lines


def _external_q_lines(result: BandpassResult) -> list[str]:
    """External Q at each port, naming the end capacitor that sets it."""
    realized_in = " (set by Ce_in)" if result.get("c_end_in") is not None else ""
    realized_out = " (set by Ce_out)" if result.get("c_end_out") is not None else ""
    return [
        f"\nExternal Q (input):  {result['qe_in']:.2f}{realized_in}",
        f"External Q (output): {result['qe_out']:.2f}{realized_out}",
    ]


def format_eseries_lines(
    result: BandpassResult, eseries: str, policy: MatchPolicy | None = None
) -> list[str]:
    """Standard-value choice for every tank and coupling capacitor.

    Inductors are wound to value, so they get no standard-value matching.
    """
    lines = eseries_section_lines(eseries, policy=policy)
    rows = [(f"Cp{i + 1}", c_tank) for i, c_tank in enumerate(result["c_tank"])]
    for label, value in rows + coupling_capacitor_rows(result):
        lines.append(f"{label} calculated {format_capacitance(value)}")
        lines.extend(format_eseries_match(value, eseries, format_capacitance, policy))
    return lines


def _frequency_response_lines(result: BandpassResult) -> list[str]:
    """Frequency response plot with zoomed passband and threshold table.

    The response is an ideal-component circuit simulation of the synthesized
    values; it does not predict layout, package, parasitic, or power effects.
    """
    from ..shared.transfer_response_dispatch import make_bp_netlist_response_db

    # ripple_db is None for non-Chebyshev results; the plot annotations still
    # need a numeric ripple, so fall back to the 0.5 dB display default.
    ripple = result.get("ripple_db") or 0.5
    sweep = netlist_frequency_sweep(result, points=PLOT_POINTS)
    # "Simulated" because this is the circuit, not the ideal response shape that the
    # shape warning compares it with; "ideal parts" because the parts are lossless and exact.
    title = (
        f"Simulated Response, ideal parts (dB): {result['filter_type'].title()}, "
        f"{result['n_resonators']} resonators"
    )
    response_fn = make_bp_netlist_response_db(result)
    plot = render_bandpass_plot_pair(
        sweep,
        result["f0"],
        result["bw"],
        f_low_hz=result["f_low"],
        f_high_hz=result["f_high"],
        title=title,
        ripple_db=ripple,
        response_fn=response_fn,
        detail_title="Simulated Response Detail",
    )
    return [f"\n{plot}", format_bandpass_thresholds(result, sweep, response_fn)]


def format_bandpass_thresholds(result: BandpassResult, sweep, response_fn) -> str:
    """Render evaluated BP thresholds identically in the CLI and wizard."""
    freqs = [f for f, _ in sweep]
    from ..shared.response_refinement import refine_response

    refined = refine_response(
        response_fn,
        freqs,
        (result["f_low"], result["f_high"]),
        reference_frequency=result["f0"],
        frequency_scale=result["bw"],
        drop_db=3.0,
    )
    freqs, dbs = list(refined.frequencies), list(refined.response_db)
    lines = []
    if not refined.converged:
        lines.append("The frequencies below did not converge; treat them as approximate.")
    thresholds = find_db_thresholds(
        freqs,
        dbs,
        filter_type="bandpass",
        reference_frequency=refined.reference_frequency,
        relative_to_peak=True,
        response_fn=response_fn,
        frequency_tolerance_hz=result["bw"] * 1e-7,
    )
    lines.append(
        "Levels below are relative to the peak nearest the center "
        f"({format_fixed(refined.reference_db, 3)} dB at "
        f"{format_frequency(refined.reference_frequency)})."
    )
    if len(refined.regions) > 1:
        lines.append(f"The response is above -3 dB in {len(refined.regions)} separate ranges.")
    lines.append(format_threshold_table(thresholds, filter_type="bandpass"))
    return "\n".join(lines)
