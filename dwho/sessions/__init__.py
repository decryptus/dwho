# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opaque sessions independent of HTTP, account storage and authorization."""
from __future__ import absolute_import

import base64
import hashlib
import json
import math
import os
import re
import time
from collections import namedtuple

from six import integer_types, string_types

TOKEN_PATTERN = re.compile(r'\A[A-Za-z0-9_-]{43}\Z')
NAMESPACE_PATTERN = re.compile(r'\A[A-Za-z0-9_-]{1,64}\Z')
MAX_TTL = 366 * 24 * 60 * 60
MAX_DATA_BYTES = 4096


class SessionBackend(object):
    """Thread-safe storage contract, with atomic operations and enforced TTL.

    Values are UTF-8 JSON strings, keys contain a namespace and token digest.
    create returns False on collision; read returns None for absent/expired keys.
    touch MUST NOT recreate missing keys or shorten an existing TTL.
    Errors must propagate (fail closed).
    Backends own their clock/expiry; callers own clients and connection lifecycle.
    """
    def create(self, key, value, ttl):
        raise NotImplementedError()

    def read(self, key):
        raise NotImplementedError()

    def touch(self, key, ttl):
        raise NotImplementedError()

    def delete(self, key):
        raise NotImplementedError()


class Session(namedtuple('_Session', 'subject data created_at absolute_expires_at')):
    __slots__ = ()


class SessionGrant(namedtuple('_SessionGrant', 'token session expires_at')):
    __slots__ = ()

    def __repr__(self):
        return 'SessionGrant(<redacted>)'


def _ttl(value):
    if isinstance(value, bool) or not isinstance(value, integer_types) or not 1 <= value <= MAX_TTL:
        raise ValueError('TTL must be an integer between 1 and %s seconds' % MAX_TTL)
    return value


class SessionManager(object):
    """Create/read/renew/revoke sessions through any SessionBackend.

    Tokens carry 256 random bits; only SHA-256 digests reach the backend.
    Reading never extends a session. Renew extends idle TTL, bounded by the
    original absolute expiry. Revocation does not cancel already admitted work.
    """
    def __init__(self, backend, namespace, idle_ttl=3600, absolute_ttl=86400,
                 clock=time.time):
        if not isinstance(namespace, string_types) or not NAMESPACE_PATTERN.match(namespace):
            raise ValueError('invalid session namespace')
        self.backend = backend
        self.prefix = namespace + ':session:'
        self.idle_ttl = _ttl(idle_ttl)
        self.absolute_ttl = _ttl(absolute_ttl)
        if self.idle_ttl > self.absolute_ttl:
            raise ValueError('idle TTL exceeds absolute TTL')
        self.clock = clock

    def _key(self, token):
        if not isinstance(token, string_types) or not TOKEN_PATTERN.match(token):
            return None
        return self.prefix + hashlib.sha256(token.encode('ascii')).hexdigest()

    def create(self, subject, data=None):
        if not isinstance(subject, string_types) or not 1 <= len(subject) <= 256:
            raise ValueError('invalid session subject')
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError('session data must be a JSON object')
        now = self.clock()
        record = {'subject': subject, 'data': data, 'created_at': now,
                  'absolute_expires_at': now + self.absolute_ttl}
        value = json.dumps(record, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
        if len(value.encode('utf-8')) > MAX_DATA_BYTES:
            raise ValueError('session data too large')
        # Round-trip so mutations by the caller cannot alter an issued record.
        session = Session(**json.loads(value))
        for _ in range(3):
            token = base64.urlsafe_b64encode(os.urandom(32)).decode('ascii').rstrip('=')
            if self.backend.create(self._key(token), value, self.idle_ttl):
                return SessionGrant(token, session, now + self.idle_ttl)
        raise RuntimeError('unable to allocate a session')

    def read(self, token):
        key = self._key(token)
        if key is None:
            return None
        value = self.backend.read(key)
        if value is None:
            return None
        # Corrupt backend data is an operational failure, never an anonymous user.
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        if len(value) > MAX_DATA_BYTES:
            raise ValueError('invalid stored session')
        record = json.loads(value)
        session = Session(**record)
        if (not isinstance(session.subject, string_types)
                or not 1 <= len(session.subject) <= 256
                or not isinstance(session.data, dict)
                or not isinstance(session.absolute_expires_at, (int, float))
                or (math.isnan(float(session.absolute_expires_at))
                    or math.isinf(float(session.absolute_expires_at)))):
            raise ValueError('invalid stored session')
        if session.absolute_expires_at <= self.clock():
            self.backend.delete(key)
            return None
        return session

    def renew(self, token):
        session = self.read(token)
        if session is None:
            return None
        now = self.clock()
        ttl = min(self.idle_ttl, int(session.absolute_expires_at - now))
        if ttl < 1 or not self.backend.touch(self._key(token), ttl):
            return None
        return SessionGrant(token, session, now + ttl)

    def revoke(self, token):
        key = self._key(token)
        return bool(key is not None and self.backend.delete(key))
