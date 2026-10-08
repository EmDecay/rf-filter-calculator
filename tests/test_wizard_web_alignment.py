"""The wizard offers the web form's options with the same labels, order, and defaults.

The web templates are the reference for wording; these tests read them as text, so a
label changed on one surface only fails here. Defaults are compared with the web's
``form_defaults`` (which needs no web extra to import).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from filter_lib.wizard.build_options import (
    BUILD_FIELDS,
    BUILD_OPTION_LABEL,
    TOROID_BUILD_HELP,
    TOROID_BUILD_LABEL,
    build_field_values,
)
from filter_lib.wizard.design_field_validation import CUTOFF_LABELS
from filter_lib.wizard.screens.bandpass import (
    BANDWIDTH_EXAMPLE,
    CENTER_EXAMPLE,
    F_HIGH_EXAMPLE,
    F_LOW_EXAMPLE,
    RESONATOR_Q_NOTE,
)
from filter_lib.wizard.screens.output_options import (
    ESERIES_CHOICES,
    FORMAT_CHOICES,
    RAW_UNITS_HELP,
    RAW_UNITS_LABEL,
    SUB_PF_HELP,
    TEXT_PLOT_HELP,
    TEXT_PLOT_LABEL,
    TOROID_CHOICES,
)
from filter_lib.wizard.state import FilterState

TEMPLATES = Path(__file__).resolve().parents[1] / "filter_lib" / "web" / "templates" / "partials"


def _template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _segmented_choices(template: str, name: str) -> list[tuple[str, str]]:
    """The ``(value, label)`` pairs of a ``segmented("<name>", ...)`` call, in order."""
    call = re.search(rf'segmented\("{name}", "[^"]*", \[(.*?)\]', template, re.S)
    assert call, name
    return re.findall(r'\("([^"]+)", "([^"]+)"\)', call.group(1))


def _wizard_choices(choices) -> list[tuple[str, str]]:
    return [(value, label.split(" - ")[0]) for value, label in choices]


@pytest.mark.parametrize(
    "name, wizard",
    [
        ("output_format", FORMAT_CHOICES),
        ("eseries", ESERIES_CHOICES),
        ("toroids", TOROID_CHOICES),
    ],
)
def test_output_choices_have_the_web_values_labels_and_order(name, wizard):
    web = _segmented_choices(_template("output_options.html"), name)

    assert _wizard_choices(wizard) == web


def test_band_choice_has_the_web_labels():
    web = _segmented_choices(_template("bandpass_fields.html"), "band_spec")

    assert web == [("center", "Center and width"), ("edges", "Band edges")]


@pytest.mark.parametrize(
    "text",
    [
        SUB_PF_HELP,
        TEXT_PLOT_LABEL,
        TEXT_PLOT_HELP,
        RAW_UNITS_LABEL,
        RAW_UNITS_HELP,
        '"Standard capacitor values"',
        '"Toroid windings (table detail)"',
    ],
)
def test_output_labels_and_help_are_the_web_text(text):
    assert text in _template("output_options.html")


def test_build_fields_have_the_web_labels_help_and_order():
    template = _template("build_options.html")
    web = re.findall(r'text_field\("(build_\w+)", ([^,]+), help="([^"]*)"', template)

    assert [(label.strip('"'), help_text) for _name, label, help_text in web] == [
        (
            "labels.q_frequency" if field.input_id == "build-reference-frequency" else field.label,
            field.help,
        )
        for field in BUILD_FIELDS
    ]
    for text in (BUILD_OPTION_LABEL, TOROID_BUILD_LABEL, TOROID_BUILD_HELP):
        assert text in template


def test_resonator_q_note_is_the_web_text():
    assert RESONATOR_Q_NOTE in _template("bandpass_fields.html")


@pytest.mark.parametrize("category", ["lowpass", "highpass", "bandpass"])
def test_defaults_are_the_web_form_defaults(category):
    from filter_lib.web.form_parsing import form_defaults

    web = form_defaults(category)
    state = FilterState()

    assert state.filter_type == web["filter_type"]
    assert f"{state.impedance:g}" == web["impedance"]
    assert f"{state.ripple_db:g}" == web["ripple"]
    assert state.eseries == web["eseries"]
    assert state.toroid_detail == web["toroids"]
    assert state.output_format == web["output_format"]
    # Text plot unticked (CLI default); the build simulation off; toroid build ticked.
    assert state.show_plot is ("plot" in web)
    assert state.build_analysis_enabled is ("sim_build" in web)
    assert state.build_use_toroid_candidates is (web["toroid_build"] == "on")
    count = web["resonators" if category == "bandpass" else "components"]
    assert str(state.order) == count
    # Build fields are pre-filled with the CLI defaults, as on the web (D10).
    values = build_field_values(state)
    for name, value in web.items():
        if name.startswith("build_"):
            input_id = name.replace("_pct", "").replace("_", "-")
            assert values[input_id] == value, name


def test_band_and_cutoff_examples_are_the_web_examples():
    from filter_lib.web.form_parsing import EXAMPLE_FIELDS

    bandpass = EXAMPLE_FIELDS["bandpass"]
    assert (CENTER_EXAMPLE, BANDWIDTH_EXAMPLE) == (bandpass["frequency"], bandpass["bandwidth"])
    assert (F_LOW_EXAMPLE, F_HIGH_EXAMPLE) == (bandpass["f_low"], bandpass["f_high"])
    for category in ("lowpass", "highpass"):
        assert f"blank = {EXAMPLE_FIELDS[category]['frequency']}" in CUTOFF_LABELS[False]
