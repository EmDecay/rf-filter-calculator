"""Navigation mixin for wizard screens with consistent Enter key handling."""
from textual.widgets import RadioSet, Input


class FilterScreenNavigationMixin:
    """Mixin providing Enter key navigation between RadioSets and first Input.

    Screens using this mixin should define:
        RADIO_SET_FLOW: list[str] - Widget IDs for RadioSets to navigate through
        FIRST_INPUT_ID: str - Widget ID of the first Input field after RadioSets

    Example:
        class LowpassScreen(FilterScreenNavigationMixin, Screen):
            RADIO_SET_FLOW = ["filter-type", "topology"]
            FIRST_INPUT_ID = "frequency"
    """

    RADIO_SET_FLOW: list[str] = []
    FIRST_INPUT_ID: str = ""

    def on_key(self, event) -> None:
        """Handle Enter key to advance from RadioSet selections."""
        if event.key != "enter":
            return

        try:
            # Check each RadioSet in the flow
            for i, radio_id in enumerate(self.RADIO_SET_FLOW):
                radio_set = self.query_one(f"#{radio_id}", RadioSet)
                if radio_set.has_focus:
                    # Move to next RadioSet or first Input
                    if i < len(self.RADIO_SET_FLOW) - 1:
                        next_radio = self.query_one(
                            f"#{self.RADIO_SET_FLOW[i + 1]}", RadioSet
                        )
                        next_radio.focus()
                    elif self.FIRST_INPUT_ID:
                        self.query_one(f"#{self.FIRST_INPUT_ID}", Input).focus()
                    event.prevent_default()
                    event.stop()
                    return
        except (AttributeError, LookupError):
            # Widget not yet mounted or not found; safe to ignore
            pass
