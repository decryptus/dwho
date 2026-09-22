# -*- coding: utf-8 -*-
import copy
import json
import sys
import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from redis.exceptions import ConnectionError, ResponseError

from dwho.adapters.redis import DWhoAdapterRedis
from dwho.classes import notifiers


class RedisNotifierTests(unittest.TestCase):
    def setUp(self):
        self.notifier = notifiers.DWhoNotifierRedis()
        self.cfg = {'general': {'uri': 'redis://localhost:6379/0', 'options': {'custom': ['original']}}}
        self.tpl = {'key': 'alerts', 'value': {'message': u'mémoire', 'value': None}}
        patcher = mock.patch.object(notifiers, 'DWhoAdapterRedis')
        self.factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.adapter = self.factory.return_value
        self.adapter.set_key.return_value = {'notifier': True}
        self.adapter.xadd.return_value = {'notifier': b'123-0'}

    def test_legacy_set_keeps_json_wire_format_return_and_inputs(self):
        cfg, tpl = copy.deepcopy(self.cfg), copy.deepcopy(self.tpl)
        result = self.notifier('legacy', self.cfg, None, {}, self.tpl)
        self.assertIsNone(result)
        self.adapter.set_key.assert_called_once_with('alerts', json.dumps(tpl['value']))
        self.assertFalse(self.adapter.xadd.called)
        self.assertEqual(self.cfg, cfg)
        self.assertEqual(self.tpl, tpl)
        self.factory.call_args[0][0]['general']['redis']['notifier']['custom'].append('changed')
        self.assertEqual(self.cfg, cfg)
        self.adapter.disconnect.assert_called_once_with(prefix='notifier')

    def test_strict_set_returns_acknowledgement(self):
        self.assertEqual(self.notifier.send('strict', self.cfg, self.tpl), {'notifier': True})

    def test_stream_serializes_the_same_payload_and_returns_entry_id(self):
        self.cfg['general'].update(redis_mode='stream', stream_maxlen=100)
        self.assertEqual(self.notifier.send('stream', self.cfg, self.tpl), {'notifier': b'123-0'})
        self.adapter.xadd.assert_called_once_with('alerts', {'payload': json.dumps(self.tpl['value'])}, maxlen=100)
        self.assertFalse(self.adapter.set_key.called)
        self.adapter.disconnect.assert_called_once_with(prefix='notifier')

    def test_stream_retention_is_explicit_and_legacy_value_types_still_work(self):
        self.cfg['general']['redis_mode'] = 'stream'
        for value in (None, False, 0, '', [], {'nested': [1, True]}):
            self.notifier.send('stream', self.cfg, {'key': 'alerts', 'value': value})
            self.assertEqual(self.adapter.xadd.call_args[1], {'maxlen': None})
            self.assertEqual(json.loads(self.adapter.xadd.call_args[0][1]['payload']), value)

    def test_strict_errors_propagate_and_legacy_errors_only_log(self):
        for mode, method in [('set', self.adapter.set_key), ('stream', self.adapter.xadd)]:
            self.cfg['general']['redis_mode'] = mode
            error = ConnectionError('offline')
            method.side_effect = error
            with self.assertRaises(ConnectionError) as raised:
                self.notifier.send('strict', self.cfg, self.tpl)
            self.assertIs(raised.exception, error)
            with mock.patch.object(notifiers.LOG, 'error') as log:
                self.assertIsNone(self.notifier('legacy', self.cfg, None, {}, self.tpl))
                self.assertTrue(log.called)
        self.assertEqual(self.adapter.disconnect.call_count, 4)

    def test_wrong_type_errors_do_not_fall_back_to_set(self):
        self.cfg['general']['redis_mode'] = 'stream'
        self.adapter.xadd.side_effect = ResponseError('WRONGTYPE')
        with self.assertRaises(ResponseError):
            self.notifier.send('stream', self.cfg, self.tpl)
        self.assertFalse(self.adapter.set_key.called)
        self.adapter.disconnect.assert_called_once_with(prefix='notifier')

    def test_missing_acknowledgements_are_not_success(self):
        for mode, method in [('set', self.adapter.set_key), ('stream', self.adapter.xadd)]:
            self.cfg['general']['redis_mode'] = mode
            for result in ({}, {'notifier': None}, {'notifier': False}, {'notifier': b''}):
                method.return_value = result
                with self.assertRaises(RuntimeError):
                    self.notifier.send('strict', self.cfg, self.tpl)

    def test_invalid_templates_and_json_fail_before_connecting(self):
        for template in (None, [], {}, {'key': 'x'}, {'value': 1}):
            with self.assertRaises(ValueError):
                self.notifier.send('invalid', self.cfg, template)
        with self.assertRaises(TypeError):
            self.notifier.send('invalid', self.cfg, {'key': 'x', 'value': object()})
        self.assertFalse(self.factory.called)

    def test_unknown_mode_is_rejected_without_writing(self):
        self.cfg['general']['redis_mode'] = 'strem'
        with self.assertRaises(ValueError):
            self.notifier.send('invalid', self.cfg, self.tpl)
        self.assertFalse(self.factory.called)

    def test_connection_setup_error_is_strict_only_for_send(self):
        self.factory.side_effect = ConnectionError('cannot connect')
        with self.assertRaises(ConnectionError):
            self.notifier.send('strict', self.cfg, self.tpl)
        with mock.patch.object(notifiers.LOG, 'error'):
            self.assertIsNone(self.notifier('legacy', self.cfg, None, {}, self.tpl))


class RedisStreamAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = DWhoAdapterRedis({'general': {'redis': {}}}, load=False)
        # These clients deliberately expose no xadd helper, as on old redis-py.
        self.first = mock.Mock(spec=['execute_command'])
        self.second = mock.Mock(spec=['execute_command'])
        self.first.execute_command.return_value = b'1-0'
        self.second.execute_command.return_value = b'2-0'
        self.adapter.servers = {'events': {'conn': self.first}, 'other': {'conn': self.second}}

    def test_uses_command_api_and_preserves_server_selection(self):
        result = self.adapter.xadd('stream', {'payload': 'json'}, maxlen=3, prefix='events')
        self.assertEqual(result, {'events': b'1-0'})
        self.first.execute_command.assert_called_once_with('XADD', 'stream', 'MAXLEN', 3, '*', 'payload', 'json')
        self.assertFalse(self.second.execute_command.called)

    def test_no_retention_limit_and_explicit_empty_server_selection(self):
        self.assertEqual(self.adapter.xadd('s', {'p': 'v'}), {'events': b'1-0', 'other': b'2-0'})
        self.first.execute_command.assert_called_once_with('XADD', 's', '*', 'p', 'v')
        self.assertEqual(self.adapter.xadd('s', {'p': 'v'}, servers={}), {})
        self.assertEqual(self.first.execute_command.call_count, 1)

    def test_invalid_retention_and_empty_fields_never_write(self):
        for value in (True, False, 0, -1, 1.5, '10', 9223372036854775808):
            with self.assertRaises(ValueError):
                self.adapter.xadd('s', {'p': 'v'}, maxlen=value)
        for value in ({}, [], None):
            with self.assertRaises(ValueError):
                self.adapter.xadd('s', value)
        self.assertFalse(self.first.execute_command.called)
        self.assertFalse(self.second.execute_command.called)


class RegistryCompatibilityTests(unittest.TestCase):
    def exercise_dispatch(self, asynchronous):
        seen = []

        class CustomRedisNotifier(notifiers.DWhoNotifierBase):
            SCHEME = ('redis',)

            # Existing third-party plugins do not need a send method.
            def __call__(self, name, cfg, uri, nvars, tpl):
                seen.append((name, cfg, uri, nvars, tpl))

        registry = notifiers.DWhoNotifiers()
        registry.register(notifiers.DWhoNotifierRedis())
        registry.register(CustomRedisNotifier())
        registry.register(notifiers.DWhoNotifierHttp())
        registry.register(notifiers.DWhoNotifierSubprocess())
        push = notifiers.DWhoPushNotifications()
        for name, scheme, uri in [('redis', 'redis', 'redis://localhost/0'),
                                  ('http', 'http', 'http://localhost/test'),
                                  ('process', 'subproc', 'subproc://' + sys.executable)]:
            cfg = {'general': {'uri': uri, 'async': asynchronous}}
            if name == 'process':
                cfg['args'] = ['-c', 'pass']
            push.notifications[name] = {'cfg': cfg, 'tags': set(['all']),
                                        'tpl': '{"key": "test", "value": "${target}"}',
                                        'notifiers': registry[scheme]}

        # Execute queued callbacks deterministically; existing worker tests cover
        # capture/lifecycle. Redis failures must not stop subsequent handlers.
        def queued(receiver, **kwargs):
            kwargs.pop('_name_')
            receiver(**kwargs)

        popen = notifiers.subprocess.Popen
        with mock.patch.object(notifiers, 'DWhoAdapterRedis') as factory, \
             mock.patch.object(notifiers.requests, 'post') as post, \
             mock.patch.object(notifiers.subprocess, 'Popen', wraps=popen) as proc, \
             mock.patch.object(notifiers, 'WorkerPool') as pool, \
             mock.patch.object(notifiers.time, 'sleep'), \
             mock.patch.object(notifiers.LOG, 'error'):
            factory.return_value.set_key.side_effect = ConnectionError('offline')
            post.return_value.status_code = 204
            pool.return_value.killable.return_value = True
            pool.return_value.run_args.side_effect = queued
            self.assertIsNone(push({'target': 'one'}, names=['redis', 'http', 'process']))
            self.assertEqual(post.call_count, 1)
            self.assertEqual(proc.call_count, 1)
            self.assertEqual(pool.return_value.run_args.call_count, 4 if asynchronous else 0)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], 'redis')
        self.assertEqual(seen[0][3]['target'], 'one')
        self.assertEqual(seen[0][4], {'key': 'test', 'value': 'one'})
        self.assertEqual(len(registry['redis']), 2)
        self.assertIs(registry['http'][0], registry['https'][0])

    def test_sync_registry_keeps_all_notifier_contracts(self):
        self.exercise_dispatch(False)

    def test_async_registry_keeps_all_notifier_contracts(self):
        self.exercise_dispatch(True)


if __name__ == '__main__':
    unittest.main()
