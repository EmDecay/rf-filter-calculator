"""Versioned toroid core data with explicit source and verification status.

Legacy records remain available for inspection.  Automatic candidate selection
is limited to exact parts whose essential core data has been checked against a
manufacturer datasheet; material application ranges retain their own source.

Unit conventions:
- A_L in nH/turn².
- Dimensions in mm and frequencies in Hz.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from .numeric import require_positive_finite


@dataclass(frozen=True)
class SourceReference:
    """One source cited by the vendored data set."""

    source_id: str
    publisher: str
    source_type: str
    title: str
    url: str
    accessed_on: str


@dataclass(frozen=True)
class WindingSpecification:
    """Manufacturer winding-table row for one wire gauge."""

    awg: int
    wire_diameter_mm: float
    single_layer_turns: int
    single_layer_dcr_ohm: float
    full_winding_turns: int
    full_winding_dcr_ohm: float


@dataclass(frozen=True)
class ManufacturerTest:
    """Published test winding and exact test conditions."""

    turns: int
    awg: int
    frequency_hz: float
    voltage_v: float | None = None
    minimum_q: float | None = None
    instrument: str | None = None


@dataclass(frozen=True)
class ToroidCore:
    """One iron-powder T-series toroid core specification."""

    name: str
    mix: str
    color_code: str
    od_mm: float
    id_mm: float
    height_mm: float
    al_nh_per_turn2: float
    al_tolerance_pct: float
    temp_coeff_ppm_per_c: float
    freq_min_hz: float
    freq_max_hz: float
    manufacturer: str | None = None
    manufacturer_part_number: str | None = None
    aliases: tuple[str, ...] = ()
    provenance_status: str = "legacy_unverified"
    core_source_id: str | None = None
    frequency_source_id: str | None = None
    winding_source_id: str | None = None
    frequency_guidance_kind: str = "legacy_unverified_range"
    field_sources: tuple[tuple[str, str], ...] = ()
    al_test: ManufacturerTest | None = None
    q_test: ManufacturerTest | None = None
    winding_table: tuple[WindingSpecification, ...] = ()

    @property
    def family(self) -> str:
        """Core family prefix (T25, T37, T50, ...)."""
        return self.name.split("-", 1)[0]

    @property
    def is_auto_selectable(self) -> bool:
        """Whether exact-part core data is primary-source verified."""
        return self.provenance_status == "primary_verified"

    def source_for(self, field_group: str) -> SourceReference | None:
        """Source for a field group, if one was recorded."""
        if not isinstance(field_group, str):
            raise ValueError("field_group must be a string")
        source_id = dict(self.field_sources).get(field_group)
        return _SOURCES.get(source_id) if source_id else None

    def winding_spec_for_awg(self, awg: int) -> WindingSpecification | None:
        """Manufacturer winding-table row for ``awg``, if published."""
        if isinstance(awg, bool) or not isinstance(awg, int) or not 0 <= awg <= 50:
            raise ValueError("awg must be an integer in [0, 50]")
        return next((row for row in self.winding_table if row.awg == awg), None)


def _require_toroid_core(core: object) -> ToroidCore:
    """Return a toroid core or raise a stable error before attribute access."""
    if not isinstance(core, ToroidCore):
        raise ValueError("core must be a ToroidCore")
    return core


def _reject_json_constant(value: str) -> None:
    """Reject NaN/Infinity extensions while loading the packaged JSON."""
    raise ValueError(f"Non-finite JSON constant {value!r} in toroid core data")


def _load_raw_data() -> dict[str, Any]:
    data_path = files(__package__).joinpath("toroid_core_data.json")
    with data_path.open("r", encoding="utf-8") as data_file:
        raw = json.load(data_file, parse_constant=_reject_json_constant)
    if not isinstance(raw, dict) or raw.get("schema_version") != 2:
        raise RuntimeError("Unsupported toroid core data schema; expected version 2")
    return raw


def _load_sources(raw_sources: dict[str, dict[str, Any]]) -> dict[str, SourceReference]:
    sources: dict[str, SourceReference] = {}
    for source_id, values in raw_sources.items():
        source = SourceReference(source_id=source_id, **values)
        if not source.url.startswith("https://"):
            raise RuntimeError(f"Toroid source {source_id!r} must use an HTTPS URL")
        sources[source_id] = source
    return sources


def _load_winding_table(raw_table: dict[str, list[Any]] | None) -> tuple[WindingSpecification, ...]:
    if not raw_table:
        return ()
    columns = (
        "awg",
        "wire_diameter_mm",
        "single_layer_turns",
        "single_layer_dcr_ohm",
        "full_winding_turns",
        "full_winding_dcr_ohm",
    )
    missing = [column for column in columns if column not in raw_table]
    if missing:
        raise RuntimeError(f"Toroid winding table is missing columns: {', '.join(missing)}")
    lengths = {len(raw_table[column]) for column in columns}
    if len(lengths) != 1:
        raise RuntimeError("Toroid winding-table columns must have equal lengths")
    return tuple(
        WindingSpecification(**dict(zip(columns, values)))
        for values in zip(*(raw_table[column] for column in columns))
    )


def _core_from_entry(raw_entry: dict[str, Any], materials: dict[str, dict[str, Any]]) -> ToroidCore:
    entry = dict(raw_entry)
    material = materials.get(entry["mix"])
    if material:
        entry["freq_min_hz"] = material["freq_min_hz"]
        entry["freq_max_hz"] = material["freq_max_hz"]
        entry.setdefault("frequency_source_id", material["frequency_source_id"])
        entry.setdefault("frequency_guidance_kind", material["guidance_kind"])

    entry.setdefault("core_source_id", "legacy-research-snapshot")
    entry.setdefault("provenance_status", "legacy_unverified")
    entry["aliases"] = tuple(entry.get("aliases", ()))
    entry["field_sources"] = tuple(sorted(entry.get("field_sources", {}).items()))
    entry["al_test"] = ManufacturerTest(**entry["al_test"]) if entry.get("al_test") else None
    entry["q_test"] = ManufacturerTest(**entry["q_test"]) if entry.get("q_test") else None
    entry["winding_table"] = _load_winding_table(entry.get("winding_table"))
    return ToroidCore(**entry)


def _validate_core(core: ToroidCore, sources: dict[str, SourceReference]) -> None:
    if not (0 < core.id_mm < core.od_mm and core.height_mm > 0):
        raise RuntimeError(f"Invalid dimensions for toroid core {core.name}")
    if core.al_nh_per_turn2 <= 0 or core.freq_min_hz <= 0:
        raise RuntimeError(f"Invalid magnetic data for toroid core {core.name}")
    if core.freq_min_hz > core.freq_max_hz:
        raise RuntimeError(f"Invalid frequency range for toroid core {core.name}")
    source_ids = {
        core.core_source_id,
        core.frequency_source_id,
        core.winding_source_id,
        *(source_id for _, source_id in core.field_sources),
    }
    unknown = sorted(
        source_id for source_id in source_ids if source_id and source_id not in sources
    )
    if unknown:
        raise RuntimeError(f"Unknown source IDs on {core.name}: {', '.join(unknown)}")
    if core.is_auto_selectable and (
        not core.manufacturer
        or not core.manufacturer_part_number
        or not core.core_source_id
        or not core.frequency_source_id
    ):
        raise RuntimeError(f"Verified core {core.name} lacks exact-part provenance")


_RAW_DATA = _load_raw_data()
_SOURCES = _load_sources(_RAW_DATA["sources"])
_MATERIALS: dict[str, dict[str, Any]] = _RAW_DATA.get("materials", {})
_CORE_LIST = [_core_from_entry(entry, _MATERIALS) for entry in _RAW_DATA["cores"]]
_CORES = {core.name: core for core in _CORE_LIST}

if len(_CORES) != len(_CORE_LIST):
    raise RuntimeError("Duplicate toroid core names in packaged data")
manifest_count = _RAW_DATA["dataset"]["core_count"]
if len(_CORES) != manifest_count:
    raise RuntimeError(f"Toroid manifest declares {manifest_count} cores, found {len(_CORES)}")
for _core in _CORE_LIST:
    _validate_core(_core, _SOURCES)


def list_cores() -> list[ToroidCore]:
    """All cores sorted by outer diameter (smallest first)."""
    return sorted(_CORES.values(), key=lambda core: (core.od_mm, core.name))


def get_core(name: str) -> ToroidCore:
    """Look up a core by exact name or recorded alias."""
    if not isinstance(name, str):
        raise ValueError("toroid core name must be a string")
    if name in _CORES:
        return _CORES[name]
    for core in _CORES.values():
        if name in core.aliases:
            return core
    raise ValueError(f"Unknown toroid core: {name!r}")


def list_sources() -> list[SourceReference]:
    """All data sources sorted by stable source ID."""
    return [_SOURCES[source_id] for source_id in sorted(_SOURCES)]


def get_source(source_id: str | None) -> SourceReference:
    """Look up a source reference by stable source ID."""
    if not isinstance(source_id, str) or source_id not in _SOURCES:
        raise ValueError(f"Unknown toroid source: {source_id!r}")
    return _SOURCES[source_id]


def iter_cores_for_frequency(freq_hz: float) -> Iterator[ToroidCore]:
    """Yield inspectable cores whose recorded material guidance covers ``freq_hz``."""
    require_positive_finite(freq_hz, "freq_hz")
    for core in list_cores():
        if core.freq_min_hz <= freq_hz <= core.freq_max_hz:
            yield core


def iter_auto_selectable_cores_for_frequency(freq_hz: float) -> Iterator[ToroidCore]:
    """Yield only primary-verified exact parts covering ``freq_hz``."""
    for core in iter_cores_for_frequency(freq_hz):
        if core.is_auto_selectable:
            yield core
