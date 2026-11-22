"""Tank-inductance advice for band-pass designs whose coupling capacitors are too small.

The 2 m acceptance design (``bp ch top -f 146MHz -b 4MHz -n 3 -r 0.5``) needs Cs12 = Cs23 =
0.38634 pF with its 54.51 nH tanks. Its advice must name a tank inductance a built-in
inductor suggestion supplies, and rerunning with the printed value must give every
coupling capacitor a part of 1 pF or more (21 nH gives 1.00241 pF; the inverse-L estimate
of 21.06 nH gives only 0.99955 pF).
"""

from __future__ import annotations

import dataclasses
import json
import re

import pytest

from filter_lib.design import DesignCancelled, DesignRequest, design
from filter_lib.design import coupling_advice as advice_module
from filter_lib.design.coupling_advice import (
    MAX_COUPLING_ADVICE_TRIALS,
    advise_coupling,
    inductance_setting,
    no_candidate_reason,
    no_value_works_reason,
)
from filter_lib.design.design_service import synthesize
from filter_lib.design.part_resolution import resolve_parts
from filter_lib.shared.parsing import parse_inductance
from tests.cli_parity_helpers import cli_stdout

TWO_METRE = ("bp", "ch", "top", "-f", "146MHz", "-b", "4MHz", "-n", "3", "-r", "0.5")


def _two_metre(**overrides) -> DesignRequest:
    return DesignRequest(
        "bandpass", "chebyshev", "top", 146e6, 50.0, 3, ripple_db=0.5, bandwidth_hz=4e6, **overrides
    )


def test_the_2m_band_pass_is_advised_21_nh_from_a_chip_inductor():
    outcome = design(_two_metre())
    advice = outcome.coupling_advice

    assert advice.short_couplers == ("CK1", "CK2")
    # 54.5148 nH x 0.38634 pF / 1 pF.
    assert advice.estimate_h == pytest.approx(21.061e-9, rel=1e-4)
    assert advice.setting == "21nH" and advice.inductance_h == 21e-9
    assert (advice.part.kind, advice.part.part_name) == ("chip", "LQW15AN21NG80D")
    # The walk starts at the largest value below the estimate and tries the next one up.
    assert [(trial.setting, trial.works) for trial in advice.trials] == [
        ("21nH", True),
        ("22nH", False),
    ]
    assert {name: match.selected_components for name, match in advice.couplers.items()} == {
        "CIN": (4.3e-12,),
        "CK1": (1e-12,),
        "CK2": (1e-12,),
        "COUT": (4.3e-12,),
    }
    assert advice.response_validation_status == "validated"


def test_rerunning_with_the_printed_value_gives_every_coupler_a_part(monkeypatch, capsys):
    text = cli_stdout(monkeypatch, capsys, *TWO_METRE)
    setting = re.search(r"\(--tank-inductance (\S+)\)", text)[1]

    rerun = json.loads(
        cli_stdout(
            monkeypatch, capsys, *TWO_METRE, "--tank-inductance", setting, "--format", "json"
        )
    )

    assert setting == "21nH"
    components = rerun["components"]
    couplers = components["coupling_capacitors"] + components["end_coupling_capacitors"]
    for coupler in couplers:
        parts = coupler["standard_match"]["selected"]["components"]
        assert min(part["value_farads"] for part in parts) >= 1e-12, coupler["name"]
    assert components["coupling_capacitors"][0]["value_farads"] == pytest.approx(
        1.00241e-12, abs=5e-18
    )
    assert rerun["coupling_advice"] is None


def test_the_inverse_l_estimate_itself_misses_the_floor():
    outcome = design(_two_metre(resonator_inductance=21.06e-9))

    assert outcome.result["c_coupling"][0] == pytest.approx(0.99955e-12, abs=5e-18)
    assert outcome.parts.capacitor("CK1").selected_components is None
    # So that design is advised a value a part supplies.
    assert outcome.coupling_advice.setting == "21nH"


def test_the_setting_reads_back_as_the_value_tried():
    for value in (21e-9, 1.2544e-6, 4.9e-9 * 256):
        assert parse_inductance(inductance_setting(value)) == pytest.approx(value, rel=1e-12)
    assert inductance_setting(21e-9) == "21nH"
    assert inductance_setting(1.2544e-6) == "1.2544uH"
    assert inductance_setting(21e-9, " ") == "21 nH"


@pytest.mark.parametrize(
    "request_",
    [
        _two_metre(resonator_inductance=21e-9),
        DesignRequest("bandpass", "butterworth", "top", 14.2e6, 50.0, 3, bandwidth_hz=350e3),
        DesignRequest("lowpass", "chebyshev", "pi", 146e6, 50.0, 5, ripple_db=0.1),
        _two_metre(eseries=None),
    ],
    ids=["every-coupler-has-a-part", "hf-band-pass", "low-pass", "no-standard-values"],
)
def test_no_advice_when_it_does_not_apply(request_):
    assert design(request_).coupling_advice is None


def test_a_design_without_advice_says_nothing_about_it(monkeypatch, capsys):
    table = cli_stdout(monkeypatch, capsys, *TWO_METRE, "--tank-inductance", "21nH")
    data = json.loads(
        cli_stdout(monkeypatch, capsys, *TWO_METRE, "--tank-inductance", "21nH", "--format", "json")
    )

    assert "Coupling Advice" not in table
    assert data["coupling_advice"] is None


def test_the_table_and_json_give_the_same_advice(monkeypatch, capsys):
    table = cli_stdout(monkeypatch, capsys, *TWO_METRE)
    data = json.loads(cli_stdout(monkeypatch, capsys, *TWO_METRE, "--format", "json"))
    advice = data["coupling_advice"]

    assert "\nCoupling Advice\n" in table
    flat = " ".join(table.split())
    assert 'Rerun with "Resonator inductance" set to 21 nH (--tank-inductance 21nH).' in flat
    assert "chip inductor LQW15AN21NG80D supplies the inductance" in flat
    assert advice["short_coupling_capacitors"] == ["Cs12", "Cs23"]
    assert advice["advised"]["setting"] == "21nH"
    assert advice["advised"]["cli"] == "--tank-inductance 21nH"
    assert advice["advised"]["inductor_part"] == "LQW15AN21NG80D"
    assert advice["max_trials"] == MAX_COUPLING_ADVICE_TRIALS
    assert [trial["setting"] for trial in advice["trials"]] == ["21nH", "22nH"]


def test_a_tank_impedance_is_cleared_by_the_advice():
    request = _two_metre(resonator_impedance=50.0)
    outcome = design(request)

    assert outcome.coupling_advice.clears_impedance
    text = " ".join(advice_module.advice_lines_text(outcome.coupling_advice))
    assert 'and clear "Resonator impedance"' in text


def _parts(request: DesignRequest):
    result = synthesize(request)
    return result, resolve_parts(request, result)


def test_with_no_candidate_value_the_advice_says_so(monkeypatch):
    request = _two_metre()
    result, parts = _parts(request)
    monkeypatch.setattr(advice_module, "_candidates", lambda *_args: [])

    advice = advise_coupling(request, result, parts)

    assert not advice.advised and advice.trials == ()
    assert advice.reason_none == no_candidate_reason(result["L_resonant"])


def test_when_no_value_works_within_the_budget_the_advice_says_so(monkeypatch):
    request = _two_metre()
    result, parts = _parts(request)
    # Only values whose couplers stay below 1 pF.
    monkeypatch.setattr(advice_module, "_candidates", lambda *_args: [22e-9, 30e-9])

    advice = advise_coupling(request, result, parts)

    assert not advice.advised
    assert [trial.setting for trial in advice.trials] == ["22nH"]
    assert advice.reason_none == no_value_works_reason(advice.trials)
    assert advice.reason_none.startswith("None of the 1 tank inductances tried (22.00 nH)")


def test_the_search_stops_at_its_trial_budget(monkeypatch):
    request = _two_metre()
    result, parts = _parts(request)
    monkeypatch.setattr(advice_module, "MAX_COUPLING_ADVICE_TRIALS", 1)
    # The first value tried is too large; the budget leaves no room for a smaller one.
    monkeypatch.setattr(advice_module, "_candidates", lambda *_args: [21e-9, 22e-9])
    monkeypatch.setattr(advice_module, "_estimate", lambda *_args: 22e-9)

    advice = advise_coupling(request, result, parts)

    assert [trial.setting for trial in advice.trials] == ["22nH"]
    assert not advice.advised


def test_a_cancel_between_trials_stops_the_advice(monkeypatch):
    request = _two_metre()
    result, parts = _parts(request)
    from filter_lib.design import design_service, part_resolution

    synthesized: list[float] = []
    real_synthesize = design_service.synthesize
    real_resolve = part_resolution.resolve_parts
    cancelled = False

    def counting_synthesize(trial_request, should_cancel=None):
        synthesized.append(trial_request.resonator_inductance)
        return real_synthesize(trial_request, should_cancel)

    def resolve_then_cancel(*args, **kwargs):
        nonlocal cancelled
        parts = real_resolve(*args, **kwargs)
        cancelled = True  # The first trial is complete.
        return parts

    monkeypatch.setattr(design_service, "synthesize", counting_synthesize)
    monkeypatch.setattr(part_resolution, "resolve_parts", resolve_then_cancel)

    with pytest.raises(DesignCancelled):
        advise_coupling(request, result, parts, should_cancel=lambda: cancelled)

    assert synthesized == [21e-9]


def test_a_run_with_suggestions_off_is_advised_a_supplied_value_without_naming_it(
    monkeypatch, capsys
):
    # The coupling capacitors do not depend on how many suggestions a run shows; the
    # advice still checks that a part supplies the value, but does not name it.
    advice = design(_two_metre(inductor_suggestions="none")).coupling_advice
    argv = (*TWO_METRE, "--inductor-suggestions", "none")
    table = " ".join(cli_stdout(monkeypatch, capsys, *argv).split())
    data = json.loads(cli_stdout(monkeypatch, capsys, *argv, "--format", "json"))

    assert advice.setting == "21nH" and not advice.names_part
    assert "a built-in inductor suggestion supplies the inductance" in table
    assert "LQW15AN21NG80D" not in table
    advised = data["coupling_advice"]["advised"]
    assert advised["setting"] == "21nH"
    assert advised["inductor_part"] is None and advised["inductor_kind"] is None


def test_toroid_candidates_reach_each_core_s_winding_capacity():
    # 400 µH tanks at 2 MHz need values above 200 turns of T68-2 (228 µH); its winding
    # table holds 950 turns, and the advice reaches 312.1092 µH.
    request = DesignRequest(
        "bandpass",
        "butterworth",
        "top",
        2e6,
        500.0,
        3,
        bandwidth_hz=140e3,
        resonator_inductance=400e-6,
    )
    advice = design(request).coupling_advice

    assert advice.setting == "312.1092uH" and advice.part.part_name == "T68-2"
    rerun = design(
        dataclasses.replace(request, resonator_inductance=parse_inductance(advice.setting))
    )
    assert rerun.coupling_advice is None


def test_an_hf_tank_is_advised_a_toroid_winding_and_told_to_clear_its_impedance(
    monkeypatch, capsys
):
    # A 1 kOhm tank at 7.1 MHz with a 10 kHz band needs 0.03 pF couplers; a 10-turn T50-2
    # winding (4.9 nH per turn squared) supplies 490 nH.
    argv = ("bp", "bw", "top", "-f", "7.1MHz", "-b", "10kHz", "-n", "3")
    text = " ".join(cli_stdout(monkeypatch, capsys, *argv, "--tank-impedance", "1000").split())
    setting = re.search(r"\(--tank-inductance (\S+)\)", text)[1]

    assert setting == "490nH"
    assert 'set to 490 nH and clear "Resonator impedance"' in text
    assert "toroid winding T50-2 supplies the inductance" in text
    rerun = json.loads(
        cli_stdout(monkeypatch, capsys, *argv, "--tank-inductance", setting, "--format", "json")
    )
    assert rerun["coupling_advice"] is None
    for coupler in rerun["components"]["coupling_capacitors"]:
        parts = coupler["standard_match"]["selected"]["components"]
        assert min(part["value_farads"] for part in parts) >= 1e-12
