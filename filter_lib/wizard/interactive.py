"""Interactive wizard for filter design.

Main entry point that launches the Textual TUI wizard. The CLI dispatches
here when invoked with no arguments (see `cli/wizard_cmd.py`).
"""


def run_wizard() -> None:
    """Main wizard entry point.

    Launches the Textual TUI application for guided filter design.
    """
    # Deliberately imported here, not at module level: the name
    # `FilterWizardApp` must not exist in this module's namespace so tests
    # can mock it with a single patch at the definition site
    # ("filter_lib.wizard.app.FilterWizardApp"). It also keeps `import
    # filter_lib.wizard` cheap — Textual is only loaded when the wizard runs.
    from .app import FilterWizardApp

    app = FilterWizardApp()
    app.run()
