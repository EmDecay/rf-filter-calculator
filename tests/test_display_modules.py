"""Display building blocks: topology diagrams, quiet/CSV/JSON formatting, and output routing.

Complete LP/HP tables, JSON, and CSV for real order-3 designs are pinned in
``test_lp_hp_display_golden.py``; this module covers every order, the formatter
edge cases, and the routing those goldens do not reach.
"""

import json
import re

import pytest

from filter_lib.bandpass.diagrams import format_top_c_diagram, print_top_c_diagram
from filter_lib.highpass import display as hp_display
from filter_lib.lowpass import display as lp_display
from filter_lib.shared.display_common import (
    build_standard_match,
    format_component_table,
    format_csv_result,
    format_header,
    format_json_result,
    format_quiet_result,
    print_component_table,
    print_header,
)
from filter_lib.shared.topology_diagrams import (
    format_pi_topology_diagram,
    format_t_topology_diagram,
    print_pi_topology_diagram,
    print_t_topology_diagram,
)

# Fixtures lowpass_result, highpass_result, lowpass_t_result, and highpass_pi_result
# come from conftest.py.

_ORDERS = range(2, 10)
_LABELINGS = [("L", "C"), ("C", "L")]  # (series, shunt): lowpass, highpass


def _centered_label(line: str, column: int, label: str) -> str:
    start = column - len(label) // 2
    return line[start : start + len(label)]


def _assert_shunt_branches(lines: list[str], taps: list[int], shunt_label: str) -> None:
    _main, wire, symbol, labels, ground_wire, ground = lines
    for index, tap in enumerate(taps, start=1):
        assert wire[tap] == ground_wire[tap] == "│"
        assert _centered_label(symbol, tap, "===") == "==="
        assert _centered_label(labels, tap, f"{shunt_label}{index}") == f"{shunt_label}{index}"
        assert _centered_label(ground, tap, "GND") == "GND"
    assert len({len(line) for line in lines}) == 1


class TestLadderTopologyDiagrams:
    @pytest.mark.parametrize(("series", "shunt"), _LABELINGS)
    @pytest.mark.parametrize("order", _ORDERS)
    def test_pi_starts_with_shunt_and_hangs_every_shunt_from_its_own_tap(
        self, order, series, shunt
    ):
        n_shunt, n_series = (order + 1) // 2, order // 2
        lines = format_pi_topology_diagram(n_shunt, n_series, series, shunt).splitlines()
        main = lines[0]
        taps = [column for column, char in enumerate(main) if char == "┬"]

        assert main.startswith("  IN ───┬")
        assert re.findall(rf"┤ ({series}\d) ├", main) == [
            f"{series}{i}" for i in range(1, n_series + 1)
        ]
        assert len(taps) == n_shunt
        # Odd orders end on a shunt tap; even orders end on a series element (no phantom tap).
        assert main.endswith("┬─── OUT") is (order % 2 == 1)
        assert main.endswith("├────── OUT") is (order % 2 == 0)
        _assert_shunt_branches(lines, taps, shunt)

    @pytest.mark.parametrize(("series", "shunt"), _LABELINGS)
    @pytest.mark.parametrize("order", _ORDERS)
    def test_t_starts_with_series_and_hangs_every_shunt_from_its_own_tap(
        self, order, series, shunt
    ):
        n_series, n_shunt = (order + 1) // 2, order // 2
        lines = format_t_topology_diagram(n_series, n_shunt, series, shunt).splitlines()
        main = lines[0]
        taps = [column for column, char in enumerate(main) if char == "┬"]

        assert main.startswith(f"  IN ───┤{series}1├")
        assert re.findall(rf"┤({series}\d)├", main) == [
            f"{series}{i}" for i in range(1, n_series + 1)
        ]
        assert len(taps) == n_shunt
        # Odd orders end on a series element; even orders end on the final shunt tap.
        assert main.endswith("├─── OUT") is (order % 2 == 1)
        assert main.endswith("┬─── OUT") is (order % 2 == 0)
        _assert_shunt_branches(lines, taps, shunt)


class TestTopCDiagram:
    @pytest.mark.parametrize("n", _ORDERS)
    def test_tanks_coupling_and_end_capacitors_are_labelled_in_place(self, n):
        lines = format_top_c_diagram(n).splitlines()
        labels, main, tank_labels, ground = lines[0], lines[1], lines[5], lines[9]
        taps = [column for column, char in enumerate(main) if char == "┬"]
        caps = [match.start() for match in re.finditer("┤├", main)]

        assert main.startswith("  IN ──┤├──┬") and main.endswith("──┤├── OUT")
        assert len(taps) == n
        assert len(caps) == n + 1  # Ce_in, n-1 series couplers, Ce_out
        for index, tap in enumerate(taps, start=1):
            assert _centered_label(tank_labels, tap, f"Cp{index:<2} L{index}") == (
                f"Cp{index:<2} L{index}"
            )
            assert _centered_label(ground, tap, "GND") == "GND"
        for label, cap in [("Ce_in", caps[0]), ("Ce_out", caps[-1])] + [
            (f"Cs{i}{i + 1}", cap) for i, cap in enumerate(caps[1:-1], start=1)
        ]:
            start = labels.index(label)
            assert start <= cap and cap + 1 < start + len(label)
        assert len({len(line) for line in lines}) == 1


@pytest.mark.parametrize(
    ("printer", "formatter", "arguments"),
    [
        (print_pi_topology_diagram, format_pi_topology_diagram, (3, 2)),
        (print_t_topology_diagram, format_t_topology_diagram, (3, 2, "C", "L")),
        (print_top_c_diagram, format_top_c_diagram, (4,)),
    ],
)
def test_diagram_printers_emit_the_formatted_diagram(printer, formatter, arguments, capsys):
    printer(*arguments)
    assert capsys.readouterr().out == formatter(*arguments) + "\n"


def test_header_and_component_table_printers_emit_formatted_text(highpass_result, capsys):
    print_header(highpass_result, topology="T", filter_category="High Pass")
    print_component_table(highpass_result, raw=True, primary_component="capacitors")

    expected = (
        format_header(highpass_result, "T", "High Pass")
        + "\n"
        + format_component_table(highpass_result, True, "capacitors")
        + "\n"
    )
    assert capsys.readouterr().out == expected


class TestQuietOutput:
    @pytest.mark.parametrize(
        ("module", "fixture", "expected"),
        [
            (
                lp_display,
                "lowpass_result",
                "C1: 100.00 pF\nC2: 200.00 pF\nC3: 100.00 pF\nL1: 1.00 µH\nL2: 1.00 µH",
            ),
            (
                lp_display,
                "lowpass_t_result",
                "L1: 1.00 µH\nL2: 1.00 µH\nL3: 1.00 µH\nC1: 100.00 pF\nC2: 200.00 pF",
            ),
            (hp_display, "highpass_result", "C1: 500.00 pF\nC2: 500.00 pF\nL1: 2.00 µH"),
            (hp_display, "highpass_pi_result", "L1: 2.00 µH\nL2: 2.00 µH\nC1: 500.00 pF"),
        ],
    )
    def test_quiet_lists_first_ladder_element_type_first(self, module, fixture, expected, request):
        assert module.format_quiet(request.getfixturevalue(fixture)) == expected

    def test_raw_quiet_uses_si_units(self, lowpass_result):
        assert lp_display.format_quiet(lowpass_result, raw=True).splitlines() == [
            "C1: 1.000000e-10 F",
            "C2: 2.000000e-10 F",
            "C3: 1.000000e-10 F",
            "L1: 1.000000e-06 H",
            "L2: 1.000000e-06 H",
        ]

    @pytest.mark.parametrize(
        ("module", "fixture"),
        [(lp_display, "lowpass_result"), (hp_display, "highpass_result")],
    )
    def test_missing_topology_uses_category_default(self, module, fixture, request):
        """Lowpass defaults to Pi and highpass to T; both lead with capacitors."""
        result = request.getfixturevalue(fixture)
        legacy = {key: value for key, value in result.items() if key != "topology"}

        assert module.format_quiet(legacy) == module.format_quiet(result)
        assert module.format_quiet(legacy).startswith("C1: ")


def test_csv_without_preferred_values_has_only_value_columns(lowpass_t_result):
    output = lp_display.format_csv(lowpass_t_result, include_toroids=False)

    assert output.splitlines() == [
        "Component,Value,Unit",
        "L1,1.00,µH",
        "L2,1.00,µH",
        "L3,1.00,µH",
        "C1,100.00,pF",
        "C2,200.00,pF",
    ]


def test_json_rejects_non_finite_component_instead_of_emitting_nan(lowpass_result):
    lowpass_result["capacitors"][0] = float("nan")

    with pytest.raises(ValueError, match=r"\$\.components\.capacitors\[0\]"):
        format_json_result(lowpass_result, primary_component="capacitors")


class TestStandardMatchRecommendationMetadata:
    def test_single_within_one_percent_is_the_explicit_selection(self):
        data = build_standard_match(100.9e-12, "E24", "value_farads", "additive")

        assert data["status"] == "recommended"
        assert data["selected"]["kind"] == "single"
        assert data["selected"]["value_farads"] == pytest.approx(100e-12, rel=1e-9, abs=0)
        assert "parallel" not in data
        assert data["policy"] == {
            "prefer_single_within_pct": 1.0,
            "min_parallel_improvement_pct_points": 0.5,
            "minimum_capacitance_f": 1e-12,
            "allow_sub_pf": False,
        }

    def test_material_parallel_pair_is_the_explicit_selection(self):
        data = build_standard_match(138.8e-12, "E24", "value_farads", "additive")

        assert data["selected"]["kind"] == "parallel"
        assert data["parallel"]["components"] == data["selected"]["components"]
        assert data["selected"]["value_farads"] == pytest.approx(
            sum(part["value_farads"] for part in data["selected"]["components"]), rel=1e-9, abs=0
        )

    def test_sub_pf_target_exports_warning_without_selection(self):
        data = build_standard_match(0.62e-12, "E24", "value_farads", "additive")

        assert data["status"] == "expert_override_required"
        assert data["selected"] is None
        assert any("1 pF" in warning for warning in data["warnings"])


class TestDisplayResultsRouting:
    @pytest.mark.parametrize(
        ("module", "fixture"),
        [(lp_display, "lowpass_result"), (hp_display, "highpass_pi_result")],
    )
    @pytest.mark.parametrize("show_match", [True, False])
    def test_machine_formats_print_formatter_output(
        self, module, fixture, show_match, request, capsys
    ):
        result = request.getfixturevalue(fixture)
        eseries = "E24" if show_match else None
        expected = {
            "json": module.format_json(result, eseries=eseries, include_toroids=False) + "\n",
            "csv": module.format_csv(result, eseries=eseries, include_toroids=False),
        }

        for output_format, text in expected.items():
            module.display_results(
                result, output_format=output_format, show_match=show_match, include_toroids=False
            )
            assert capsys.readouterr().out == text
        payload = json.loads(expected["json"])
        assert ("standard_match" in payload["components"]["capacitors"][0]) is show_match

    def test_quiet_table_prints_quiet_listing(self, highpass_pi_result, capsys):
        hp_display.display_results(highpass_pi_result, quiet=True)
        assert capsys.readouterr().out == hp_display.format_quiet(highpass_pi_result) + "\n"

    def test_raw_table_omits_preferred_value_selection(self, lowpass_result, capsys):
        lp_display.display_results(lowpass_result, raw=True, show_match=True, include_toroids=False)
        out = capsys.readouterr().out

        assert "│ C1: 1.000000e-10 F     │ L1: 1.000000e-06 H     │" in out.splitlines()
        assert "Preferred-Value Capacitor Selection" not in out


class TestJsonResultComponentValues:
    def test_empty_component_lists_serialize_as_empty_arrays(self):
        result_dict = {
            "filter_type": "butterworth",
            "freq_hz": 1e6,
            "impedance": 50.0,
            "order": 0,
            "capacitors": [],
            "inductors": [],
            "ripple": None,
        }
        data = json.loads(format_json_result(result_dict))
        assert data["components"]["capacitors"] == []
        assert data["components"]["inductors"] == []

    def test_extreme_component_values_are_preserved_unrounded(self):
        result_dict = {
            "filter_type": "butterworth",
            "freq_hz": 1e6,
            "impedance": 50.0,
            "order": 2,
            "capacitors": [1e-15, 1e-3],  # femtofarad to millifarad
            "inductors": [1e-12, 1],  # picohenry to henry
            "ripple": None,
        }
        data = json.loads(format_json_result(result_dict))
        assert data["components"]["capacitors"][0]["value_farads"] == 1e-15
        assert data["components"]["capacitors"][1]["value_farads"] == 1e-3
        assert data["components"]["inductors"][0]["value_henries"] == 1e-12
        assert data["components"]["inductors"][1]["value_henries"] == 1


class TestCsvResultRows:
    def test_empty_components_produce_header_only(self):
        output = format_csv_result({"capacitors": [], "inductors": []})
        assert output.strip().split("\n") == ["Component,Value,Unit"]

    def test_extreme_capacitances_split_into_value_and_unit_columns(self):
        output = format_csv_result({"capacitors": [1e-15, 1e-3], "inductors": []})
        assert output.strip().split("\n") == [
            "Component,Value,Unit",
            "C1,1.00,fF",
            "C2,1.00,mF",
        ]

    def test_sub_nanohenry_inductance_keeps_plain_henry_unit_column(self):
        output = format_csv_result({"capacitors": [], "inductors": [1e-12, 1.0]})
        assert output.strip().split("\n") == [
            "Component,Value,Unit",
            "L1,1.000000e-12,H",
            "L2,1.00,H",
        ]


class TestQuietResultLines:
    def test_empty_components_produce_empty_output(self):
        assert format_quiet_result({"capacitors": [], "inductors": []}) == ""

    def test_raw_mode_prints_base_units_in_scientific_notation(self):
        output = format_quiet_result({"capacitors": [1e-15], "inductors": [1.0]}, raw=True)
        assert output == "C1: 1.000000e-15 F\nL1: 1.000000e+00 H"

    def test_formatted_mode_prints_engineering_units(self):
        output = format_quiet_result({"capacitors": [1e-12], "inductors": [1e-6]}, raw=False)
        assert output == "C1: 1.00 pF\nL1: 1.00 µH"
