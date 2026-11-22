"""The packaged chip-inductor catalog matches its evidence page and refuses malformed data."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from pathlib import Path

import pytest

from filter_lib.shared import chip_inductor_data, packaged_data
from filter_lib.shared.chip_inductor_data import catalog_range_h, chip_parts

EVIDENCE = Path(__file__).resolve().parents[1] / "docs" / "component-data-sources.md"
# One catalog row of the evidence page's "Recommended catalog" table.
_ROW = re.compile(
    r"^\| (?P<part>\S+) \| (?P<l>\d+) nH at (?P<fm>\d+) MHz \| (?P<tol>[^|]+) \| "
    r"(?P<srf>\d+) MHz \| (?P<q>\d+) at (?P<qf>\d+) MHz \| \[(?P<source>[^\]]+)\] "
    r"(?P<page>p\. [\d, ]+) \|$"
)
_SOURCE = re.compile(
    r"^\| (?P<id>[A-Z0-9-]+) \| [^|]+ \| [^|]+ \| (?P<url>\S+) \| (?P<sha>[0-9a-f]{64}) \|$"
)


def _data() -> dict:
    return json.loads(files("filter_lib.shared").joinpath("chip_inductor_data.json").read_text())


def _evidence_rows() -> dict[str, dict]:
    rows = {}
    for line in EVIDENCE.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if match:
            rows[match["part"]] = match.groupdict()
    return rows


def _evidence_sources() -> dict[str, tuple[str, str]]:
    sources = {}
    for line in EVIDENCE.read_text(encoding="utf-8").splitlines():
        match = _SOURCE.match(line)
        if match:
            sources[match["id"]] = (match["url"], match["sha"])
    return sources


def test_the_catalog_is_the_four_recommended_families_from_10_to_100_nh():
    parts = chip_parts()
    families = {part.family.name for part in parts}

    assert families == {"0603CS", "LQW18AN_00", "LQW18AN_80", "LQW15AN_80"}
    assert len(_data()["parts"]) == 119
    assert len(parts) == 259  # every offered tolerance code of the 119 rows
    assert len({round(part.inductance_h * 1e9, 6) for part in parts}) == 48
    assert catalog_range_h() == (10e-9, 100e-9)
    # No 1% variant, and 0603CS-47NXH is not offered on Coilcraft's web part page.
    assert {part.tolerance_pct for part in parts} == {2.0, 3.0, 5.0}
    assert "0603CS-47NXHRW" not in {part.part_number for part in parts}
    assert [part.part_number for part in parts] == sorted(part.part_number for part in parts)


def test_every_packaged_row_matches_the_evidence_page():
    evidence = _evidence_rows()
    data = _data()
    codes = {name: family["tolerance_codes"] for name, family in data["families"].items()}

    assert len(evidence) == len(data["parts"])
    for row in data["parts"]:
        documented = evidence[row["part_number"]]
        assert int(documented["l"]) == row["inductance_nh"]
        assert int(documented["fm"]) == row["test_frequency_mhz"]
        assert int(documented["srf"]) == row["srf_min_mhz"]
        assert int(documented["q"]) == row["q_min"]
        assert int(documented["qf"]) == row["q_test_frequency_mhz"]
        assert documented["page"] == row["page"]
        source = data["families"][row["family"]]["source"]
        assert documented["source"] == source
        offered = {
            code
            for code, percent in re.findall(r"\b([GHJ]) (\d) %", documented["tol"])
            if f"{code} {percent} % printed, not offered" not in documented["tol"]
        }
        assert offered == set(row["tolerance_codes"])
        for code in offered:
            stated = re.search(rf"\b{code} (\d) %", documented["tol"])
            assert float(stated[1]) == codes[row["family"]][code]


def test_every_source_is_the_copy_the_evidence_page_records():
    documented = _evidence_sources()

    for source_id, source in _data()["sources"].items():
        assert documented[source_id] == (source["url"], source["sha256"])


def test_every_family_states_guaranteed_limits_and_its_measurement():
    for family in _data()["families"].values():
        assert family["tolerance_guarantee"] == "maximum"
        assert family["srf_guarantee"] == family["q_guarantee"] == "minimum"
        assert family["measurement"]


def test_catalog_values_load_as_the_decimal_they_state():
    part = next(part for part in chip_parts() if part.part_number == "0603CS-22NXJRW")

    # 22 × 1e-9 is 2.2000000000000002e-08; the loader keeps the stated decimal.
    assert repr(part.inductance_h) == "2.2e-08"
    assert (part.test_frequency_hz, part.srf_min_hz) == (250e6, 3e9)


def _reload_with(monkeypatch, tmp_path, change) -> None:
    """Load the packaged catalog after ``change(data)`` edits a copy of it."""
    data = _data()
    change(data)
    (tmp_path / "chip_inductor_data.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(packaged_data, "files", lambda _package: tmp_path)
    chip_inductor_data.chip_parts.cache_clear()
    try:
        chip_inductor_data.chip_parts()
    finally:
        chip_inductor_data.chip_parts.cache_clear()


def _row(data, index=0):
    return data["parts"][index]


def _family(data, name="0603CS"):
    return data["families"][name]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: _row(d).update(inductance_nh=0), "must be positive"),
        (lambda d: _row(d).update(q_min=True), "finite number"),
        (lambda d: _row(d).update(srf_min_mhz=250), "at or above its minimum SRF"),
        (lambda d: _row(d).update(part_number="0603CS-10NXRW"), "one '_'"),
        (lambda d: _row(d).update(part_number="0603CS-10NX_R\nW"), "single line"),
        (lambda d: _row(d).update(family="0402CS"), "unknown family"),
        (lambda d: _row(d).update(tolerance_codes=["F"]), "does not define"),
        (lambda d: _row(d).update(tolerance_codes=["G", "G"]), "does not define"),
        (lambda d: _row(d).update(page="page 2"), "page of its source row"),
        (lambda d: d["parts"].append(dict(_row(d))), "listed once"),
        (lambda d: _family(d).update(srf_guarantee="typical"), "not a guaranteed limit"),
        (lambda d: _family(d).update(q_guarantee="typ"), "unknown guarantee type"),
        (lambda d: _family(d).update(source="CC-0402CS"), "source that was not read"),
        (lambda d: _family(d).update(tolerance_codes={"g": 2}), "single capital letters"),
        (lambda d: _family(d).update(tolerance_codes={"G": 100}), "below 100%"),
        (lambda d: _family(d).update(measurement="two\nlines"), "single line"),
        (lambda d: d["sources"]["CC-0603CS"].update(url="http://www.coilcraft.com/x"), "HTTPS"),
        (lambda d: d["sources"]["CC-0603CS"].update(sha256="abc"), "SHA-256"),
        (lambda d: d["sources"]["CC-0603CS"].update(title=""), "single line"),
        (lambda d: d.update(schema_version=2), "expected version 1"),
    ],
)
def test_loader_refuses_malformed_data(monkeypatch, tmp_path, change, message):
    with pytest.raises(RuntimeError, match=message):
        _reload_with(monkeypatch, tmp_path, change)


@pytest.mark.parametrize(("key", "value"), [("srf_min_mhz", "nan"), ("inductance_nh", "inf")])
def test_loader_refuses_non_finite_numbers_while_parsing(monkeypatch, tmp_path, key, value):
    with pytest.raises(ValueError, match="Non-finite JSON constant"):
        _reload_with(monkeypatch, tmp_path, lambda d: _row(d).update({key: float(value)}))
