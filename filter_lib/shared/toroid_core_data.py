"""Iron-powder T-series toroid core database.

Data vendored from toroids.info via research repo:
https://github.com/EmDecay/toroid-calc-research (snapshot 2026-02-03)

Unit conventions:
- A_L in nH/turn² — NOT Amidon catalog "µH per 100 turns²"; mixing the two
  gives ~3x-wrong turn counts (see toroid_inductance.py for the derivation).
- Dimensions in mm, frequencies in Hz.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from importlib.resources import files

# The vendored snapshot contains exactly 43 iron-powder T-series cores
# (including the double-height variants T200-2B and T225-2B). The loader
# asserts this count so an accidental edit or truncation of the JSON fails
# loudly at import time instead of silently shrinking the candidate pool.
_EXPECTED_CORE_COUNT = 43


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

    @property
    def family(self) -> str:
        """Core family prefix (T25, T37, T50, ...)."""
        return self.name.split("-", 1)[0]


def _load_cores() -> dict[str, ToroidCore]:
    """Load and validate the vendored core JSON, keyed by core name."""
    data_path = files(__package__).joinpath("toroid_core_data.json")
    with data_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    cores = {entry["name"]: ToroidCore(**entry) for entry in raw}
    if len(cores) != _EXPECTED_CORE_COUNT:
        raise RuntimeError(f"Expected {_EXPECTED_CORE_COUNT} T-series cores, found {len(cores)}")
    return cores


_CORES: dict[str, ToroidCore] = _load_cores()


def list_cores() -> list[ToroidCore]:
    """All cores sorted by outer diameter (smallest first)."""
    return sorted(_CORES.values(), key=lambda c: (c.od_mm, c.name))


def get_core(name: str) -> ToroidCore:
    """Look up a core by exact name (e.g. 'T50-2'). Case-sensitive.

    Raises:
        ValueError: If the name is not in the vendored database.
    """
    if name not in _CORES:
        raise ValueError(f"Unknown toroid core: {name!r}")
    return _CORES[name]


def iter_cores_for_frequency(freq_hz: float) -> Iterator[ToroidCore]:
    """Yield cores whose published frequency range covers freq_hz."""
    for core in list_cores():
        if core.freq_min_hz <= freq_hz <= core.freq_max_hz:
            yield core
