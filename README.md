# dwho

Shared building blocks for Python services: plugin and module lifecycles,
configuration, notifications, Redis, SQL objects and Linux filesystem events.
Used by [Covenant](https://github.com/decryptus/covenant) and
[Auton](https://github.com/decryptus/auton).
The name is a nod to **Doctor Who**, alongside Sonicprobe, HTTPdis (TARDIS)
and Auton. This is an independent project, not an official Doctor Who product.

## Where it fits

- **sonicprobe** provides general helpers, workers, networking and SQL adapters.
- **httpdis** provides HTTP routing, requests and responses.
- **dwho** provides the shared application conventions on top of these libraries.

Use dwho when extending an existing service in this ecosystem. It is a library,
not a standalone daemon or a replacement for every web framework.

## Installation and compatibility

```sh
python -m pip install dwho
```

Linux is required for inotify. Dependencies with native code, such as pycurl,
may need a compiler and libcurl development headers when wheels are unavailable.
The declared interpreter range remains Python 2.7 and Python 3.5+; modern Python
is preferred for new deployments. Legacy Python requires legacy dependency
versions. CI records which interpreters pass; it does not certify every plugin,
Redis server or database driver. `pyasyncore` supplies pyinotify's removed
standard-library dependency on Python 3.12+.

## Load trusted plugins

```python
from dwho.classes.libloader import DwhoLibLoader
modules = DwhoLibLoader.load_dir('my_service.plugins', '/etc/my-service/plugins')
```

Each visible `.py` file (except names ending in `__init__.py`) executes once per
module name. Later calls reuse `sys.modules`; this is not a hot-reload API.
Modules register in `sys.modules` before execution, and failed loads are removed
so they can be retried. Python 2.7 uses `imp`; modern interpreters use `importlib`.
Plugin files execute arbitrary Python and must be trusted.

## Redis

```python
from dwho.adapters.redis import DWhoAdapterRedis

config = {'general': {'redis': {
    'cache': {'url': 'redis://127.0.0.1:6379/0'},
    'events': {'url': 'redis://127.0.0.1:6379/1'},
}}}
adapter = DWhoAdapterRedis(config)
try:
    adapter.set_key('example', 'hello', expire=60, prefix='cache')
finally:
    adapter.disconnect()
```

Connections are cached per server name. `prefix` selects configured names;
write operations return a mapping of server names to results.

## Notifications and filesystem events

`DWhoPushNotifications(config_path=...)` reads YAML files from a directory.
Each has `general.uri`, optional `general.tags`, `general.async` and a template
file path. Supported schemes are HTTP(S), Redis and `subproc`.

```yaml
# notifications/webhook.yml
general:
  uri: 'https://example.org/events/${target}'
  tags: [all]
```

```python
from dwho.classes.notifiers import DWhoPushNotifications
notify = DWhoPushNotifications(config_path='/etc/my-service/notifications')
notify({'target': 'worker'}, names=['webhook'])
```

Mako templates and subprocess configurations are trusted administrator inputs.
Each invocation receives its own configuration and variables. Subprocess timeout
is configured at the YAML top level with `timeout` (seconds); shutdown attempts
terminate, then kill after one second, and reaps the direct child. Commands should
not daemonize or leave descendants holding their output pipes.

### Explicit delivery results

Existing `notify(...)` calls keep their legacy behavior, including asynchronous
dispatch and logged delivery failures. Built-in `__call__` signatures and URI
registration through `DWhoNotifiers` are unchanged.

For callers that must know whether delivery succeeded, use the opt-in API:

```python
results = notify.send({'target': 'worker'}, names=['webhook'])
# {'webhook': [True]} on HTTP success; failures raise an exception.
```

`send()` renders the same configuration/templates and runs selected handlers
**synchronously**, even when `general.async` is true. It returns a dictionary
mapping notification names to a list of handler results (one URI scheme can have
multiple registered handlers). It stops at the first delivery error. Unknown names,
an explicit empty name list, or an empty selection raise rather than report success.
Omitting `names` selects all configured names using the existing tag/enabled filters.

All built-in handlers expose the same direct API:
`send(name, cfg, tpl=None, nvars=None)`. Direct calls receive already-rendered
configuration and template dictionaries; use `DWhoPushNotifications.send()` when
you need YAML loading, URI/template rendering and notification variables.

| Handler | Successful result | Failure |
| --- | --- | --- |
| HTTP(S) | `True` for a final 2xx response | HTTP, timeout and connection exceptions propagate |
| Redis `set` | Mapping of server names to SET acknowledgements | Configuration, serialization and Redis errors propagate |
| Redis `stream` | Mapping of server names to generated entry IDs | Same, including unsupported commands and wrong key types |
| Subprocess | `True` after exit code 0 | Nonzero exit, spawn error or timeout raises; child cleanup still runs |

These acknowledge the destination response, not downstream processing. Multiple
destinations are not a transaction: earlier sends may succeed before a later one
fails. A retry can duplicate deliveries, including after a network timeout with
an uncertain write outcome. Consumers should handle duplicates. For a webhook
bridge, use one explicit destination and return HTTP success only after `send()`
returns successfully; map delivery failures to an appropriate retryable response.

Custom notifiers implementing only `__call__` continue to work with the legacy
dispatcher. To opt in, implement `send(name, cfg, tpl=None, nvars=None)` and return
a truthy acknowledgement or raise. The base implementation raises
`NotImplementedError`; strict dispatch rejects legacy-only handlers before any
delivery. It never infers success by calling a legacy handler that returns `None`.

### Redis Streams

Redis notifications still default to **SET**, with the original `key`/`value`
template and JSON encoding. Repeated writes to that key replace the value.
To append events instead, set `general.redis_mode: stream`:

```yaml
# /etc/my-service/notifications/events.yml
general:
  uri: 'redis://127.0.0.1:6379/0?socket_timeout=5&socket_connect_timeout=5'
  tags: [all]
  redis_mode: stream
  stream_maxlen: 10000
  template: /etc/my-service/templates/event.json
```

```json
{"key": "monitoring:alerts", "value": ${json.dumps(_VARS_)}}
```

The second snippet is a trusted Mako template, rendered into JSON by the dispatcher.
Each `XADD` creates an ID and stores the complete serialized `value` in a stream
field named `payload`. `stream_maxlen` is an optional positive integer: when set,
exact `MAXLEN` trimming bounds the stream length. If omitted, no trimming is
performed. Trimming can remove events before a slow consumer processes them.

```python
from dwho.classes.notifiers import DWhoPushNotifications
notify = DWhoPushNotifications(config_path='/etc/my-service/notifications')
ids = notify.send({'status': 'firing', 'container': 'web'}, names=['events'])
# {'events': [{'notifier': b'...-0'}]} with the default redis-py decoding settings.
```

Streams require **Redis server 5.0+**. The adapter uses `execute_command('XADD', ...)`
so the new mode does not require upgrading old redis-py clients merely to obtain
an `xadd()` helper. The existing dependency and Python compatibility ranges remain
unchanged. Use a new key when migrating from SET: an existing string key is not
converted, deleted or overwritten if XADD reports `WRONGTYPE`.

Server persistence, retention and consumer acknowledgements are separate choices;
successful XADD does not guarantee survival of a Redis crash or consumer processing.
No automatic retry, consumer group, Pub/Sub publication or webhook server is added
by this library change. Keep connection timeouts finite for request/response callers.
See the [Redis XADD reference](https://redis.io/docs/latest/commands/xadd/).

Inotify dispatch chooses the most specific matching directory, using path
components rather than string prefixes. Filtering plugins for one event no longer
changes the configured list for later events.

## Encryption and migration

For new data use authenticated encryption with a random **16, 24 or 32 byte key**:

```python
from Crypto.Random import get_random_bytes
from dwho.helpers.crypto import DWhoCryptoHelper
key = get_random_bytes(32)  # Persist securely; do not regenerate when reading.
token = DWhoCryptoHelper.serialize_authenticated(key, {'status': 'ready'})
assert DWhoCryptoHelper.unserialize_authenticated(key, token) == {'status': 'ready'}
```

The `dwho-eax-v1:` format uses AES-EAX and JSON serialization. Altered ciphertext,
incorrect keys and legacy tokens are rejected by the authenticated reader.
`encrypt_authenticated` / `decrypt_authenticated` handle raw bytes; text inputs
are encoded as UTF-8 and decrypted output is bytes. JSON preserves JSON types,
not arbitrary Python objects.

Existing `encrypt` / `decrypt` retain the historical CBC wire format and key
truncation, including its unusual treatment of exactly 24/32 byte keys. CBC does
**not** authenticate data. `serialize` uses pickle protocol 2 for legacy readers.
`unserialize` accepts ordinary data but blocks arbitrary pickle globals by default;
custom Python objects now require `trusted=True`. That option can execute code:
use it only for known, trusted historical records, never attacker-controlled data.
Do not expose legacy CBC deserialization as a public endpoint.

Migration is explicit: read trusted legacy data, write authenticated JSON, and
upgrade all readers before switching writers. Older dwho cannot read EAX tokens.
Store keys separately from encrypted records. This is not a password KDF.

## SQL objects

`DWhoObjectSQLBase` keeps values bound as parameters. Column names in conditions,
updates, searches and ordering must be simple identifiers (optionally qualified,
e.g. `jobs.id`); sorting accepts `ASC` or `DESC`. SQL expressions in these fields
are now rejected. Empty `IN` lists match nothing. A zero limit returns no rows.
Use explicit reviewed queries through the SQL adapter for expression-based queries.

## Development and releases

```sh
python -m pip install -e . mock
python -m unittest discover -s tests -v
python -m pip install build twine
python -m build
python -m twine check --strict dist/*
```

Tests use temporary files, SQLite, mocked Redis and actual local subprocesses.
CI also exercises SET and Streams against disposable Redis 5 and Redis 7 services.
To run those integration tests locally, point `DWHO_REDIS_TEST_URL` at a disposable
server and run `python -m unittest discover -s tests -p test_redis_integration.py -v`.
Only UUID-prefixed test keys are created/deleted; the database is never flushed.
No production service is contacted. See `.github/workflows/tests.yml` for the
compatibility matrix and `.github/workflows/pypi.yml` for release gates.

To release, update `VERSION`, `RELEASE` and both version fields in `setup.yml`
together, then merge the tested PR. The publication workflow validates the package,
creates `vX.Y.Z` on master and publishes the same artifacts using PyPI Trusted
Publishing (`decryptus/dwho`, `pypi.yml`, environment `pypi`). Existing version tags
are never moved. Ordinary commits on an already tagged version do not republish it.

License: GPL-3.0-or-later. See [LICENSE](LICENSE).

See the [September 2026 code and architecture review](docs/REVIEW.md) (French).
