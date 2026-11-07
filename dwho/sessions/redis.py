# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Redis implementation; inject a redis-py client with finite timeouts."""
from dwho.sessions import SessionBackend, _ttl


class RedisSessionBackend(SessionBackend):
    def __init__(self, client):
        self.client = client

    def create(self, key, value, ttl):
        return bool(self.client.execute_command('SET', key, value, 'EX', _ttl(ttl), 'NX'))

    def read(self, key):
        return self.client.get(key)

    def touch(self, key, ttl):
        # Atomic and cannot resurrect a revoked or expired session.
        return bool(self.client.expire(key, _ttl(ttl)))

    def delete(self, key):
        return bool(self.client.delete(key))
