"""CLI subcommand ``run()`` contracts exercised with argparse Namespaces.

``_lp_args()``/``_hp_args()``/``_bp_args()`` mirror the parsed defaults so each test
overrides only the fields it exercises; validation branches run without re-parsing argv.
Usage problems exit 2 through the subcommand's argparse error; invalid numeric design
input raises ``ValueError`` (``cli.main`` turns it into exit 1).
"""

import csv
import io
import json
import math
from argparse import ArgumentParser, Namespace

import pytest

from filter_lib.bandpass import calculate_bandpass_filter
from filter_lib.bandpass.formatters import format_quiet as bandpass_format_quiet
from filter_lib.cli.bandpass_cmd import run as bandpass_run
from filter_lib.cli.bandpass_cmd import setup_parser as bandpass_setup
from filter_lib.cli.highpass_cmd import run as highpass_run
from filter_lib.cli.highpass_cmd import setup_parser as highpass_setup
from filter_lib.cli.lowpass_cmd import run as lowpass_run
from filter_lib.cli.lowpass_cmd import setup_parser as lowpass_setup
from filter_lib.shared.cli_aliases import (
    FILTER_EXPLANATIONS,
    FILTER_EXPLANATIONS_BANDPASS,
    FILTER_EXPLANATIONS_HIGHPASS,
)
from filter_lib.shared.cli_helpers import export_plot_data, validate_filter_args

# --- Namespace builders ---


def _lp_args(**overrides):
    """Build lowpass CLI Namespace."""
    defaults = dict(
        filter_type="butterworth",
        type_flag=None,
        frequency="10MHz",
        freq_flag=None,
        topology_pos="pi",
        topology_flag=None,
        impedance="50",
        components=3,
        ripple=None,
        raw=False,
        format="table",
        quiet=True,
        explain=False,
        eseries="E24",
        no_match=True,
        sim_matched=False,
        plot=False,
        plot_data=None,
        no_toroids=True,
        toroid_compact=False,
        toroid_full=False,
        _parser=ArgumentParser(prog="filter-calc lowpass"),
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def _hp_args(**overrides):
    """Build highpass CLI Namespace."""
    defaults = dict(
        filter_type="butterworth",
        type_flag=None,
        frequency="10MHz",
        freq_flag=None,
        topology_pos="t",
        topology_flag=None,
        impedance="50",
        components=3,
        ripple=None,
        raw=False,
        format="table",
        quiet=True,
        explain=False,
        eseries="E24",
        no_match=True,
        sim_matched=False,
        plot=False,
        plot_data=None,
        no_toroids=True,
        toroid_compact=False,
        toroid_full=False,
        _parser=ArgumentParser(prog="filter-calc highpass"),
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def _bp_args(**overrides):
    """Build bandpass CLI Namespace."""
    defaults = dict(
        filter_type="butterworth",
        type_flag=None,
        coupling_pos="top",
        coupling_flag=None,
        frequency="14.175MHz",
        bandwidth="350kHz",
        f_low=None,
        f_high=None,
        impedance="50",
        resonators=3,
        ripple=None,
        q_safety=2.0,
        qu=None,
        raw=False,
        format="table",
        quiet=True,
        explain=False,
        eseries="E24",
        no_match=True,
        sim_matched=False,
        plot=False,
        plot_data=None,
        no_toroids=True,
        toroid_compact=False,
        toroid_full=False,
        _parser=ArgumentParser(prog="filter-calc bandpass"),
    )
    defaults.update(overrides)
    return Namespace(**defaults)


_ARGS = {"lowpass": _lp_args, "highpass": _hp_args, "bandpass": _bp_args}
_RUN = {"lowpass": lowpass_run, "highpass": highpass_run, "bandpass": bandpass_run}
_CATEGORIES = tuple(_RUN)
_LADDERS = ("lowpass", "highpass")


def _run(category: str, **overrides) -> None:
    _RUN[category](_ARGS[category](**overrides))


def _usage_error(category: str, capsys, **overrides) -> str:
    """Run a command that must fail with an argparse usage error; return stderr."""
    with pytest.raises(SystemExit) as exc_info:
        _run(category, **overrides)
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert err.startswith(f"usage: filter-calc {category}")
    return err


@pytest.mark.parametrize(
    ("category", "setup", "argv"),
    [
        ("lowpass", lowpass_setup, ["butterworth", "pi", "10MHz"]),
        ("highpass", highpass_setup, ["butterworth", "t", "10MHz"]),
        ("bandpass", bandpass_setup, ["butterworth", "top", "-f", "14.175MHz", "-b", "350kHz"]),
    ],
)
def test_namespace_helpers_mirror_real_parser_defaults(category, setup, argv):
    """Helpers may only deviate from parsed defaults where they deliberately trim output."""
    parser = ArgumentParser()
    setup(parser)
    parsed = vars(parser.parse_args(argv))
    helper = vars(_ARGS[category]())
    deliberate = {"quiet": True, "no_match": True, "no_toroids": True}

    fields = set(helper) - {"_parser"} - set(deliberate)
    assert set(helper) - {"_parser"} <= set(parsed)
    assert {key: helper[key] for key in fields} == {key: parsed[key] for key in fields}
    assert {key: parsed[key] for key in deliberate} == dict.fromkeys(deliberate, False)


# --- validate_filter_args / export_plot_data ---


class TestValidateFilterArgs:
    @pytest.mark.parametrize("components", [2, 9])
    def test_accepts_order_boundaries(self, components):
        assert validate_filter_args(10e6, 50, components) is None

    @pytest.mark.parametrize(
        ("frequency", "impedance", "components", "message"),
        [
            (-10e6, 50, 5, "Frequency must be positive"),
            (0.0, 50, 5, "Frequency must be positive"),
            (10e6, 0, 5, "Impedance must be positive"),
            (10e6, 50, 1, "Components must be 2-9"),
            (10e6, 50, 10, "Components must be 2-9"),
            (10e6, 50, True, "Components must be 2-9"),
            (10e6, 50, 3.0, "Components must be 2-9"),
        ],
    )
    def test_rejects_out_of_range_values(self, frequency, impedance, components, message):
        with pytest.raises(ValueError, match=message):
            validate_filter_args(frequency, impedance, components)

    @pytest.mark.parametrize("frequency", [float("nan"), float("inf"), True, "10MHz", None])
    def test_rejects_non_finite_or_non_numeric_frequency(self, frequency):
        with pytest.raises(ValueError, match="Frequency must be positive and finite"):
            validate_filter_args(frequency, 50, 3)

    @pytest.mark.parametrize("impedance", [float("nan"), float("inf"), True, "50", None])
    def test_rejects_non_finite_or_non_numeric_impedance(self, impedance):
        with pytest.raises(ValueError, match="Impedance must be positive and finite"):
            validate_filter_args(10e6, impedance, 3)


class TestExportPlotData:
    def test_json_carries_metadata_and_points(self, capsys):
        meta = {"category": "lowpass", "response_type": "butterworth", "order": 3, "cutoff_hz": 1e6}
        assert export_plot_data(Namespace(plot_data="json"), [1e6], [-3.0], meta) is True

        out = json.loads(capsys.readouterr().out)
        assert out["filter"]["category"] == "lowpass"
        assert out["data"] == [{"frequency_hz": 1e6, "magnitude_db": -3.0}]

    def test_csv_writes_header_and_rows(self, capsys):
        assert export_plot_data(Namespace(plot_data="csv"), [1e6], [-3.0], {}) is True
        # Frequencies are written as their shortest round-trip decimal, matching JSON.
        assert capsys.readouterr().out == "frequency_hz,magnitude_db\n1000000.0,-3.00\n"

    def test_disabled_export_prints_nothing(self, capsys):
        assert export_plot_data(Namespace(plot_data=None), [1e6], [-3.0], {}) is False
        assert capsys.readouterr().out == ""


# --- Design dispatch ---

# Quiet listings at 10 MHz, 50 ohm, n=3 from published normalized prototypes:
# Butterworth g = (1, 2, 1); Chebyshev 0.5 dB g = (1.5963, 1.0967, 1.5963);
# Bessel (3 dB normalized) g = (0.3374, 0.9705, 2.2034).
# LP: C = g/(Z*w), L = g*Z/w.  HP: C = 1/(g*Z*w), L = Z/(g*w).
_LADDER_QUIET_CASES = [
    ("lowpass", "butterworth", "pi", "C1: 318.31 pF\nC2: 318.31 pF\nL1: 1.59 µH\n"),
    ("lowpass", "ch", "t", "L1: 1.27 µH\nL2: 1.27 µH\nC1: 349.09 pF\n"),
    ("lowpass", "bs", "pi", "C1: 107.40 pF\nC2: 701.36 pF\nL1: 772.30 nH\n"),
    ("highpass", "b", "t", "C1: 318.31 pF\nC2: 318.31 pF\nL1: 397.89 nH\n"),
    ("highpass", "c", "pi", "L1: 498.52 nH\nL2: 498.52 nH\nC1: 290.25 pF\n"),
    ("highpass", "bessel", "t", "C1: 943.42 pF\nC2: 144.46 pF\nL1: 819.96 nH\n"),
]


class TestDesignDispatch:
    @pytest.mark.parametrize(
        ("category", "filter_type", "topology", "expected"), _LADDER_QUIET_CASES
    )
    def test_ladder_type_alias_and_topology_reach_textbook_values(
        self, category, filter_type, topology, expected, capsys
    ):
        _run(category, filter_type=filter_type, topology_pos=topology)
        assert capsys.readouterr().out == expected

    def test_bandpass_run_matches_library_design(self, capsys):
        _run("bandpass", filter_type="bw", coupling_pos="t")

        expected = calculate_bandpass_filter(14.175e6, 350e3, 50.0, 3, "butterworth", "top")
        assert capsys.readouterr().out == bandpass_format_quiet(expected) + "\n"

    @pytest.mark.parametrize(
        ("category", "positional", "flagged"),
        [
            (
                "lowpass",
                dict(filter_type="chebyshev", frequency="5MHz"),
                dict(filter_type=None, type_flag="chebyshev", frequency=None, freq_flag="5MHz"),
            ),
            ("lowpass", dict(topology_pos="t"), dict(topology_pos=None, topology_flag="t")),
            (
                "highpass",
                dict(filter_type="bessel", frequency="5MHz"),
                dict(filter_type=None, type_flag="bessel", frequency=None, freq_flag="5MHz"),
            ),
            ("highpass", dict(topology_pos="pi"), dict(topology_pos=None, topology_flag="pi")),
            ("bandpass", dict(filter_type="bessel"), dict(filter_type=None, type_flag="bessel")),
            ("bandpass", dict(coupling_pos="t"), dict(coupling_pos=None, coupling_flag="t")),
        ],
    )
    def test_flag_forms_design_the_same_filter_as_positional_forms(
        self, category, positional, flagged, capsys
    ):
        _run(category)
        default_design = capsys.readouterr().out
        _run(category, **positional)
        positional_design = capsys.readouterr().out
        _run(category, **flagged)

        assert capsys.readouterr().out == positional_design
        if category != "bandpass" or "filter_type" in positional:
            # Non-default values prove the flag was read rather than defaulted.
            assert positional_design != default_design

    @pytest.mark.parametrize(
        ("category", "alias", "explanation"),
        [
            ("lowpass", "bs", FILTER_EXPLANATIONS["bessel"]),
            ("highpass", "c", FILTER_EXPLANATIONS_HIGHPASS["chebyshev"]),
            ("bandpass", "bw", FILTER_EXPLANATIONS_BANDPASS["butterworth"]),
        ],
    )
    def test_explain_prints_category_explanation_for_resolved_alias(
        self, category, alias, explanation, capsys
    ):
        design_fields = (
            dict(coupling_pos=None, frequency=None, bandwidth=None)
            if category == "bandpass"
            else dict(topology_pos=None, frequency=None)
        )
        _run(
            category,
            filter_type=alias,
            explain=True,
            quiet=False,
            no_match=False,
            no_toroids=False,
            **design_fields,
        )

        assert capsys.readouterr().out == explanation + "\n"


# --- Missing and duplicated design arguments ---


class TestDesignArgumentUsageErrors:
    @pytest.mark.parametrize("category", _CATEGORIES)
    def test_missing_filter_type(self, category, capsys):
        err = _usage_error(category, capsys, filter_type=None)
        assert "error: filter type required: butterworth/chebyshev/bessel" in err

    @pytest.mark.parametrize("category", _CATEGORIES)
    def test_explain_without_filter_type(self, category, capsys):
        err = _usage_error(
            category, capsys, filter_type=None, explain=True, quiet=False, no_match=False
        )
        assert "error: filter type required for --explain" in err

    @pytest.mark.parametrize("category", _LADDERS)
    def test_ladder_missing_frequency(self, category, capsys):
        err = _usage_error(category, capsys, frequency=None)
        assert "error: frequency required (try: filter-calc" in err

    @pytest.mark.parametrize("category", _LADDERS)
    def test_ladder_missing_topology(self, category, capsys):
        err = _usage_error(category, capsys, topology_pos=None)
        assert "error: topology required: pi or t, positional or -T" in err

    def test_bandpass_missing_coupling(self, capsys):
        err = _usage_error("bandpass", capsys, coupling_pos=None)
        assert "error: coupling topology required: top" in err

    @pytest.mark.parametrize(
        ("category", "overrides", "label"),
        [
            ("lowpass", {"type_flag": "chebyshev"}, "filter type"),
            ("lowpass", {"freq_flag": "5MHz"}, "frequency"),
            ("lowpass", {"topology_flag": "t"}, "topology"),
            ("highpass", {"type_flag": "chebyshev"}, "filter type"),
            ("highpass", {"freq_flag": "5MHz"}, "frequency"),
            ("highpass", {"topology_flag": "pi"}, "topology"),
            ("bandpass", {"type_flag": "chebyshev"}, "filter type"),
            ("bandpass", {"coupling_flag": "top"}, "coupling"),
        ],
    )
    def test_value_supplied_positionally_and_by_flag(self, category, overrides, label, capsys):
        err = _usage_error(category, capsys, **overrides)
        assert f"error: {label} supplied both positionally and by flag; use only one form" in err


# --- Chebyshev ripple ---


class TestRippleHandling:
    @pytest.mark.parametrize("category", _CATEGORIES)
    def test_ripple_ceiling_is_inclusive(self, category, capsys):
        _run(category, filter_type="chebyshev", ripple=3.0, quiet=False, format="json")
        assert json.loads(capsys.readouterr().out)["ripple_db"] == 3.0

    @pytest.mark.parametrize(
        ("category", "ripple", "message"),
        [
            ("lowpass", 3.01, "Ripple must be at most 3.0 dB"),
            ("highpass", 3.01, "Ripple must be at most 3.0 dB"),
            ("bandpass", 3.5, "Ripple must be at most 3.0 dB"),
            ("lowpass", -0.1, "Ripple must be positive"),
            ("highpass", -0.5, "Ripple must be positive"),
            ("bandpass", -0.5, "Ripple must be positive and finite"),
            ("lowpass", float("nan"), "ripple_db must be positive, finite"),
            ("bandpass", float("nan"), "Ripple must be positive and finite"),
        ],
    )
    def test_ripple_outside_supported_range_is_rejected(self, category, ripple, message):
        with pytest.raises(ValueError, match=message):
            _run(category, filter_type="chebyshev", ripple=ripple)

    @pytest.mark.parametrize("category", _CATEGORIES)
    def test_ripple_is_ignored_with_warning_for_non_chebyshev(self, category, capsys):
        _run(category)
        baseline = capsys.readouterr().out
        _run(category, ripple=0.5)
        captured = capsys.readouterr()

        assert captured.out == baseline
        assert captured.err == "Warning: ripple is only used by Chebyshev; ignoring\n"

    @pytest.mark.parametrize("category", _CATEGORIES)
    def test_chebyshev_ripple_is_used_without_warning(self, category, capsys):
        _run(category, filter_type="chebyshev", ripple=1.0, quiet=False, format="json")
        captured = capsys.readouterr()

        assert json.loads(captured.out)["ripple_db"] == 1.0
        assert "ripple is only used by Chebyshev" not in captured.err


# --- Bandpass-only inputs ---


class TestBandpassInputs:
    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            (
                {"f_low": "14MHz", "f_high": "14.35MHz"},
                "use (-f + -b) OR (--fl + --fh), not both",
            ),
            ({"f_low": "13MHz"}, "use (-f + -b) OR (--fl + --fh), not both"),
            ({"f_high": "15MHz"}, "use (-f + -b) OR (--fl + --fh), not both"),
            (
                {"frequency": None, "bandwidth": None},
                "frequency required: (-f + -b) or (--fl + --fh)",
            ),
            ({"bandwidth": None}, "-f/--frequency and -b/--bandwidth must be supplied together"),
            ({"frequency": None}, "-f/--frequency and -b/--bandwidth must be supplied together"),
            (
                {"frequency": None, "bandwidth": None, "f_low": "13MHz"},
                "--fl and --fh must be supplied together",
            ),
            (
                {"frequency": None, "bandwidth": None, "f_high": "15MHz"},
                "--fl and --fh must be supplied together",
            ),
        ],
    )
    def test_frequency_specification_usage_errors(self, overrides, message, capsys):
        err = _usage_error("bandpass", capsys, **overrides)
        assert f"error: {message}" in err

    @pytest.mark.parametrize(("f_low", "f_high"), [("15MHz", "14MHz"), ("14MHz", "14MHz")])
    def test_edge_frequencies_must_be_increasing(self, f_low, f_high):
        with pytest.raises(ValueError, match="Lower frequency must be less than upper"):
            _run("bandpass", frequency=None, bandwidth=None, f_low=f_low, f_high=f_high)

    @pytest.mark.parametrize("q_safety", [0.0, -1.5])
    def test_q_safety_must_be_positive(self, q_safety):
        with pytest.raises(ValueError, match="Q safety factor must be positive"):
            _run("bandpass", q_safety=q_safety)

    def test_chebyshev_requires_odd_resonator_count(self):
        with pytest.raises(ValueError, match="Chebyshev requires odd resonator count"):
            _run("bandpass", filter_type="chebyshev", resonators=4)

    def test_wide_fractional_bandwidth_warns_on_stderr(self, capsys):
        _run("bandpass", bandwidth="2MHz")
        captured = capsys.readouterr()

        assert captured.out.startswith("Cp1: ")
        assert captured.err.startswith(
            "Warning: FBW 14.1% exceeds the studied edge-calibration range (<=10%) for Top-C"
        )

    def test_table_reports_cohn_insertion_loss_at_standard_qu(self, capsys):
        _run("bandpass", quiet=False)
        out = capsys.readouterr().out

        assert "Est. insertion loss (Cohn): 7.0 dB @ Qu=100, 2.8 dB @ Qu=250" in out
        assert "Loss examples use complete-resonator unloaded Q (not inductor Q alone)." in out
        assert "Minimum usable Q" not in out
        assert "Q safety factor" not in out

    def test_user_qu_adds_a_third_estimate(self, capsys):
        _run("bandpass", quiet=False, qu=150.0)
        assert "2.8 dB @ Qu=250, 4.7 dB @ Qu=150" in capsys.readouterr().out

    @pytest.mark.parametrize("qu", [0.0, -5.0, float("inf"), float("nan")])
    def test_invalid_qu_is_rejected(self, qu):
        with pytest.raises(ValueError, match="must be positive and finite"):
            _run("bandpass", qu=qu)

    def test_json_carries_standard_il_estimates(self, capsys):
        _run("bandpass", quiet=False, format="json")
        estimates = json.loads(capsys.readouterr().out)["il_estimates"]

        assert set(estimates) == {"100", "250"}
        # Cohn's dissipation loss is inversely proportional to resonator Qu.
        assert estimates["100"] / estimates["250"] == pytest.approx(2.5)


# --- Output-mode combinations ---


class TestOutputModeConflicts:
    @pytest.mark.parametrize("category", _CATEGORIES)
    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"plot": True, "format": "json"}, "--plot cannot be used with --format json"),
            ({"plot": True, "format": "csv"}, "--plot cannot be used with --format csv"),
            ({"raw": True, "format": "json"}, "--raw cannot be used with --format json"),
            ({"quiet": True, "plot": True}, "--quiet and --plot cannot be used together"),
            (
                {"plot": True, "plot_data": "json"},
                "--plot-data is a standalone output mode; remove --plot",
            ),
        ],
    )
    def test_contradictory_output_modes_are_usage_errors(
        self, category, overrides, message, capsys
    ):
        settings = {"quiet": False, **overrides}
        err = _usage_error(category, capsys, **settings)
        assert f"error: {message}" in err


def _first_capacitor(category: str) -> str:
    return "Cp1" if category == "bandpass" else "C1"


class TestOutputModes:
    @pytest.mark.parametrize(
        ("category", "expected_line"),
        [
            ("lowpass", "│ C1: 3.183099e-10 F     │ L1: 1.591549e-06 H     │"),
            ("highpass", "│ C1: 3.183099e-10 F     │ L1: 3.978874e-07 H     │"),
            ("bandpass", "│ Cp1: 1.858357e-10 F    │ L1: 5.614516e-07 H     │"),
        ],
    )
    def test_raw_table_uses_si_notation_and_omits_preferred_values(
        self, category, expected_line, capsys
    ):
        _run(category, raw=True, quiet=False, no_match=False, eseries="E12")
        out = capsys.readouterr().out

        assert expected_line in out.splitlines()
        assert "Preferred-Value" not in out

    @pytest.mark.parametrize(
        ("category", "nearest_e96"),
        [("lowpass", "316.00"), ("highpass", "316.00"), ("bandpass", "187.00")],
    )
    def test_csv_reports_selected_series_for_capacitors_only(self, category, nearest_e96, capsys):
        _run(category, format="csv", quiet=False, no_match=False, eseries="E96")
        rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
        by_name = {row["Component"]: row for row in rows}

        first_cap = by_name[_first_capacitor(category)]
        assert (first_cap["NearestStdValue"], first_cap["NearestStdUnit"]) == (nearest_e96, "pF")
        for row in rows:
            expected_series = "E96" if row["Component"].startswith("C") else ""
            assert row["Eseries"] == expected_series

    @pytest.mark.parametrize("category", _CATEGORIES)
    def test_no_match_removes_preferred_values_from_every_format(self, category, capsys):
        _run(category, quiet=False, format="table")
        assert "Preferred-Value" not in capsys.readouterr().out

        _run(category, quiet=False, format="json")
        components = json.loads(capsys.readouterr().out)["components"]
        entries = [entry for group in components.values() for entry in group]
        assert entries
        assert not any("standard_match" in entry for entry in entries)

        _run(category, quiet=False, format="csv")
        header = capsys.readouterr().out.splitlines()[0]
        assert header == "Component,Value,Unit"

    @pytest.mark.parametrize("category", _LADDERS)
    def test_ladder_plot_data_json_is_the_analytic_response(self, category, capsys):
        _run(category, quiet=False, plot_data="json")
        payload = json.loads(capsys.readouterr().out)

        assert payload["filter"]["category"] == category
        assert payload["filter"]["cutoff_hz"] == 10e6
        points = payload["data"]
        assert len(points) == 51
        at_cutoff = next(p for p in points if p["frequency_hz"] == pytest.approx(10e6))
        # Butterworth is 3.01 dB down at the cutoff for every order.
        assert at_cutoff["magnitude_db"] == pytest.approx(-3.01, abs=0.01)

    @pytest.mark.parametrize(("category", "rows"), [("lowpass", 51), ("bandpass", 601)])
    def test_plot_data_csv_is_a_rectangular_numeric_table(self, category, rows, capsys):
        _run(category, quiet=False, plot_data="csv")
        lines = capsys.readouterr().out.splitlines()

        assert lines[0] == "frequency_hz,magnitude_db"
        values = [tuple(map(float, line.split(","))) for line in lines[1:]]
        assert len(values) == rows
        assert all(math.isfinite(f) and math.isfinite(db) for f, db in values)
        assert max(db for _, db in values) == pytest.approx(0.0, abs=0.05)

    @pytest.mark.parametrize("category", _LADDERS)
    def test_plot_with_table_shows_components_response_and_thresholds(self, category, capsys):
        _run(category, quiet=False, plot=True)
        out = capsys.readouterr().out

        assert out.index("Component Values") < out.index("Frequency Response (dB)")
        assert "Passband Detail (0 to -6 dB)" in out
        assert "dB Threshold Summary" in out
