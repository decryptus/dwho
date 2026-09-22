# -*- coding: utf-8 -*-
"""Opt-in tests using only UUID-prefixed keys on a disposable Redis server."""
import json
import os
import unittest
import uuid

from redis import Redis
from redis.exceptions import ResponseError

from dwho.classes.notifiers import DWhoNotifierRedis


@unittest.skipUnless(os.environ.get('DWHO_REDIS_TEST_URL'), 'requires disposable Redis')
class RedisIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = Redis.from_url(os.environ['DWHO_REDIS_TEST_URL'])
        self.key = 'dwho-test:' + uuid.uuid4().hex
        self.cfg = {'general': {'uri': os.environ['DWHO_REDIS_TEST_URL']}}
        self.notifier = DWhoNotifierRedis()
        self.addCleanup(self.client.connection_pool.disconnect)
        self.addCleanup(self.client.delete, self.key)

    def test_legacy_set_still_replaces_the_json_value(self):
        for value in ({'state': 'firing'}, {'state': 'resolved'}):
            self.assertIsNone(self.notifier('test', self.cfg, None, {}, {'key': self.key, 'value': value}))
            self.assertEqual(json.loads(self.client.get(self.key).decode('utf-8')), value)

    def test_stream_returns_readable_ids_and_exact_retention(self):
        self.cfg['general'].update(redis_mode='stream', stream_maxlen=2)
        ids = []
        for value in range(3):
            result = self.notifier.send('test', self.cfg, {'key': self.key, 'value': {'index': value}})
            ids.append(result['notifier'])
        entries = self.client.execute_command('XRANGE', self.key, '-', '+')
        self.assertEqual([entry[0] for entry in entries], ids[-2:])
        self.assertEqual(len(set(ids)), 3)
        for index, entry in enumerate(entries, 1):
            # Raw execute_command response differs across redis-py generations.
            fields = entry[1]
            payload = fields[b'payload'] if isinstance(fields, dict) else fields[1]
            self.assertEqual(json.loads(payload.decode('utf-8')), {'index': index})

    def test_wrong_type_raises_without_overwriting_existing_data(self):
        self.client.set(self.key, 'existing')
        self.cfg['general']['redis_mode'] = 'stream'
        with self.assertRaises(ResponseError):
            self.notifier.send('test', self.cfg, {'key': self.key, 'value': 'event'})
        self.assertEqual(self.client.get(self.key), b'existing')


if __name__ == '__main__':
    unittest.main()
