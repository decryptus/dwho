import copy
import io
import os
import subprocess
import sys
import threading
import unittest
try:
    from unittest import mock
except ImportError:
    import mock

from dwho.adapters import redis
from dwho.classes import inotify, notifiers
from dwho.classes.abstract import DWhoAbstractDB

class RedisTests(unittest.TestCase):
    def test_multiple_servers_and_reconnection(self):
        config = {'general': {'redis': {'first': {'url': 'redis://localhost/0'},
                                       'second': {'url': 'redis://localhost/1'}}}}
        with mock.patch.object(redis, 'Redis') as client:
            client.return_value.from_url.side_effect = [mock.Mock(), mock.Mock(), mock.Mock()]
            adapter = redis.DWhoAdapterRedis(config)
            first = adapter.servers['first']['conn']
            self.assertEqual(len(adapter.servers), 2)
            adapter.connect('first')
            self.assertEqual(client.return_value.from_url.call_count, 2)
            adapter.disconnect('second')
            adapter.connect('second')
            self.assertIs(adapter.servers['first']['conn'], first)
            self.assertEqual(client.return_value.from_url.call_count, 3)

class DatabaseTests(unittest.TestCase):
    def test_multiple_sql_connections(self):
        helper = DWhoAbstractDB()
        helper.config = {'general': {'db_uri_first': 'sqlite3::memory:', 'db_uri_second': 'sqlite3::memory:'}}
        first = helper.db_connect('first')
        second = helper.db_connect('second')
        self.addCleanup(helper.db_disconnect, 'first')
        self.addCleanup(helper.db_disconnect, 'second')
        self.assertIsNot(first['conn'], second['conn'])
        self.assertIs(helper.db_connect('first')['conn'], first['conn'])

class InotifyTests(unittest.TestCase):
    def test_path_boundaries_and_most_specific_watch(self):
        watcher = object.__new__(inotify.DWhoInotify)
        watcher.cfg_paths = {'/srv/app': 'parent', '/srv/app/deep/': 'child'}
        self.assertIsNone(watcher.get_cfg_path('/srv/application/file'))
        self.assertEqual(watcher.get_cfg_path('/srv/app/file'), 'parent')
        self.assertEqual(watcher.get_cfg_path('/srv/app/deep/file'), 'child')
        self.assertEqual(watcher.get_cfg_path('/srv/app/deep/../file'), 'parent')
        watcher.cfg_paths['/'] = 'root'
        self.assertEqual(watcher.get_cfg_path('/elsewhere'), 'root')

    def test_plugin_filter_does_not_modify_configuration(self):
        first, second = mock.Mock(PLUGIN_NAME='first'), mock.Mock(PLUGIN_NAME='second')
        cfg = inotify.DWhoInotifyCfgPath('/tmp', plugins=[first, second])
        watcher = mock.Mock(config={})
        handler = inotify.DWhoInotifyEventHandler(dw_inotify=watcher, plugs_class=mock.Mock())
        event = mock.Mock(pathname='/tmp/file')
        handler.call_plugins(cfg, event, include_plugins=['first'])
        filtered = handler.plugs_class.call_args[0][1]
        self.assertEqual(filtered.plugins, [first])
        self.assertEqual(cfg.plugins, [first, second])
        handler.call_plugins(cfg, event)
        self.assertEqual(handler.plugs_class.call_args[0][1].plugins, [first, second])

class NotificationTests(unittest.TestCase):
    def test_repeated_render_keeps_original_configuration(self):
        push = notifiers.DWhoPushNotifications()
        received = []
        def receiver(name, cfg, uri, nvars, tpl):
            received.append(cfg['general']['uri'])
            cfg['general']['nested']['value'] = 'changed'
        cfg = {'general': {'uri': 'http://${target}/', 'nested': {'value': 'original'}}}
        push.notif_names = set(['test'])
        push.notifications['test'] = {'cfg': cfg, 'tpl': None, 'tags': set(['all']), 'notifiers': [receiver]}
        original = copy.deepcopy(cfg)
        with mock.patch.object(notifiers, 'WorkerPool') as pool, mock.patch.object(notifiers.time, 'sleep'):
            pool.return_value.killable.return_value = True
            push._run({'target': 'first'})
            push._run({'target': 'second'})
        self.assertEqual(received, ['http://first/', 'http://second/'])
        self.assertEqual(cfg, original)

    def test_async_notifications_capture_their_own_names(self):
        push = notifiers.DWhoPushNotifications()
        for name in ['first', 'second']:
            push.notifications[name] = {'cfg': {'general': {'uri': 'http://localhost/', 'async': True}},
                                        'tpl': None, 'tags': set(['all']), 'notifiers': [mock.Mock()]}
        with mock.patch.object(notifiers, 'WorkerPool') as pool, mock.patch.object(notifiers.time, 'sleep'):
            pool.return_value.killable.return_value = True
            push._run(names=['first', 'second'])
            calls = pool.return_value.run_args.call_args_list
        self.assertEqual([call[1]['nvars']['_NAME_'] for call in calls], ['first', 'second'])

class SubprocessTests(unittest.TestCase):
    def test_reader_returns_at_eof(self):
        stream, log = io.BytesIO(b'hello\n'), mock.Mock()
        thread = threading.Thread(target=notifiers.DWhoNotifierSubprocess._proc_std,
                                  args=(stream, log, threading.Event()))
        thread.daemon = True
        thread.start(); thread.join(2)
        self.assertFalse(thread.is_alive())
        log.assert_called_once_with(b'hello')
        self.assertTrue(stream.closed)

    def test_wait_process_sleeps_while_running(self):
        proc = mock.Mock()
        proc.poll.side_effect = [None, None, 0]
        with mock.patch.object(notifiers.time, 'sleep') as sleep:
            self.assertTrue(notifiers.DWhoNotifierSubprocess._wait_process(proc, 10))
            self.assertEqual(sleep.call_count, 2)
        proc.wait.assert_called_once_with()

    def test_timeout_kills_and_reaps_real_child(self):
        notifier = notifiers.DWhoNotifierSubprocess()
        cfg = {'timeout': 0.2, 'args': ['-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)']}
        child = []
        popen = subprocess.Popen
        def capture(*args, **kwargs):
            proc = popen(*args, **kwargs); child.append(proc); return proc
        with mock.patch.object(notifier, '_set_default_env', return_value=dict(os.environ)), \
             mock.patch.object(notifiers.subprocess, 'Popen', side_effect=capture):
            notifier('test', cfg, ('subproc', None, sys.executable), {})
        self.assertEqual(len(child), 1)
        self.assertIsNotNone(child[0].poll())
        self.assertTrue(child[0].stdout.closed)
        self.assertTrue(child[0].stderr.closed)
