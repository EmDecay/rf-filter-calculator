"""The acceptance designs get the parts the evidence page's coverage table records.

``docs/component-data-sources.md`` (Coverage of the acceptance designs) lists, for every
inductor of the four VHF/UHF acceptance designs, the chip inductor that ranks first, how
many catalog variants qualify, its drift screen, error budget, achieved inductance and
self-capacitance, and why VHF toroids and air-core coils offer none. Every positive row
asserts its exact part and figures; every negative row asserts the limit that failed. The
band-pass is also covered after applying its coupling advice, as the criterion requires.
"""

from __future__ import annotations

import pytest

from filter_lib.design import DesignRequest, design
from filter_lib.shared.chip_inductor_data import chip_parts
from filter_lib.shared.chip_selection import qualifying_chips
from filter_lib.shared.inductor_suggestion import AIR_COIL_EXCLUSION, VHF_TOROID_EXCLUSION
from filter_lib.shared.parsing import parse_inductance
from filter_lib.shared.srf_screen import (
    LIMIT_ALLOWANCE,
    CheckWindow,
    PartModel,
    check_window,
    screen_part,
)


def _lowpass(frequency_hz: float) -> DesignRequest:
    return DesignRequest("lowpass", "chebyshev", "pi", frequency_hz, 50.0, 5, ripple_db=0.1)


def _bandpass(**overrides) -> DesignRequest:
    return DesignRequest(
        "bandpass", "chebyshev", "top", 146e6, 50.0, 3, ripple_db=0.5, bandwidth_hz=4e6, **overrides
    )


# (design, inductor, target nH, part, qualifying count, drift screen % of catalog L,
#  (mismatch, tolerance, drift low, drift high) % of target, worst case %, achieved nH,
#  C_self pF), as printed in the coverage table (two decimals; achieved L three, C_self
#  four). 21 nH counts 12 variants: 0603CS-22NXJRW reaches exactly +10.00%, at the limit.
ROWS = [
    (
        _lowpass(146e6),
        "L1",
        74.7381,
        "LQW15AN75NG80D",
        18,
        (-0.17, 0.20),
        (0.35, 2.01, -0.17, 0.20),
        (-1.83, 2.56),
        75.148,
        0.0587,
    ),
    (
        _lowpass(222e6),
        "L1",
        49.1521,
        "LQW18AN48NG80D",
        19,
        (-0.14, 0.54),
        (-2.34, 1.95, -0.13, 0.54),
        (-4.43, 0.15),
        48.260,
        0.0725,
    ),
    (
        _lowpass(440e6),
        "L1",
        24.7995,
        "LQW15AN25NG80D",
        17,
        (-0.06, 1.10),
        (0.81, 2.02, -0.06, 1.14),
        (-1.27, 3.96),
        25.276,
        0.0603,
    ),
    (
        _bandpass(),
        "LT1",
        54.5148,
        "0603CS-56NXGRW",
        18,
        (-1.11, 0.00),
        (2.72, 2.05, -1.12, 0.00),
        (-0.45, 4.78),
        55.718,
        0.1267,
    ),
    (
        _bandpass(resonator_inductance=21e-9),
        "LT1",
        21.0,
        "LQW15AN21NG80D",
        12,
        (-0.05, 0.06),
        (0.00, 2.00, -0.05, 0.06),
        (-2.05, 2.06),
        21.012,
        0.0596,
    ),
    (
        _bandpass(resonator_inductance=20e-9),
        "LT1",
        20.0,
        "LQW18AN20NG00D",
        9,
        (-0.04, 0.05),
        (0.00, 2.00, -0.04, 0.05),
        (-2.04, 2.05),
        20.010,
        0.0528,
    ),
]
IDS = ["lp-146", "lp-222", "lp-440", "bp-146-as-designed", "bp-146-21nH", "bp-146-20nH"]


@pytest.mark.parametrize(
    "request_, name, target_nh, part, count, drift, budget, worst, achieved_nh, c_self_pf",
    ROWS,
    ids=IDS,
)
def test_each_inductor_gets_the_recorded_chip_inductor(
    request_, name, target_nh, part, count, drift, budget, worst, achieved_nh, c_self_pf
):
    outcome = design(request_)
    inductor = outcome.parts.inductor(name)
    chips = inductor.kind("chip").suggestions
    best = chips[0]
    screen = best.build.screen

    assert inductor.target_h * 1e9 == pytest.approx(target_nh, abs=5e-5)
    assert best.part_name == part
    assert len(qualifying_chips(inductor.target_h, outcome.parts.check_window)) == count
    assert [round(value * 100, 2) for value in screen.drift_range] == list(drift)
    terms = best.error_budget
    assert [
        round(value, 2)
        for value in (terms.nominal_mismatch_pct, terms.tolerance_pct, *terms.srf_drift_pct)
    ] == list(budget)
    assert [round(value, 2) for value in terms.worst_case_pct] == list(worst)
    assert round(best.achieved_h * 1e9, 3) == achieved_nh
    assert round(best.part_model.self_capacitance_f * 1e12, 4) == c_self_pf
    # No toroid is rated at VHF, so the build uses the chip inductor.
    assert inductor.build_pick == best


@pytest.mark.parametrize("request_", [row[0] for row in ROWS[:4]], ids=IDS[:4])
def test_vhf_toroids_and_air_coils_state_why_they_offer_none(request_):
    outcome = design(request_)

    for inductor in outcome.parts.inductors.values():
        assert VHF_TOROID_EXCLUSION in inductor.kind("toroid").reason_none
        assert inductor.kind("air-coil").reason_none == AIR_COIL_EXCLUSION
        assert inductor.kind("chip").suggestions


@pytest.mark.parametrize(
    "request_, number, worst_pct",
    [(_lowpass(222e6), "0603CS-47NXJRW", -10.07), (_lowpass(440e6), "LQW15AN26NJ80D", 11.30)],
    ids=["lp-222", "lp-440"],
)
def test_the_close_misses_fail_the_allowance(request_, number, worst_pct):
    outcome = design(request_)
    target = outcome.result["inductors"][0]
    part = next(part for part in chip_parts() if part.part_number == number)
    model = PartModel(part.inductance_h, part.test_frequency_hz, part.srf_min_hz)

    screen = screen_part(target, check_window(outcome.result, "lowpass"), model, part.tolerance_pct)

    assert screen.failed_limits == {LIMIT_ALLOWANCE}
    assert round(max(screen.worst_case_pct, key=abs), 2) == worst_pct
    shown = outcome.parts.inductor("L1").kind("chip").suggestions
    assert number not in {suggestion.part_name for suggestion in shown}


def test_the_band_pass_coupling_values_are_supplied_by_a_chip():
    # The coupling advice can reach 1 pF with 21 nH (only LQW15AN21N_80D) or 20 nH
    # (LQW18AN20N_00D or LQW15AN20N_80D) from the catalog.
    window = CheckWindow(0.0, 148.01369798755184e6)

    assert {chip.part.part_number for chip in qualifying_chips(21e-9, window)} >= {"LQW15AN21NG80D"}
    assert {
        chip.part.part_number[:9]
        for chip in qualifying_chips(20e-9, window)
        if round(chip.part.inductance_h * 1e9) == 20
    } == {"LQW18AN20", "LQW15AN20"}
    assert not any(
        round(chip.part.inductance_h * 1e9) == 21 and chip.part.family.name != "LQW15AN_80"
        for chip in qualifying_chips(21e-9, window)
    )


def test_the_band_pass_after_its_coupling_advice_gets_its_chip_inductor():
    # The fourth acceptance design is the 2 m band-pass after applying its coupling advice,
    # rerun with the advised value exactly as printed.
    advice = design(_bandpass()).coupling_advice
    assert advice is not None and advice.setting == "21nH"

    rerun = design(_bandpass(resonator_inductance=parse_inductance(advice.setting)))

    assert rerun.coupling_advice is None
    for inductor in rerun.parts.inductors.values():
        assert inductor.build_pick.part_name == "LQW15AN21NG80D"
        assert VHF_TOROID_EXCLUSION in inductor.kind("toroid").reason_none
        assert inductor.kind("air-coil").reason_none == AIR_COIL_EXCLUSION
