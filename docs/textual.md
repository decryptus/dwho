# Optional Textual dashboards

The optional `dwho.tui.textual` package provides a shared terminal presentation
for modern applications. It requires **Python 3.9+** and **Textual 8.2.8–8.x**.
Install the Textual extra (product palettes require DWho 0.3.66+):

```sh
python -m pip install 'dwho[textual]>=0.3.66'
python -m dwho.tui.textual.demo
```

The demo uses synthetic container and job data. It connects to no service and
performs no intervention. `/` focuses search, Escape clears it, `q` quits, and
`c` opens a demonstration confirmation. Use at least 80 columns by 24 rows;
120 columns or more gives the details panel more room.

## Product colors

Dashboards select their palette from the product name, ignoring letter case:

| Product | Palette |
| --- | --- |
| Atraxis | Midnight blue / cyan |
| Auton | Turquoise / orange |
| monit-docker | Steel blue |
| Galliflow | Violet |
| CertLord | Gold / charcoal |

Navigation, tables, input forms and confirmation dialogs share that palette.
Layout and shortcuts stay the same. Status labels keep their shared meaning:
blue acceptance/queue, violet in progress, green confirmed success, amber warning
or unknown outcome, and red failure/refusal. Product accents never indicate success.

Unknown product names use the default blue. For a customized product label, pass
`palette='auton'` (or `atraxis`, `monit-docker`, `galliflow`, `certlord`, `default`)
to `DashboardApp`. An invalid explicit palette raises `ValueError`.
Themes are independent per application instance.

## Integration

```python
from dwho.cli import require_terminal
from dwho.tui.textual import DashboardApp, TableRow

class Inventory(DashboardApp):
    def __init__(self):
        super().__init__(
            product='My product', heading='Resources',
            columns=('NAME', 'STATUS'), mode='read_only')

    def on_mount(self):
        self.display_rows([
            TableRow('api-01', ('API', 'HEALTHY'), 'API', 'Latest observation: healthy')
        ])

if __name__ == '__main__':
    require_terminal('This interface requires an interactive terminal.')
    Inventory().run()
```

Textual dispatches mount handlers through the class hierarchy automatically;
do not explicitly call the parent `on_mount`. Columns are created during
composition so subclass mount handlers can immediately supply rows.

`TableRow(key, cells, title, details)` uses a stable, unique string key.
`display_rows(rows)` replaces the current snapshot and preserves selection by
key across reordering. Invalid or duplicate rows raise `ValueError` before
replacing the previous snapshot. Search matches displayed cells, ignoring case.
No matches clears the previous detail selection. Snapshots are limited to 10,000
rows and 20 columns; each cell is limited to 1,024 characters and details to
65,536 characters. These are display bounds, not a pagination service.

Applications own collection, refresh intervals, cancellation and error handling.
Call widget methods from the application thread; a worker should use Textual's
`app.call_from_thread(...)` to deliver a completed snapshot. Do not block the UI
thread with network requests or commands.

## Components and messages

- `DashboardApp`: product heading, optional navigation pairs `(key, label)`,
  up to four metric tuples `(label, value, note, state)`, search, table, details
  and recent activity. Metric values in this initial shell are set at creation.
- `DashboardApp.NavigationRequested`: emits the requested `key`. The owning
  application loads the view and calls `select_navigation(key)` when appropriate.
- `DashboardApp.SelectionChanged`: emits the highlighted row `key`; it does not
  execute an operation. Refreshes can emit selection messages too.
- `set_notice(state, text)` and `set_activity(text)`: update visible status and
  multiline activity. Activity replaces its previous contents; it is not a log store.
- `StatusLine`, `MetricCard`, `DetailPanel`: reusable presentation widgets.
  Standalone layouts can reuse `SHELL_CSS` from `dwho.tui.textual.theme`.
- `Confirmation(title, details, confirm_label='Confirm')`: use
  `app.push_screen(dialog, callback)`. The callback receives a boolean intent;
  Cancel is focused initially and Escape returns `False`.

- `InputForm(title, fields, hint='', submit='Continue')`: fields are tuples of
  `(key, label, initial_value, secret)`. The callback receives a dictionary of
  literal values, or `None` on cancellation. Services must validate the values.
- `ServiceDashboard.perform(call, done, failed=None, label=...)`: runs one blocking
  service call in a background thread and returns its result to the UI thread.
  Concurrent requests are refused; errors never trigger a retry. The application
  supplies safe error presentation and remains responsible for request deadlines.
  Ordinary quit waits for the pending request; forced process termination cannot
  establish the remote outcome.

States include `info`, `accepted`, `queued`, `running`, `success`, `warning`,
`unknown`, `failure` and `denied`. Text accompanies the color, and acceptance is
distinct from success. Unrecognized states display as unknown.

## Application responsibilities

`read_only`, `test` and `interactive` are visible mode labels only. The application
and its services must enforce permissions, test isolation, request validation
and any execution policy. Confirmation never authorizes a server operation.
The shell imports no storage adapter or HTTP framework and starts no service.

Values supplied to these components render as literal text. Control characters
are replaced and Rich markup is not evaluated. Applications must redact secrets
before display; truncation and literal rendering do not provide redaction.

Base `dwho.cli` and `dwho.tui` remain usable without installing Textual or Rich.
Existing curses consumers are unchanged. Product integrations and full feature
parity must be validated separately before switching their default interfaces.
