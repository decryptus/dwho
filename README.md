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
No production service is contacted. See `.github/workflows/tests.yml` for the
compatibility matrix and `.github/workflows/pypi.yml` for release gates.

To release, update `VERSION`, `RELEASE` and both version fields in `setup.yml`
together, then merge the tested PR. The publication workflow validates the package,
creates `vX.Y.Z` on master and publishes the same artifacts using PyPI Trusted
Publishing (`decryptus/dwho`, `pypi.yml`, environment `pypi`). Existing version tags
are never moved. Ordinary commits on an already tagged version do not republish it.

License: GPL-3.0-or-later. See [LICENSE](LICENSE).

See the [September 2026 code and architecture review](docs/REVIEW.md) (French).
