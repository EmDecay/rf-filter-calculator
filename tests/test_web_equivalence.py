"""Everything the web UI shows or downloads is byte-identical to ``filter-calc`` output.

Each design moves its fields off the web defaults (impedance, order, ripple, E-series,
toroid detail, tank settings), so a form field the web drops or misreads changes the
document and fails the comparison against live CLI stdout.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

pytest.importorskip("fastapi")

from tests.cli_parity_helpers import cli_stdout  # noqa: E402
from tests.web_helpers import HTMX, output_text, web_client  # noqa: E402

TOROID_FLAG = {"best": (), "full": ("--toroid-full",), "compact": ("--toroid-compact",)}
EXPORT_FLAGS = {
    "json": ("--format", "json"),
    "csv": ("--format", "csv"),
    "spice-exact": ("--format", "spice", "--spice-realization", "exact"),
    "spice-nominal": ("--format", "spice", "--spice-realization", "nominal-build"),
    "response-json": ("--plot-data", "json"),
    "response-csv": ("--plot-data", "csv"),
}
EXPORT_TYPES = {
    "json": ("json", "application/json"),
    "csv": ("csv", "text/csv; charset=utf-8"),
    "spice-exact": ("cir", "text/plain; charset=utf-8"),
    "spice-nominal": ("cir", "text/plain; charset=utf-8"),
    "response-json": ("json", "application/json"),
    "response-csv": ("csv", "text/csv; charset=utf-8"),
}
# Modes in which the CLI accepts an explicit E-series choice.
ESERIES_MODES = {"table", "json", "csv", "spice-nominal"}


@dataclass(frozen=True)
class Design:
    id: str
    category: str
    argv: tuple[str, ...]
    fields: dict = field(default_factory=dict)
    eseries: str = "E24"
    toroids: str = "best"

    def form(self, **extra) -> dict:
        return {**self.fields, "eseries": self.eseries, "toroids": self.toroids, **extra}

    def cli_argv(self, mode: str, *flags: str) -> tuple[str, ...]:
        """CLI arguments for ``mode`` (an export kind or ``table``)."""
        argv = list(self.argv)
        if mode in ESERIES_MODES:
            argv += ["--no-match"] if self.eseries == "none" else ["-e", self.eseries]
        if mode == "table":
            argv += TOROID_FLAG[self.toroids]
        else:
            argv += EXPORT_FLAGS[mode]
        return (*argv, *flags)


DESIGNS = [
    Design(
        "lp-chebyshev-t",
        "lowpass",
        ("lp", "ch", "t", "7.1MHz", "-n", "5", "-z", "75", "-r", "0.25"),
        dict(
            filter_type="chebyshev",
            topology="t",
            frequency="7.1MHz",
            components="5",
            impedance="75",
            ripple="0.25",
        ),
        eseries="E96",
        toroids="full",
    ),
    Design(
        "hp-bessel-pi",
        "highpass",
        ("hp", "bs", "pi", "3.5MHz", "-n", "4", "-z", "50"),
        dict(filter_type="bessel", topology="pi", frequency="3.5MHz", components="4"),
        eseries="E12",
        toroids="compact",
    ),
    Design(
        "bp-butterworth-tank",
        "bandpass",
        (
            "bp",
            "bw",
            "top",
            "-f",
            "14.175MHz",
            "-b",
            "350kHz",
            "-n",
            "4",
            "-z",
            "75",
            "--resonator-impedance",
            "100",
        ),
        dict(
            filter_type="butterworth",
            frequency="14.175MHz",
            bandwidth="350kHz",
            resonators="4",
            impedance="75",
            resonator_impedance="100",
        ),
        eseries="none",
    ),
    Design(
        "bp-chebyshev-edges",
        "bandpass",
        (
            *("bp", "ch", "top", "--fl", "14MHz", "--fh", "14.35MHz", "-n", "5", "-r", "0.25"),
            *("--resonator-inductance", "1.5uH"),
        ),
        dict(
            filter_type="chebyshev",
            band_spec="edges",
            f_low="14MHz",
            f_high="14.35MHz",
            resonators="5",
            ripple="0.25",
            resonator_inductance="1.5uH",
        ),
        toroids="full",
    ),
]
IDS = [design.id for design in DESIGNS]


@pytest.fixture(scope="module")
def client():
    with web_client() as test_client:
        yield test_client


@pytest.mark.parametrize("design", DESIGNS, ids=IDS)
def test_api_design_returns_the_cli_json_document(monkeypatch, capsys, client, design):
    expected = cli_stdout(monkeypatch, capsys, *design.cli_argv("json"))

    response = client.post(f"/api/design/{design.category}", data=design.form())

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.content.decode() == expected


@pytest.mark.parametrize("kind", list(EXPORT_FLAGS))
@pytest.mark.parametrize("design", DESIGNS, ids=IDS)
def test_each_export_is_the_cli_document(monkeypatch, capsys, client, design, kind):
    if kind == "spice-nominal" and design.eseries == "none":
        pytest.skip("nominal-build SPICE needs selected capacitor values (see test_web_errors)")
    expected = cli_stdout(monkeypatch, capsys, *design.cli_argv(kind))

    response = client.post(f"/export/{design.category}/{kind}", data=design.form())

    assert response.status_code == 200
    extension, media_type = EXPORT_TYPES[kind]
    assert response.headers["content-type"] == media_type
    assert response.headers["content-disposition"] == (
        f'attachment; filename="{design.category}-{kind}.{extension}"'
    )
    assert response.content.decode() == expected


TABLE_VARIANTS = [
    ("table", {}, ()),
    ("ascii-plot", {"plot": "on"}, ("--plot",)),
    ("quiet", {"output_format": "quiet"}, ("-q",)),
    ("raw", {"raw": "on"}, ("--raw",)),
    ("json", {"output_format": "json"}, ("--format", "json")),
    ("csv", {"output_format": "csv"}, ("--format", "csv")),
]


@pytest.mark.parametrize(
    "extra, flags", [v[1:] for v in TABLE_VARIANTS], ids=[v[0] for v in TABLE_VARIANTS]
)
@pytest.mark.parametrize("design", DESIGNS, ids=IDS)
def test_design_view_shows_the_cli_text(monkeypatch, capsys, client, design, extra, flags):
    mode = extra.get("output_format", "table")
    if mode == "quiet" or extra.get("raw"):
        # The CLI rejects explicit E-series and toroid-detail flags in these modes.
        argv = (*design.argv, *flags)
        form = design.form(**extra, eseries="E24", toroids="best")
        if extra.get("raw"):
            argv = (*design.argv, *TOROID_FLAG[design.toroids], *flags)
            form = design.form(**extra, eseries="E24")
    elif mode in ("json", "csv"):
        # Toroid detail is table-only: the page disables it, so it is not sent.
        argv = design.cli_argv(mode)
        form = {k: v for k, v in design.form(**extra).items() if k != "toroids"}
    else:
        argv = design.cli_argv("table", *flags)
        form = design.form(**extra)
    expected = cli_stdout(monkeypatch, capsys, *argv)

    response = client.post(f"/design/{design.category}", data=form, headers=HTMX)

    assert response.status_code == 200
    assert output_text(response.text) + "\n" == expected


@pytest.mark.parametrize(
    "design, output_format",
    [(DESIGNS[0], "table"), (DESIGNS[0], "json"), (DESIGNS[3], "table"), (DESIGNS[3], "json")],
    ids=["lp-table", "lp-json", "bp-table", "bp-json"],
)
def test_realized_build_output_is_the_cli_output(
    monkeypatch, capsys, client, design, output_format
):
    build_fields = dict(
        sim_build="on",
        build_grid_points="101",
        build_sample_count="2",
        build_seed="5",
        build_capacitor_tolerance_pct="2",
    )
    build_flags = (
        "--sim-build",
        "--analysis-points",
        "101",
        "--sample-count",
        "2",
        "--seed",
        "5",
        "--capacitor-tolerance",
        "2",
    )
    if design.category == "lowpass":
        build_fields["build_inductor_q"] = "120"
        build_flags += ("--inductor-q", "120")
    form = design.form(output_format=output_format, **build_fields)
    mode = "table" if output_format == "table" else "json"
    expected = cli_stdout(monkeypatch, capsys, *design.cli_argv(mode, *build_flags))

    if output_format == "json":
        response = client.post(f"/api/design/{design.category}", data=form)
        body = response.content.decode()
    else:
        response = client.post(f"/design/{design.category}", data=form, headers=HTMX)
        body = output_text(response.text) + "\n"

    assert response.status_code == 200
    assert body == expected


def test_nominal_spice_uses_the_submitted_loss_and_ports(monkeypatch, capsys, client):
    design = DESIGNS[1]
    form = design.form(
        sim_build="on", build_capacitor_q="500", build_load_resistance="75", toroid_build="off"
    )
    expected = cli_stdout(
        monkeypatch,
        capsys,
        *design.cli_argv(
            "spice-nominal", "--capacitor-q", "500", "--load-resistance", "75", "--no-toroid-build"
        ),
    )

    response = client.post(f"/export/{design.category}/spice-nominal", data=form)

    assert response.content.decode() == expected


def test_only_the_json_download_carries_the_build_analysis(client):
    form = DESIGNS[1].form(sim_build="on", build_grid_points="51")

    json_body = client.post("/export/highpass/json", data=form).json()
    csv_response = client.post("/export/highpass/csv", data=form)

    assert {"nominal_build", "tolerance_analysis"} <= set(json_body)
    assert csv_response.status_code == 200
    assert csv_response.text == client.post("/export/highpass/csv", data=DESIGNS[1].form()).text
