"""Readable part names that match the component tables.

The bandpass named circuit (``circuit_builders``) uses SPICE-style element names:
``CT{i}`` (resonator capacitor), ``LT{i}`` (resonator inductor), ``CK{i}`` (coupling
capacitor between resonators i and i+1), ``CIN`` and ``COUT`` (end capacitors). The
bandpass component table calls the same parts ``Cp{i}``, ``L{i}``, ``Cs{i}{i+1}``,
``Ce_in`` and ``Ce_out``. Readable text (build simulation block, warnings, limitation
prose) uses the table names. SPICE element names and JSON ``logical_name`` values keep
the circuit names; the SPICE deck carries a ``* names:`` comment that maps them.

Low-pass and high-pass names (``C1``, ``L1``) are the same in both places and pass
through unchanged. A physical part of a parallel pair has a one-letter suffix
(``CK1A``, ``CK1B``); it reads as ``Cs12 (part A)``.
"""

import re
from collections.abc import Iterable

from .circuit_model import NamedCircuit

_INDEXED = re.compile(r"^(CT|LT|CK)(\d+)([A-Z]?)$")
_END = re.compile(r"^(CIN|COUT)([A-Z]?)$")
_END_NAMES = {"CIN": "Ce_in", "COUT": "Ce_out"}
_NUMBERED = re.compile(r"^([A-Za-z_]+?)(\d+)$")


def _with_part_suffix(name: str, suffix: str) -> str:
    return f"{name} (part {suffix})" if suffix else name


def display_component_name(name: str) -> str:
    """Return the component-table name for a circuit element name."""
    match = _INDEXED.match(name)
    if match:
        prefix, index_text, suffix = match.groups()
        index = int(index_text)
        if prefix == "CT":
            return _with_part_suffix(f"Cp{index}", suffix)
        if prefix == "LT":
            return _with_part_suffix(f"L{index}", suffix)
        return _with_part_suffix(f"Cs{index}{index + 1}", suffix)
    match = _END.match(name)
    if match:
        base, suffix = match.groups()
        return _with_part_suffix(_END_NAMES[base], suffix)
    return name


def format_name_list(names: Iterable[str]) -> str:
    """Join part names, writing three or more consecutive ones as a range (``L1–L3``)."""
    ordered = list(dict.fromkeys(names))
    pieces: list[str] = []
    index = 0
    while index < len(ordered):
        match = _NUMBERED.match(ordered[index])
        end = index
        if match:
            prefix, number = match.group(1), int(match.group(2))
            while end + 1 < len(ordered):
                following = _NUMBERED.match(ordered[end + 1])
                if not following or following.group(1) != prefix:
                    break
                if int(following.group(2)) != number + (end + 1 - index):
                    break
                end += 1
        if end - index >= 2:
            pieces.append(f"{ordered[index]}–{ordered[end]}")
        else:
            pieces.extend(ordered[index : end + 1])
        index = end + 1
    return ", ".join(pieces)


def spice_names_comment(circuit: NamedCircuit) -> str | None:
    """Return a ``* names:`` SPICE comment mapping element names to table names.

    Parallel parts are joined with ``+`` (``CT2A+CT2B=Cp2``). Returns ``None`` when every
    element already uses its table name (low-pass and high-pass decks).
    """
    groups: dict[str, list[str]] = {}
    for element in circuit.elements:
        logical = element.logical_name or element.name
        groups.setdefault(logical, []).append(element.name)
    if all(display_component_name(logical) == logical for logical in groups):
        return None
    pairs = (
        f"{'+'.join(names)}={display_component_name(logical)}" for logical, names in groups.items()
    )
    return "* names: " + " ".join(pairs)
