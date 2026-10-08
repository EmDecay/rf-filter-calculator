"""Navigation mixin for the design screens: Enter moves through the form in order."""

from textual.widgets import Input, RadioSet


class FilterScreenNavigationMixin:
    """Enter advances through ``FOCUS_FLOW``, the screen's controls in form order.

    Enter inside a RadioSet has no useful default mid-form, so the LP/HP/BP screens
    repurpose it as "accept selection and advance"; Enter in an Input (its Submitted
    message) advances too. Controls the screen currently hides or disables are skipped
    (``_is_shown``), so keyboard users flow top to bottom with Enter alone.

    Screens using this mixin define ``FOCUS_FLOW``: widget ids of RadioSets and Inputs
    in form order, ending with the Next button's id.

    Example:
        class LowpassScreen(FilterScreenNavigationMixin, Screen):
            FOCUS_FLOW = ("filter-type", "topology", "ripple", "frequency", "next-btn")
    """

    FOCUS_FLOW: tuple[str, ...] = ()

    def _is_shown(self, widget_id: str) -> bool:
        """Whether ``widget_id`` can take focus now; screens hide fields per choice."""
        return self.query_one(f"#{widget_id}").disabled is not True

    def _focus_after(self, widget_id: str) -> None:
        """Focus the first control after ``widget_id`` that is shown."""
        flow = self.FOCUS_FLOW
        for candidate in flow[flow.index(widget_id) + 1 :]:
            if self._is_shown(candidate):
                self.query_one(f"#{candidate}").focus()
                return

    def on_key(self, event) -> None:
        """Handle Enter key to advance from RadioSet selections."""
        if event.key != "enter":
            return

        try:
            for widget_id in self.FOCUS_FLOW:
                widget = self.query_one(f"#{widget_id}")
                if isinstance(widget, RadioSet) and widget.has_focus:
                    self._focus_after(widget_id)
                    # Swallow the key so the RadioSet doesn't also act on it.
                    event.prevent_default()
                    event.stop()
                    return
        except (AttributeError, LookupError):
            # Key events can arrive before the widgets are mounted (or from a
            # screen that mis-declares an ID); ignoring beats crashing the app
            # on a keystroke.
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in a field advances to the next shown control."""
        if event.input.id in self.FOCUS_FLOW:
            self._focus_after(event.input.id)
