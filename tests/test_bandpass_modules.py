"""Bandpass prototype g-values and the JSON, CSV, quiet, table, and diagram outputs."""

import copy
import csv
import io
import json
import math

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.diagrams import format_top_c_diagram, print_top_c_diagram
from filter_lib.bandpass.display import PLOT_POINTS, display_results, format_q_model_lines
from filter_lib.bandpass.formatters import format_csv, format_json, format_quiet
from filter_lib.bandpass.g_values import (
    calculate_butterworth_g_values,
    get_bessel_g_values,
    get_chebyshev_g_values,
    get_g_values,
)

_SI_PREFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "µ": 1e-6, "m": 1e-3, "": 1.0}
_COMPONENT_ORDER = ["Cp1", "Cp2", "Cp3", "L1", "L2", "L3", "Cs12", "Cs23", "Ce_in", "Ce_out"]


def _make_result(**overrides):
    """Helper to create a bandpass filter result dict."""
    kwargs = dict(
        f0=14.175e6, bw=350e3, z0=50.0, n_resonators=3, filter_type="butterworth", coupling="top"
    )
    kwargs.update(overrides)
    return calculate_bandpass_filter(**kwargs)


@pytest.fixture(scope="module")
def _reference_result():
    return _make_result()


@pytest.fixture
def result(_reference_result):
    """Fresh copy of the 14.175 MHz / 350 kHz Butterworth n=3 design."""
    return copy.deepcopy(_reference_result)


def _expected_values(result):
    """Component values in export order, from the synthesis result."""
    n = result["n_resonators"]
    return (
        list(result["c_tank"])
        + [result["L_resonant"]] * n
        + list(result["c_coupling"])
        + [result["c_end_in"], result["c_end_out"]]
    )


def _si_value(value: str, unit: str) -> float:
    """Parse a formatted ``value unit`` pair such as ``185.84 pF`` into SI units."""
    return float(value) * _SI_PREFIX[unit[:-1]]


# --- g_values ---


class TestPrototypeGValues:
    def test_butterworth_closed_form_reference_values(self):
        assert calculate_butterworth_g_values(3) == pytest.approx([1.0, 2.0, 1.0], rel=1e-12)
        assert calculate_butterworth_g_values(5) == pytest.approx(
            [0.6180339887, 1.6180339887, 2.0, 1.6180339887, 0.6180339887], rel=1e-9
        )

    @pytest.mark.parametrize(
        "n, ripple_db, expected",
        [
            (3, 0.1, [1.0316, 1.1474, 1.0316]),
            (3, 0.5, [1.5963, 1.0967, 1.5963]),
            (5, 0.5, [1.7058, 1.2296, 2.5408, 1.2296, 1.7058]),
        ],
    )
    def test_chebyshev_matches_published_equal_ripple_tables(self, n, ripple_db, expected):
        """Matthaei/Young/Jones tables list g1..gn; the unused g0 slot is not returned."""
        assert get_chebyshev_g_values(n, ripple_db) == pytest.approx(expected, abs=1e-4)

    def test_chebyshev_ripple_between_table_entries_is_computed(self):
        """Any ripple in (0, 3.0] computes; 0.2 dB lies between the 0.1 and 0.5 dB rows."""
        g = get_chebyshev_g_values(3, 0.2)
        assert 1.0316 < g[0] < 1.5963
        assert g[0] == pytest.approx(g[2], rel=1e-12)

    @pytest.mark.parametrize(
        "n, ripple_db, message",
        [
            (3, 3.5, "Ripple .* not supported"),
            (3, 0.0, "must be positive"),
            (3, float("nan"), "must be positive"),
            (4, 0.5, "odd resonator count"),
        ],
    )
    def test_chebyshev_rejects_unsupported_designs(self, n, ripple_db, message):
        with pytest.raises(ValueError, match=message):
            get_chebyshev_g_values(n, ripple_db)

    def test_bessel_returns_zverev_row_as_independent_copy(self):
        g = get_bessel_g_values(3)
        assert g == [0.3374, 0.9705, 2.2034]
        g[0] = 99.0
        assert get_bessel_g_values(3)[0] == 0.3374

    def test_bessel_invalid_order(self):
        with pytest.raises(ValueError, match="2-9 resonators"):
            get_bessel_g_values(10)

    def test_get_g_values_dispatches_by_family(self):
        assert get_g_values("butterworth", 4) == calculate_butterworth_g_values(4)
        assert get_g_values("chebyshev", 5, 1.0) == get_chebyshev_g_values(5, 1.0)
        assert get_g_values("bessel", 3) == get_bessel_g_values(3)

    def test_get_g_values_unknown(self):
        with pytest.raises(ValueError, match="Unknown filter type"):
            get_g_values("invalid", 3)

    @pytest.mark.parametrize("order", [True, 3.0, "3", None])
    @pytest.mark.parametrize(
        "calculator, message",
        [
            (calculate_butterworth_g_values, "n must be a positive integer"),
            (get_bessel_g_values, "only available for 2-9 resonators"),
            (lambda order: get_chebyshev_g_values(order, 0.5), "n must be a positive integer"),
        ],
    )
    def test_public_g_value_helpers_reject_noninteger_orders(self, calculator, message, order):
        with pytest.raises(ValueError, match=message):
            calculator(order)

    @pytest.mark.parametrize("ripple", [True, "0.5", None])
    def test_public_chebyshev_helper_rejects_nonnumeric_ripple(self, ripple):
        with pytest.raises(ValueError, match="positive and finite"):
            get_chebyshev_g_values(3, ripple)


# --- formatters ---


class TestFormatters:
    def test_format_json_reports_requested_design_and_every_component(self, result):
        data = json.loads(format_json(result, include_toroids=False))

        assert data["filter_type"] == "butterworth"
        assert data["coupling"] == "top"
        assert data["center_frequency_hz"] == result["f0"]
        assert data["bandwidth_hz"] == result["bw"]
        assert (data["f_low_hz"], data["f_high_hz"]) == (result["f_low"], result["f_high"])
        assert data["impedance_ohms"] == 50.0
        assert data["n_resonators"] == 3
        components = data["components"]
        assert [c["name"] for c in components["tank_capacitors"]] == ["Cp1", "Cp2", "Cp3"]
        assert [c["value_farads"] for c in components["tank_capacitors"]] == result["c_tank"]
        assert [c["name"] for c in components["inductors"]] == ["L1", "L2", "L3"]
        assert {c["value_henries"] for c in components["inductors"]} == {result["L_resonant"]}
        assert [c["name"] for c in components["coupling_capacitors"]] == ["Cs12", "Cs23"]
        assert [c["value_farads"] for c in components["coupling_capacitors"]] == (
            result["c_coupling"]
        )
        assert data["external_q"] == {"input": result["qe_in"], "output": result["qe_out"]}
        assert "ripple_db" not in data
        assert "resonator_toroid_candidates" not in data

    def test_format_json_eseries_matches_capacitors_only(self, result):
        data = json.loads(format_json(result, eseries="E24", include_toroids=False))
        first_tank_cap = data["components"]["tank_capacitors"][0]
        first_inductor = data["components"]["inductors"][0]
        first_coupling_cap = data["components"]["coupling_capacitors"][0]

        assert "standard_match" in first_tank_cap
        assert "standard_match" in first_coupling_cap
        assert "standard_match" not in first_inductor

    def test_format_json_with_ripple(self):
        result = _make_result(filter_type="chebyshev", n_resonators=5, ripple_db=0.5)
        data = json.loads(format_json(result, include_toroids=False))
        assert data["ripple_db"] == 0.5

    def test_format_csv_lists_every_component_with_si_units(self, result):
        rows = list(csv.reader(io.StringIO(format_csv(result, include_toroids=False))))

        assert rows[0] == ["Component", "Value", "Unit"]
        assert [row[0] for row in rows[1:]] == _COMPONENT_ORDER
        assert [row[2][-1] for row in rows[1:]] == list("FFFHHHFFFF")
        parsed = [_si_value(value, unit) for _, value, unit in rows[1:]]
        # Two-decimal display rounding bounds the relative error of these values.
        assert parsed == pytest.approx(_expected_values(result), rel=2e-3, abs=0)

    def test_format_csv_eseries_leaves_inductor_match_columns_empty(self, result):
        output = format_csv(result, eseries="E24", include_toroids=False)
        rows = [line.split(",") for line in output.splitlines()]
        inductor_row = next(row for row in rows if row[0] == "L1")
        cap_row = next(row for row in rows if row[0] == "Cp1")

        assert inductor_row[3:9] == [""] * 6
        assert cap_row[3] != ""

    def test_format_quiet_lists_every_component_with_units(self, result):
        lines = format_quiet(result, raw=False).splitlines()
        names = [line.split(": ")[0] for line in lines]
        assert names == _COMPONENT_ORDER
        parsed = [_si_value(*line.split(": ")[1].split(" ")) for line in lines]
        assert parsed == pytest.approx(_expected_values(result), rel=2e-3, abs=0)

    def test_format_quiet_raw_prints_scientific_si_values(self, result):
        lines = format_quiet(result, raw=True).splitlines()
        assert [line.split(": ")[0] for line in lines] == _COMPONENT_ORDER
        units = [line.rsplit(" ", 1)[1] for line in lines]
        assert units == list("FFFHHHFFFF")
        values = [float(line.split(": ")[1].split(" ")[0]) for line in lines]
        assert values == pytest.approx(_expected_values(result), rel=1e-6, abs=0)


# --- display ---


class TestDisplay:
    @pytest.mark.parametrize(
        "options, expected",
        [
            ({"output_format": "json"}, lambda r: format_json(r, eseries="E24") + "\n"),
            ({"output_format": "csv"}, lambda r: format_csv(r, eseries="E24")),
            ({"quiet": True}, lambda r: format_quiet(r) + "\n"),
        ],
    )
    def test_machine_and_quiet_modes_print_exact_formatter_output(
        self, result, capsys, options, expected
    ):
        display_results(result, **options)
        assert capsys.readouterr().out == expected(result)

    def test_display_table_header_describes_the_design(self, result, capsys):
        display_results(result, output_format="table", include_toroids=False)
        out = capsys.readouterr().out
        assert "Butterworth Coupled Resonator Bandpass Filter" in out
        assert "Center Frequency f₀: 14.18 MHz" in out
        assert "Bandwidth BW:        350 kHz" in out
        assert "Resonators:          3" in out
        assert "Coupling:            Top-C (Series)" in out
        assert "Ripple:" not in out

    def test_display_table_shows_ripple_and_warnings(self, capsys):
        result = _make_result(filter_type="chebyshev", ripple_db=0.5)
        result["warnings"] = ["synthetic warning for display"]
        display_results(result, output_format="table")
        out = capsys.readouterr().out
        assert "Ripple:              0.5 dB" in out
        assert "⚠ synthetic warning for display" in out

    @pytest.mark.parametrize(
        "q_model, expected_lines",
        [
            (
                {"resonator_qu": None},
                ["", "Loss examples use complete-resonator unloaded Q (not inductor Q alone)."],
            ),
            (
                {"resonator_qu": 150.0},
                ["", "Loss-model complete-resonator unloaded Q: 150"],
            ),
            (
                {"resonator_qu": 400.0 / 3.0, "inductor_ql": 200.0, "capacitor_qc": 400.0},
                [
                    "",
                    "Loss-model complete-resonator unloaded Q: 133.3",
                    "  Derived from QL=200 and QC=400 at f₀",
                ],
            ),
            (
                {"resonator_qu": 400.0, "inductor_ql": None, "capacitor_qc": 400.0},
                [
                    "",
                    "Loss-model complete-resonator unloaded Q: 400",
                    "  Derived from QC=400 at f₀",
                ],
            ),
        ],
    )
    def test_q_model_lines_name_the_component_q_sources(self, q_model, expected_lines):
        assert format_q_model_lines({"q_model": q_model}) == expected_lines

    @pytest.mark.parametrize(
        ("q_model", "expected_lines"),
        [
            ({"resonator_qu": 12345.0}, ["", "Loss-model complete-resonator unloaded Q: 12345"]),
            ({"resonator_qu": 1e6}, ["", "Loss-model complete-resonator unloaded Q: 1e+06"]),
            ({"resonator_qu": 123456.7}, ["", "Loss-model complete-resonator unloaded Q: 123457"]),
            (
                {
                    "resonator_qu": 12345.0 * 20000.0 / 32345.0,
                    "inductor_ql": 12345.0,
                    "capacitor_qc": 20000.0,
                },
                [
                    "",
                    "Loss-model complete-resonator unloaded Q: 7633",
                    "  Derived from QL=12345 and QC=20000 at f₀",
                ],
            ),
        ],
    )
    def test_large_q_values_use_the_insertion_loss_qu_labels(self, q_model, expected_lines):
        assert format_q_model_lines({"q_model": q_model}) == expected_lines

    def test_widened_user_qu_label_matches_the_insertion_loss_line(self):
        result = calculate_bandpass_filter(10e6, 350e3, 50, 3, "butterworth", "top", qu=100.00001)

        assert format_q_model_lines(result)[1] == (
            "Loss-model complete-resonator unloaded Q: 100.00001"
        )

    def test_display_with_eseries(self, result, capsys):
        display_results(result, eseries="E12", include_toroids=False)
        out = capsys.readouterr().out
        assert "E12 Preferred-Value Capacitor Selection" in out
        assert "Cp1 Calculated:" in out

        display_results(result, eseries="E12", raw=True, include_toroids=False)
        assert "Preferred-Value Capacitor Selection" not in capsys.readouterr().out

    def test_display_plot_appends_simulated_response_and_thresholds(self, result, capsys):
        display_results(result, include_toroids=False)
        without_plot = capsys.readouterr().out
        display_results(result, show_plot=True, include_toroids=False)
        with_plot = capsys.readouterr().out

        for marker in (
            "Butterworth 3-pole Response",
            "Passband Detail",
            "Threshold reference: local peak",
            "dB Threshold Summary",
        ):
            assert marker in with_plot
            assert marker not in without_plot

    def test_display_plot_data_json(self, result, capsys):
        display_results(result, plot_data="json")
        data = json.loads(capsys.readouterr().out)
        assert data["filter"]["category"] == "bandpass"
        assert len(data["data"]) == PLOT_POINTS
        peak_db = max(point["magnitude_db"] for point in data["data"])
        assert peak_db == pytest.approx(0.0, abs=0.01)

    def test_display_plot_data_csv(self, result, capsys):
        display_results(result, plot_data="csv")
        rows = list(csv.reader(io.StringIO(capsys.readouterr().out.strip())))
        assert rows[0] == ["frequency_hz", "magnitude_db"]
        assert len(rows) == PLOT_POINTS + 1
        assert all(math.isfinite(float(value)) for row in rows[1:] for value in row)


# --- diagrams ---


class TestDiagrams:
    @pytest.mark.parametrize("n", [2, 5, 9])
    def test_top_c_diagram_labels_every_tank_and_coupling_capacitor(self, n, capsys):
        print_top_c_diagram(n)
        out = capsys.readouterr().out
        assert out == format_top_c_diagram(n) + "\n"
        assert out.count("GND") == n
        for index in range(1, n + 1):
            assert f"Cp{index}" in out
            assert f"L{index}" in out
        for index in range(1, n):
            assert f"Cs{index}{index + 1}" in out
        assert f"Cs{n}{n + 1}" not in out


# --- end-coupling capacitors across output surfaces ---


class TestEndCapOutputs:
    """Ce_in/Ce_out must appear in every Top-C output format."""

    def test_diagram_shows_end_caps(self):
        diagram = format_top_c_diagram(3)
        assert "Ce_in" in diagram
        assert "Ce_out" in diagram
        assert "IN ──┤├──" in diagram
        assert "──┤├── OUT" in diagram

    def test_json_includes_end_coupling_capacitors(self, result):
        data = json.loads(format_json(result, eseries="E24", include_toroids=False))
        end_caps = data["components"]["end_coupling_capacitors"]
        assert [c["name"] for c in end_caps] == ["Ce_in", "Ce_out"]
        assert end_caps[0]["value_farads"] == result["c_end_in"]
        assert "standard_match" in end_caps[0]

    def test_json_omits_end_caps_when_absent(self, result):
        # Formatter stays tolerant of result dicts without end caps
        result = {**result, "c_end_in": None, "c_end_out": None}
        data = json.loads(format_json(result, include_toroids=False))
        assert "end_coupling_capacitors" not in data["components"]

    def test_table_includes_end_caps_and_realized_q(self, result, capsys):
        display_results(result, output_format="table")
        out = capsys.readouterr().out
        assert "Ce_in" in out
        assert "Ce_out" in out
        assert "(realized by Ce_in)" in out
        assert "(realized by Ce_out)" in out

    def test_table_eseries_section_covers_end_caps(self, result, capsys):
        display_results(result, output_format="table", eseries="E24")
        out = capsys.readouterr().out
        assert "Ce_in Calculated:" in out
        assert "Ce_out Calculated:" in out

    def test_wizard_table_and_recs_include_end_caps(self, result):
        from filter_lib.wizard.formatting_helpers import (
            format_bandpass_eseries_recs,
            format_bandpass_table,
        )
        from filter_lib.wizard.state import FilterState

        state = FilterState()
        table = "\n".join(format_bandpass_table(result, state))
        assert "Ce_in" in table
        assert "(realized by Ce_out)" in table
        recs = "\n".join(format_bandpass_eseries_recs(result, "E24"))
        assert "Ce_in Calculated:" in recs
        assert "Ce_out Calculated:" in recs
