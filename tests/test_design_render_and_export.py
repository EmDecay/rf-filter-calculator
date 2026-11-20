"""The shared dispatcher prints exactly what ``filter-calc`` prints.

Every case renders a ``DesignResult`` through ``render_lines``, ``export_spice``, or
``export_response_data`` and compares the document with live CLI stdout for the same
design, so the CLI, wizard, and web surfaces cannot drift from one another.
"""

from __future__ import annotations

import dataclasses
import json
import re

import pytest

from filter_lib.design import (
    DesignRequest,
    DesignResult,
    RenderOptions,
    design,
    export_response_data,
    export_spice,
    render_lines,
    response_series,
)
from filter_lib.design.render import BUILD_TARGET_NOTE
from filter_lib.design.render_options import BUILD_NEEDS_ESERIES_MESSAGE
from filter_lib.shared.build_types import BuildConfig
from tests.cli_parity_helpers import cli_stdout

LP_ARGV = ("lp", "ch", "t", "7.1MHz", "-n", "5", "-z", "75", "-r", "0.25")
HP_ARGV = ("hp", "bs", "pi", "7.1MHz", "-n", "4", "-z", "75")
BP_ARGV = (
    "bp",
    "ch",
    "top",
    "-f",
    "14.175MHz",
    "-b",
    "350kHz",
    "-n",
    "5",
    "-z",
    "75",
    "-r",
    "0.25",
)
FAST_BUILD_ARGV = ("--sim-build", "--analysis-points", "51")


def _request(category: str) -> DesignRequest:
    if category == "lowpass":
        return DesignRequest("lowpass", "chebyshev", "t", 7.1e6, 75.0, 5, ripple_db=0.25)
    if category == "highpass":
        return DesignRequest("highpass", "bessel", "pi", 7.1e6, 75.0, 4)
    return DesignRequest(
        "bandpass", "chebyshev", "top", 14.175e6, 75.0, 5, ripple_db=0.25, bandwidth_hz=350e3
    )


ARGV = {"lowpass": LP_ARGV, "highpass": HP_ARGV, "bandpass": BP_ARGV}


@pytest.fixture(scope="module")
def outcomes() -> dict[str, DesignResult]:
    return {category: design(_request(category)) for category in ARGV}


def _document(lines: list[str]) -> str:
    """The CLI prints the joined lines followed by one newline."""
    return "\n".join(lines) + "\n"


# (id, CLI flags, render options, request fields that differ from ``_request``)
RENDER_CASES = [
    ("table", (), RenderOptions(), {}),
    (
        "table-plot-full-e96",
        ("--plot", "--inductor-suggestions", "full", "-e", "E96"),
        RenderOptions(show_plot=True),
        {"inductor_suggestions": "full", "eseries": "E96"},
    ),
    ("table-raw-no-match", ("--raw", "--no-match"), RenderOptions(raw=True), {"eseries": None}),
    (
        "table-compact",
        ("--inductor-suggestions", "compact", "-e", "E12"),
        RenderOptions(),
        {"inductor_suggestions": "compact", "eseries": "E12"},
    ),
    (
        "table-no-suggestions",
        ("--inductor-suggestions", "none"),
        RenderOptions(),
        {"inductor_suggestions": "none"},
    ),
    ("quiet", ("-q",), RenderOptions(output_format="quiet"), {}),
    ("quiet-raw", ("-q", "--raw"), RenderOptions(output_format="quiet", raw=True), {}),
    (
        "json-e12",
        ("--format", "json", "-e", "E12"),
        RenderOptions(output_format="json"),
        {"eseries": "E12"},
    ),
    (
        "json-no-match",
        ("--format", "json", "--no-match"),
        RenderOptions(output_format="json"),
        {"eseries": None},
    ),
    (
        "json-no-suggestions",
        ("--format", "json", "--inductor-suggestions", "none"),
        RenderOptions(output_format="json"),
        {"inductor_suggestions": "none"},
    ),
    ("csv", ("--format", "csv"), RenderOptions(output_format="csv"), {}),
    (
        "csv-e96",
        ("--format", "csv", "-e", "E96"),
        RenderOptions(output_format="csv"),
        {"eseries": "E96"},
    ),
]


@pytest.mark.parametrize("category", list(ARGV))
@pytest.mark.parametrize(
    "flags, options, request_fields",
    [case[1:] for case in RENDER_CASES],
    ids=[case[0] for case in RENDER_CASES],
)
def test_render_lines_is_the_cli_output(
    monkeypatch, capsys, outcomes, category, flags, options, request_fields
):
    expected = cli_stdout(monkeypatch, capsys, *ARGV[category], *flags)
    outcome = (
        design(dataclasses.replace(_request(category), **request_fields))
        if request_fields
        else outcomes[category]
    )

    assert _document(render_lines(outcome, options)) == expected


@pytest.mark.parametrize("category", ["lowpass", "bandpass"])
@pytest.mark.parametrize("output_format", ["table", "json"])
def test_build_analysis_output_is_the_cli_output(monkeypatch, capsys, category, output_format):
    request = dataclasses.replace(
        _request(category), realization=BuildConfig(grid_points=51), run_build_analysis=True
    )
    expected = cli_stdout(
        monkeypatch, capsys, *ARGV[category], *FAST_BUILD_ARGV, "--format", output_format
    )

    rendered = render_lines(design(request), RenderOptions(output_format=output_format))

    assert _document(rendered) == expected


def test_wizard_layout_differs_from_the_cli_only_by_its_framing(outcomes):
    outcome = dataclasses.replace(
        outcomes["highpass"],
        build_analysis=design(
            dataclasses.replace(
                _request("highpass"),
                realization=BuildConfig(grid_points=51),
                run_build_analysis=True,
            )
        ).build_analysis,
    )
    cli_lines = render_lines(outcome, RenderOptions())
    wizard_lines = render_lines(
        outcome, RenderOptions(trailing_blank=False, build_target_note=True)
    )
    table = render_lines(outcomes["highpass"], RenderOptions(trailing_blank=False))

    assert wizard_lines[: len(table)] == table
    assert wizard_lines[len(table) : len(table) + 2] == ["", BUILD_TARGET_NOTE]
    assert cli_lines[: len(table) + 1] == [*table, ""]
    assert wizard_lines[len(table) + 2 :] == cli_lines[len(table) + 1 :]


@pytest.mark.parametrize(
    "options, message",
    [
        (
            RenderOptions(output_format="csv"),
            "Build simulation needs table or JSON output",
        ),
        (
            RenderOptions(output_format="quiet"),
            "Build simulation cannot be used with values-only output",
        ),
    ],
)
def test_build_mode_rules(options, message):
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        options.validate_for_build()


def test_build_needs_standard_values_in_the_request():
    with pytest.raises(ValueError, match=f"^{re.escape(BUILD_NEEDS_ESERIES_MESSAGE)}$"):
        dataclasses.replace(_request("lowpass"), eseries=None, run_build_analysis=True)


def test_render_lines_rejects_an_analysis_the_format_cannot_carry(outcomes):
    analysis = design(
        dataclasses.replace(
            _request("lowpass"), realization=BuildConfig(grid_points=51), run_build_analysis=True
        )
    ).build_analysis
    outcome = dataclasses.replace(outcomes["lowpass"], build_analysis=analysis)

    with pytest.raises(ValueError, match="^Build simulation needs table or JSON output$"):
        render_lines(outcome, RenderOptions(output_format="csv"))


def test_render_options_reject_unknown_formats_and_requests_unknown_suggestion_detail():
    with pytest.raises(ValueError, match="^Unknown output format: spice$"):
        RenderOptions(output_format="spice")
    # The suggestion detail is one request field, so "compact and full" cannot be asked for.
    with pytest.raises(
        ValueError, match="^Inductor suggestions must be best, full, compact, or none$"
    ):
        dataclasses.replace(_request("lowpass"), inductor_suggestions="compact+full")


def test_unknown_category_is_rejected(outcomes):
    outcome = dataclasses.replace(outcomes["lowpass"], category="notch", result={})

    with pytest.raises(ValueError, match="^Unknown filter category$"):
        render_lines(outcome, RenderOptions())
    with pytest.raises(ValueError, match="^Unknown filter category$"):
        response_series(outcome)


@pytest.mark.parametrize("category", list(ARGV))
@pytest.mark.parametrize("realization", ["exact", "nominal-build"])
def test_spice_export_is_the_cli_deck(monkeypatch, capsys, outcomes, category, realization):
    expected = cli_stdout(
        monkeypatch,
        capsys,
        *ARGV[category],
        "--format",
        "spice",
        "--spice-realization",
        realization,
    )

    deck = export_spice(outcomes[category], realization.replace("-", "_"))

    # The CLI prints the deck with end="", so the deck carries its own final newline.
    assert deck == expected


@pytest.mark.parametrize("category", list(ARGV))
@pytest.mark.parametrize("fmt", ["json", "csv"])
def test_response_export_is_the_cli_plot_data(monkeypatch, capsys, outcomes, category, fmt):
    expected = cli_stdout(monkeypatch, capsys, *ARGV[category], "--plot-data", fmt)

    assert export_response_data(outcomes[category], fmt) + "\n" == expected


@pytest.mark.parametrize("category", list(ARGV))
def test_response_series_is_the_exported_data(outcomes, category):
    freqs, response_db = response_series(outcomes[category])
    payload = json.loads(export_response_data(outcomes[category], "json"))

    assert len(freqs) == len(response_db) == len(payload["data"])
    assert payload["data"][0]["frequency_hz"] == freqs[0]
    assert payload["data"][-1]["frequency_hz"] == freqs[-1]


def test_unknown_response_format_is_rejected(outcomes):
    with pytest.raises(ValueError, match="^Unknown response data format: xml$"):
        export_response_data(outcomes["lowpass"], "xml")
