"""Generate and compare the HF baseline corpus.

The corpus (``tests/fixtures/hf_baseline.json``) records, for a fixed set of HF designs
(1.8-30 MHz; low-pass, high-pass and band-pass; every response type; orders 3, 5 and 9;
E12, E24 and E96; toroid suggestions on), the physical facts each output states: the
calculated values, each capacitor's chosen parts and status, the toroid picks, the
band-pass response check, both SPICE decks, and the build simulation's measurements and
tolerance cases. It was generated once from the release before the worst-case capacitor
rule and is never regenerated to absorb a change.

A later change may alter these facts only in the ways the VHF/UHF work permits:

(a) a capacitor choice that the worst-case rule changes;
(b) a new inductor kind that qualifies;
(c) build-simulation numbers that shift because stray and self-capacitance are modelled;
(d) the band-pass trimmer split;
(e) tolerance cases that use each part's own tolerance.

Each changed item is listed in ``tests/fixtures/hf_baseline_allowed_changes.json`` with
its kind and reason; ``tests/test_hf_baseline.py`` fails on any change that is not listed,
and on any listed change that no longer happens.

The corpus predates the 3.0.0 names. The recorder reads the toroid picks from the
generic ``inductor_suggestions`` record (toroid kind) and maps the renamed build method
``suggested_inductor`` (kind ``toroid``) back to the recorded
``verified_toroid_integer_turns``, so a rename is never a recorded change and only the
physical facts are compared.

Usage (from the repository root)::

    uv run python -m tests.hf_baseline_tool --write-corpus     # only from the old release
    uv run python -m tests.hf_baseline_tool --write-allowed    # after reviewing every diff
    uv run python -m tests.hf_baseline_tool --report           # print the current diffs
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"
CORPUS_PATH = FIXTURES / "hf_baseline.json"
ALLOWED_PATH = FIXTURES / "hf_baseline_allowed_changes.json"

SERIES = ("E12", "E24", "E96")
# The deck with chosen parts is recorded for this series; the JSON records every series.
SPICE_SERIES = "E24"

# Which permitted kinds may explain a change to each item type. Items whose type is not
# listed (the calculated values, the exact deck, the calculated-circuit measurement) may
# never change.
ITEM_KINDS: dict[str, frozenset[str]] = {
    "capacitor": frozenset("a"),
    "toroid": frozenset("b"),
    "response_check": frozenset(),
    "values": frozenset(),
    "spice_exact": frozenset(),
    "spice_nominal": frozenset("abcd"),
    "build_calculated": frozenset(),
    "build_parts": frozenset("abd"),
    "build_nominal": frozenset("abcd"),
    "build_summaries": frozenset("abcde"),
    "build_cases": frozenset("abcde"),
}

# Relative tolerance for measured numbers: refinement is deterministic, but the last bits
# of libm results can differ between platforms.
MEASUREMENT_REL_TOL = 1e-7
VALUE_REL_TOL = 1e-12


@dataclass(frozen=True)
class Design:
    """One HF design in the corpus."""

    case_id: str
    argv: tuple[str, ...]
    category: str
    build_series: str | None


_LADDER_FREQUENCIES = (
    "1.8MHz",
    "3.5MHz",
    "7.1MHz",
    "10.1MHz",
    "14.2MHz",
    "18.1MHz",
    "21MHz",
    "24.9MHz",
    "28MHz",
    "30MHz",
)
_BANDS = (
    ("1.9MHz", "50kHz"),
    ("3.6MHz", "100kHz"),
    ("7.1MHz", "200kHz"),
    ("10.12MHz", "300kHz"),
    ("14.2MHz", "350kHz"),
    ("18.1MHz", "500kHz"),
    ("21.2MHz", "500kHz"),
    ("24.9MHz", "800kHz"),
    ("28.5MHz", "1MHz"),
)
_TYPES = ("bw", "ch", "bs")
_ORDERS = (3, 5, 9)


def designs() -> tuple[Design, ...]:
    """The corpus designs, in a fixed order.

    Every ladder (type, order, topology) appears once, at a frequency that rotates
    through the HF bands; one topology of each (type, order) also runs the build
    simulation, with the series rotating. Every band-pass (type, order) appears once;
    orders 3 and 5 run the build (order 9 costs several seconds per run).
    """
    items: list[Design] = []
    index = 0
    for alias in ("lp", "hp"):
        for type_index, kind in enumerate(_TYPES):
            for order_index, order in enumerate(_ORDERS):
                for topology_index, topology in enumerate(("pi", "t")):
                    frequency = _LADDER_FREQUENCIES[index % len(_LADDER_FREQUENCIES)]
                    index += 1
                    ripple = ("-r", "0.5") if kind == "ch" else ()
                    builds = topology_index == (type_index + order_index) % 2
                    series = SERIES[(type_index * 3 + order_index) % 3] if builds else None
                    items.append(
                        Design(
                            case_id=f"{alias}-{kind}-{topology}-{frequency}-n{order}",
                            argv=(alias, kind, topology, frequency, "-n", str(order), *ripple),
                            category={"lp": "lowpass", "hp": "highpass"}[alias],
                            build_series=series,
                        )
                    )
    for type_index, kind in enumerate(_TYPES):
        for order_index, order in enumerate(_ORDERS):
            center, bandwidth = _BANDS[(type_index * 3 + order_index) % len(_BANDS)]
            ripple = ("-r", "0.5") if kind == "ch" else ()
            series = SERIES[(type_index + order_index) % 3] if order != 9 else None
            items.append(
                Design(
                    case_id=f"bp-{kind}-top-{center}-{bandwidth}-n{order}",
                    argv=("bp", kind, "top", "-f", center, "-b", bandwidth, "-n", str(order))
                    + ripple,
                    category="bandpass",
                    build_series=series,
                )
            )
    return tuple(items)


def _run_cli(*argv: str) -> str:
    """Run ``filter-calc *argv`` in-process and return its standard output."""
    from filter_lib import cli

    saved = sys.argv
    sys.argv = ["filter-calc", *argv]
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            cli.main()
    except SystemExit as exit_:
        if exit_.code not in (0, None):
            message = f"filter-calc {shlex.join(argv)} failed: {err.getvalue()}"
            raise RuntimeError(message) from exit_
    finally:
        sys.argv = saved
    return out.getvalue()


# -- Normalizing the JSON into recorded facts ----------------------------------------


def _part_values(selected: dict | None) -> list[float] | None:
    if selected is None:
        return None
    return [part["value_farads"] for part in selected["components"]]


def _capacitor_rows(document: dict, category: str) -> list[dict]:
    components = document["components"]
    if category == "bandpass":
        groups = ("tank_capacitors", "coupling_capacitors", "end_coupling_capacitors")
        return [row for group in groups for row in components[group]]
    return components["capacitors"]


def _value_rows(document: dict) -> list[list]:
    components = document["components"]
    rows = []
    for group in components.values():
        for row in group:
            value = row.get("value_farads", row.get("value_henries"))
            rows.append([row["name"], value])
    return rows


def _toroid_rows(document: dict, category: str) -> dict[str, list]:
    inductors = document["components"]["inductors"]
    if category == "bandpass":
        # Every resonator has the same inductance, so one candidate list serves them all.
        return {"resonators": _toroid_pick(inductors[0])}
    return {row["name"]: _toroid_pick(row) for row in inductors}


def _toroid_pick(inductor: dict) -> list:
    """The toroid kind's suggestions of one inductor, as the corpus recorded them."""
    kinds = inductor["inductor_suggestions"]["kinds"]
    [toroids] = [group for group in kinds if group["kind"] == "toroid"]
    return [
        [
            item["part_name"],
            item["build"]["winding"]["turns"],
            item["build"]["winding"]["l_actual_henries"],
            item["status"],
        ]
        for item in toroids["suggestions"]
    ]


# The build method's 3.0.0 name, mapped back to the name the corpus recorded.
_RECORDED_METHODS = {("suggested_inductor", "toroid"): "verified_toroid_integer_turns"}


def _recorded_method(part: dict) -> str:
    return _RECORDED_METHODS.get((part["method"], part.get("inductor_kind")), part["method"])


def _measurement(measurement: dict) -> dict:
    keys = (
        "f_low_hz",
        "f_high_hz",
        "worst_design_passband_gain_db",
        "peak_transducer_gain_db",
        "edge_at_simulation_grid_boundary",
        "measurement_converged",
    )
    return {key: measurement.get(key) for key in keys}


def _spice_elements(deck: str) -> list[list]:
    """The deck's element lines (name, nodes, value), without comments or controls."""
    rows = []
    for line in deck.splitlines():
        if not line or line.startswith(("*", ".")):
            continue
        fields = line.split()
        if fields[0].upper().startswith("V"):
            rows.append(fields)
            continue
        rows.append([fields[0], fields[1], fields[2], float(fields[3])])
    return rows


def record(design: Design) -> dict[str, object]:
    """Return ``{item: facts}`` for one corpus design, from the CLI's own output."""
    items: dict[str, object] = {}
    for series in SERIES:
        document = json.loads(_run_cli(*design.argv, "--format", "json", "--eseries", series))
        if series == SERIES[0]:
            items["values"] = _value_rows(document)
            for name, picks in _toroid_rows(document, design.category).items():
                items[f"toroid:{name}"] = picks
            if design.category == "bandpass":
                items["response_check"] = document["response_validation_status"]
        for row in _capacitor_rows(document, design.category):
            match = row["standard_match"]
            items[f"capacitor:{series}:{row['name']}"] = {
                "status": match["status"],
                "kind": None if match["selected"] is None else match["selected"]["kind"],
                "parts": _part_values(match["selected"]),
            }
    items["spice_exact"] = _spice_elements(
        _run_cli(*design.argv, "--format", "spice", "--spice-realization", "exact")
    )
    items["spice_nominal"] = _spice_elements(
        _run_cli(*design.argv, "--format", "spice", "--eseries", SPICE_SERIES)
    )
    if design.build_series is not None:
        build = json.loads(
            _run_cli(
                *design.argv, "--format", "json", "--sim-build", "--eseries", design.build_series
            )
        )
        items["build_calculated"] = _measurement(build["simulated"]["measurement"])
        items["build_nominal"] = _measurement(build["nominal_build"]["measurement"])
        items["build_parts"] = [
            [
                part["logical_name"],
                part["kind"],
                part["physical_parts_si"],
                part["core_name"],
                part["turns"],
                _recorded_method(part),
                part["status"],
            ]
            for part in build["nominal_build"]["substitutions"]
        ]
        analysis = build["tolerance_analysis"]
        items["build_summaries"] = [
            [
                summary["metric"],
                summary["minimum"],
                summary["p50"],
                summary["maximum"],
                summary["included_cases"],
                summary["omitted_cases"],
            ]
            for summary in analysis["metric_summaries"]
        ]
        items["build_cases"] = [
            [
                case["case_id"],
                [[f["physical_element_name"], f["factor"]] for f in case["component_factors"]],
                _measurement(case["measurement"]),
            ]
            for case in analysis["cases"]
        ]
    return items


def generate() -> dict:
    """Return the whole corpus as a JSON-ready dict."""
    return {
        "description": (
            "HF baseline corpus; see tests/hf_baseline_tool.py. Never regenerate it to "
            "absorb a change: list the change in hf_baseline_allowed_changes.json."
        ),
        "designs": {design.case_id: record(design) for design in designs()},
    }


def _corpus_text(corpus: dict) -> str:
    """The corpus as JSON with one line per item, so it stays small and easy to read."""
    lines = ["{", f' "description": {json.dumps(corpus["description"])},', ' "designs": {']
    design_blocks = []
    for case_id, items in corpus["designs"].items():
        item_lines = ",\n".join(
            f"   {json.dumps(item)}: {json.dumps(facts)}" for item, facts in items.items()
        )
        design_blocks.append(f"  {json.dumps(case_id)}: {{\n{item_lines}\n  }}")
    lines.append(",\n".join(design_blocks))
    lines.extend((" }", "}"))
    return "\n".join(lines) + "\n"


# -- Comparing -------------------------------------------------------------------------


def item_type(item: str) -> str:
    """The type of an item key (``capacitor:E24:C1`` -> ``capacitor``)."""
    return item.split(":", 1)[0]


def _close(expected: object, actual: object, rel_tol: float, abs_tol: float = 0.0) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if expected == actual:
            return True
        if not (math.isfinite(expected) and math.isfinite(actual)):
            return False
        return math.isclose(expected, actual, rel_tol=rel_tol, abs_tol=abs_tol)
    if isinstance(expected, dict) and isinstance(actual, dict):
        return expected.keys() == actual.keys() and all(
            _close(expected[key], actual[key], rel_tol, abs_tol) for key in expected
        )
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            _close(left, right, rel_tol, abs_tol) for left, right in zip(expected, actual)
        )
    return expected == actual


# Items holding only measurements (Hz, dB, case factors near 1, counts): a tiny absolute
# floor keeps a gain of 0 dB from differing with -1e-15 dB. Every other item holds
# capacitances or inductances, which must keep a purely relative comparison.
_MEASUREMENT_ITEMS = frozenset(
    {"build_calculated", "build_nominal", "build_summaries", "build_cases"}
)


def _same(item: str, expected: object, actual: object) -> bool:
    kind = item_type(item)
    if kind in _MEASUREMENT_ITEMS:
        return _close(expected, actual, MEASUREMENT_REL_TOL, 1e-9)
    if kind in {"values", "spice_exact"}:
        return _close(expected, actual, VALUE_REL_TOL)
    return _close(expected, actual, MEASUREMENT_REL_TOL)


def changed_items(expected: dict[str, object], actual: dict[str, object]) -> dict[str, tuple]:
    """``{item: (expected, actual)}`` for every item that differs (or appears/disappears)."""
    changes = {}
    for item in sorted(set(expected) | set(actual)):
        before, after = expected.get(item), actual.get(item)
        if item not in expected or item not in actual or not _same(item, before, after):
            changes[item] = (before, after)
    return changes


def load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def load_allowed() -> dict[tuple[str, str], dict]:
    """``{(case_id, item): entry}`` from the allow-list (empty when there is none)."""
    if not ALLOWED_PATH.exists():
        return {}
    entries = json.loads(ALLOWED_PATH.read_text(encoding="utf-8"))["changes"]
    return {(entry["case"], entry["item"]): entry for entry in entries}


# -- Describing a change for the allow-list -------------------------------------------


def _format_pf(value: float) -> str:
    return f"{value * 1e12:.4g} pF"


def _describe_parts(facts: dict | None) -> str:
    if facts is None:
        return "absent"
    parts = facts.get("parts")
    if not parts:
        return f"no part ({facts.get('status')})"
    return " || ".join(_format_pf(value) for value in parts) + f" [{facts.get('status')}]"


_STRAY_NAME = re.compile(r"^CSTRAY_")
# A chip inductor's self-capacitance branch, named for the inductor it is across.
_SELF_CAPACITANCE_NAME = re.compile(r"^CSELF_(?P<inductor>\S+)$")


def _changed_capacitors(changes: dict[str, tuple], series: str | None) -> list[str]:
    """Capacitors of ``series`` whose chosen parts changed (a status change alone does not)."""
    return [
        item
        for item, (before, after) in changes.items()
        if item.startswith(f"capacitor:{series}:")
        and (before or {}).get("parts") != (after or {}).get("parts")
    ]


def _build_pairs(parts: list) -> list[str]:
    """Names of the capacitors the build realized as a parallel pair."""
    return [row[0] for row in parts or [] if row[1] == "C" and len(row[2]) > 1]


def _parts_not_at_five_percent(parts: list) -> list[str]:
    """Capacitors with a part whose own tolerance differs from the old uniform 5%."""
    from fractions import Fraction

    from filter_lib.shared.capacitor_choice import part_pf, part_tolerance_pf
    from filter_lib.shared.eseries import DEFAULT_MATCH_POLICY

    names = []
    for name, kind, values, *_rest in parts or []:
        if kind != "C":
            continue
        for value in values:
            tolerance = part_tolerance_pf(part_pf(value), DEFAULT_MATCH_POLICY)
            if tolerance is not None and tolerance != part_pf(value) * Fraction(5, 100):
                names.append(name)
                break
    return names


def classify(
    design: Design, item: str, before: Any, after: Any, changes: dict[str, tuple], actual: dict
) -> tuple[list[str], str]:
    """Return the permitted kinds that explain a change, and a reason, by item type.

    A build change is explained by the causes present in that build: capacitor choices
    of its series that changed (a), a stray capacitor added across a pair (c), and parts
    whose own tolerance is not the old uniform 5% (e). A deck change is also explained by
    inductors now built as chip inductors (b), each with its self-capacitance across it (c).
    """
    kind = item_type(item)
    if kind == "capacitor":
        name = item.split(":", 1)[1]
        if before and after and before["parts"] == after["parts"]:
            return ["a"], (
                f"{name}: parts unchanged ({_describe_parts(after)}); at least one is not "
                "in the sourced table, so the nominal rule is kept and labelled"
            )
        return ["a"], (
            f"{name}: {_describe_parts(before)} -> {_describe_parts(after)} "
            "(worst-case interval rule)"
        )
    if kind == "spice_nominal":
        kinds, reasons = [], []
        names_before = {row[0] for row in before or []}
        names_after = {row[0] for row in after or []}
        added = sorted(name for name in names_after - names_before if _STRAY_NAME.match(name))
        if added:
            kinds.append("c")
            reasons.append(f"stray capacitor across each pair ({', '.join(added)})")
        # An inductor with a self-capacitance branch is a chip inductor: its value is the
        # part model's L0, which the new kind (b) and the branch (c) explain together. It
        # counts only when the inductor is still on its original terminals and the branch
        # is across those same terminals.
        terminals_before = {row[0]: tuple(row[1:3]) for row in before or []}
        terminals_after = {row[0]: tuple(row[1:3]) for row in after or []}
        chips = sorted(
            inductor
            for name in names_after - names_before
            if (match := _SELF_CAPACITANCE_NAME.match(name))
            and (inductor := match["inductor"]) in terminals_before
            and terminals_before[inductor] == terminals_after.get(inductor) == terminals_after[name]
        )
        self_capacitance = {f"CSELF_{inductor}" for inductor in chips}
        if chips:
            kinds.extend(code for code in ("b", "c") if code not in kinds)
            reasons.append(
                f"inductors built as chip inductors with their self-capacitance "
                f"({', '.join(chips)})"
            )

        def unexplained(rows):
            return [
                row
                for row in rows or []
                if not _STRAY_NAME.match(str(row[0]))
                and row[0] not in self_capacitance
                and row[0] not in chips
            ]

        other_before = unexplained(before)
        other_after = unexplained(after)
        if not _close(other_before, other_after, MEASUREMENT_REL_TOL):
            changed = _changed_capacitors(changes, SPICE_SERIES)
            if changed:
                kinds.append("a")
                reasons.append(f"chosen parts changed ({', '.join(changed)})")
        return kinds, "; ".join(reasons)
    if kind == "build_parts":
        changed = _changed_capacitors(changes, design.build_series)
        if changed:
            return ["a"], f"chosen parts changed ({', '.join(changed)})"
        # Each row ends with the substitution's status.
        relabelled = sorted(
            {row[0] for row in after or [] if row[-1] == "tolerance_not_sourced"}
            - {row[0] for row in before or [] if row[-1] == "tolerance_not_sourced"}
        )
        if relabelled and [row[:-1] for row in before] == [row[:-1] for row in after]:
            return [
                "a"
            ], f"parts unchanged, labelled tolerance not sourced ({', '.join(relabelled)})"
        return [], "not a permitted change"
    if kind in {"build_nominal", "build_summaries", "build_cases"}:
        parts = actual.get("build_parts")
        causes = (
            ("a", _changed_capacitors(changes, design.build_series), "new capacitor choices"),
            ("c", _build_pairs(parts), "a fixed stray across each pair"),
            ("e", _parts_not_at_five_percent(parts), "parts at their own tolerance"),
        )
        if kind == "build_nominal":
            # The nominal build has no tolerance cases.
            causes = causes[:2]
        kinds = [code for code, names, _text in causes if names]
        reason = "; ".join(f"{text} ({', '.join(names)})" for _code, names, text in causes if names)
        return kinds, reason
    return [], "not a permitted change"


def current_changes() -> list[dict]:
    """Every change between the corpus and the current code, classified."""
    corpus = load_corpus()["designs"]
    changes = []
    for design in designs():
        actual = record(design)
        changed = changed_items(corpus[design.case_id], actual)
        for item, (before, after) in changed.items():
            kinds, reason = classify(design, item, before, after, changed, actual)
            changes.append(
                {
                    "case": design.case_id,
                    "item": item,
                    "kinds": kinds,
                    "reason": reason,
                    # The reviewed new facts: any later change to the item fails the test.
                    "after": after,
                }
            )
    return changes


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate and compare the HF baseline corpus.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write-corpus", action="store_true")
    group.add_argument("--write-allowed", action="store_true")
    group.add_argument("--report", action="store_true")
    args = parser.parse_args(argv)
    if args.write_corpus:
        FIXTURES.mkdir(exist_ok=True)
        CORPUS_PATH.write_text(_corpus_text(generate()), encoding="utf-8")
        return
    changes = current_changes()
    if args.report:
        for change in changes:
            print(f"{change['case']} {change['item']} {change['kinds']}: {change['reason']}")
        return
    unexplained = [change for change in changes if not change["kinds"]]
    if unexplained:
        for change in unexplained:
            print(f"NOT PERMITTED: {change['case']} {change['item']}", file=sys.stderr)
        raise SystemExit(1)
    ALLOWED_PATH.write_text(_allowed_text(changes), encoding="utf-8")


def _allowed_text(changes: list[dict]) -> str:
    """The allow-list as JSON with one line per change, so a review reads it entry by entry."""
    lines = ",\n".join(f"  {json.dumps(change, ensure_ascii=False)}" for change in changes)
    return '{\n "changes": [\n' + lines + "\n ]\n}\n"


if __name__ == "__main__":
    main()
