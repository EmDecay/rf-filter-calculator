"""Design-field rules shared by the wizard's live Input styling and its Next handlers.

The LP/HP/BP forms once styled the ripple field with a 0.01 dB floor that their Next
handlers did not apply. One parser now owns the ripple contract, and the Textual
validator delegates to it, so a field turns red exactly when Next would reject it.
"""

import math

from textual.validation import ValidationResult, Validator

from ..bandpass.numeric_validation import MAX_CHEBYSHEV_RIPPLE_DB


def parse_ripple_db(text: str) -> float:
    """Parse a Chebyshev ripple entry under the shared ``0 < ripple <= 3.0 dB`` contract.

    Raises:
        ValueError: With the text shown after ``Invalid ripple:``, including the
            ``float()`` message for unparseable input.
    """
    if not isinstance(text, str):
        raise ValueError("must be supplied as text")
    ripple = float(text)
    if not math.isfinite(ripple):
        raise ValueError("must be finite")
    if ripple <= 0:
        raise ValueError("must be positive")
    if ripple > MAX_CHEBYSHEV_RIPPLE_DB:
        raise ValueError(f"must be <= {MAX_CHEBYSHEV_RIPPLE_DB} dB")
    return ripple


class RippleValidator(Validator):
    """Textual validator whose verdict and message come from :func:`parse_ripple_db`."""

    def validate(self, value: str) -> ValidationResult:
        try:
            parse_ripple_db(value)
        except ValueError as error:
            return self.failure(str(error), value)
        return self.success()
