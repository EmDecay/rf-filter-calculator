"""Bandpass prototype g-values and the JSON, CSV, quiet, table, and diagram outputs."""

import copy
import csv
import io
import json
import math

import pytest

from filter_lib.bandpass.calculations import calculate_bandpass_filter
from filter_lib.bandpass.diagrams import format_top_c_diagram
from filter_lib.bandpass.display import PLOT_POINTS, display_results, format_q_model_lines
from filter_lib.bandpass.formatters import format_csv, format_json, format_quiet
from filter_lib.bandpass.g_values import (
    calculate_butterworth_g_values,
    get_bessel_g_values,
    get_chebyshev_g_values,
    get_g_values,
)
from filter_lib.shared.chebyshev_g_calculator import MAX_PROTOTYPE_ORDER

_SI_PREFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "µ": 1e-6, "m": 1e-3, "": 1.0}
_FREQUENCY_UNIT = {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9}
_COMPONENT_ORDER = ["Cp1", "Cp2", "Cp3", "L1", "L2", "L3", "Cs12", "Cs23", "Ce_in", "Ce_out"]
# Values-only output follows the component table: Ce_in, then Cs12…, then Ce_out.
_TABLE_ORDER = ["Cp1", "Cp2", "Cp3", "L1", "L2", "L3", "Ce_in", "Cs12", "Cs23", "Ce_out"]


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


def _expected_table_values(result):
    """Component values in component-table order, from the synthesis result."""
    n = result["n_resonators"]
    return (
        list(result["c_tank"])
        + [result["L_resonant"]] * n
        + [result["c_end_in"]]
        + list(result["c_coupling"])
        + [result["c_end_out"]]
    )


def _si_value(value: str, unit: str) -> float:
    """Parse a formatted ``value unit`` pair such as ``185.84 pF`` into SI units."""
    return float(value) * _SI_PREFIX[unit[:-1]]


# --- g_values ---


class TestPrototypeGValues:
    def test_butterworth_closed_form_reference_values(self):
        assert calculate_butterworth_g_values(1) == pytest.approx([2.0], rel=1e-12)
        assert calculate_butterworth_g_values(3) == pytest.approx([1.0, 2.0, 1.0], rel=1e-12)
        assert calculate_butterworth_g_values(5) == pytest.approx(
            [0.6180339887, 1.6180339887, 2.0, 1.6180339887, 0.6180339887], rel=1e-9
        )

    def test_butterworth_order_limit_is_inclusive(self):
        g = calculate_butterworth_g_values(MAX_PROTOTYPE_ORDER)
        assert len(g) == MAX_PROTOTYPE_ORDER
        assert g[0] == pytest.approx(math.pi / MAX_PROTOTYPE_ORDER, rel=1e-8)  # 2·sin(π/2n)
        assert max(g) == pytest.approx(2.0, rel=1e-7)  # 2·cos(π/2n) for even n
        with pytest.raises(ValueError, match="n must be a positive integer"):
            calculate_butterworth_g_values(MAX_PROTOTYPE_ORDER + 1)

    @pytest.mark.parametrize(
        "n, ripple_db, expected",
        [
            (3, 0.1, [1.0316, 1.1474, 1.0316]),
            (3, 0.2, [1.2275, 1.1525, 1.2275]),
            (3, 0.5, [1.5963, 1.0967, 1.5963]),
            # The inclusive 3.0 dB ceiling.
            (3, 3.0, [3.3487, 0.7117, 3.3487]),
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
            (3, math.nextafter(3.0, 4.0), "Ripple .* not supported"),
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
        # Chebyshev ripple defaults to 0.5 dB (Matthaei/Young/Jones row).
        assert get_g_values("chebyshev", 3) == pytest.approx([1.5963, 1.0967, 1.5963], abs=1e-4)
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
        assert names == _TABLE_ORDER
        parsed = [_si_value(*line.split(": ")[1].split(" ")) for line in lines]
        assert parsed == pytest.approx(_expected_table_values(result), rel=2e-3, abs=0)

    def test_format_quiet_raw_prints_scientific_si_values(self, result):
        lines = format_quiet(result, raw=True).splitlines()
        assert [line.split(": ")[0] for line in lines] == _TABLE_ORDER
        units = [line.rsplit(" ", 1)[1] for line in lines]
        assert units == list("FFFHHHFFFF")
        values = [float(line.split(": ")[1].split(" ")[0]) for line in lines]
        assert values == pytest.approx(_expected_table_values(result), rel=1e-6, abs=0)


# --- display ---


class TestDisplay:
    @pytest.mark.parametrize(
        "options, expected",
        [
            ({"output_format": "json"}, lambda r: format_json(r, eseries="E24") + "\n"),
            ({"output_format": "csv"}, lambda r: format_csv(r, eseries="E24") + "\n"),
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
        assert "Butterworth Coupled-Resonator Band-Pass Filter" in out
        assert "Center Frequency f₀: 14.175 MHz" in out
        assert "-3 dB Bandwidth:     350 kHz" in out
        assert "Resonators:          3" in out
        assert "Coupling:            Top-C (series capacitors)" in out
        assert "Ripple:" not in out

    @staticmethod
    def _header_hz(out: str) -> dict[str, float]:
        """Header frequencies in Hz, keyed by the label before the colon."""
        values = {}
        for line in out.splitlines():
            label, separator, text = line.partition(":")
            number, _, unit = text.strip().partition(" ")
            if separator and unit in _FREQUENCY_UNIT:
                values[label] = float(number) * _FREQUENCY_UNIT[unit]
        return values

    @pytest.mark.parametrize(
        ("f0", "bw", "n_resonators", "filter_type"),
        [
            # 0.1% FBW: four figures printed 99.95 / 100.1 MHz beside a 100 kHz bandwidth.
            (100e6, 100e3, 3, "butterworth"),
            (7.0735e6, 12.345e3, 3, "butterworth"),
            (14.175e6, 350e3, 3, "butterworth"),
            (455e3, 10e3, 4, "bessel"),
            # 50% FBW: 7.808 / 12.81 MHz implied a 5.002 MHz bandwidth.
            (10e6, 5e6, 3, "butterworth"),
        ],
    )
    def test_header_edges_resolve_the_printed_bandwidth(
        self, capsys, f0, bw, n_resonators, filter_type
    ):
        result = _make_result(f0=f0, bw=bw, n_resonators=n_resonators, filter_type=filter_type)

        display_results(result, eseries=None, include_toroids=False)

        header = self._header_hz(capsys.readouterr().out)
        lower, upper = header["Lower -3 dB Edge fₗ"], header["Upper -3 dB Edge fₕ"]
        bandwidth = header["-3 dB Bandwidth"]
        assert bandwidth == bw
        # The printed edges subtract to the printed bandwidth at four significant figures.
        assert float(f"{upper - lower:.4g}") == float(f"{bandwidth:.4g}")
        assert abs(lower - result["f_low"]) <= 1e-4 * bw
        assert abs(upper - result["f_high"]) <= 1e-4 * bw

    def test_header_restates_the_typed_design_values(self, capsys):
        result = _make_result(f0=7.0735e6, bw=12.345e3, z0=12345.0)

        display_results(result, eseries=None, include_toroids=False)

        lines = capsys.readouterr().out.splitlines()
        assert "Center Frequency f₀: 7.0735 MHz" in lines
        assert "-3 dB Bandwidth:     12.345 kHz" in lines
        assert "Impedance Z₀:        12345 Ω" in lines

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
            ({"resonator_qu": None}, [""]),
            ({"resonator_qu": 150.0}, ["", "Your Qu: 150"]),
            (
                {"resonator_qu": 400.0 / 3.0, "inductor_ql": 200.0, "capacitor_qc": 400.0},
                ["", "Your Qu: 133.3 (from QL=200 and QC=400 at f₀)"],
            ),
            (
                {"resonator_qu": 400.0, "inductor_ql": None, "capacitor_qc": 400.0},
                ["", "Your Qu: 400 (from QC=400 at f₀)"],
            ),
        ],
    )
    def test_q_model_lines_name_the_component_q_sources(self, q_model, expected_lines):
        assert format_q_model_lines({"q_model": q_model}) == expected_lines

    @pytest.mark.parametrize(
        ("q_model", "expected_lines"),
        [
            ({"resonator_qu": 12345.0}, ["", "Your Qu: 12345"]),
            ({"resonator_qu": 1e6}, ["", "Your Qu: 1e+06"]),
            ({"resonator_qu": 123456.7}, ["", "Your Qu: 123457"]),
            (
                {
                    "resonator_qu": 12345.0 * 20000.0 / 32345.0,
                    "inductor_ql": 12345.0,
                    "capacitor_qc": 20000.0,
                },
                ["", "Your Qu: 7633 (from QL=12345 and QC=20000 at f₀)"],
            ),
        ],
    )
    def test_large_q_values_use_the_insertion_loss_qu_labels(self, q_model, expected_lines):
        assert format_q_model_lines({"q_model": q_model}) == expected_lines

    def test_widened_user_qu_label_matches_the_insertion_loss_line(self):
        result = calculate_bandpass_filter(10e6, 350e3, 50, 3, "butterworth", "top", qu=100.00001)

        assert format_q_model_lines(result)[1] == "Your Qu: 100.00001"

    def test_display_with_eseries(self, result, capsys):
        display_results(result, eseries="E12", include_toroids=False)
        out = capsys.readouterr().out
        assert "E12 Standard Capacitor Values" in out
        assert "Cp1 calculated " in out

        display_results(result, eseries="E12", raw=True, include_toroids=False)
        assert "Standard Capacitor Values" not in capsys.readouterr().out

    def test_display_plot_appends_simulated_response_and_thresholds(self, result, capsys):
        display_results(result, include_toroids=False)
        without_plot = capsys.readouterr().out
        display_results(result, show_plot=True, include_toroids=False)
        with_plot = capsys.readouterr().out

        for marker in (
            "Simulated Response, ideal parts (dB): Butterworth, 3 resonators",
            "Simulated Response Detail",
            "Levels below are relative to the peak nearest the center (",
            "Frequencies at -3 / -10 / -20 dB",
        ):
            assert marker in with_plot
            assert marker not in without_plot

    def test_threshold_note_names_separate_ranges_only_when_there_are_several(self, capsys):
        split = calculate_bandpass_filter(10e6, 1e6, 50, 9, "chebyshev", "top", ripple_db=3.0)
        display_results(split, show_plot=True, eseries=None, include_toroids=False)
        split_out = capsys.readouterr().out
        display_results(_make_result(), show_plot=True, eseries=None, include_toroids=False)
        single_out = capsys.readouterr().out

        assert "The response is above -3 dB in 5 separate ranges." in split_out
        assert "separate ranges" not in single_out
        assert "Levels below are relative to the peak nearest the center (" in single_out
        assert " Hz;" not in single_out  # the reference frequency carries a unit prefix

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
    def test_top_c_diagram_labels_every_tank_and_coupling_capacitor(self, n):
        out = format_top_c_diagram(n)
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
        assert "(set by Ce_in)" in out
        assert "(set by Ce_out)" in out

    def test_table_eseries_section_covers_end_caps(self, result, capsys):
        display_results(result, output_format="table", eseries="E24")
        out = capsys.readouterr().out
        assert "Ce_in calculated " in out
        assert "Ce_out calculated " in out

    def test_wizard_table_includes_end_caps_and_their_preferred_values(self, result):
        from filter_lib.wizard.formatting_helpers import format_bandpass_table
        from filter_lib.wizard.state import FilterState

        table = "\n".join(format_bandpass_table(result, FilterState(show_plot=False)))
        assert "Ce_in" in table
        assert "(set by Ce_out)" in table
        assert "Ce_in calculated " in table
        assert "Ce_out calculated " in table
