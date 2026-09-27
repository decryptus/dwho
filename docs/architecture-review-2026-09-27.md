# Architecture review — 2026-09-27

Reviewed commit: `3ea4a1002a37fd84c45b6c13e158ed61c67b5c95` on `master`.
Status: **review and engineering requirements only; runtime findings remain open**.

Scope: separation of application logic, interfaces and adapters; callback and
initialization ownership; fixed validation contracts. Source files were fetched
at the pinned commit. This PR does not change runtime code or claim CI enforcement
of the new requirements. [Pinned source](https://github.com/decryptus/dwho/tree/3ea4a1002a37fd84c45b6c13e158ed61c67b5c95).

## Confirmed findings

### D1 — Medium: reading configuration installs process signal handlers

`dwho/config.py:load_conf` calls `signal.signal` for SIGTERM and SIGINT before
loading/validating the file. A configuration caller therefore also changes global
process lifecycle; calling it from a worker thread can fail at signal registration.
Separate read/parse/validate from launcher-owned signal installation and shutdown.
Keep `init_modules`, `init_plugins`, `start_plugins` and inotify startup explicit.
Acceptance: configuration loading works in a worker and does not replace a host
process's signal handlers; startup/shutdown tests still exercise the launcher.

### D2 — Medium: registries and configuration lifecycle are process-global

`classes/modules.py:MODULES`, `classes/plugins.py:PLUGINS` and `config.py`'s
thread/inotify lifecycle bind composition to shared mutable state. Modules register
routes through global `httpdis.register`; the initialized flag is on the registered
module instance. A second configured application cannot assume isolated modules,
plugins or routing. Introduce explicit registry/runtime contexts where independent
instances are needed; preserve the existing extension hooks deliberately.

## Role boundaries

`DWhoModuleBase` imports HTTPdis and Mako and implements route registration. This
is appropriate for a framework HTTP adapter; it must not become the parent of
neutral application services simply to reuse business operations. The plugin base
and helper paths do not import a CLI. Configuration logging/startup helpers are
valid launcher operations if invoked explicitly at that boundary.

## Verification and limits

AST imports and lazy functions were inspected in all 19 package Python files.
No CLI, argparse or curses import was found. Config loading, module registration,
plugin lifecycle and abstract helpers were traced in source. This is a source
architecture review, not a rerun of all SQL/Redis/inotify integration tests.
