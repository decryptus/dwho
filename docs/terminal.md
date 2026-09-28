# Shared terminal presentation (0.3.63 candidate)

`dwho.cli` and `dwho.tui` provide small presentation primitives extracted from
Galliflow and monit-docker. They do not initialize the HTTP framework, install
signals, read configuration, connect to Redis or own application operations.
Importing either module does not import curses. Interactive widgets require
Python 3.5+ and a Python build with curses; applications own `curses.wrapper`.

## Current scope

- `write_json(value, stream=None, **options)`: the existing JSON serialization
  options, one trailing newline, dynamic stdout or an explicit output stream.
  The application must redact sensitive data before calling it.
- `require_terminal(message, stdin=None, stdout=None)`: require both terminal
  streams before importing an application's interactive interface.
- `put(screen, row, text, style=0)`: bounded screen writes with resize tolerance.
- `prompt(screen, title, initial='', help_text=..., max_length=1024)`: editable
  input; Escape returns `None`, Enter accepts the value, including an empty one.
- `view_details(screen, title, source, help_text=...)`: wrapped, scrollable text.
- `confirm(screen, title, source, help_text=..., accept_keys=('y',),
  cancel_keys=('\x1b', 'q', 'n'))`: presentation-only confirmation. It never
  invokes an action. Galliflow explicitly keeps its existing French text and `o`.

The caller owns selection and permission checks, parsing, exception mapping,
exit codes, translations and secret handling. Do not import these interfaces
from neutral business services. Confirmation is not authorization.

## Consumers and compatibility

Galliflow's site/token interfaces use these primitives while preserving their
public entry points, prompts and shortcuts. monit-docker reuses JSON output;
its current main branch has no ncurses interface to extract. Its local YAML
model and all command arguments remain unchanged.

`examples/certlord_terminal.py` shows the same CertLord service index through
JSON or a curses detail screen. It accepts an already composed service and
contains no certificate storage or issuance logic. This is an integration
example, not an installed CertLord command or a production administration UI.

## Deliberate limits

This first extraction does not unify existing command parsers or provide a
command registry, universal forms, permissions or a Centrex client. Those need
separate interface contracts; migrating every command is not needed to reuse
the tested presentation primitives. No automatic refresh or disk logging is
added. JSON output is preserved byte-for-byte for existing call options.

## Rollout

Review and release DWho 0.3.63 first, then merge the consumer changes requiring
that version. Consumer PRs must remain drafts until that package is available.
The Galliflow admin image also needs the new dependency. No version is
published by creating these PRs.

## Verification

`python -m unittest discover -s tests -p test_terminal.py -v` exercises output,
terminal detection, keyboard editing, confirmation, scrolling, narrow windows,
resize errors and optional-import independence. Existing Galliflow terminal
scenarios and CLI contract suites remain the consumer regression gates.
