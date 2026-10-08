"""The shared applicability rule, tabulated for the page's script.

The page disables an option that cannot apply and shows the reason next to it, as the
user changes Format, Standard capacitor values, Raw units, Simulate the built filter,
or Toroid windings. Those five choices have 64 combinations, so the server evaluates
``filter_lib.design.option_applicability`` for each one and the script only looks the
answer up: the rule is never restated in JavaScript.
"""

from __future__ import annotations

import json
from itertools import product

from ..design.option_applicability import OutputChoices, inapplicable_options
from ..shared.cli_aliases import DEFAULT_ESERIES

# The page's Format values, in its order.
PAGE_FORMATS = ("table", "quiet", "json", "csv")


def state_key(
    output_format: str, no_eseries: bool, raw: bool, build: bool, no_toroids: bool
) -> str:
    """Key of one combination; ``app.js`` builds the same string from the form."""
    return "|".join(
        (output_format, *("1" if on else "0" for on in (no_eseries, raw, build, no_toroids)))
    )


def option_states() -> dict:
    """``{"reasons": [text, ...], "states": {key: {option: reason index}}}``.

    Each reason is stored once and referred to by index to keep the page small.
    """
    reasons: list[str] = []
    states: dict[str, dict[str, int]] = {}
    for output_format, no_eseries, raw, build, no_toroids in product(
        PAGE_FORMATS, *[(False, True)] * 4
    ):
        choices = OutputChoices(
            output_format=output_format,
            eseries=None if no_eseries else DEFAULT_ESERIES,
            raw=raw,
            build=build,
            include_toroids=not no_toroids,
        )
        entry = {}
        for option, reason in inapplicable_options(choices).items():
            if reason not in reasons:
                reasons.append(reason)
            entry[option] = reasons.index(reason)
        states[state_key(output_format, no_eseries, raw, build, no_toroids)] = entry
    return {"reasons": reasons, "states": states}


OPTION_STATES_JSON = json.dumps(option_states(), separators=(",", ":"))
