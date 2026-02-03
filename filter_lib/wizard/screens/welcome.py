"""Welcome screen for filter category selection."""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static, OptionList
from textual.widgets.option_list import Option
from textual.containers import VerticalScroll


class WelcomeScreen(Screen):
    """Initial screen for selecting filter category."""

    BINDINGS = [
        ("escape", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("RF Filter Calculator", classes="header")
        with VerticalScroll(classes="content"):
            yield Static("Select Filter Type", classes="welcome-title")
            yield Static(
                "Design LC filters for RF applications",
                classes="welcome-subtitle"
            )
            yield OptionList(
                Option("Low-Pass Filter - Attenuates frequencies above cutoff", id="lowpass"),
                Option("High-Pass Filter - Attenuates frequencies below cutoff", id="highpass"),
                Option("Band-Pass Filter - Passes frequencies within a range", id="bandpass"),
                id="filter-options",
            )
        yield Footer()

    def on_mount(self) -> None:
        """Focus on the option list when screen mounts."""
        self.query_one("#filter-options", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle filter category selection via Enter key."""
        option_id = event.option.id
        app = self.app

        if option_id == "lowpass":
            app.filter_state.category = "lowpass"
            from .lowpass import LowpassScreen
            app.push_screen(LowpassScreen())
        elif option_id == "highpass":
            app.filter_state.category = "highpass"
            from .highpass import HighpassScreen
            app.push_screen(HighpassScreen())
        elif option_id == "bandpass":
            app.filter_state.category = "bandpass"
            from .bandpass import BandpassScreen
            app.push_screen(BandpassScreen())

    def action_quit(self) -> None:
        """Exit the application from welcome screen."""
        self.app.exit()
