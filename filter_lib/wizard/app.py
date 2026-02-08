"""Main Textual application for the filter wizard."""

from textual.app import App
from textual.binding import Binding

from .state import FilterState


class FilterWizardApp(App):
    """Textual TUI application for guided filter design."""

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
        from .screens import WelcomeScreen

        self.push_screen(WelcomeScreen())

    def action_back(self) -> None:
        """Go back to the previous screen."""
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
