# Shared Textual presentation candidate — 2026-10-06

## Scope and boundaries

This candidate starts from DWho `4e5b13ad3efc840049d2d7b7994479f7ba4bc42b`.
It adds an optional presentation package, an executable synthetic demo and
separate tests. It does not change the runtime, storage adapters, notifiers,
authentication, rules, execution engine or existing curses primitives.

DWho owns shared layout, visual states and interaction conventions. Product
adapters own collection, domain models, authorization and operations. Sonicprobe
remains a lower-level utility library. Atraxis, monit-docker and Auton are future
consumers; none has been migrated by this change.

The dashboard emits navigation and selection messages. Confirmations return
intent only. No request is sent automatically. Mode labels do not enforce test
isolation or permissions. Accepted, running and successful operations have
separate presentation states. External values render literally with bounded
length, not interpreted markup or control sequences.

## Compatibility and rollout

The extra `textual` depends on Textual 8.2.8–8.x on Python 3.9+. Base DWho keeps
its existing interpreter range and dependencies; importing `dwho.cli` or
`dwho.tui` does not import Textual/Rich. The modern optional test directory must
not be included in legacy interpreter discovery. Its dedicated CI matrix covers
Python 3.9, 3.12 and 3.14; existing modern, legacy and consumer jobs remain.

Keep this work on its feature branch while the concurrent DWho/HTTPdis review
is reconciled. Do not merge or publish a package as part of this candidate.
Version and release files deliberately remain unchanged. A published package
version and consumer minimum versions must be decided after review.

Migrate monit-docker and Auton separately, with parity checks for current views,
keyboard navigation, refresh, JSON/noninteractive output, API authorization and
operation failure handling. Preserve existing entry points until that work is
accepted. A working synthetic demo is not evidence of a production integration.

## Validation

Local Python 3.12.14 validation:

- Collection guard: 114 declarations and 114 unittest cases across `tests`,
  `textual_tests` and `.github/tests`.
- Base suite: 86 cases, 83 passed and 3 deliberately skipped because no disposable
  Redis URL was supplied. These existing integration cases retain their CI job.
- Optional suite: 10 passed, including keyboard search, selection across refresh,
  empty results, malformed snapshot rejection, resize, literal remote text,
  cancellation/confirmation, demo navigation and blocked framework imports.
- CI-helper suite: 18 cases, 17 passed and one pytest-specific case deliberately
  skipped under unittest.
- Wheel and source archive built; optional tests also passed against the installed
  wheel outside the source checkout. The installed base suite produced the same
  83 passes and 3 intentional Redis skips.
- User and contributor documentation built with Sphinx warnings treated as errors.
- Actual headless Textual rendering inspected at 156 by 46. A duplicated header
  exposed by visual inspection was corrected and covered in the demo test.

The complete remote interpreter matrix is a CI gate, not a local result.
No interactive SSH-terminal acceptance, consumer migration or production service
exercise is claimed.

## Reproduce

```sh
python -m pip install '.[textual]'
python .github/scripts/check-test-collection.py --runner unittest tests textual_tests .github/tests
python -m unittest discover -s tests -v
python -m unittest discover -s textual_tests -v
python -m unittest discover -s .github/tests -v
```

To verify an installed wheel, run these commands from a temporary directory,
using absolute paths for the guard and discovery roots. Do not add the checkout
to `PYTHONPATH`. Build documentation from `docs` with
`python -m sphinx -W --keep-going -b html . /tmp/dwho-docs`.
