# Explicit configuration and runtime composition

`dwho.configuration.read_conf()` reads YAML (including relative module/plugin,
credential and custom files), or the configured environment variable, and normalizes
general settings. It does not install signals, configure logging, register routes,
create directories for inotify, or start plugins/watchers. It can run in a worker
thread. A supplied parser replaces the default parser and is responsible for its
own side effects. Inotify-specific validation/preparation happens at runtime
initialization; successful reading alone does not validate watcher paths/events.

`dwho.runtime.DWhoRuntime` accepts explicit dictionaries of **fresh extension
instances**, an optional route registration callable and optional watcher/parser
factories. It owns a copied configuration, local registries, shared keystore,
stop callbacks and (when configured) a watcher with its own command queue.
Reusing an initialized extension or one already claimed by a runtime is rejected.
Registries should be completed before initialization; this is not hot reload.

Example with the new HTTPdis context API (HTTPdis PR #5):

```python
from dwho.configuration import read_conf
from dwho.runtime import DWhoRuntime
from httpdis.httpdis import HttpServerContext

transport = HttpServerContext()
runtime = DWhoRuntime(
    modules={'example': ExampleModule()},
    plugins={'worker': WorkerPlugin()},
    route_registrar=transport.register)
try:
    runtime.initialize(read_conf('application.yml'))
    # Pass launcher-created HTTP options as before; no signals by default.
    transport.init(options)
    runtime.start()
    transport.run()
finally:
    try:
        transport.stop()
    finally:
        runtime.stop()
```

Existing HTTPdis releases can still be used with an explicitly supplied registrar;
the isolated HTTP server API is only needed for separate HTTP servers. The neutral
runtime and configuration modules do not import HTTPdis, Mako, CLI, curses, or
pyinotify. Watcher integration is loaded only when requested. Module classes remain
transport adapters and may import HTTP/template dependencies.

The launcher owns options, signals, logging, transport startup/shutdown and module
HTTP lifecycle hooks. The runtime calls plugin hooks with their existing signatures.
Its lifecycle is one-shot: initialize, optional start, stop. Initialization/start
failures clean up registered plugin/watcher callbacks and preserve the original
exception. Stop attempts every callback once, then raises the first cleanup error.
As with legacy callbacks, they must return promptly: no forced cancellation or
bounded joins are introduced here. Serialize initialization/start/stop in the
launcher; repeated stop calls consume the callback list only once.

If initialization fails after route registration, discard the runtime and its
transport: arbitrary extension side effects and registered routes are not rolled
back. Extensions must make `at_stop` safe after partial `safe_init`.

## Compatibility

- `dwho.config.load_conf`, `parse_conf`, the global registries, `DWHO_THREADS`,
  `DWHO_SHARED`, software-name/version helpers and start/stop functions remain
  legacy process-wide entry points. `load_conf` still installs SIGINT/SIGTERM and
  initializes modules/plugins, and therefore still belongs in the main launcher
  thread. Import the new `dwho.configuration` module for a neutral dependency path.
- Existing module `.init(config)` and plugin hooks retain their signatures.
  Modules without a bound registrar still use `httpdis.register`.
- `DWhoInotify.add/rem` remain static legacy queue operations. New contexts use
  `DWhoInotifyContext.add/rem` and an instance queue. Inotify configuration can
  accept an explicit plugin registry; the default resolves the legacy registry.
- Existing exception imports and pickle paths remain valid; configuration errors
  are now also available from the neutral `dwho.errors` module.
- Global default objects are deliberately shared. New contexts do not isolate
  application-owned globals, class attributes, callbacks or arbitrary plugins that
  explicitly reference the legacy globals. Such extensions need explicit adapter
  adoption; this addition does not silently migrate existing applications.

Tests cover threaded configuration reads, relative imports, environment/custom
configuration, error identity, import boundaries, local route/plugin ownership,
partial failure cleanup, watcher queues and unchanged legacy entry points. CI
runs against the existing dependency baseline and separately against the pinned
HTTPdis context candidate, plus consumer regressions and distribution checks.
