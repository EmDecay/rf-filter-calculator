"""Sizing each band-pass tank as a fixed standard part plus a sourced trimmer.

The need (what the fixed part and trimmer must cover together) is recomputed here from
the branch formulas alone; the trimmer's range at the tank frequency follows its series
inductance; and every fit is conditional on that inductance.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import math

import pytest

from filter_lib.design import DesignRequest, design
from filter_lib.shared import tank_trimmers
from filter_lib.shared.build_types import BuildConfig
from filter_lib.shared.capacitor_choice import eligible_parts_pf
from filter_lib.shared.eseries import DEFAULT_MATCH_POLICY
from filter_lib.shared.tank_trimmers import (
    ASSUMED_TRIMMER_SERIES_INDUCTANCE_H,
    TankNeed,
    effective_capacitance,
    no_part_assumption,
    port_branch_range,
    series_inductance,
    toroid_assumption,
    trimmer_range_f,
)
from filter_lib.shared.trimmer_data import trimmer_parts
from tests.cli_parity_helpers import cli_stdout

TANK_FREQUENCY_2M = 145_973_950.62110272
OMEGA_2M = 2 * math.pi * TANK_FREQUENCY_2M


def _two_metre(**overrides) -> DesignRequest:
    return DesignRequest(
        "bandpass", "chebyshev", "top", 146e6, 50.0, 3, ripple_db=0.5, bandwidth_hz=4e6, **overrides
    )


def _trimmer(part_number: str):
    return next(part for part in trimmer_parts() if part_number in part.part_numbers)


# -- The trimmer's range at the tank frequency -------------------------------------------


@pytest.mark.parametrize(
    ("frequency_hz", "expected_pf"),
    [(29e6, 3.00299), (146e6, 3.07770), (440e6, 3.89252)],
)
def test_a_series_inductance_raises_the_low_stop(frequency_hz, expected_pf):
    # BFC280820109 (3-10 pF guaranteed at 200 kHz) with 10 nH in series.
    assert effective_capacitance(3e-12, 10e-9, frequency_hz) * 1e12 == pytest.approx(
        expected_pf, abs=5e-6
    )


def test_a_3_pf_low_end_is_out_of_reach_at_146_mhz(monkeypatch):
    trimmer = _trimmer("BFC280820109")
    low, high = trimmer_range_f(trimmer, 10e-9, 146e6, None, 146e6)
    assert (low * 1e12, high * 1e12) == (pytest.approx(3.07770, abs=5e-6), pytest.approx(10.0))

    # Every other input sourced: the trimmer alone must cover 3.00-9.00 pF (no fixed part
    # helps below the trimmer's minimum), which it reaches only from 3.0777 pF.
    monkeypatch.setattr(tank_trimmers, "series_inductance", lambda _trimmer: (10e-9, False))
    candidates = eligible_parts_pf(DEFAULT_MATCH_POLICY, "E24")
    best_split = tank_trimmers._best_split_for
    reachable = best_split(
        trimmer, TankNeed(3.08e-12, 9e-12), 146e6, None, 146e6, DEFAULT_MATCH_POLICY, candidates
    )
    assert reachable is not None and reachable.fixed_parts_f == ()
    assert (
        best_split(
            trimmer, TankNeed(3.0e-12, 9e-12), 146e6, None, 146e6, DEFAULT_MATCH_POLICY, candidates
        )
        is None
    )


def test_a_vishay_minimum_srf_bounds_the_inductance_and_every_other_part_is_assumed():
    assert series_inductance(_trimmer("BFC280820109")) == (
        pytest.approx(10.1321e-9, rel=1e-5),
        False,
    )
    # No guaranteed SRF: the labelled assumption.
    assert series_inductance(_trimmer("BFC280824508")) == (
        ASSUMED_TRIMMER_SERIES_INDUCTANCE_H,
        True,
    )
    assert series_inductance(_trimmer("AT 0310 R2")) == (ASSUMED_TRIMMER_SERIES_INDUCTANCE_H, True)


def test_a_trimmer_at_its_series_resonance_has_no_range():
    # 1/(omega^2 Cmin) = 10 nH at about 919 MHz for a 3 pF stop.
    assert trimmer_range_f(_trimmer("BFC280820109"), 10e-9, 920e6, None, 920e6) is None


# -- The end coupling through its port ----------------------------------------------------


def test_the_end_coupling_shunt_is_ce_over_one_plus_omega_r_ce_squared():
    low, high = port_branch_range((2.662e-12, 2.662e-12), 0.0, 50.0, OMEGA_2M, None, 146e6)

    assert low == high
    assert low / OMEGA_2M * 1e12 == pytest.approx(2.623, abs=5e-4)


def test_the_end_coupling_interval_includes_its_interior_maximum():
    # A 400 ohm port and a 2.7 pF +/-20% coupler: the shunt peaks at C = 1/(omega R) =
    # 2.7257 pF, inside 2.16-3.24 pF, where it is half of it.
    low, high = port_branch_range((2.16e-12, 3.24e-12), 0.0, 400.0, OMEGA_2M, None, 146e6)

    assert high / OMEGA_2M * 1e12 == pytest.approx(1.3629, abs=5e-5)
    ends = [c / (1 + (OMEGA_2M * 400 * c) ** 2) for c in (2.16e-12, 3.24e-12)]
    assert low / OMEGA_2M == pytest.approx(min(ends), rel=1e-12)
    assert high / OMEGA_2M > max(ends)


def test_a_lossy_end_coupler_keeps_its_maximum_along_the_stray_edge():
    # With capacitor Q the parts and the stray no longer add exactly; the extremes are
    # still on the box's corners or along its edges.
    reference_hz, q, resistance = 146e6, 50.0, 400.0

    def point(parts_f, stray_f):
        esr = 1 / (2 * math.pi * reference_hz * parts_f * q)
        branch = 1 / complex(esr, -1 / (OMEGA_2M * parts_f)) + 1j * OMEGA_2M * stray_f
        return (branch / (1 + resistance * branch)).imag

    low, high = port_branch_range(
        (2.16e-12, 3.24e-12), 0.2e-12, resistance, OMEGA_2M, q, reference_hz
    )
    grid = [point(2.16e-12 + i * 0.00108e-12, j * 0.01e-12) for i in range(1001) for j in range(21)]
    assert low == pytest.approx(min(grid), rel=1e-12)
    assert high >= max(grid)
    assert high == pytest.approx(max(grid), rel=1e-6)


# -- The need, recomputed independently ---------------------------------------------------


def _chip_corners(pick, omega, q=None, reference_hz=None):
    """The inductor's susceptance at both tolerance ends, at its minimum SRF and with none.

    With ``q``, each inductance has the series resistance that gives that Q at
    ``reference_hz``.
    """

    def inductor(value):
        resistance = 0.0 if q is None else 2 * math.pi * reference_hz * value / q
        return (1 / complex(resistance, omega * value)).imag

    model = pick.part_model
    values = []
    for sign in (-1, 1):
        catalog = model.catalog_inductance_h * (1 + sign * pick.tolerance_pct / 100)
        l0 = catalog * (1 - (model.test_frequency_hz / model.srf_hz) ** 2)
        c_self = 1 / ((2 * math.pi * model.srf_hz) ** 2 * l0)
        values += [inductor(l0) + omega * c_self, inductor(catalog)]
    return min(values), max(values)


def test_an_inner_tank_s_need_is_its_target_less_every_branch_at_either_end():
    outcome = design(_two_metre(resonator_inductance=21e-9))
    result, parts = outcome.result, outcome.parts
    omega = 2 * math.pi * result["f_tank_hz"]
    tank = parts.tank("CT2")

    # The calculated tank: Cp2 + Cs12 + Cs23 against L, resonant at the tank frequency.
    target = omega * (result["c_tank"][1] + sum(result["c_coupling"])) - 1 / (
        omega * result["L_resonant"]
    )
    low_l, high_l = _chip_corners(parts.inductor("LT2").build_pick, omega)
    low_c = high_c = 0.0
    for name in ("CK1", "CK2"):
        match = parts.capacitor(name)
        [value], [tolerance] = match.selected_components, match.part_tolerances_f
        low_c += omega * (value - tolerance)
        high_c += omega * (value + tolerance)

    assert tank.target_susceptance_s == pytest.approx(target, abs=1e-12)
    assert abs(target / omega) < 1e-15
    assert tank.need.low_f == pytest.approx((target - high_l - high_c) / omega, rel=1e-12)
    assert tank.need.high_f == pytest.approx((target - low_l - low_c) / omega, rel=1e-12)
    assert not tank.need.conditional


def test_an_end_tank_s_need_takes_its_coupler_through_the_port():
    outcome = design(_two_metre(resonator_inductance=21e-9))
    result, parts = outcome.result, outcome.parts
    omega = 2 * math.pi * result["f_tank_hz"]

    def shunt(capacitance):
        return omega * capacitance / (1 + (omega * 50.0 * capacitance) ** 2)

    low_l, high_l = _chip_corners(parts.inductor("LT1").build_pick, omega)
    ck = parts.capacitor("CK1")
    cin = parts.capacitor("CIN")
    ends_ck = [
        omega * (v + sign * t)
        for v, t in zip(ck.selected_components, ck.part_tolerances_f)
        for sign in (-1, 1)
    ]
    ends_cin = [
        shunt(v + sign * t)
        for v, t in zip(cin.selected_components, cin.part_tolerances_f)
        for sign in (-1, 1)
    ]
    target = parts.tank("CT1").target_susceptance_s
    need = parts.tank("CT1").need

    assert need.low_f == pytest.approx(
        (target - high_l - max(ends_ck) - max(ends_cin)) / omega, rel=1e-12
    )
    assert need.high_f == pytest.approx(
        (target - low_l - min(ends_ck) - min(ends_cin)) / omega, rel=1e-12
    )


def test_the_build_s_own_settings_do_not_change_the_sizing():
    # Every output of a design shows the same split, so the build's inductor tolerance,
    # ports, part Q and inductor choice change only the settings it simulates.
    baseline = design(_two_metre(resonator_inductance=21e-9)).parts.tanks
    for config, build_inductors in (
        (BuildConfig(inductor_tolerance_pct=10.0), "auto"),
        (BuildConfig(source_resistance_ohm=75.0, load_resistance_ohm=30.0), "auto"),
        (BuildConfig(inductor_q=5.0, capacitor_q=20.0), "auto"),
        (BuildConfig(), "calculated"),
    ):
        request = _two_metre(
            resonator_inductance=21e-9, realization=config, build_inductors=build_inductors
        )
        assert design(request).parts.tanks == baseline


def test_the_design_s_resonator_q_changes_the_need():
    # The resonator inductor Q is a design input (--ql), so the sizing includes its loss.
    lossless = design(_two_metre(resonator_inductance=21e-9)).parts.tank("CT2").need
    outcome = design(_two_metre(resonator_inductance=21e-9, ql=5.0))
    lossy = outcome.parts.tank("CT2").need
    omega = 2 * math.pi * outcome.result["f_tank_hz"]
    pick = outcome.parts.inductor("LT2").build_pick
    # A lossy inductor's susceptance is lower: each corner's resistance follows its own
    # value from Q at the loss reference frequency (the center), so the tank needs less.
    low_q, high_q = _chip_corners(pick, omega, 5.0, 146e6)
    low_l, high_l = _chip_corners(pick, omega)

    assert lossy.low_f == pytest.approx(lossless.low_f - (high_q - high_l) / omega, rel=1e-12)
    assert lossy.high_f == pytest.approx(lossless.high_f - (low_q - low_l) / omega, rel=1e-12)
    assert lossy.high_f < lossless.high_f


# -- Sourced and conditional needs ---------------------------------------------------------


def test_the_original_2m_band_pass_gets_a_conditional_need_not_a_guaranteed_split():
    tanks = design(_two_metre()).parts.tanks
    unsourced = no_part_assumption(5)

    assert tanks["CT1"].need.assumptions == (("Cs12", unsourced),)
    assert tanks["CT2"].need.assumptions == (("Cs12", unsourced), ("Cs23", unsourced))
    assert tanks["CT3"].need.assumptions == (("Cs23", unsourced),)
    assert all(tank.split is not None for tank in tanks.values())


def test_the_json_names_a_conditional_need_and_every_fit_as_conditional(monkeypatch, capsys):
    data = json.loads(
        cli_stdout(
            monkeypatch,
            capsys,
            *("bp", "ch", "top", "-f", "146MHz", "-b", "4MHz", "-n", "3", "-r", "0.5"),
            "--format",
            "json",
        )
    )
    trimmers = data["tank_trimmers"]

    assert trimmers["tuning_frequency_hz"] == pytest.approx(TANK_FREQUENCY_2M)
    assert trimmers["assumed_series_inductance_h"] == ASSUMED_TRIMMER_SERIES_INDUCTANCE_H
    first = trimmers["tanks"][0]
    assert first["name"] == "Cp1" and first["need_basis"] == "conditional"
    assert first["assumptions"] == [{"part": "Cs12", "assumption": no_part_assumption(5)}]
    assert {split["fit"] for tank in trimmers["tanks"] for split in tank["splits"]} == {
        "conditional_on_series_inductance"
    }


def test_after_the_advice_every_need_is_sourced(monkeypatch, capsys):
    tanks = design(_two_metre(resonator_inductance=21e-9)).parts.tanks

    assert not any(tank.need.conditional for tank in tanks.values())


def test_a_toroid_winding_s_tolerance_makes_the_need_conditional():
    request = DesignRequest("bandpass", "bessel", "top", 21.2e6, 50.0, 3, bandwidth_hz=500e3)
    tank = design(request).parts.tank("CT1")

    assert tank.need.assumptions == (("L1", toroid_assumption(10)),)


# -- Fit and ranking ----------------------------------------------------------------------


def test_splits_rank_by_range_then_centring_then_fewer_parts():
    tank = design(_two_metre(resonator_inductance=21e-9)).parts.tank("CT2")
    splits = tank.splits

    assert 1 <= len(splits) <= tank_trimmers.MAX_TANK_SPLITS
    assert len({split.trimmer.part_name for split in splits}) == len(splits)
    keys = [
        (
            split.trimmer_range_f[1] - split.trimmer_range_f[0],
            split.centring_f,
            len(split.fixed_parts_f),
            split.trimmer.part_name,
        )
        for split in splits
    ]
    assert keys == sorted(keys)
    for split in splits:
        low, high = split.trimmer_range_f
        assert low <= split.required_f[0] <= split.required_f[1] <= high
        # What the trimmer must supply is the need less the fixed part at either end.
        fixed_low = sum(v - t for v, t in zip(split.fixed_parts_f, split.fixed_tolerances_f))
        fixed_high = sum(v + t for v, t in zip(split.fixed_parts_f, split.fixed_tolerances_f))
        assert split.required_f[0] == pytest.approx(tank.need.low_f - fixed_high - split.stray_f)
        assert split.required_f[1] == pytest.approx(tank.need.high_f - fixed_low)
        assert split.stray_f == pytest.approx(0.2e-12 * len(split.fixed_parts_f))


def test_a_tank_no_trimmer_can_cover_names_what_it_needs(monkeypatch, capsys):
    # A 3.6 MHz toroid tank at ±10% needs about 190 pF, more than any packaged trimmer spans
    # once the fixed part's own tolerance is added.
    argv = ("bp", "bw", "top", "-f", "3.6MHz", "-b", "100kHz", "-n", "3")
    table = cli_stdout(monkeypatch, capsys, *argv)
    data = json.loads(cli_stdout(monkeypatch, capsys, *argv, "--format", "json"))

    for tank in data["tank_trimmers"]["tanks"]:
        assert tank["fits"] is False and tank["splits"] == []
        low, high = (value * 1e12 for value in tank["need_f"])
        line = f"{tank['name']}: no packaged trimmer fits. The fixed part and trimmer"
        assert line in table
        assert f"{low:.2f}–{high:.2f} pF" in " ".join(table.split())


def test_the_csv_lists_each_tank_s_split(monkeypatch, capsys):
    argv = ("bp", "ch", "top", "-f", "146MHz", "-b", "4MHz", "-n", "3", "-r", "0.5")
    text = cli_stdout(monkeypatch, capsys, *argv, "--format", "csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    cp1, l1 = rows[0], rows[3]

    assert cp1["Component"] == "Cp1"
    assert cp1["TrimmerPart"] == "BFC280820508"
    assert cp1["TankFixedParts"] == "15.00 pF"
    assert cp1["TankNeedBasis"] == "conditional"
    assert float(cp1["TrimmerRequiredMinPF"]) <= float(cp1["TrimmerRequiredMaxPF"])
    assert l1["Component"] == "L1" and l1["TrimmerPart"] == ""


def test_no_standard_values_means_no_tank_sizing(monkeypatch, capsys):
    argv = ("bp", "ch", "top", "-f", "146MHz", "-b", "4MHz", "-n", "3", "-r", "0.5", "--no-match")
    data = json.loads(cli_stdout(monkeypatch, capsys, *argv, "--format", "json"))

    assert data["tank_trimmers"] is None
    assert "Tank Trimmers" not in cli_stdout(monkeypatch, capsys, *argv)


def test_the_intro_names_unequal_ports_and_a_trimmer_alone_has_no_fixed_part():
    from filter_lib.bandpass.trimmer_display import _fixed_text, _ports_text

    assert _ports_text(50.0, 50.0) == "the 50 Ω source and load"
    assert _ports_text(50.0, 100.0) == "the 50 Ω source and the 100 Ω load"
    split = design(_two_metre(resonator_inductance=21e-9)).parts.tank("CT2").split
    assert _fixed_text(split) == "47.00 pF +"
    alone = dataclasses.replace(split, fixed_parts_f=(), fixed_tolerances_f=())
    assert _fixed_text(alone) == "no fixed part,"


@pytest.mark.parametrize(
    ("part_number", "frequency_hz", "q"),
    [
        ("BFC280800018", 439.906e6, None),
        ("BFC280800018", 439.906e6, 50.0),
        ("BFC280831229", 439.906e6, None),  # the knob reaches the series resonance
        ("BFC280820109", 146e6, 20.0),
        ("AT 0310 R2", 440e6, 5.0),
    ],
)
def test_every_value_in_the_range_is_reachable_for_any_inductance_up_to_the_bound(
    part_number, frequency_hz, q
):
    trimmer = _trimmer(part_number)
    bound, _assumed = series_inductance(trimmer)
    omega = 2 * math.pi * frequency_hz
    span = trimmer_range_f(trimmer, bound, frequency_hz, q, frequency_hz)
    assert span is not None
    low, high = span
    settings = [
        trimmer.cmin_max_f * (trimmer.cmax_min_f / trimmer.cmin_max_f) ** (i / 400)
        for i in range(401)
    ]
    for step in range(11):
        inductance = bound * step / 10
        # The knob's rising part at this inductance: below the resonance or loss peak.
        top = tank_trimmers.capacitive_branch_top(inductance, omega, q, frequency_hz)
        values = [
            tank_trimmers.trimmer_admittance(c, inductance, omega, q, frequency_hz).imag / omega
            for c in settings
            if c < top
        ]
        reaches_pole = q is None and trimmer.cmax_min_f >= top
        assert min(values) <= low * (1 + 1e-12)
        assert reaches_pole or max(values) >= high * (1 - 1e-9)


def test_a_trimmer_whose_loss_peak_is_below_the_need_does_not_fit():
    # At capacitor Q 0.5 and 440 MHz, BFC280800018 with up to 17.59 nH peaks at about
    # 0.4393 pF (knob 3.928 pF), far below the range its stops would suggest.
    trimmer = _trimmer("BFC280800018")
    bound, _assumed = series_inductance(trimmer)
    omega = 2 * math.pi * 439.906e6
    # Q applies at the 440 MHz center, as in the build.
    top = tank_trimmers.capacitive_branch_top(bound, omega, 0.5, 440e6)
    peak = tank_trimmers.trimmer_admittance(top, bound, omega, 0.5, 440e6).imag / omega

    assert top * 1e12 == pytest.approx(3.928, abs=1e-3)
    assert peak * 1e12 == pytest.approx(0.43934, abs=1e-5)
    span = trimmer_range_f(trimmer, bound, 439.906e6, 0.5, 440e6)
    assert span is None or span[1] <= peak * (1 + 1e-12)
    # A design whose resonator capacitors have that Q (--qc 0.5) offers no split.
    request = DesignRequest(
        "bandpass", "chebyshev", "top", 440e6, 50.0, 3, ripple_db=0.5, bandwidth_hz=13.2e6, qc=0.5
    )
    assert all(tank.split is None for tank in design(request).parts.tanks.values())


def test_a_build_q_the_sizing_did_not_see_flags_the_cases_the_trimmer_cannot_reach():
    # The lossless design fits trimmers; a build that adds capacitor Q 0.5 leaves them
    # little rising range, so its cases are flagged rather than claimed tuned.
    request = DesignRequest(
        "bandpass",
        "chebyshev",
        "top",
        440e6,
        50.0,
        3,
        ripple_db=0.5,
        bandwidth_hz=13.2e6,
        realization=BuildConfig(grid_points=51, capacitor_q=0.5),
        run_build_analysis=True,
    )
    outcome = design(request)

    assert all(tank.split is not None for tank in outcome.parts.tanks.values())
    analysis = outcome.build_analysis
    assert analysis.has_trimmers
    assert analysis.out_of_range_cases() == len(analysis.cases)


def test_tank_sizing_stops_when_cancelled(monkeypatch):
    from filter_lib.design import DesignCancelled

    tried: list[str] = []
    real = tank_trimmers._best_split_for

    def counting(trimmer, *args, **kwargs):
        tried.append(trimmer.part_name)
        return real(trimmer, *args, **kwargs)

    monkeypatch.setattr(tank_trimmers, "_best_split_for", counting)
    request = DesignRequest("bandpass", "butterworth", "top", 10e6, 50.0, 9, bandwidth_hz=650e3)

    with pytest.raises(DesignCancelled):
        design(request, should_cancel=lambda: len(tried) >= 5)

    # The check fires before the sixth trimmer is tried.
    assert len(tried) == 5


def test_the_standard_values_say_to_use_the_split_and_keep_the_plain_choice(monkeypatch, capsys):
    argv = ("bp", "ch", "top", "-f", "146MHz", "-b", "4MHz", "-n", "3", "-r", "0.5")
    table = cli_stdout(monkeypatch, capsys, *argv, "--tank-inductance", "21nH")

    assert (
        "Cp1 calculated 51.43 pF\n"
        "  Use:            22.00 pF || 24.00 pF + trimmer QM10 (see Tank Trimmers)\n"
        "  No trimmer:     51.00 pF (-0.8%)\n"
    ) in table
    # A coupling capacitor keeps its own standard value.
    assert "Cs12 calculated 1.00 pF\n  Use:            1.00 pF" in table
