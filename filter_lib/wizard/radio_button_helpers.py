"""Shared utility functions for wizard screens."""

from textual.screen import Screen
from textual.widgets import RadioButton, RadioSet


def get_selected_radio(screen: Screen, radio_set_id: str) -> str:
    """Get the ID of the selected radio button in a RadioSet.

    Args:
        screen: The screen containing the RadioSet
        radio_set_id: The ID of the RadioSet widget

    Returns:
        The ID of the selected radio button, or empty string if none selected.
        The empty-string fallback lets callers substitute their own default
        (e.g. `get_selected_radio(...) or "E24"`) instead of handling None.
    """
    radio_set = screen.query_one(f"#{radio_set_id}", RadioSet)
    if radio_set.pressed_button:
        return radio_set.pressed_button.id
    return ""


class EnabledRadioSet(RadioSet):
    """A RadioSet whose disabled buttons cannot be pressed from the keyboard.

    Textual keeps the arrow-key highlight on a button that becomes disabled, and Space
    or Enter then presses it. The wizard disables choices that cannot apply (the shared
    option rule), so a highlighted disabled button is left as it is.
    """

    def action_toggle_button(self) -> None:
        # ``_selected`` is Textual's highlight index (private, hence the guarded read).
        selected = getattr(self, "_selected", None)
        buttons = list(self.query(RadioButton))
        if selected is not None and 0 <= selected < len(buttons) and buttons[selected].disabled:
            return
        super().action_toggle_button()
