"""What the CLI prints and exports is the value it calculated.

JSON carries the calculation API's exact binary64 values; CSV, quiet, and table text carry
the same values in an engineering unit, rounded to two decimals of that unit; raw text keeps
seven significant figures. Every format lists the same components in the same order, and
preferred-value columns agree with the JSON selection they summarize.
"""

import contextlib
import csv
import functools
import io
import json
import math
import sys
from unittest.mock import patch

import pytest

from filter_lib import cli
from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.highpass import calculations as highpass
from filter_lib.lowpass import calculations as lowpass
from filter_lib.shared.formatting import (
    format_fixed,
    format_restated_frequency,
    format_restated_value,
)

_SCALE = {
    "fF": 1e-15,
    "pF": 1e-12,
    "nF": 1e-9,
    "µF": 1e-6,
    "mF": 1e-3,
    "F": 1.0,
    "pH": 1e-12,
    "nH": 1e-9,
    "µH": 1e-6,
    "mH": 1e-3,
    "H": 1.0,
}


@functools.cache
def _cli(*argv: str) -> str:
    """Run the real entry point once per distinct command and return stdout."""
    stdout = io.StringIO()
    with patch.object(sys, "argv", ["filter-calc", *argv]), contextlib.redirect_stdout(stdout):
        cli.main()
    return stdout.getvalue()


def _strict_json(text: str) -> dict:
    def reject(constant: str):
        raise AssertionError(f"non-standard JSON constant {constant}")

    return json.loads(text, parse_constant=reject)


def _json_components(payload: dict) -> dict[str, float]:
    return {
        item["name"]: item.get("value_farads", item.get("value_henries"))
        for group in payload["components"].values()
        for item in group
    }


def _assert_engineering_text_matches(number: str, unit: str, value: float) -> None:
    """Engineering text is the value in a sensible prefix, rounded to 0.01 of that prefix."""
    scale = _SCALE[unit]
    assert "e" not in number, f"{value!r} fell back to scientific notation"
    assert abs(float(number) * scale - value) <= 0.005 * scale * (1 + 1e-12)
    if unit not in {"fF", "mF", "H", "pH"}:
        # Between the smallest and largest prefixes the mantissa stays in [1, 1000).
        assert 1 <= float(number) < 1000, (number, unit)


# (command, ladder parameters used for the API call). The designs span every prefix from
# pH to mH and from pF to µF, both topologies, and all three response types.
_LADDER_DESIGNS = [
    (("lp", "bw", "pi", "7.1MHz", "-n", "5"), ("lowpass", "butterworth", 7.1e6, 50.0, 5, None)),
    (
        ("lp", "ch", "t", "28MHz", "-n", "7", "-r", "1.0", "-z", "75"),
        ("lowpass", "chebyshev", 28e6, 75.0, 7, 1.0),
    ),
    (
        ("lp", "bs", "t", "2.4GHz", "-n", "3", "-z", "12.5"),
        ("lowpass", "bessel", 2.4e9, 12.5, 3, None),
    ),
    (
        ("lp", "bw", "pi", "1kHz", "-n", "2", "-z", "1k"),
        ("lowpass", "butterworth", 1e3, 1e3, 2, None),
    ),
    (
        ("hp", "ch", "t", "3.5MHz", "-n", "9", "-r", "0.01"),
        ("highpass", "chebyshev", 3.5e6, 50.0, 9, 0.01),
    ),
    (
        ("hp", "bs", "pi", "455kHz", "-n", "4", "-z", "600"),
        ("highpass", "bessel", 455e3, 600.0, 4, None),
    ),
    (("hp", "bw", "t", "100Hz", "-n", "6"), ("highpass", "butterworth", 100.0, 50.0, 6, None)),
    # Sub-nanohenry inductors (15.9 pH) print in picohenries, not as "0.02 nH".
    (
        ("lp", "bw", "t", "10GHz", "-n", "3", "-z", "1"),
        ("lowpass", "butterworth", 10e9, 1.0, 3, None),
    ),
]


def _ladder_api_values(category, response, frequency, impedance, order, ripple, topology):
    module = lowpass if category == "lowpass" else highpass
    function = getattr(module, f"calculate_{response}")
    arguments = (frequency, impedance, ripple, order) if ripple else (frequency, impedance, order)
    first, second, _ = function(*arguments, topology=topology)
    capacitors, inductors = (first, second) if category == "lowpass" else (second, first)
    return capacitors, inductors


@pytest.fixture(params=_LADDER_DESIGNS, ids=lambda design: " ".join(design[0]))
def ladder(request):
    command, (category, response, frequency, impedance, order, ripple) = request.param
    capacitors, inductors = _ladder_api_values(
        category, response, frequency, impedance, order, ripple, command[2]
    )
    expected = {f"C{i + 1}": value for i, value in enumerate(capacitors)}
    expected |= {f"L{i + 1}": value for i, value in enumerate(inductors)}
    # Ladder listings lead with the element type at the first ladder position.
    first = "C" if (category == "lowpass") == (command[2] == "pi") else "L"
    order_names = sorted(expected, key=lambda name: (name[0] != first, int(name[1:])))
    return {
        "command": command,
        "expected": expected,
        "names": order_names,
        "frequency": frequency,
        "impedance": impedance,
        "order": order,
        "ripple": ripple,
    }


class TestLadderOutputsCarryTheCalculatedValues:
    def test_json_is_the_exact_api_result(self, ladder):
        payload = _strict_json(_cli(*ladder["command"], "--format", "json", "--no-toroids"))

        assert _json_components(payload) == ladder["expected"]
        assert [name for name in _json_components(payload)] == ladder["names"]
        assert payload["cutoff_frequency_hz"] == ladder["frequency"]
        assert payload["impedance_ohms"] == ladder["impedance"]
        assert payload["order"] == ladder["order"]
        assert payload.get("ripple_db") == ladder["ripple"]

    def test_csv_values_and_units_round_the_api_result(self, ladder):
        rows = list(csv.DictReader(io.StringIO(_cli(*ladder["command"], "--format", "csv"))))

        assert [row["Component"] for row in rows] == ladder["names"]
        for row in rows:
            _assert_engineering_text_matches(
                row["Value"], row["Unit"], ladder["expected"][row["Component"]]
            )

    def test_quiet_and_table_print_the_csv_text(self, ladder):
        rows = list(csv.DictReader(io.StringIO(_cli(*ladder["command"], "--format", "csv"))))
        csv_text = [f"{row['Component']}: {row['Value']} {row['Unit']}" for row in rows]
        quiet = _cli(*ladder["command"], "-q", "--no-match", "--no-toroids").splitlines()
        table_cells = {
            cell.strip()
            for line in _cli(*ladder["command"], "--no-match", "--no-toroids").splitlines()
            if line.startswith("│ ")
            for cell in line.strip("│").split("│")
        }

        assert quiet == csv_text
        assert set(csv_text) <= table_cells

    def test_raw_text_keeps_seven_significant_figures(self, ladder):
        quiet = _cli(*ladder["command"], "-q", "--raw", "--no-toroids", "--no-match").splitlines()
        table = _cli(*ladder["command"], "--raw", "--no-toroids", "--no-match")

        assert [line.split(":")[0] for line in quiet] == ladder["names"]
        for line in quiet:
            name, text = line.split(": ")
            number, unit = text.split(" ")
            assert unit == ("F" if name.startswith("C") else "H")
            assert float(number) == pytest.approx(ladder["expected"][name], rel=5e-7, abs=0)
            assert f"│ {line}" in table

    def test_table_header_restates_the_requested_design(self, ladder):
        lines = _cli(*ladder["command"], "--no-match", "--no-toroids").splitlines()

        assert f"Cutoff Frequency:    {format_restated_frequency(ladder['frequency'])}" in lines
        assert f"Impedance Z0:        {format_restated_value(ladder['impedance'])} Ohm" in lines
        assert f"Order:               {ladder['order']}" in lines
        ripple_lines = [line for line in lines if line.startswith("Ripple:")]
        expected_ripple = (
            [f"Ripple:              {ladder['ripple']} dB"] if ladder["ripple"] else []
        )
        assert ripple_lines == expected_ripple


def _preferred_value_rows(command: tuple[str, ...], series: str):
    payload = _strict_json(_cli(*command, "--format", "json", "-e", series, "--no-toroids"))
    matches = {
        item["name"]: item["standard_match"]
        for group in payload["components"].values()
        for item in group
        if "standard_match" in item
    }
    rows = list(csv.DictReader(io.StringIO(_cli(*command, "--format", "csv", "-e", series))))
    return matches, [row for row in rows if row["Component"] in matches]


@pytest.mark.parametrize("series", ["E12", "E24", "E96"])
@pytest.mark.parametrize(
    "command",
    [
        ("lp", "bw", "pi", "7.1MHz", "-n", "5"),
        ("hp", "ch", "t", "3.5MHz", "-n", "9", "-r", "0.01"),
        ("bp", "bw", "top", "-f", "14.175MHz", "-b", "350kHz"),
    ],
    ids=["lowpass", "highpass", "bandpass"],
)
def test_csv_and_table_preferred_values_restate_the_json_selection(command, series):
    matches, rows = _preferred_value_rows(command, series)
    table = _cli(*command, "-e", series, "--no-toroids").splitlines()

    assert len(rows) == len(matches) > 0
    for row in rows:
        match = matches[row["Component"]]
        nearest = match["nearest"]
        _assert_engineering_text_matches(
            row["NearestStdValue"], row["NearestStdUnit"], nearest["value_farads"]
        )
        assert row["NearestStdErrorPct"] == format_fixed(nearest["error_pct"], 1)
        assert row["Eseries"] == series
        assert row["RecommendationStatus"] == match["status"]
        selected = match["selected"]
        assert row["RecommendedStdKind"] == (selected["kind"] if selected else "none")
        if selected:
            parts = [part["value_farads"] for part in selected["components"]]
            texts = row["RecommendedStdValues"].split(" || ")
            assert len(texts) == len(parts)
            for text, part in zip(texts, parts):
                _assert_engineering_text_matches(*text.split(" "), part)
            assert selected["value_farads"] == pytest.approx(sum(parts), rel=1e-12, abs=0)
            assert row["RecommendedStdErrorPct"] == format_fixed(selected["error_pct"], 1)
        # The table prints the same nearest part and one-decimal error for this capacitor.
        calculated = table.index(f"{row['Component']} Calculated: {row['Value']} {row['Unit']}")
        nearest_line = table[calculated + 1]
        assert f"{row['NearestStdValue']} {row['NearestStdUnit']}" in nearest_line
        error = float(row["NearestStdErrorPct"])
        assert nearest_line.endswith(f"({'+' if error > 0 else ''}{row['NearestStdErrorPct']}%)")


_BANDPASS_DESIGNS = [
    (
        ("bp", "bw", "top", "-f", "14.175MHz", "-b", "350kHz"),
        (14.175e6, 350e3, 50.0, 3, "butterworth", 0.5),
    ),
    (
        ("bp", "ch", "top", "-f", "7.15MHz", "-b", "200kHz", "-n", "5", "-r", "0.5"),
        (7.15e6, 200e3, 50.0, 5, "chebyshev", 0.5),
    ),
    (
        ("bp", "bs", "top", "-f", "455kHz", "-b", "10kHz", "-n", "4", "-z", "75"),
        (455e3, 10e3, 75.0, 4, "bessel", 0.5),
    ),
]


@pytest.fixture(params=_BANDPASS_DESIGNS, ids=lambda design: " ".join(design[0][1:]))
def bandpass(request):
    command, (f0, bw, z0, n, response, ripple) = request.param
    result = calculate_bandpass_filter(f0, bw, z0, n, response, "top", ripple_db=ripple)
    expected = {f"Cp{i + 1}": value for i, value in enumerate(result["c_tank"])}
    expected |= {f"L{i + 1}": result["L_resonant"] for i in range(n)}
    expected |= {f"Cs{i + 1}{i + 2}": value for i, value in enumerate(result["c_coupling"])}
    expected |= {"Ce_in": result["c_end_in"], "Ce_out": result["c_end_out"]}
    return {"command": command, "result": result, "expected": expected}


class TestBandpassOutputsCarryTheCalculatedValues:
    def test_json_is_the_exact_api_result(self, bandpass):
        payload = _strict_json(_cli(*bandpass["command"], "--format", "json", "--no-toroids"))
        result = bandpass["result"]

        assert _json_components(payload) == bandpass["expected"]
        assert (payload["f_low_hz"], payload["f_high_hz"]) == (result["f_low"], result["f_high"])
        assert payload["center_frequency_hz"] == result["f0"]
        assert payload["bandwidth_hz"] == result["bw"]
        assert payload["impedance_ohms"] == result["z0"]

    def test_csv_quiet_raw_and_table_agree_with_the_api_result(self, bandpass):
        command, expected = bandpass["command"], bandpass["expected"]
        rows = list(csv.DictReader(io.StringIO(_cli(*command, "--format", "csv"))))
        quiet = _cli(*command, "-q", "--no-match", "--no-toroids").splitlines()
        raw = _cli(*command, "-q", "--raw", "--no-match", "--no-toroids").splitlines()
        table = _cli(*command, "--no-match", "--no-toroids")
        raw_table = _cli(*command, "--raw", "--no-match", "--no-toroids")

        assert sorted(row["Component"] for row in rows) == sorted(expected)
        assert [line.split(":")[0] for line in quiet] == [row["Component"] for row in rows]
        for row, quiet_line, raw_line in zip(rows, quiet, raw):
            name = row["Component"]
            _assert_engineering_text_matches(row["Value"], row["Unit"], expected[name])
            assert quiet_line == f"{name}: {row['Value']} {row['Unit']}"
            assert f"│ {quiet_line} " in table
            raw_number, raw_unit = raw_line.split(": ")[1].split(" ")
            assert raw_unit == ("H" if name.startswith("L") else "F")
            assert float(raw_number) == pytest.approx(expected[name], rel=5e-7, abs=0)
            assert f"│ {raw_line} " in raw_table

    def test_table_header_restates_calculated_band(self, bandpass):
        payload = _strict_json(_cli(*bandpass["command"], "--format", "json", "--no-toroids"))
        lines = _cli(*bandpass["command"], "--no-match", "--no-toroids").splitlines()

        for label, key in (
            ("Center Frequency f₀: ", "center_frequency_hz"),
            ("Bandwidth BW:        ", "bandwidth_hz"),
        ):
            assert f"{label}{format_restated_frequency(payload[key])}" in lines
        # Edges carry enough digits for their difference to restate the bandwidth.
        edge = {
            label: next(line for line in lines if line.startswith(label))
            for label in ("Lower Cutoff fₗ:", "Upper Cutoff fₕ:")
        }
        for label, key in (("Lower Cutoff fₗ:", "f_low_hz"), ("Upper Cutoff fₕ:", "f_high_hz")):
            number, unit = edge[label].removeprefix(label).split()
            printed = float(number) * {"kHz": 1e3, "MHz": 1e6}[unit]
            assert abs(printed - payload[key]) <= 1e-4 * payload["bandwidth_hz"]
        assert f"Fractional BW:       {payload['fractional_bw'] * 100:.2f}%" in lines
        assert f"Resonators:          {payload['n_resonators']}" in lines
        # Top-C end capacitors realize the printed external Q.
        assert f"External Q (input):  {payload['external_q']['input']:.2f} (realized by Ce_in)" in (
            lines
        )


def test_edge_specified_bandpass_reports_the_requested_edges_in_every_format():
    command = ("bp", "ch", "top", "--fl", "7MHz", "--fh", "7.3MHz", "-n", "5", "-r", "0.5")
    payload = _strict_json(_cli(*command, "--format", "json", "--no-toroids"))
    values = _json_components(payload)
    rows = list(csv.DictReader(io.StringIO(_cli(*command, "--format", "csv", "--no-match"))))
    quiet = _cli(*command, "-q", "--no-match", "--no-toroids").splitlines()
    table = _cli(*command, "--no-match", "--no-toroids").splitlines()

    # Edges reconstructed from the geometric center reproduce the request to rounding.
    assert payload["f_low_hz"] == pytest.approx(7e6, rel=1e-14, abs=0)
    assert payload["f_high_hz"] == pytest.approx(7.3e6, rel=1e-14, abs=0)
    assert "Lower Cutoff fₗ:     7 MHz" in table
    assert "Upper Cutoff fₕ:     7.3 MHz" in table
    assert quiet == [f"{row['Component']}: {row['Value']} {row['Unit']}" for row in rows]
    for row in rows:
        _assert_engineering_text_matches(row["Value"], row["Unit"], values[row["Component"]])


@pytest.mark.parametrize(
    "spelling",
    [
        "10MHz",
        "10mhz",
        "10 MHz",
        "10M",
        "10m",
        "10e6",
        "1e7",
        "10000000",
        "10000000Hz",
        "10000kHz",
        "10000 k",
        "0.01GHz",
        "0.01g",
    ],
)
def test_documented_frequency_spellings_design_the_same_filter(spelling):
    payload = _strict_json(_cli("lp", "bw", "pi", spelling, "--format", "json", "--no-toroids"))
    reference = _strict_json(_cli("lp", "bw", "pi", "10MHz", "--format", "json", "--no-toroids"))

    assert payload["cutoff_frequency_hz"] == 10e6
    assert payload == reference


@pytest.mark.parametrize(
    "spelling", ["1000", "1k", "1K", "1kohm", "1 kohm", "1kΩ", "1000Ω", "1000 ohm", "0.001M"]
)
def test_documented_impedance_spellings_design_the_same_filter(spelling):
    payload = _strict_json(
        _cli("hp", "bw", "t", "1MHz", "-z", spelling, "--format", "json", "--no-toroids")
    )

    assert payload["impedance_ohms"] == 1000.0
    # HP T series capacitor: C = 1/(g * Z * w) with g1 = 1 for a third-order Butterworth.
    first = payload["components"]["capacitors"][0]["value_farads"]
    assert first == pytest.approx(1 / (1000.0 * 2 * math.pi * 1e6), rel=1e-12, abs=0)


class TestResponseDataAgreesAcrossFormats:
    @pytest.mark.parametrize(
        "command",
        [
            ("lp", "ch", "pi", "10MHz", "-n", "5", "-r", "0.5"),
            ("hp", "bs", "t", "10MHz", "-n", "5"),
            ("bp", "ch", "top", "-f", "14.2MHz", "-b", "500kHz", "-n", "5", "-r", "0.5"),
        ],
        ids=["lowpass", "highpass", "bandpass"],
    )
    def test_json_and_csv_plot_data_are_the_same_samples(self, command):
        points = _strict_json(_cli(*command, "--plot-data", "json"))["data"]
        rows = _cli(*command, "--plot-data", "csv").splitlines()

        assert rows[0] == "frequency_hz,magnitude_db"
        assert [f"{p['frequency_hz']!r},{p['magnitude_db']:.2f}" for p in points] == rows[1:]

    @pytest.mark.parametrize(
        ("command", "expected_db"),
        [
            # Chebyshev cutoff is the ripple-band edge: attenuation equals the ripple there.
            (("lp", "ch", "pi", "10MHz", "-n", "5", "-r", "0.5"), -0.5),
            (("hp", "ch", "t", "10MHz", "-n", "7", "-r", "1.5"), -1.5),
            # Butterworth and 3 dB-normalized Bessel are 3.01 dB down at the cutoff.
            (("lp", "bs", "t", "10MHz", "-n", "4"), -3.01),
            (("hp", "bs", "t", "10MHz", "-n", "5"), -3.01),
        ],
    )
    def test_ladder_sample_at_cutoff_is_the_analytic_attenuation(self, command, expected_db):
        payload = _strict_json(_cli(*command, "--plot-data", "json"))
        at_cutoff = [p["magnitude_db"] for p in payload["data"] if p["frequency_hz"] == 10e6]

        assert payload["filter"]["cutoff_hz"] == 10e6
        assert at_cutoff == [expected_db]

    def test_bandpass_samples_include_the_calculated_edges_at_half_power(self):
        command = ("bp", "ch", "top", "-f", "14.2MHz", "-b", "500kHz", "-n", "5", "-r", "0.5")
        design = _strict_json(_cli(*command, "--format", "json", "--no-toroids"))
        response = _strict_json(_cli(*command, "--plot-data", "json"))
        samples = {p["frequency_hz"]: p["magnitude_db"] for p in response["data"]}

        assert response["filter"]["f0_hz"] == design["center_frequency_hz"]
        assert response["filter"]["bw_hz"] == design["bandwidth_hz"]
        assert samples[design["f_low_hz"]] == samples[design["f_high_hz"]] == -3.01
        assert samples[design["center_frequency_hz"]] == 0.0
