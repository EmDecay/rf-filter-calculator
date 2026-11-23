<!--
Thank you for contributing. Text between these comment markers does not appear in the
pull request, so you can leave it in place.

Title: use a conventional commit, such as "fix: keep band-pass edges inside the sweep", or
"feat!: ..." for a breaking change. A squash merge uses the title as the commit message.
-->

## Summary

<!--
What changes and why, in a few sentences or bullets. Say what someone using the command
line, wizard or web UI will notice. Start a breaking change (a removed or renamed flag,
choice value, JSON key or CSV column) with **Breaking:**.
-->

## Related issue

<!--
"Closes #123" closes the issue when this pull request merges; "Refs #123" links it without
closing it. Write "None" if there is no issue.
-->

## Testing

<!--
The commands you ran and their results, such as the pytest summary line. If calculated
values, chosen parts or other results change, give one design's command with its output
before and after.
-->

<!--
Optional sections: delete the comment markers around a section to use it.

## Stack

This is PR N of M in a stack: `first-branch` → `second-branch` → `third-branch`. Its base
is `first-branch`. Merge in order.

## Review

For each review round: the reviewer, the commit reviewed, and what was decided.

| # | Finding | Severity | Disposition | Evidence | Fix |
|---|---|---|---|---|---|
-->

## Checklist

<!-- Tick each item that is done or does not apply to this change. -->

- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass.
- [ ] `uv run pytest tests/` passes with the `web` extra installed
      (`uv sync --group dev --extra web`), and new behavior and fixed bugs have tests.
      CI also requires 90% coverage
      ([Testing Guide](https://github.com/EmDecay/rf-filter-calculator/blob/main/docs/testing.md#quality-gates)).
- [ ] **Docs and changelog.** A change users can see (output, flags, wizard or web UI
      controls, JSON keys or CSV columns) updates the affected docs and the newest entry in
      `docs/project-changelog.md`. Documented `uv run filter-calc` examples still run as
      written; the tests run them.
- [ ] **Command line, wizard and web UI agree.** A new input or rule goes through
      `filter_lib.design`, and `design/option_applicability.py` decides when an option
      applies, never one interface on its own. All three give the same result, and a
      message shown on more than one of them uses its shared constant
      ([User-Facing Text](https://github.com/EmDecay/rf-filter-calculator/blob/main/docs/code-standards.md#user-facing-text)).
- [ ] **HF baseline.** If `tests/test_hf_baseline.py` reports a change
      (`uv run python -m tests.hf_baseline_tool --report` lists them), each changed item is
      listed with a permitted kind and a reason in
      `tests/fixtures/hf_baseline_allowed_changes.json`. The recorded corpus is never
      regenerated to absorb a change.
- [ ] **Part data.** New or changed packaged part data (capacitor grades, toroid cores, chip
      inductors, trimmers) cites the manufacturer's datasheet, specification or catalog page
      and updates
      [Component Data Sources](https://github.com/EmDecay/rf-filter-calculator/blob/main/docs/component-data-sources.md).
