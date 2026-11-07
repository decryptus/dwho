# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import threading
import unittest

from dwho.sessions import SessionManager
from dwho.sessions.memory import MemorySessionBackend


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.now = [1000.0]
        self.backend = MemorySessionBackend(clock=lambda: self.now[0])
        self.manager = SessionManager(self.backend, 'example', 10, 25, lambda: self.now[0])

    def test_opaque_token_digest_and_copied_data(self):
        data = {'version': 1}
        grant = self.manager.create('alice', data)
        data['version'] = 9
        self.assertNotIn(grant.token, repr(grant))
        self.assertNotIn(grant.token, repr(self.backend._values))
        self.assertEqual(self.manager.read(grant.token).data, {'version': 1})
        grant.session.data['version'] = 8
        self.assertEqual(self.manager.read(grant.token).data, {'version': 1})

    def test_read_does_not_renew_idle_expiration(self):
        grant = self.manager.create('alice')
        self.now[0] += 9
        self.assertIsNotNone(self.manager.read(grant.token))
        self.now[0] += 1
        self.assertIsNone(self.manager.read(grant.token))
        self.assertIsNone(self.manager.renew(grant.token))

    def test_absolute_lifetime_caps_renewal(self):
        grant = self.manager.create('alice')
        for now in (1009, 1018, 1024):
            self.now[0] = now
            renewed = self.manager.renew(grant.token)
            self.assertLessEqual(renewed.expires_at, 1025)
        self.now[0] = 1025
        self.assertIsNone(self.manager.read(grant.token))

    def test_revocation_racing_renew_cannot_resurrect(self):
        grant = self.manager.create('alice')
        original = self.backend.touch
        def racing_touch(key, ttl):
            self.manager.revoke(grant.token)
            return original(key, ttl)
        self.backend.touch = racing_touch
        self.assertIsNone(self.manager.renew(grant.token))
        self.assertIsNone(self.manager.read(grant.token))

    def test_namespaces_and_independent_devices(self):
        first = self.manager.create('alice')
        second = self.manager.create('alice')
        other = SessionManager(self.backend, 'other')
        self.assertIsNone(other.read(first.token))
        self.assertTrue(self.manager.revoke(first.token))
        self.assertFalse(self.manager.revoke(first.token))
        self.assertIsNotNone(self.manager.read(second.token))

    def test_stale_touch_cannot_shorten_a_newer_renewal(self):
        grant = self.manager.create('alice')
        key = self.manager._key(grant.token)
        self.assertTrue(self.backend.touch(key, 20))
        self.assertTrue(self.backend.touch(key, 5))
        self.now[0] += 15
        self.assertIsNotNone(self.manager.read(grant.token))

    def test_invalid_inputs_never_reach_storage(self):
        for token in (None, '', 'x' * 42, 'x' * 43 + '\n', 'a' * 10000):
            self.assertIsNone(self.manager.read(token))
            self.assertFalse(self.manager.revoke(token))
        for ttl in (True, 0, -1, 1.1, '2'):
            with self.assertRaises(ValueError):
                SessionManager(self.backend, 'test', ttl)
        for namespace in ('', 'a:b', 'a\n'):
            with self.assertRaises(ValueError):
                SessionManager(self.backend, namespace)
        with self.assertRaises(ValueError):
            self.manager.create('alice', {'large': 'x' * 4096})

    def test_capacity_purges_only_expired_sessions(self):
        backend = MemorySessionBackend(capacity=1, clock=lambda: self.now[0])
        manager = SessionManager(backend, 'test', 10, 20, lambda: self.now[0])
        first = manager.create('alice')
        with self.assertRaises(RuntimeError):
            manager.create('bob')
        self.assertIsNotNone(manager.read(first.token))
        self.now[0] += 10
        self.assertEqual(manager.create('bob').session.subject, 'bob')

    def test_parallel_creates_are_unique(self):
        grants = []
        threads = [threading.Thread(target=lambda: grants.append(self.manager.create('alice')))
                   for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        self.assertEqual(len(set(grant.token for grant in grants)), 20)

    def test_backend_errors_and_corruption_fail_closed(self):
        grant = self.manager.create('alice')
        key = self.manager._key(grant.token)
        self.backend._values[key] = (json.dumps({'broken': True}), 1010)
        with self.assertRaises(TypeError):
            self.manager.read(grant.token)
        def unavailable(key):
            raise IOError('offline')
        self.backend.read = unavailable
        with self.assertRaises(IOError):
            self.manager.read(grant.token)

    def test_neutral_modules_import_without_http_or_framework(self):
        code = '''
import sys
class Block(object):
    def find_spec(self, fullname, path=None, target=None):
        return self.find_module(fullname, path)
    def find_module(self, fullname, path=None):
        if fullname.startswith(('httpdis', 'dwho.modules', 'dwho.runtime', 'dwho.config')):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
from dwho.sessions import SessionManager
from dwho.sessions.memory import MemorySessionBackend
from dwho.sessions.redis import RedisSessionBackend
assert SessionManager(MemorySessionBackend(), 'test').create('alice').session.subject == 'alice'
'''
        subprocess.check_call([sys.executable, '-c', code], cwd=os.getcwd())
