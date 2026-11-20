"""The wizard offers the web form's options with the same labels, order, and defaults.

The web templates are the reference for wording; these tests read them as text, so a
label changed on one surface only fails here. A template that shows a shared label as
``labels.<key>`` is resolved through ``filter_lib/web/app.py``, also read as text.
Defaults are compared with the web's ``form_defaults`` (which needs no web extra to
import).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from filter_lib.design import inductor_option_inputs
from filter_lib.wizard.build_options import (
    BUILD_FIELDS,
    BUILD_OPTION_LABEL,
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
    BUILD_INDUCTOR_CHOICES,
    BUILD_INDUCTORS_HELP,
    BUILD_INDUCTORS_LABEL,
    ESERIES_CHOICES,
    FORMAT_CHOICES,
    INDUCTOR_CHOICES,
    INDUCTOR_DETAIL_HELP,
    INDUCTOR_DETAIL_LABEL,
    RAW_UNITS_HELP,
    RAW_UNITS_LABEL,
    SUB_PF_HELP,
    TEXT_PLOT_HELP,
    TEXT_PLOT_LABEL,
)
from filter_lib.wizard.state import FilterState

WEB = Path(__file__).resolve().parents[1] / "filter_lib" / "web"
TEMPLATES = WEB / "templates" / "partials"


def _template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _web_label(key: str):
    """``labels.<key>`` in the templates, as ``create_app`` sets it in ``app.py``.

    The entries these tests resolve name constants of
    ``filter_lib.design.inductor_option_inputs``, which the wizard also imports.
    """
    entry = re.search(rf'^\s*"{key}": (\w+),$', (WEB / "app.py").read_text("utf-8"), re.M)
    assert entry, key
    return getattr(inductor_option_inputs, entry.group(1))


def _segmented_choices(template: str, name: str) -> list[tuple[str, str]]:
    """The ``(value, label)`` pairs of a ``segmented("<name>", ...)`` call, in order.

    The choices are a literal list or a ``labels.<key>`` entry.
    """
    call = re.search(
        rf'segmented\("{name}", (?:"[^"]*"|labels\.\w+), (\[.*?\]|labels\.\w+)', template, re.S
    )
    assert call, name
    choices = call.group(1)
    if choices.startswith("labels."):
        return [tuple(pair) for pair in _web_label(choices.removeprefix("labels."))]
    return re.findall(r'\("([^"]+)", "([^"]+)"\)', choices)


def _wizard_choices(choices) -> list[tuple[str, str]]:
    """The wizard's labels without the description after " - " or the default marker."""
    return [(value, label.split(" - ")[0].removesuffix(" (default)")) for value, label in choices]


@pytest.mark.parametrize(
    "template, name, wizard",
    [
        ("output_options.html", "output_format", FORMAT_CHOICES),
        ("output_options.html", "eseries", ESERIES_CHOICES),
        ("output_options.html", "inductor_suggestions", INDUCTOR_CHOICES),
        ("build_options.html", "build_inductors", BUILD_INDUCTOR_CHOICES),
    ],
)
def test_output_choices_have_the_web_values_labels_and_order(template, name, wizard):
    web = _segmented_choices(_template(template), name)

    assert _wizard_choices(wizard) == web


@pytest.mark.parametrize(
    "template, name, label, help_text",
    [
        (
            "output_options.html",
            "inductor_suggestions",
            INDUCTOR_DETAIL_LABEL,
            INDUCTOR_DETAIL_HELP,
        ),
        ("build_options.html", "build_inductors", BUILD_INDUCTORS_LABEL, BUILD_INDUCTORS_HELP),
    ],
)
def test_inductor_controls_have_the_web_label_and_help(template, name, label, help_text):
    text = _template(template)
    call = re.search(rf'segmented\("{name}", labels\.(\w+), ', text)

    assert call, name
    key = call.group(1)
    assert _web_label(key) == label
    assert f"{{{{ labels.{key}_help }}}}" in text
    assert _web_label(f"{key}_help") == help_text


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
    assert BUILD_OPTION_LABEL in template


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
    assert state.inductor_detail == web["inductor_suggestions"]
    assert state.output_format == web["output_format"]
    # Text plot unticked (CLI default); the build simulation off; build inductors Auto.
    assert state.show_plot is ("plot" in web)
    assert state.build_analysis_enabled is ("sim_build" in web)
    assert state.build_inductors == web["build_inductors"]
    count = web["resonators" if category == "bandpass" else "components"]
    assert str(state.order) == count
    # Build fields are pre-filled with the CLI defaults, as on the web (D10).
    values = build_field_values(state)
    for name, value in web.items():
        if name.startswith("build_") and name != "build_inductors":
            input_id = name.replace("_pct", "").replace("_", "-")
            assert values[input_id] == value, name


def test_band_and_cutoff_examples_are_the_web_examples():
    from filter_lib.web.form_parsing import EXAMPLE_FIELDS

    bandpass = EXAMPLE_FIELDS["bandpass"]
    assert (CENTER_EXAMPLE, BANDWIDTH_EXAMPLE) == (bandpass["frequency"], bandpass["bandwidth"])
    assert (F_LOW_EXAMPLE, F_HIGH_EXAMPLE) == (bandpass["f_low"], bandpass["f_high"])
    for category in ("lowpass", "highpass"):
        assert f"blank = {EXAMPLE_FIELDS[category]['frequency']}" in CUTOFF_LABELS[False]
