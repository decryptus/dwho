# Contributor documentation

This guide is for people changing or maintaining dwho. For installation, configuration and everyday use, start with the [user documentation](https://github.com/decryptus/dwho/blob/master/README.md).

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

License: GPL-3.0-or-later. See [LICENSE](https://github.com/decryptus/dwho/blob/master/LICENSE).

See the [September 2026 code and architecture review](https://github.com/decryptus/dwho/blob/master/docs/REVIEW.md) (French).

## Documentation rules

Keep user instructions and contributor material separate. The repository [engineering requirements](https://github.com/decryptus/dwho/blob/master/AGENTS.md) define the review and validation rules. Preserve user-facing compatibility, security and recovery guidance when moving internal explanations.
