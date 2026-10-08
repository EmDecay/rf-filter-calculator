"""The build simulation's Q reference frequency, as the wizard and the web name it.

The CLI's flag is ``--loss-reference-frequency``; both interfaces show the field as
``Q_FREQUENCY_LABEL`` (blank = the cutoff or center frequency) and parse it with
``parse_q_frequency``, so a rejected entry names the field the user sees.
"""

from __future__ import annotations

from ..shared.parsing import parse_frequency

Q_FREQUENCY_LABEL = "Frequency at which the Q values apply"
Q_FREQUENCY_HELP = (
    "Blank = the cutoff frequency (low-pass, high-pass) or the center frequency (band-pass)."
)

# The shared parser writes "Invalid <label.lower()>: ..."; inside a sentence only the
# first letter should drop to lower case, so "Q" stays a capital.
_Q_FREQUENCY_LOWERED = Q_FREQUENCY_LABEL.lower()
_Q_FREQUENCY_IN_SENTENCE = Q_FREQUENCY_LABEL[:1].lower() + Q_FREQUENCY_LABEL[1:]


def parse_q_frequency(value: str) -> float:
    """Parse a Q reference frequency entry (``10MHz``, ``10M``, ``10e6``)."""
    try:
        return parse_frequency(value, label=Q_FREQUENCY_LABEL)
    except ValueError as error:
        message = str(error).replace(_Q_FREQUENCY_LOWERED, _Q_FREQUENCY_IN_SENTENCE, 1)
        raise ValueError(message) from None
