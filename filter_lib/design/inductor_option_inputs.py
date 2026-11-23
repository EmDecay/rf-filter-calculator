"""The inductor suggestion and build-inductor controls as the wizard and the web show them.

Both interfaces use these labels, choices and help texts for the CLI's
``--inductor-suggestions`` and ``--build-inductors``; the values are the CLI's. The web
offers "Inductors in the build" with the build simulation's fields, so it applies to the
build and to the "SPICE – chosen parts" download only while the build is ticked.
"""

from __future__ import annotations

from ..shared.inductor_suggestion import BUILD_INDUCTOR_CHOICES, INDUCTOR_DETAILS

INDUCTOR_DETAIL_LABEL = "Inductor suggestions (table detail)"
# The wizard adds a description after " - "; the web shows the label only.
INDUCTOR_DETAIL_CHOICES = (
    ("best", "Best, detailed"),
    ("full", "Up to 3 per kind, detailed"),
    ("compact", "Best, one line"),
    ("none", "None"),
)
INDUCTOR_DETAIL_HELP = (
    "Best shows the part the build uses, else the first in the order toroid winding, "
    "air-core coil, chip inductor; up to 3 per kind also says why a kind has none. JSON "
    "lists up to three per kind and CSV the best, whatever is chosen here. None leaves "
    "the suggestions out of JSON, CSV, the build simulation, and the SPICE – chosen parts "
    "download."
)
BUILD_INDUCTORS_LABEL = "Inductors in the build"
BUILD_INDUCTORS_CHOICES = (
    ("auto", "Auto"),
    ("toroid", "Toroid windings"),
    ("air-coil", "Air-core coils"),
    ("chip", "Chip inductors"),
    ("calculated", "Calculated values"),
)
BUILD_INDUCTORS_HELP = (
    "Auto uses each inductor's first suggestion in the order toroid winding, air-core "
    "coil, chip inductor; a kind uses that kind's best suggestion. An inductor with no "
    "such suggestion, or Calculated values, uses the calculated inductance."
)

assert tuple(value for value, _label in INDUCTOR_DETAIL_CHOICES) == INDUCTOR_DETAILS
assert tuple(value for value, _label in BUILD_INDUCTORS_CHOICES) == BUILD_INDUCTOR_CHOICES

__all__ = [
    "BUILD_INDUCTORS_CHOICES",
    "BUILD_INDUCTORS_HELP",
    "BUILD_INDUCTORS_LABEL",
    "INDUCTOR_DETAIL_CHOICES",
    "INDUCTOR_DETAIL_HELP",
    "INDUCTOR_DETAIL_LABEL",
]
