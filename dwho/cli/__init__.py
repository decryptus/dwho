# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Terminal output primitives, independent of curses and framework startup."""
from __future__ import absolute_import

import json
import sys


def write_json(value, stream=None, **options):
    """Write one JSON value and newline using the caller's serialization policy.

    The caller owns redaction and exit codes. No buffering, logging or implicit
    conversion of unsupported objects is added here.
    """
    target = sys.stdout if stream is None else stream
    target.write(json.dumps(value, **options) + '\n')


def require_terminal(message, stdin=None, stdout=None):
    """Reject interactive entry points before importing their curses module."""
    source = sys.stdin if stdin is None else stdin
    target = sys.stdout if stdout is None else stdout
    if not source.isatty() or not target.isatty():
        raise ValueError(message)
