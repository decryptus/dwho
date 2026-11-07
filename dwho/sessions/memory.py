# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded process-local backend for tests and single-process development."""
import threading
import time

from six import integer_types
from dwho.sessions import SessionBackend, _ttl


class MemorySessionBackend(SessionBackend):
    def __init__(self, capacity=10000, clock=time.time):
        if isinstance(capacity, bool) or not isinstance(capacity, integer_types) or capacity < 1:
            raise ValueError('invalid capacity')
        self.capacity = capacity
        self.clock = clock
        self._values = {}
        self._lock = threading.RLock()

    def _read(self, key):
        value = self._values.get(key)
        if value is not None and value[1] <= self.clock():
            del self._values[key]
            return None
        return value

    def create(self, key, value, ttl):
        _ttl(ttl)
        with self._lock:
            if self._read(key) is not None:
                return False
            if len(self._values) >= self.capacity:
                for expired in list(self._values):
                    self._read(expired)
                if len(self._values) >= self.capacity:
                    raise RuntimeError('session capacity exhausted')
            self._values[key] = (value, self.clock() + ttl)
            return True

    def read(self, key):
        with self._lock:
            value = self._read(key)
            return value[0] if value is not None else None

    def touch(self, key, ttl):
        _ttl(ttl)
        with self._lock:
            value = self._read(key)
            if value is None:
                return False
            self._values[key] = (value[0], max(value[1], self.clock() + ttl))
            return True

    def delete(self, key):
        with self._lock:
            return self._values.pop(key, None) is not None
