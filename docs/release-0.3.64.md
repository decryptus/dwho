# dwho 0.3.64

- Do not initialize or execute disabled inotify plugins.
- Reject invalid notification filters instead of broadening delivery.
- Clean up failed runtime startup while preserving the original error.
- Escape literal SQL LIKE wildcards and cover audit regressions.

See [audit validation and remaining limits](audit-corrections-2026-10-07.md).

Install with `python -m pip install dwho==0.3.64`.
