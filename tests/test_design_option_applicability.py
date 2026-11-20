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
    BUILD_INDUCTORS,
    BUILD_INDUCTORS_NEEDS_SUGGESTIONS_MESSAGE,
    CAPACITOR_GRADE,
    CAPACITOR_TOLERANCE,
    CSV_BUILD_INDUCTORS_MESSAGE,
    ESERIES,
    ESERIES_RAW_MESSAGE,
    ESERIES_VALUES_ONLY_MESSAGE,
    EXACT_SPICE_BUILD_INDUCTORS_MESSAGE,
    EXACT_SPICE_MATCHING_MESSAGE,
    INDUCTOR_DETAIL,
    INDUCTOR_DETAIL_NEEDS_TABLE_MESSAGE,
    LOSS_Q,
    LOSS_Q_DISABLED_MESSAGE,
    LOSS_Q_NOT_SHOWN_MESSAGE,
    MATCHING_OPTIONS,
    OPTIONS,
    RAW_NEEDS_TABLE_MESSAGE,
    RAW_UNITS,
    RESPONSE_DATA_BUILD_INDUCTORS_MESSAGE,
    RESPONSE_DATA_MATCHING_MESSAGE,
    STRAY_CAPACITANCE,
    SUB_PF_RAW_MESSAGE,
    SUB_PF_VALUES_ONLY_MESSAGE,
    TEXT_PLOT,
    TEXT_PLOT_NEEDS_TABLE_MESSAGE,
    OutputChoices,
    document_own_options,
    document_reason,
    document_reasons,
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
from filter_lib.shared.inductor_suggestion import (
    FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE,
    FORCED_KINDS,
)

TABLE_ONLY = {
    TEXT_PLOT: TEXT_PLOT_NEEDS_TABLE_MESSAGE,
    INDUCTOR_DETAIL: INDUCTOR_DETAIL_NEEDS_TABLE_MESSAGE,
}
# The capacitor grade, tolerance and stray follow the sub-pF option's rule, in its words.
POLICY_LABELS = {
    CAPACITOR_GRADE: "Capacitor grade",
    CAPACITOR_TOLERANCE: "Capacitor tolerance",
    STRAY_CAPACITANCE: "Stray capacitance",
}
POLICY_VALUES_ONLY = {
    option: f'"{label}" has no effect with Values only, which shows only calculated values'
    for option, label in POLICY_LABELS.items()
}
POLICY_RAW = {
    option: f'"{label}" has no effect with Raw units unless the build simulation is on'
    for option, label in POLICY_LABELS.items()
}
POLICY_NEEDS_ESERIES = {
    option: f'"{label}" needs an E-series (E12, E24, or E96) to choose standard capacitor values'
    for option, label in POLICY_LABELS.items()
}


def test_the_default_table_output_takes_every_option():
    assert inapplicable_options(OutputChoices()) == {}


def test_values_only_takes_raw_units_but_no_standard_values_plot_detail_or_build():
    assert inapplicable_options(OutputChoices(output_format="quiet")) == {
        ESERIES: ESERIES_VALUES_ONLY_MESSAGE,
        ALLOW_SUB_PF: SUB_PF_VALUES_ONLY_MESSAGE,
        **POLICY_VALUES_ONLY,
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
    assert LOSS_Q_NOT_SHOWN_MESSAGE == loss_q_not_shown_message(
        ["Qu", "Resonator inductor Q", "Resonator capacitor Q"]
    )
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


def test_the_calculated_values_deck_has_its_own_rule_for_chosen_parts():
    """Exact SPICE uses no chosen part: every matching option and the build inductors are
    left out of it (the CLI refuses them with an exact deck)."""
    assert set(MATCHING_OPTIONS) == {ESERIES, ALLOW_SUB_PF, *POLICY_LABELS}
    chosen_parts = frozenset({*MATCHING_OPTIONS, BUILD_INDUCTORS})
    assert document_own_options("spice-exact") == chosen_parts
    for document in ("json", "spice-nominal"):
        assert document_own_options(document) == frozenset()
    # The CSV has no build, so its best suggestion is the one Auto would build.
    assert document_own_options("csv") == frozenset({BUILD_INDUCTORS})
    assert document_reason("csv", BUILD_INDUCTORS) == CSV_BUILD_INDUCTORS_MESSAGE
    # Response data is the ideal response, which no chosen part changes.
    for document in ("response-json", "response-csv"):
        assert document_own_options(document) == chosen_parts
        for option in MATCHING_OPTIONS:
            assert document_reason(document, option) == RESPONSE_DATA_MATCHING_MESSAGE
        assert document_reason(document, BUILD_INDUCTORS) == RESPONSE_DATA_BUILD_INDUCTORS_MESSAGE
    reasons = document_reasons(OutputChoices(), "spice-exact")
    for option in MATCHING_OPTIONS:
        assert reasons[option] == EXACT_SPICE_MATCHING_MESSAGE
        assert document_reason("spice-exact", option) == EXACT_SPICE_MATCHING_MESSAGE
        assert document_reason("spice-nominal", option) is None
    assert reasons[BUILD_INDUCTORS] == EXACT_SPICE_BUILD_INDUCTORS_MESSAGE
    assert document_reason("spice-nominal", BUILD_INDUCTORS) is None


def test_no_standard_values_rules_out_sub_pf_and_the_build():
    assert inapplicable_options(OutputChoices(eseries=None)) == {
        ALLOW_SUB_PF: SUB_PF_NEEDS_ESERIES_MESSAGE,
        **POLICY_NEEDS_ESERIES,
        BUILD: BUILD_NEEDS_ESERIES_MESSAGE,
    }


def test_raw_units_rule_out_standard_values_unless_the_build_uses_them():
    assert inapplicable_options(OutputChoices(raw=True)) == {
        ESERIES: ESERIES_RAW_MESSAGE,
        ALLOW_SUB_PF: SUB_PF_RAW_MESSAGE,
        **POLICY_RAW,
    }
    assert inapplicable_options(OutputChoices(raw=True, build=True)) == {}


def test_raw_units_that_do_not_apply_take_nothing_away():
    # Raw units do not apply to JSON, so the standard values still do.
    assert ESERIES not in inapplicable_options(OutputChoices(output_format="json", raw=True))


def test_with_raw_units_a_build_waiting_for_an_eseries_keeps_the_choice_open():
    """Choosing None with Raw units and the build ticked must be reversible."""
    assert inapplicable_options(OutputChoices(eseries=None, raw=True, build=True)) == {
        ALLOW_SUB_PF: SUB_PF_NEEDS_ESERIES_MESSAGE,
        **POLICY_NEEDS_ESERIES,
        BUILD: BUILD_NEEDS_ESERIES_MESSAGE,
    }
    # A build the format rules out does not need the E-series.
    reasons = inapplicable_options(OutputChoices(output_format="quiet", raw=True, build=True))
    assert reasons[ESERIES] == ESERIES_VALUES_ONLY_MESSAGE


def test_values_only_is_reported_before_raw_units():
    reasons = inapplicable_options(OutputChoices(output_format="quiet", raw=True))

    assert reasons[ESERIES] == ESERIES_VALUES_ONLY_MESSAGE
    assert RAW_UNITS not in reasons


def test_without_inductor_suggestions_the_build_has_none_to_use():
    reasons = inapplicable_options(OutputChoices(build=True, inductor_detail="none"))

    assert reasons == {BUILD_INDUCTORS: BUILD_INDUCTORS_NEEDS_SUGGESTIONS_MESSAGE}
    # The CLI refuses a forced kind with --inductor-suggestions none in the same words.
    assert BUILD_INDUCTORS_NEEDS_SUGGESTIONS_MESSAGE == FORCED_KIND_NEEDS_SUGGESTIONS_MESSAGE


def test_reasons_come_in_option_order_and_name_their_subject():
    reasons = inapplicable_options(OutputChoices(output_format="quiet", inductor_detail="none"))

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


def test_unknown_inductor_detail_is_refused():
    with pytest.raises(ValueError, match="^Inductor suggestions must be best, full, compact"):
        OutputChoices(inductor_detail="most")


FORMAT_FLAGS = {
    "table": (),
    "quiet": ("--quiet",),
    "json": ("--format", "json"),
    "csv": ("--format", "csv"),
}
ESERIES_FLAGS = {"default": (), "E12": ("-e", "E12"), "none": ("--no-match",)}
# One capacitor policy option at a time (they share one rule), or none.
POLICY_FLAGS = {
    "none": (None, ()),
    "sub_pf": (ALLOW_SUB_PF, ("--allow-sub-pf",)),
    "grade": (CAPACITOR_GRADE, ("--capacitor-grade", "tight")),
    "tolerance": (CAPACITOR_TOLERANCE, ("--capacitor-tolerance", "3")),
    "stray": (STRAY_CAPACITANCE, ("--stray-capacitance", "0.1pF")),
}
INDUCTOR_FLAGS = {
    "best": (),
    "full": ("--inductor-suggestions", "full"),
    "compact": ("--inductor-suggestions", "compact"),
    "none": ("--inductor-suggestions", "none"),
}
# "Inductors in the build" is read only while the build is ticked.
BUILD_INDUCTORS_FLAGS = {
    "auto": (),
    "toroid": ("--build-inductors", "toroid"),
    "calculated": ("--build-inductors", "calculated"),
}


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
    """Every Format/E-series/inductor choice with every on/off box, against the CLI.

    An option counts as selected when its CLI flag is given; ``--no-match`` and
    ``--inductor-suggestions best`` or ``none`` are choices of the E-series and
    inductor controls, not selections the rule refuses, as in the CLI; ``full`` and
    ``compact`` select the table-only detail. "Inductors in the build" is read only
    with the build ticked, and only a forced kind counts as selected ("Calculated
    values" is what None means anyway). Band-pass adds resonator Q (``--qu``).
    """
    design_argv, _setup, loss_q_values = CATEGORIES[category]
    disagreements = []
    for fmt, series, detail, loss_q, policy, raw, plot, build in product(
        FORMAT_FLAGS,
        ESERIES_FLAGS,
        INDUCTOR_FLAGS,
        loss_q_values,
        POLICY_FLAGS,
        *[(False, True)] * 3,
    ):
        for build_inductors in BUILD_INDUCTORS_FLAGS if build else ("auto",):
            policy_option, policy_flags = POLICY_FLAGS[policy]
            argv = [*design_argv, *FORMAT_FLAGS[fmt], *ESERIES_FLAGS[series]]
            argv += [*INDUCTOR_FLAGS[detail], *(("--qu", "200") if loss_q else ()), *policy_flags]
            argv += [
                flag
                for on, flag in (
                    (raw, "--raw"),
                    (plot, "--plot"),
                    (build, "--sim-build"),
                )
                if on
            ]
            argv += BUILD_INDUCTORS_FLAGS[build_inductors]
            choices = OutputChoices(
                output_format=fmt,
                eseries=None if series == "none" else "E24",
                raw=raw,
                build=build,
                inductor_detail=detail,
            )
            selected = [
                option
                for on, option in (
                    (series == "E12", ESERIES),
                    (policy_option is not None, policy_option),
                    (detail in ("full", "compact"), INDUCTOR_DETAIL),
                    (plot, TEXT_PLOT),
                    (raw, RAW_UNITS),
                    (build, BUILD),
                    (build_inductors in FORCED_KINDS, BUILD_INDUCTORS),
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


@pytest.mark.parametrize("policy", [name for name in POLICY_FLAGS if name != "none"])
@pytest.mark.parametrize("realization", ["exact", "nominal-build"])
def test_spice_decks_take_capacitor_options_exactly_as_the_cli_does(policy, realization):
    option, flags = POLICY_FLAGS[policy]
    argv = [*CATEGORIES["lowpass"][0], "--format", "spice", "--spice-realization", realization]
    document = "spice-exact" if realization == "exact" else "spice-nominal"

    cli_accepts = _cli_accepts("lowpass", [*argv, *flags])

    assert cli_accepts is (document_reason(document, option) is None)
    assert cli_accepts is (realization == "nominal-build")
