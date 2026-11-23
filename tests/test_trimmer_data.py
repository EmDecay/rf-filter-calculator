"""The packaged trimmer data matches its evidence page and refuses malformed data."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from pathlib import Path

import pytest

from filter_lib.shared import packaged_data, trimmer_data
from filter_lib.shared.trimmer_data import trimmer_parts

DOCS = Path(__file__).resolve().parents[1] / "docs"
EVIDENCE = DOCS / "component-data-sources.md"
# The Knowles Voltronics lines, part by part (an appendix to the evidence page).
KNOWLES = DOCS / "component-data-sources-knowles-trimmers.md"
# One row of the evidence page's per-part trimmer table.
_ROW = re.compile(
    r"^\| (?P<parts>[^|]+) \| (?P<cmin>[\d.]+) pF \| (?P<cmax>[\d.]+) pF \| (?P<q>[^|]+) \| "
    r"(?P<srf>[^|]+) \| (?P<dielectric>[^|]+) \| (?P<voltage>\d+) V \| "
    r"\[(?P<source>[^\]]+)\] (?P<page>p\. \d+) \|$"
)
_KNOWLES_ROW = re.compile(
    r"^\| (?P<parts>[^|]+) \| (?P<cmin>[\d.]+) pF \| (?P<cmax>[\d.]+) pF \| (?P<q>[^|]+) \| "
    r"(?P<dielectric>[^|]+) \| (?P<voltage>\d+) V \| (?P<mounting>[^|]+) \| "
    r"\[(?P<source>[^\]]+)\] (?P<page>p\. \d+) \|$"
)
_SOURCE = re.compile(
    r"^\| (?P<id>[A-Z0-9-]+) \| [^|]+ \| (?P<revision>[^|]+) \| (?P<url>\S+) \| "
    r"(?P<sha>[0-9a-f]{64}) \|$"
)


def _data() -> dict:
    return json.loads(files("filter_lib.shared").joinpath("trimmer_data.json").read_text())


def _evidence_rows() -> list[dict]:
    lines = EVIDENCE.read_text(encoding="utf-8").splitlines()
    start = lines.index("## Trimmer capacitors")
    rows = []
    for line in lines[start:]:
        if line.startswith("## Coverage"):
            break
        if match := _ROW.match(line):
            rows.append(match.groupdict())
    return rows


def _knowles_rows() -> list[dict]:
    return [
        match.groupdict()
        for line in KNOWLES.read_text(encoding="utf-8").splitlines()
        if (match := _KNOWLES_ROW.match(line))
    ]


def _evidence_sources() -> dict[str, dict]:
    sources = {}
    for line in EVIDENCE.read_text(encoding="utf-8").splitlines():
        if match := _SOURCE.match(line):
            sources[match["id"]] = match.groupdict()
    return sources


def _parts_of(row: dict) -> list[str]:
    return [number.strip() for number in row["parts"].split(",")]


def test_the_data_is_every_row_of_both_per_part_tables_in_order():
    rows, knowles = _evidence_rows(), _knowles_rows()
    parts = trimmer_parts()

    assert (len(rows), len(knowles), len(parts)) == (58, 124, 182)
    assert sum(len(part.part_numbers) for part in parts) == 96 + 258
    assert {part.maker for part in parts} == {"Vishay", "Exxelia", "Suntan", "Knowles"}
    for row, part in zip(knowles, parts[len(rows) :], strict=True):
        assert _parts_of(row) == list(part.part_numbers)
        assert part.maker == "Knowles"
        assert part.cmin_max_f == pytest.approx(float(row["cmin"]) * 1e-12, rel=1e-15, abs=0)
        assert part.cmax_min_f == pytest.approx(float(row["cmax"]) * 1e-12, rel=1e-15, abs=0)
        assert part.q_as_stated == row["q"].strip()
        assert part.dielectric == row["dielectric"].strip()
        assert part.working_voltage_v == int(row["voltage"])
        assert part.mounting == row["mounting"].strip()
        assert (part.source.source_id, part.page) == (row["source"], row["page"])
        # No Knowles line states an SRF.
        assert part.srf_min_at_cmax_hz is None and part.srf_as_stated is None
    for row, part in zip(rows, parts, strict=False):
        assert _parts_of(row) == list(part.part_numbers)
        assert part.cmin_max_f == pytest.approx(float(row["cmin"]) * 1e-12, rel=1e-15, abs=0)
        assert part.cmax_min_f == pytest.approx(float(row["cmax"]) * 1e-12, rel=1e-15, abs=0)
        assert part.q_as_stated == row["q"].strip()
        assert part.dielectric == row["dielectric"].strip()
        assert part.working_voltage_v == int(row["voltage"])
        assert part.source.source_id == row["source"]
        assert part.page == row["page"]
        srf = row["srf"].strip()
        assert part.srf_as_stated == (None if srf == "—" else srf)
        minimum = re.fullmatch(r"min (\d+) MHz at Cmax", srf)
        # Only a guaranteed minimum is packaged as a number; a typical SRF stays text.
        assert part.srf_min_at_cmax_hz == (None if minimum is None else int(minimum[1]) * 1e6)


def test_only_vishay_and_knowles_glass_and_quartz_ranges_state_their_frequency():
    for part in trimmer_parts():
        if part.maker == "Vishay":
            expected = 200e3
        elif part.maker == "Knowles" and "piston" in part.family:
            expected = 1e6  # "Capacitance measured at 1 MHz" (catalog p. 41)
        else:
            expected = None
        assert part.range_measured_at_hz == expected, part.part_name


def test_every_source_matches_the_source_index():
    evidence = _evidence_sources()
    data = _data()["sources"]

    assert set(data) == {part.source.source_id for part in trimmer_parts()}
    for source_id, source in data.items():
        assert source["url"] == evidence[source_id]["url"]
        assert source["sha256"] == evidence[source_id]["sha"]
        assert source["revision"] == evidence[source_id]["revision"].strip()


def test_the_series_inductance_bound_comes_from_the_minimum_srf_at_the_maximum():
    # BFC280820109: 3-10 pF, SRF at least 500 MHz at Cmax, so L <= 1/((2 pi 500 MHz)^2 10 pF).
    [part] = [part for part in trimmer_parts() if part.part_name == "BFC280820109"]

    assert part.series_inductance_bound_h == pytest.approx(10.1321e-9, rel=1e-5)
    exxelia = next(part for part in trimmer_parts() if part.maker == "Exxelia")
    assert exxelia.series_inductance_bound_h is None


def _load_with(monkeypatch, changed: dict) -> None:
    """Load ``changed`` in place of the packaged file, bypassing the cache."""
    real = packaged_data.load_packaged_json

    def fake(package, filename, **kwargs):
        if filename == "trimmer_data.json":
            return changed
        return real(package, filename, **kwargs)

    monkeypatch.setattr(trimmer_data, "load_packaged_json", fake)
    trimmer_data.trimmer_parts.cache_clear()
    try:
        trimmer_data.trimmer_parts()
    finally:
        trimmer_data.trimmer_parts.cache_clear()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"cmin_max_pf": "10"}, "minimum below its maximum"),
        ({"cmin_max_pf": 3}, "decimal number of pF written as text"),
        ({"source": "NOT-READ"}, "cites a source that was not read"),
        ({"page": "page 3"}, "needs the page of its source row"),
        ({"part_numbers": []}, "must list its part numbers once each"),
        ({"srf_as_stated": None}, "needs the SRF as stated with its minimum"),
        ({"working_voltage_v": True}, "must be a finite number"),
    ],
)
def test_a_malformed_row_is_refused(monkeypatch, change, message):
    data = _data()
    data["trimmers"][4] = {**data["trimmers"][4], **change}

    with pytest.raises(RuntimeError, match=message):
        _load_with(monkeypatch, data)


def test_a_part_number_listed_twice_is_refused(monkeypatch):
    data = _data()
    data["trimmers"][5]["part_numbers"] = list(data["trimmers"][4]["part_numbers"])

    with pytest.raises(RuntimeError, match="must be listed once"):
        _load_with(monkeypatch, data)


def test_a_source_without_its_hash_is_refused(monkeypatch):
    data = _data()
    data["sources"]["VIS-28526"] = {**data["sources"]["VIS-28526"], "sha256": "abc"}

    with pytest.raises(RuntimeError, match="needs a SHA-256"):
        _load_with(monkeypatch, data)


def test_every_stated_q_names_the_setting_it_was_measured_at():
    # Vishay states tan δ at Cmax, Exxelia and Suntan Q at Cmax; a graph has no setting;
    # Knowles states the setting for K_HV only, and says so where it does not.
    settings = (", Cmax", "maximum rated C", "setting not stated")
    for part in trimmer_parts():
        assert part.q_as_stated == "graph only" or any(
            setting in part.q_as_stated for setting in settings
        ), part.part_name
