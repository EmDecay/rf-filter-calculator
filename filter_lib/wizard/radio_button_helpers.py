"""Shared utility functions for wizard screens."""

from textual.screen import Screen
from textual.widgets import RadioSet


def get_selected_radio(screen: Screen, radio_set_id: str) -> str:
    """Get the ID of the selected radio button in a RadioSet.

    Args:
        screen: The screen containing the RadioSet
        radio_set_id: The ID of the RadioSet widget

    Returns:
        The ID of the selected radio button, or empty string if none selected
    """
    radio_set = screen.query_one(f"#{radio_set_id}", RadioSet)
    if radio_set.pressed_button:
        return radio_set.pressed_button.id
    return ""
