"""Navigation mixin for wizard screens with consistent Enter key handling."""

from textual.widgets import Input, RadioSet


class FilterScreenNavigationMixin:
    """Mixin providing Enter key navigation between RadioSets and first Input.

    Enter inside a RadioSet has no useful default mid-form, so the LP/HP/BP
    screens repurpose it as "accept selection and advance", letting keyboard
    users flow top-to-bottom through the form with Enter alone (Inputs then
    chain onward via their own Submitted handlers).

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
            for i, radio_id in enumerate(self.RADIO_SET_FLOW):
                radio_set = self.query_one(f"#{radio_id}", RadioSet)
                if radio_set.has_focus:
                    # Last RadioSet hands focus to the first Input field.
                    if i < len(self.RADIO_SET_FLOW) - 1:
                        next_radio = self.query_one(f"#{self.RADIO_SET_FLOW[i + 1]}", RadioSet)
                        next_radio.focus()
                    elif self.FIRST_INPUT_ID:
                        self.query_one(f"#{self.FIRST_INPUT_ID}", Input).focus()
                    # Swallow the key so the RadioSet doesn't also act on it.
                    event.prevent_default()
                    event.stop()
                    return
        except (AttributeError, LookupError):
            # Key events can arrive before the widgets are mounted (or from a
            # screen that mis-declares an ID); ignoring beats crashing the app
            # on a keystroke.
            pass
