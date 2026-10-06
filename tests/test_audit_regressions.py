# -*- coding: utf-8 -*-
import copy
import shutil
import sqlite3
import tempfile
import threading
import unittest
try:
    from unittest import mock
except ImportError:
    import mock

from dwho.classes.inoplugs import DWhoInoPlugBase
from dwho.classes.inotify import DWhoInotifyConfig, DWhoInotifyPlugs
from dwho.classes.notifiers import DWhoNotifierBase, DWhoPushNotifications
from dwho.classes.objects import DWhoObjectSQLBase
from dwho.runtime import DWhoRuntime


class InotifyAuditTests(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.path)
        self.calls = []
        calls = self.calls
        class Plugin(DWhoInoPlugBase):
            PLUGIN_NAME = 'audit'
            def __call__(self, *args):
                calls.append('event')
            def safe_init(self):
                calls.append('init')
            def at_stop(self):
                calls.append('stop')
        self.plugin_class = Plugin

    def configure(self, global_options, path_options=None):
        plugin = self.plugin_class()
        watcher = mock.Mock()
        path_config = {} if path_options is None else {'plugins': {'audit': path_options}}
        ino = {'plugins': {'audit': global_options}, 'paths': {self.path: path_config}}
        normalized = DWhoInotifyConfig({'audit': plugin})(watcher, copy.deepcopy(ino))
        config = {'general': {'server_id': 'test'}, 'inotify': normalized}
        plugin.init(config)
        return plugin, config, watcher.add.call_args[0][0]

    def dispatch(self, config, cfg_path):
        event = mock.Mock(plugs_flag=threading.Event())
        DWhoInotifyPlugs(config, cfg_path, event, self.path + '/test').run()
        self.assertTrue(event.plugs_flag.is_set())

    def test_global_disable_cannot_be_overridden_by_path(self):
        for global_options in (False, {'enabled': False}, {}, {'enabled': 'false'}):
            for path_options in (None, True, {'enabled': True}, {'dest': '/tmp'}):
                plugin, config, cfg = self.configure(global_options, path_options)
                self.assertFalse(plugin.enabled)
                self.assertEqual(cfg.plugins, [])
                self.dispatch(config, cfg)
        self.assertEqual(self.calls, [])

    def test_enabled_plugins_and_options_only_paths_still_execute(self):
        for global_options in (True, {'enabled': True}):
            for path_options in (None, True, {'enabled': True}, {'dest': '/tmp'}):
                plugin, config, cfg = self.configure(global_options, path_options)
                self.assertEqual(cfg.plugins, [plugin])
                self.dispatch(config, cfg)
        self.assertEqual(self.calls, ['event'] * 8)

    def test_path_disable_restricts_enabled_global_plugin(self):
        for path_options in (False, {'enabled': False}, {}, {'enabled': 'false'}):
            plugin, config, cfg = self.configure(True, path_options)
            self.assertTrue(plugin.enabled)
            self.assertEqual(cfg.plugins, [])
            self.dispatch(config, cfg)
        self.assertEqual(self.calls, [])

    def test_worker_rechecks_runtime_and_global_disable(self):
        plugin, config, cfg = self.configure(True)
        plugin.enabled = False
        self.dispatch(config, cfg)
        plugin.enabled = True
        config['inotify']['plugins']['audit'] = False
        self.dispatch(config, cfg)
        self.assertEqual(self.calls, [])

    def test_disabled_plugin_lifecycle_has_no_side_effects(self):
        plugin = self.plugin_class()
        runtime = DWhoRuntime(inoplugs={'audit': plugin}, inotify_factory=lambda: mock.Mock())
        runtime.initialize({'general': {'server_id': 'test'},
                            'inotify': {'plugins': {'audit': {'enabled': False}},
                                        'paths': {self.path: {}}}})
        runtime.start(); runtime.stop()
        self.assertEqual(self.calls, [])

    def test_legacy_launcher_skips_disabled_plugin_initialization(self):
        from dwho import config as legacy
        plugin, config, cfg = self.configure(False)
        with mock.patch.object(legacy, 'INOPLUGS', {'audit': plugin}), \
             mock.patch.object(legacy, '_INOTIFY'), \
             mock.patch.object(legacy, 'DWHO_THREADS', []):
            legacy.init_inotify(config)
            self.assertEqual(legacy.DWHO_THREADS, [])
        self.assertEqual(self.calls, [])


class NotificationAuditTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        calls = self.calls
        class Recorder(DWhoNotifierBase):
            SCHEME = 'audit'
            def send(self, *args):
                calls.append(args[0]); return True
        self.push = DWhoPushNotifications()
        self.push.notif_names = set(['recipient'])
        self.push.notifications = {'recipient': {'cfg': {'general': {'uri': 'http://example.invalid/'}},
            'tpl': None, 'tags': set(['all']), 'notifiers': [Recorder()]}}

    def test_invalid_explicit_tags_never_deliver(self):
        for tags in ([], (), set(), 'all', 1, ['!invalid!'], ['all', None],
                     ['all\n'], [' all'], [u'\u00e9mail'], ['a' * 33], ['all', '!bad!']):
            with self.assertRaises(ValueError):
                self.push.send({}, tags=tags)
        self.assertEqual(self.calls, [])

    def test_omitted_and_valid_tags_keep_selection_contract(self):
        self.assertEqual(self.push.send({}), {'recipient': [True]})
        self.assertEqual(self.push.send({}, tags=['all']), {'recipient': [True]})
        self.assertEqual(self.calls, ['recipient', 'recipient'])

    def test_legacy_tag_normalization_is_preserved(self):
        self.assertEqual(self.push._parse_tags(['!invalid!']), set(['all']))


class SQLAuditTests(unittest.TestCase):
    def test_like_literal_metacharacters_match_only_literal_values(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        values = ['item_1', 'itemX1', '10%done', '10Xdone', r'a\b', 'a!b', 'normal', 'a!_%\\b']
        db.execute('CREATE TABLE items (name TEXT)')
        db.executemany('INSERT INTO items VALUES (?)', [(v,) for v in values])
        for value in values:
            clause, params = DWhoObjectSQLBase._prepare_cond_like(['name'], value)
            self.assertEqual(db.execute('SELECT name FROM items WHERE ' + clause, params).fetchall(), [(value,)])
