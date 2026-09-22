# -*- coding: utf-8 -*-
import copy
import subprocess
import sys
import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from dwho.classes import notifiers


class HttpSendTests(unittest.TestCase):
    def setUp(self):
        self.notifier = notifiers.DWhoNotifierHttp()
        self.cfg = {'general': {'uri': 'https://example.invalid/events'}, 'timeout': 4, 'verify': True}

    def test_success_keeps_request_options_and_legacy_result(self):
        tpl = {'method': 'put', 'payload': {'state': 'ready'}, 'auth': {'user': 'test'}}
        with mock.patch.object(notifiers.requests, 'put') as put:
            put.return_value.status_code = 202
            self.assertTrue(self.notifier.send('http', self.cfg, tpl))
            self.assertTrue(self.notifier('http', self.cfg, None, {}, tpl))
            self.assertEqual(put.call_count, 2)
            put.assert_called_with('https://example.invalid/events', auth=tpl['auth'],
                                   headers={}, data=tpl['payload'], timeout=4, verify=True)

    def test_non_success_and_transport_errors_are_strict_only(self):
        with mock.patch.object(notifiers.requests, 'post') as post, \
             mock.patch.object(notifiers.LOG, 'error'):
            for status in (301, 400, 503):
                post.return_value.status_code = status
                with self.assertRaises(notifiers.requests.HTTPError) as raised:
                    self.notifier.send('http', self.cfg)
                self.assertIs(raised.exception.response, post.return_value)
                self.assertIsNone(self.notifier('http', self.cfg, None, {}))
            error = notifiers.requests.Timeout('timeout')
            post.side_effect = error
            with self.assertRaises(notifiers.requests.Timeout) as raised:
                self.notifier.send('http', self.cfg)
            self.assertIs(raised.exception, error)
            self.assertIsNone(self.notifier('http', self.cfg, None, {}))

    def test_invalid_method_preserves_configuration_error(self):
        for method in (self.notifier.send, lambda n, c, t: self.notifier(n, c, None, {}, t)):
            with self.assertRaises(ValueError):
                method('http', self.cfg, {'method': 'unknown'})


class SubprocessSendTests(unittest.TestCase):
    def test_success_supplies_metadata_and_preserves_input(self):
        cfg = {'general': {'uri': 'subproc://' + sys.executable},
               'args': ['-c', 'import os; assert os.environ["DWHO_NOTIFIER_NAME"] == "test"']}
        original = copy.deepcopy(cfg)
        self.assertTrue(notifiers.DWhoNotifierSubprocess().send('test', cfg))
        self.assertEqual(cfg, original)

    def test_exit_error_and_missing_executable_propagate(self):
        notifier = notifiers.DWhoNotifierSubprocess()
        cfg = {'general': {'uri': 'subproc://' + sys.executable}, 'args': ['-c', 'import sys; sys.exit(7)']}
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            notifier.send('test', cfg)
        self.assertEqual(raised.exception.returncode, 7)
        with self.assertRaises(OSError):
            notifier.send('test', {'general': {'uri': 'subproc:///does-not-exist/dwho-test'}})
        with self.assertRaises(ValueError):
            notifier.send('test', {'general': {'uri': 'subproc://'}})

    def test_timeout_still_terminates_and_reaps_before_raising(self):
        notifier = notifiers.DWhoNotifierSubprocess()
        cfg = {'general': {'uri': 'subproc://' + sys.executable}, 'timeout': 0.1,
               'args': ['-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)']}
        children = []
        original = subprocess.Popen

        def start(*args, **kwargs):
            child = original(*args, **kwargs)
            children.append(child)
            return child

        with mock.patch.object(notifiers.subprocess, 'Popen', side_effect=start):
            with self.assertRaises(RuntimeError):
                notifier.send('test', cfg)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(children[0].stdout.closed)
        self.assertTrue(children[0].stderr.closed)


class DispatcherSendTests(unittest.TestCase):
    def setUp(self):
        self.push = notifiers.DWhoPushNotifications()

    def add(self, name, handler, asynchronous=False, enabled=True):
        self.push.notifications[name] = {
            'cfg': {'general': {'uri': 'http://${target}/', 'async': asynchronous, 'enabled': enabled}},
            'tags': set(['all']), 'tpl': '{"value": "${target}"}', 'notifiers': [handler]}
        self.push.notif_names.add(name)

    def test_sends_synchronously_with_templates_and_returns_results(self):
        self.add('http', notifiers.DWhoNotifierHttp(), asynchronous=True)
        original = copy.deepcopy(self.push.notifications['http']['cfg'])
        with mock.patch.object(notifiers.requests, 'post') as post, \
             mock.patch.object(notifiers, 'WorkerPool') as pool:
            post.return_value.status_code = 204
            self.assertEqual(self.push.send({'target': 'one'}, names=['http']), {'http': [True]})
            self.assertEqual(post.call_args[0][0], 'http://one/')
            self.assertFalse(pool.called)
        self.assertEqual(self.push.notifications['http']['cfg'], original)

    def test_rejects_legacy_only_plugins_before_any_send(self):
        class LegacyPlugin(notifiers.DWhoNotifierBase):
            SCHEME = 'legacy'

            def __call__(self, name, cfg, uri, nvars, tpl):
                return None

        self.add('http', notifiers.DWhoNotifierHttp())
        self.add('legacy', LegacyPlugin())
        with mock.patch.object(notifiers.requests, 'post') as post:
            with self.assertRaises(NotImplementedError):
                self.push.send({'target': 'one'}, names=['http', 'legacy'])
            self.assertFalse(post.called)

    def test_dispatcher_stream_template_returns_redis_ids(self):
        self.add('events', notifiers.DWhoNotifierRedis(), asynchronous=True)
        notification = self.push.notifications['events']
        notification['cfg']['general'].update(uri='redis://localhost/0', redis_mode='stream', stream_maxlen=10)
        notification['tpl'] = '{"key": "monitoring:alerts", "value": ${json.dumps(_VARS_)}}'
        payload = {'status': 'firing', 'container': 'web'}
        with mock.patch.object(notifiers, 'DWhoAdapterRedis') as factory:
            factory.return_value.xadd.return_value = {'notifier': b'1-0'}
            self.assertEqual(self.push.send(payload, names=['events']), {'events': [{'notifier': b'1-0'}]})
            import json
            self.assertEqual(json.loads(factory.return_value.xadd.call_args[0][1]['payload']), payload)
            self.assertEqual(factory.return_value.xadd.call_args[1], {'maxlen': 10})

    def test_custom_strict_handler_keeps_its_return_value(self):
        class StrictPlugin(notifiers.DWhoNotifierBase):
            SCHEME = 'custom'

            def send(self, name, cfg, tpl=None, nvars=None):
                return {'ack': tpl['value']}

        self.add('custom', StrictPlugin())
        self.assertEqual(self.push.send({'target': 'one'}), {'custom': [{'ack': 'one'}]})

    def test_empty_or_unknown_selection_never_claims_success(self):
        self.add('http', notifiers.DWhoNotifierHttp())
        with mock.patch.object(notifiers.requests, 'post') as post:
            for names in ([], '', False, 3, ['missing'], ['http', 'missing']):
                with self.assertRaises(ValueError):
                    self.push.send({'target': 'one'}, names=names)
            with self.assertRaises(ValueError):
                self.push.send({'target': 'one'}, tags=['other'])
            self.push.notifications['http']['cfg']['general']['enabled'] = False
            with self.assertRaises(ValueError):
                self.push.send({'target': 'one'})
            self.assertFalse(post.called)

    def test_failure_stops_further_sends_and_releases_dispatcher_lock(self):
        self.add('first', notifiers.DWhoNotifierHttp())
        self.add('second', notifiers.DWhoNotifierHttp())
        with mock.patch.object(notifiers.requests, 'post') as post:
            post.side_effect = notifiers.requests.Timeout('offline')
            with self.assertRaises(notifiers.requests.Timeout):
                self.push.send({'target': 'one'}, names=['first', 'second'])
            self.assertEqual(post.call_count, 1)
            post.side_effect = None
            post.return_value.status_code = 204
            self.assertEqual(self.push.send({'target': 'one'}, names=['first']), {'first': [True]})

    def test_custom_handler_must_acknowledge(self):
        class NoAcknowledgement(notifiers.DWhoNotifierBase):
            SCHEME = 'custom'

            def send(self, name, cfg, tpl=None, nvars=None):
                return None

        self.add('custom', NoAcknowledgement())
        with self.assertRaises(RuntimeError):
            self.push.send({'target': 'one'})


if __name__ == '__main__':
    unittest.main()
