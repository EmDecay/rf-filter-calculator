"""The shared rule for which output and build options apply, and why the others do not.

The wizard and the web disable a control this rule says cannot apply; the last test
checks the rule against the CLI's own validation for every combination, so the three
surfaces accept the same choices.
"""

from __future__ import annotations

import argparse
from itertools import product

import pytest

from filter_lib.cli.bandpass_cmd import setup_parser as bandpass_setup
from filter_lib.cli.lowpass_cmd import setup_parser as lowpass_setup
from filter_lib.design.option_applicability import (
    ALLOW_SUB_PF,
    BUILD,
    ESERIES,
    ESERIES_RAW_MESSAGE,
    ESERIES_VALUES_ONLY_MESSAGE,
    LOSS_Q,
    LOSS_Q_DISABLED_MESSAGE,
    LOSS_Q_NOT_SHOWN_MESSAGE,
    OPTIONS,
    RAW_NEEDS_TABLE_MESSAGE,
    RAW_UNITS,
    SUB_PF_RAW_MESSAGE,
    SUB_PF_VALUES_ONLY_MESSAGE,
    TEXT_PLOT,
    TEXT_PLOT_NEEDS_TABLE_MESSAGE,
    TOROID_BUILD,
    TOROID_BUILD_NEEDS_TOROIDS_MESSAGE,
    TOROID_DETAIL,
    TOROID_DETAIL_NEEDS_TABLE_MESSAGE,
    OutputChoices,
    document_reason,
    inapplicable_options,
    option_reason,
    require_applicable,
)
from filter_lib.design.render_options import (
    BUILD_NEEDS_ESERIES_MESSAGE,
    BUILD_NEEDS_TABLE_OR_JSON_MESSAGE,
    BUILD_NOT_WITH_VALUES_ONLY_MESSAGE,
    SUB_PF_NEEDS_ESERIES_MESSAGE,
)
from filter_lib.shared.cli_bandpass_output_validation import (
    loss_q_not_shown_message,
    validate_bandpass_output_args,
)
from filter_lib.shared.cli_output_validation import validate_output_mode_args

TABLE_ONLY = {
    TEXT_PLOT: TEXT_PLOT_NEEDS_TABLE_MESSAGE,
    TOROID_DETAIL: TOROID_DETAIL_NEEDS_TABLE_MESSAGE,
}


def test_the_default_table_output_takes_every_option():
    assert inapplicable_options(OutputChoices()) == {}


def test_values_only_takes_raw_units_but_no_standard_values_plot_detail_or_build():
    assert inapplicable_options(OutputChoices(output_format="quiet")) == {
        ESERIES: ESERIES_VALUES_ONLY_MESSAGE,
        ALLOW_SUB_PF: SUB_PF_VALUES_ONLY_MESSAGE,
        **TABLE_ONLY,
        BUILD: BUILD_NOT_WITH_VALUES_ONLY_MESSAGE,
        LOSS_Q: LOSS_Q_DISABLED_MESSAGE,
    }


def test_json_takes_standard_values_and_the_build_but_no_table_options():
    assert inapplicable_options(OutputChoices(output_format="json", raw=True, build=True)) == {
        **TABLE_ONLY,
        RAW_UNITS: RAW_NEEDS_TABLE_MESSAGE,
    }


def test_csv_also_has_no_build():
    assert inapplicable_options(OutputChoices(output_format="csv")) == {
        **TABLE_ONLY,
        RAW_UNITS: RAW_NEEDS_TABLE_MESSAGE,
        BUILD: BUILD_NEEDS_TABLE_OR_JSON_MESSAGE,
        LOSS_Q: LOSS_Q_DISABLED_MESSAGE,
    }


def test_resonator_q_is_refused_with_the_shared_loss_q_message():
    assert LOSS_Q_NOT_SHOWN_MESSAGE == loss_q_not_shown_message(["Qu", "QL", "QC"])
    for output_format in ("table", "json"):
        assert option_reason(OutputChoices(output_format=output_format), LOSS_Q) is None
    for output_format in ("quiet", "csv"):
        with pytest.raises(ValueError) as caught:
            require_applicable(OutputChoices(output_format=output_format), [LOSS_Q])
        assert str(caught.value) == LOSS_Q_NOT_SHOWN_MESSAGE


def test_disabled_resonator_q_reason_names_the_outputs_that_use_it():
    """A disabled field cannot be cleared, so its reason never asks for removal."""
    reason = option_reason(OutputChoices(output_format="csv"), LOSS_Q)

    assert reason == LOSS_Q_DISABLED_MESSAGE
    assert "remove" not in reason.lower()
    assert "choose Table or JSON" in reason


@pytest.mark.parametrize(
    "document, expected",
    [
        ("json", None),
        ("spice-nominal", None),
        ("csv", LOSS_Q_DISABLED_MESSAGE),
        ("spice-exact", LOSS_Q_DISABLED_MESSAGE),
        ("response-json", LOSS_Q_DISABLED_MESSAGE),
        ("response-csv", LOSS_Q_DISABLED_MESSAGE),
    ],
)
def test_document_reason_judges_each_document_by_its_own_format(document, expected):
    assert document_reason(document, LOSS_Q) == expected
    with pytest.raises(ValueError, match="Unknown document"):
        document_reason("pdf", LOSS_Q)


def test_no_standard_values_rules_out_sub_pf_and_the_build():
    assert inapplicable_options(OutputChoices(eseries=None)) == {
        ALLOW_SUB_PF: SUB_PF_NEEDS_ESERIES_MESSAGE,
        BUILD: BUILD_NEEDS_ESERIES_MESSAGE,
    }


def test_raw_units_rule_out_standard_values_unless_the_build_uses_them():
    assert inapplicable_options(OutputChoices(raw=True)) == {
        ESERIES: ESERIES_RAW_MESSAGE,
        ALLOW_SUB_PF: SUB_PF_RAW_MESSAGE,
    }
    assert inapplicable_options(OutputChoices(raw=True, build=True)) == {}


def test_raw_units_that_do_not_apply_take_nothing_away():
    # Raw units do not apply to JSON, so the standard values still do.
    assert ESERIES not in inapplicable_options(OutputChoices(output_format="json", raw=True))


def test_with_raw_units_a_build_waiting_for_an_eseries_keeps_the_choice_open():
    """Choosing None with Raw units and the build ticked must be reversible."""
    assert inapplicable_options(OutputChoices(eseries=None, raw=True, build=True)) == {
        ALLOW_SUB_PF: SUB_PF_NEEDS_ESERIES_MESSAGE,
        BUILD: BUILD_NEEDS_ESERIES_MESSAGE,
    }
    # A build the format rules out does not need the E-series.
    reasons = inapplicable_options(OutputChoices(output_format="quiet", raw=True, build=True))
    assert reasons[ESERIES] == ESERIES_VALUES_ONLY_MESSAGE


def test_values_only_is_reported_before_raw_units():
    reasons = inapplicable_options(OutputChoices(output_format="quiet", raw=True))

    assert reasons[ESERIES] == ESERIES_VALUES_ONLY_MESSAGE
    assert RAW_UNITS not in reasons


def test_without_toroid_windings_there_are_none_to_simulate():
    reasons = inapplicable_options(OutputChoices(build=True, include_toroids=False))

    assert reasons == {TOROID_BUILD: TOROID_BUILD_NEEDS_TOROIDS_MESSAGE}


def test_reasons_come_in_option_order_and_name_their_subject():
    reasons = inapplicable_options(OutputChoices(output_format="quiet", include_toroids=False))

    assert list(reasons) == [option for option in OPTIONS if option in reasons]
    assert all(reason and not reason.endswith(".") for reason in reasons.values())


def test_option_reason_answers_for_one_option():
    choices = OutputChoices(output_format="csv")

    assert option_reason(choices, TEXT_PLOT) == TEXT_PLOT_NEEDS_TABLE_MESSAGE
    assert option_reason(choices, ESERIES) is None
    with pytest.raises(ValueError, match="Unknown option: tint"):
        option_reason(choices, "tint")


def test_require_applicable_refuses_only_selected_options_in_option_order():
    choices = OutputChoices(output_format="quiet")

    require_applicable(choices, [RAW_UNITS])
    require_applicable(choices, [])
    with pytest.raises(ValueError) as excinfo:
        require_applicable(choices, [BUILD, TEXT_PLOT])
    assert str(excinfo.value) == TEXT_PLOT_NEEDS_TABLE_MESSAGE
    with pytest.raises(ValueError, match="Unknown option: tint"):
        require_applicable(choices, ["tint"])


def test_unknown_output_format_is_refused():
    with pytest.raises(ValueError, match="Unknown output format: spice"):
        OutputChoices(output_format="spice")


FORMAT_FLAGS = {
    "table": (),
    "quiet": ("--quiet",),
    "json": ("--format", "json"),
    "csv": ("--format", "csv"),
}
ESERIES_FLAGS = {"default": (), "E12": ("-e", "E12"), "none": ("--no-match",)}
TOROIDS_FLAGS = {"best": (), "full": ("--toroid-full",), "none": ("--no-toroids",)}


# Per category: the design arguments, the parser, and whether resonator Q exists.
CATEGORIES = {
    "lowpass": (("bw", "pi", "10MHz"), lowpass_setup, (False,)),
    "bandpass": (("bw", "top", "-f", "14MHz", "-b", "500kHz"), bandpass_setup, (False, True)),
}


def _cli_accepts(category: str, argv: list[str]) -> bool:
    parser = argparse.ArgumentParser(prog=f"filter-calc {category}")
    CATEGORIES[category][1](parser)
    args = parser.parse_args(argv)
    try:
        validate_output_mode_args(args)
        if category == "bandpass":
            validate_bandpass_output_args(args)
    except SystemExit:
        return False
    return True


@pytest.mark.parametrize("category", list(CATEGORIES))
def test_the_rule_accepts_exactly_what_the_cli_accepts(capsys, category):
    """Every Format/E-series/toroid choice with every on/off box, against the CLI.

    An option counts as selected when its CLI flag is given; ``--no-match`` and
    ``--no-toroids`` are choices of the E-series and toroid controls, not selections
    the rule refuses, as in the CLI. Band-pass adds resonator Q (``--qu``).
    """
    design_argv, _setup, loss_q_values = CATEGORIES[category]
    disagreements = []
    for fmt, series, toroids, loss_q, raw, plot, sub_pf, build in product(
        FORMAT_FLAGS, ESERIES_FLAGS, TOROIDS_FLAGS, loss_q_values, *[(False, True)] * 4
    ):
        argv = [*design_argv, *FORMAT_FLAGS[fmt], *ESERIES_FLAGS[series]]
        argv += [*TOROIDS_FLAGS[toroids], *(("--qu", "200") if loss_q else ())]
        argv += [
            flag
            for on, flag in (
                (raw, "--raw"),
                (plot, "--plot"),
                (sub_pf, "--allow-sub-pf"),
                (build, "--sim-build"),
            )
            if on
        ]
        choices = OutputChoices(
            output_format=fmt,
            eseries=None if series == "none" else "E24",
            raw=raw,
            build=build,
            include_toroids=toroids != "none",
        )
        selected = [
            option
            for on, option in (
                (series == "E12", ESERIES),
                (sub_pf, ALLOW_SUB_PF),
                (toroids == "full", TOROID_DETAIL),
                (plot, TEXT_PLOT),
                (raw, RAW_UNITS),
                (build, BUILD),
                (loss_q, LOSS_Q),
            )
            if on
        ]
        try:
            require_applicable(choices, selected)
            rule_accepts = True
        except ValueError:
            rule_accepts = False
        if rule_accepts != _cli_accepts(category, argv):
            disagreements.append((argv, rule_accepts))
    capsys.readouterr()

    assert disagreements == []
