# Audit correction compatibility

Inotify plugins require an explicit boolean `true` globally. A watched path can
restrict that selection but cannot reactivate a globally disabled plugin.
Nonempty path mappings containing only plugin options still select a globally
enabled plugin. String values such as `"false"` no longer enable plugins.
Disabled plugins do not run initialization/cleanup hooks or event callbacks.

With the default `strict=True`, notification `tags` must be a nonempty collection
of valid tags. Invalid or empty explicit filters raise `ValueError` before any
notification is delivered. Omit `tags` to retain the default selection. The
existing explicit `strict=False` behavior and configuration normalization remain.

SQL substring searches treat `%`, `_` and `!` as literal input using an explicit
SQL escape character, while keeping query parameters separate from SQL text.

Modern package builds require setuptools 83 or newer on Python 3.10+.
Legacy interpreter build constraints remain unchanged and are not covered by the
modern dependency security validation. Install coordinated Sonicprobe and HTTPdis
corrections to obtain the full corrected dependency set.
