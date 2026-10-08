"""Design-field rules shared by the wizard's live Input styling and its Next handlers.

The LP/HP/BP forms once styled the ripple field with a 0.01 dB floor that their Next
handlers did not apply. One parser now owns the ripple contract, and the Textual
validator delegates to it, so a field turns red exactly when Next would reject it.
"""

import math

from textual.validation import ValidationResult, Validator

from ..shared.cli_aliases import MAX_RIPPLE_DB, RIPPLE_RANGE_MESSAGE

# Field labels shared by the design screens. Those keyed by ``is_chebyshev`` follow the
# response choice: the Chebyshev cutoff is the edge of the ripple band, not the -3 dB
# point, and Chebyshev needs an odd number of components or resonators.
CUTOFF_LABELS = {
    False: "Cutoff frequency, the -3 dB point (e.g. 14.2MHz, 7100kHz; blank = 10MHz):",
    True: "Cutoff frequency, the ripple-band edge (e.g. 14.2MHz, 7100kHz; blank = 10MHz):",
}
COUNT_LABELS = {
    False: "Number of components (2-9):",
    True: "Number of components (Chebyshev: odd only — 3, 5, 7, 9):",
}
RESONATOR_COUNT_LABELS = {
    False: "Number of resonators (2-9):",
    True: "Number of resonators (Chebyshev: odd only — 3, 5, 7, 9):",
}
RIPPLE_LABEL = f"Passband ripple, dB (above 0, up to {MAX_RIPPLE_DB:g}):"


def parse_ripple_db(text: str) -> float:
    """Parse a Chebyshev ripple entry under the shared ``0 < ripple <= 3.0 dB`` contract.

    Raises:
        ValueError: With the shared ripple-range message (the CLI's and web's text) for
            any entry outside the range, including text that is not a number.
    """
    if not isinstance(text, str):
        raise ValueError("must be supplied as text")
    try:
        ripple = float(text)
    except ValueError:
        raise ValueError(RIPPLE_RANGE_MESSAGE) from None
    if not math.isfinite(ripple) or not 0 < ripple <= MAX_RIPPLE_DB:
        raise ValueError(RIPPLE_RANGE_MESSAGE)
    return ripple


class RippleValidator(Validator):
    """Textual validator whose verdict and message come from :func:`parse_ripple_db`."""

    def validate(self, value: str) -> ValidationResult:
        try:
            parse_ripple_db(value)
        except ValueError as error:
            return self.failure(str(error), value)
        return self.success()
