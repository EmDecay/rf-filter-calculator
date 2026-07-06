"""Interactive wizard module for guided filter design.

Only `run_wizard` is public API; the Textual app, screens, and state are
internal and reached through it.
"""

from .interactive import run_wizard

__all__ = [
    "run_wizard",
]
