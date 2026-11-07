# Sessions with pluggable storage

The `dwho.sessions` API is available from the repository development version.
It does not authenticate passwords or decide permissions. Your application
verifies the account, creates a session, and resolves its subject on requests.
Accounts and passwords remain in the application's account repository.

```python
from redis import Redis
from dwho.sessions import SessionManager
from dwho.sessions.redis import RedisSessionBackend

client = Redis.from_url('redis://127.0.0.1:6379/0',
                        socket_connect_timeout=2, socket_timeout=2)
sessions = SessionManager(RedisSessionBackend(client), namespace='example',
                          idle_ttl=3600, absolute_ttl=86400)
grant = sessions.create('user-id', {'credential_version': 1})
# Send grant.token only over TLS; do not log it.
session = sessions.read(grant.token)
renewed = sessions.renew(grant.token)  # None if missing/expired/revoked
sessions.revoke(grant.token)
client.connection_pool.disconnect()  # application owns client lifecycle
```

Tokens contain 256 random bits. Storage keys contain only a SHA-256 digest and
an application namespace; records contain the subject, JSON data and creation /
absolute expiry dates. Do not put passwords or other credentials in session data.
Use a stable unique namespace (letters, digits, underscore or dash, 1–64 chars).
`grant.expires_at` is the idle expiry; `grant.session.absolute_expires_at` is the
maximum lifetime. TTL values are integer seconds, bounded to 366 days.

Reads do not renew. Renewal atomically extends the idle TTL without exceeding
the absolute lifetime. It cannot recreate a revoked/expired key. Revocation is
per token/device; an already admitted request may finish. For account-wide
revocation, check a credential version in your account store on every request.
There is no device listing or bulk account revocation API in this module.

Redis failures propagate: the application must fail closed (normally 503), never
silently fall back to local memory. Use finite connection/read timeouts. Secure
Redis with network isolation and, where appropriate, ACLs and TLS. Persistence
and backups are deployment choices: AOF `everysec` can lose about one second of
changes after a crash, including a recent revocation. Prefer `appendfsync always`
when that durability matters; benchmark the write cost. Avoid rolling back a
session database from an old backup without invalidating its namespace.

`MemorySessionBackend(capacity=10000, clock=...)` offers the same contract for
tests or one-process development, with a lock and a capacity limit. It rejects
new sessions when full after purging expired entries; live sessions are not
evicted. It is neither persistent nor shared between workers.

To add a backend, implement `SessionBackend.create(key, value, ttl)`, `read(key)`,
`touch(key, ttl)` and `delete(key)`. Creation must be atomic and conditional on
absence; reads enforce expiry; touch must be atomic and never insert. Store
UTF-8 JSON values, return booleans from mutations and None for an absent read.
Backend errors must propagate. Inject the adapter into `SessionManager`; no
registry, HTTP import, configuration loader or global mutable state is required.
