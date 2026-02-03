"""Interactive wizard for filter design.

Main entry point that launches the Textual TUI wizard.
"""


def run_wizard() -> None:
    """Main wizard entry point.

    Launches the Textual TUI application for guided filter design.
    """
    from .app import FilterWizardApp

    app = FilterWizardApp()
    app.run()
