"""Generic SPICE export from the same named circuits used by simulation."""

import re

import pytest

from filter_lib.shared.build_simulation import BuildConfig
from filter_lib.shared.netlist_builders import build_named_circuit
from filter_lib.shared.spice_export import export_spice_deck


def _lp_result() -> dict:
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": [1e-9, 2e-9],
        "inductors": [3e-6],
        "order": 3,
        "topology": "pi",
    }


def _hp_result() -> dict:
    return {
        "filter_type": "butterworth",
        "freq_hz": 10e6,
        "impedance": 50.0,
        "capacitors": [1e-9, 2e-9],
        "inductors": [3e-6],
        "order": 3,
        "topology": "t",
    }


def _bp_result() -> dict:
    return {
        "filter_type": "butterworth",
        "f0": 10e6,
        "bw": 1e6,
        "f_low": 9.5e6,
        "f_high": 10.5e6,
        "z0": 50.0,
        "n_resonators": 2,
        "L_resonant": 1e-6,
        "c_tank": [10e-12, 11e-12],
        "c_coupling": [2e-12],
        "c_end_in": 3e-12,
        "c_end_out": 4e-12,
        "q_model": {
            "resonator_qu": None,
            "inductor_ql": None,
            "capacitor_qc": None,
        },
    }


class TestExactSpiceDecks:
    def test_lowpass_golden_deck(self):
        deck = export_spice_deck(
            _lp_result(),
            "lowpass",
            realization="exact",
            config=BuildConfig(
                source_resistance_ohm=50,
                load_resistance_ohm=75,
                use_toroid_candidates=False,
            ),
        )
        assert (
            deck
            == """* RF Filter Calculator generic AC deck
* category: lowpass
* realization: calculated_exact
* printed trace: vm(2) is load-node voltage, not gain in dB
* transducer gain: Gt=4*Rs/Rl*|V(2)/V(NSOURCE)|^2
* limitations: ideal values omit layout, parasitics, SRF, temperature, and power behavior
* ports: input=1 output=2 ground=0 source=NSOURCE
VINPUT NSOURCE 0 AC 1
RSOURCE NSOURCE 1 50
C1 1 0 1e-09
L1 1 2 3e-06
C2 2 0 2e-09
RLOAD 2 0 75
.ac dec 200 1000000 100000000
.print ac vm(2)
.end
"""
        )

    @pytest.mark.parametrize(
        "category, result, expected_lines",
        [
            ("lowpass", _lp_result(), ["C1 1 0", "L1 1 2", "C2 2 0"]),
            ("highpass", _hp_result(), ["C1 1 2", "L1 2 0", "C2 2 3"]),
            (
                "bandpass",
                _bp_result(),
                [
                    "CT1 1 0",
                    "LT1 1 0",
                    "CT2 2 0",
                    "LT2 2 0",
                    "CK1 1 2",
                    "CIN 3 1",
                    "COUT 2 4",
                ],
            ),
        ],
    )
    def test_supported_topologies_have_golden_named_elements(
        self, category, result, expected_lines
    ):
        deck = export_spice_deck(result, category, realization="exact")
        for line in expected_lines:
            assert re.search(rf"(?m)^{re.escape(line)}\s", deck)

        circuit = build_named_circuit(result, category)
        for element in circuit.elements:
            assert re.search(rf"(?m)^{re.escape(element.name)}\s", deck)


class TestNominalSpiceDecks:
    def test_parallel_physical_caps_and_loss_resistors_are_exported_separately(self):
        result = {
            "filter_type": "butterworth",
            "freq_hz": 10e6,
            "impedance": 50.0,
            "capacitors": [318.31e-12],
            "inductors": [],
            "order": 1,
            "topology": "pi",
        }
        deck = export_spice_deck(
            result,
            "lowpass",
            realization="nominal_build",
            config=BuildConfig(
                capacitor_q=200,
                use_toroid_candidates=False,
            ),
        )

        assert re.search(r"(?m)^C1A\s", deck)
        assert re.search(r"(?m)^C1B\s", deck)
        assert re.search(r"(?m)^RLOSSC1A\s", deck)
        assert re.search(r"(?m)^RLOSSC1B\s", deck)
        assert "e_series_parallel" in deck
        assert "47e-12" not in deck  # values are canonical generic SPICE numbers
        assert "4.7e-11" in deck
        assert "2.7e-10" in deck

    def test_missing_toroid_candidate_fallback_is_visible_in_comments(self):
        result = {
            "filter_type": "butterworth",
            "freq_hz": 1e12,
            "impedance": 50.0,
            "capacitors": [],
            "inductors": [1e-6],
            "order": 1,
            "topology": "t",
        }
        deck = export_spice_deck(result, "lowpass", realization="nominal_build")
        assert "exact_fallback" in deck
        assert "No verified integer-turn toroid candidate" in deck

    def test_nominal_deck_is_deterministic(self):
        config = BuildConfig(inductor_q=100, capacitor_q=200)
        first = export_spice_deck(
            _lp_result(), "lowpass", realization="nominal_build", config=config
        )
        second = export_spice_deck(
            _lp_result(), "lowpass", realization="nominal_build", config=config
        )
        assert first == second


class TestSpiceValidation:
    @pytest.mark.parametrize(
        "category, result",
        [("lowpass", _lp_result()), ("highpass", _hp_result()), ("bandpass", _bp_result())],
    )
    @pytest.mark.parametrize("realization", ["exact", "nominal_build"])
    def test_decks_are_finite_and_have_generic_ac_control(self, category, result, realization):
        deck = export_spice_deck(
            result,
            category,
            realization=realization,
            config=BuildConfig(use_toroid_candidates=False),
        )
        assert re.search(r"(?im)^\.ac\s+dec\s+\d+\s+[0-9.e+-]+\s+[0-9.e+-]+$", deck)
        assert re.search(r"(?im)^\.end\s*$", deck)
        assert not re.search(r"(?i)(?<![a-z])(?:nan|[+-]?inf(?:inity)?)(?![a-z])", deck)
        assert "VINPUT" in deck and "RSOURCE" in deck and "RLOAD" in deck

    def test_invalid_realization_rejected(self):
        with pytest.raises(ValueError, match="realization"):
            export_spice_deck(_lp_result(), "lowpass", realization="measured")

    @pytest.mark.parametrize("config", [False, 0, {}, [], "config"])
    def test_wrong_config_type_is_rejected(self, config):
        with pytest.raises(ValueError, match="config must be a BuildConfig or None"):
            export_spice_deck(_lp_result(), "lowpass", config=config)

    def test_nonfinite_frequency_span_rejected(self):
        result = _lp_result()
        result["freq_hz"] = 1e308
        with pytest.raises(ValueError, match="finite"):
            export_spice_deck(result, "lowpass")
