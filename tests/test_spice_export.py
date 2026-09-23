"""Generic SPICE export from the same named circuits used by simulation."""

import math
import re

import pytest

from filter_lib.shared.build_simulation import BuildConfig, realize_nominal_build
from filter_lib.shared.netlist_builders import build_named_circuit
from filter_lib.shared.spice_export import export_spice_deck


def _netlist(deck: str) -> dict[str, tuple[str, str, float]]:
    """Parse two-terminal deck branches as ``name -> (node1, node2, value)``."""
    branches = {}
    for line in deck.splitlines():
        if line.startswith(("*", ".", "VINPUT ")):
            continue
        name, node1, node2, value = line.split()
        branches[name] = (node1, node2, float(value))
    return branches


def _expected_netlist(circuit, source: float, load: float) -> dict[str, tuple[str, str, float]]:
    """Deck branches implied by a named circuit: series loss sits behind each lossy part."""
    expected = {
        "RSOURCE": ("NSOURCE", str(circuit.in_node), source),
        "RLOAD": (str(circuit.out_node), "0", load),
    }
    for element in circuit.elements:
        if element.series_resistance_ohm:
            internal = f"NLOSS{element.name}"
            expected[element.name] = (str(element.node1), internal, element.value)
            expected[f"RLOSS{element.name}"] = (
                internal,
                str(element.node2),
                element.series_resistance_ohm,
            )
        else:
            expected[element.name] = (str(element.node1), str(element.node2), element.value)
    return expected


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


class TestDeckMatchesNamedCircuit:
    @pytest.mark.parametrize(
        "category, result",
        [("lowpass", _lp_result()), ("highpass", _hp_result()), ("bandpass", _bp_result())],
        ids=["lowpass", "highpass", "bandpass"],
    )
    @pytest.mark.parametrize("realization", ["exact", "nominal_build"])
    def test_deck_branches_nodes_values_and_controls_match_the_simulated_circuit(
        self, category, result, realization
    ):
        config = BuildConfig(
            inductor_q=100,
            capacitor_q=400,
            source_resistance_ohm=25,
            load_resistance_ohm=100,
            use_toroid_candidates=False,
        )
        deck = export_spice_deck(result, category, realization=realization, config=config)
        circuit = (
            build_named_circuit(result, category)
            if realization == "exact"
            else realize_nominal_build(result, category, config).circuit
        )

        netlist = _netlist(deck)
        expected = _expected_netlist(circuit, 25.0, 100.0)
        assert netlist.keys() == expected.keys()
        for name, (node1, node2, value) in expected.items():
            assert netlist[name][:2] == (node1, node2), name
            # abs=0 keeps the 12-significant-digit check meaningful for pF/nH values.
            assert netlist[name][2] == pytest.approx(value, rel=1e-11, abs=0), name
        has_loss = any(name.startswith("RLOSS") for name in netlist)
        assert has_loss is (realization == "nominal_build")

        lines = deck.splitlines()
        assert "VINPUT NSOURCE 0 AC 1" in lines
        sweep_kind = "lin" if category == "bandpass" else "dec"
        assert re.fullmatch(rf"\.ac {sweep_kind} \d+ [0-9.e+-]+ [0-9.e+-]+", lines[-3])
        assert lines[-2:] == [f".print ac vm({circuit.out_node})", ".end"]
        assert not re.search(r"(?i)(?<![a-z])(?:nan|[+-]?inf(?:inity)?)(?![a-z])", deck)


def _bp_resonators(n: int, bw: float = 1e6) -> dict:
    """Synthetic Top-C chain; exact export only needs well-formed positive values."""
    return {
        **_bp_result(),
        "bw": bw,
        "n_resonators": n,
        "c_tank": [10e-12] * n,
        "c_coupling": [2e-12] * (n - 1),
    }


class TestBandpassSweep:
    @pytest.mark.parametrize("n, bw", [(2, 1e6), (3, 10e3), (9, 200e3), (5, 9e6)])
    def test_linear_sweep_resolves_128_intervals_per_resonator_bandwidth(self, n, bw):
        deck = export_spice_deck(_bp_resonators(n, bw), "bandpass")
        _, kind, points, start, stop = next(
            line for line in deck.splitlines() if line.startswith(".ac ")
        ).split()

        assert kind == "lin"
        step = (float(stop) - float(start)) / (int(points) - 1)
        assert step <= bw / (128 * n)
        assert float(start) < 10e6 - bw / 2 and float(stop) > 10e6 + bw / 2

    def test_sweep_beyond_the_resolution_budget_is_refused(self):
        """600 resonators over a 5-20 MHz window need 1,152,001 points (limit 1,000,000)."""
        with pytest.raises(ValueError, match="exceeds the supported resolution budget"):
            export_spice_deck(_bp_resonators(600), "bandpass")


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

        netlist = _netlist(deck)
        # 318.31 pF is realized as 47 pF || 270 pF, each with its own Q=200 series loss
        # R = 1 / (2*pi*f*C*Q) at the 10 MHz design frequency.
        for name, capacitance in (("C1A", 47e-12), ("C1B", 270e-12)):
            assert netlist[name] == (
                "1",
                f"NLOSS{name}",
                pytest.approx(capacitance, rel=1e-12, abs=0),
            )
            assert netlist[f"RLOSS{name}"] == (
                f"NLOSS{name}",
                "0",
                pytest.approx(1 / (2 * math.pi * 10e6 * capacitance * 200), rel=1e-11, abs=0),
            )
        assert "e_series_parallel" in deck
        assert "47e-12" not in deck  # values are canonical generic SPICE numbers
        assert "C1A 1 NLOSSC1A 4.7e-11" in deck
        assert "C1B 1 NLOSSC1B 2.7e-10" in deck

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
    def test_invalid_realization_rejected(self):
        with pytest.raises(ValueError, match="realization"):
            export_spice_deck(_lp_result(), "lowpass", realization="measured")

    @pytest.mark.parametrize("config", [False, 0, {}, [], "config"])
    def test_wrong_config_type_is_rejected(self, config):
        with pytest.raises(ValueError, match="config must be a BuildConfig or None"):
            export_spice_deck(_lp_result(), "lowpass", config=config)

    @pytest.mark.parametrize(
        "category, key, value, message",
        [
            ("lowpass", "freq_hz", 1e308, "frequency span must be positive and finite"),
            ("lowpass", "freq_hz", float("nan"), "freq_hz must be positive and finite"),
            ("lowpass", "impedance", -50.0, "impedance must be positive and finite"),
            ("bandpass", "bw", 0.0, "bandpass f0 and bw must be positive and finite"),
            # 10 * bw is below the resolution of f0, so the sweep would have zero width.
            (
                "bandpass",
                "bw",
                1e-12,
                "bandpass bandwidth is too small relative to f0 to form a sweep span",
            ),
            # f0 + 10 * bw overflows binary64.
            ("bandpass", "bw", 1e308, "frequency span must be finite"),
        ],
    )
    def test_nonphysical_design_values_are_rejected_before_rendering(
        self, category, key, value, message
    ):
        result = _lp_result() if category == "lowpass" else _bp_result()
        result[key] = value
        with pytest.raises(ValueError, match=message):
            export_spice_deck(result, category)
