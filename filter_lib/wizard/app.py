"""Main Textual application for the filter wizard.

Screen flow: welcome → filter config (LP/HP/BP) → output options → results.
Screens never pass data to each other directly; they read and mutate the
single `FilterState` instance hung on the app as `filter_state`.
"""

from textual.app import App
from textual.binding import Binding

from .state import FilterState


class FilterWizardApp(App):
    """Textual TUI application for guided filter design.

    Owns the shared `filter_state` that every screen reads/writes; screens
    are pushed onto the stack so Escape can walk back through the flow.
    """

    TITLE = "RF Filter Calculator"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Previous", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.filter_state = FilterState()

    def on_mount(self) -> None:
        """Push the welcome screen on startup."""
        # Deferred so importing FilterWizardApp (e.g. to patch it in tests)
        # doesn't drag in the whole screen tree.
        from .screens import WelcomeScreen

        self.push_screen(WelcomeScreen())

    def action_back(self) -> None:
        """Go back to the previous screen.

        The guard keeps Textual's base default screen on the stack — popping
        it would leave the app blank. (WelcomeScreen rebinds Escape to quit,
        so this is a safety net for any screen that doesn't.)
        """
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_quit(self) -> None:
        """Exit the application."""
        self.exit()


def run_app() -> None:
    """Run the filter wizard TUI application."""
    app = FilterWizardApp()
    app.run()


if __name__ == "__main__":
    run_app()
