import copy
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
try:
    from unittest import mock
except ImportError:
    import mock

from dwho import configuration, config
from dwho.runtime import DWhoRuntime
from dwho.classes.modules import DWhoModuleBase
from dwho.classes.inotify import (DWhoInotify, DWhoInotifyContext,
                                DWhoInotifyConfig, DWHO_INOQ, MODE_ADD)


class Module(DWhoModuleBase):
    MODULE_NAME = 'sample'

    def handle(self, request):
        return self.server_id


class Plugin(object):
    def __init__(self, fail=False):
        self.enabled = True
        self.autostart = True
        self.initialized = False
        self.events = []
        self.fail = fail

    def init(self, conf):
        self.initialized = True
        self.conf = conf
        self.events.append('init')

    def safe_init(self):
        self.events.append('safe_init')
        if self.fail:
            raise ValueError('broken init')

    def at_start(self):
        self.events.append('start')

    def at_stop(self):
        self.events.append('stop')


class RuntimeTests(unittest.TestCase):
    def test_isolated_routes_data_plugins_and_shutdown(self):
        data = configuration.parse_conf({'general': {'server_id': 'localhost'},
            'modules': {'sample': {'routes': {'r': {'name': '/same', 'handler': 'handle'}}}}})
        original = copy.deepcopy(data)
        first, second = Module(), Module()
        p1, p2 = Plugin(), Plugin()
        routes1, routes2 = [], []
        r1 = DWhoRuntime({'sample': first}, {'p': p1},
                        route_registrar=lambda **route: routes1.append(route))
        r2 = DWhoRuntime({'sample': second}, {'p': p2},
                        route_registrar=lambda **route: routes2.append(route))
        with mock.patch('dwho.classes.modules.httpdis.register') as legacy:
            r1.initialize(data).start()
            r2.initialize(data).start()
            self.assertEqual(legacy.call_count, 0)
        self.assertIs(routes1[0]['handler'].__self__, first)
        self.assertIs(routes2[0]['handler'].__self__, second)
        first.config['general']['server_id'] = 'changed'
        self.assertEqual(second.config['general']['server_id'], 'localhost')
        self.assertEqual(data, original)
        self.assertIsNot(r1.shared, r2.shared)
        r1.stop(); r1.stop()
        self.assertEqual(p1.events, ['init', 'safe_init', 'start', 'stop'])
        self.assertEqual(p2.events, ['init', 'safe_init', 'start'])
        r2.stop()

    def test_httpdis_context_integration_when_available(self):
        from httpdis import httpdis
        if not hasattr(httpdis, 'HttpServerContext'):
            self.skipTest('Requires the isolated HTTPdis context API')
        data = configuration.parse_conf({'general': {'server_id': 'localhost'},
            'modules': {'sample': {'routes': {'r': {'name': '/same', 'handler': 'handle'}}}}})
        contexts = [httpdis.HttpServerContext(), httpdis.HttpServerContext()]
        modules = [Module(), Module()]
        runtimes = []
        for context, module in zip(contexts, modules):
            runtime = DWhoRuntime({'sample': module}, route_registrar=context.register)
            runtimes.append(runtime.initialize(data))
            self.assertEqual(len(context.commands), 1)
            route = list(context.commands.values())[0]
            self.assertIs(route.handler.__self__, module)
        self.assertIsNot(contexts[0].commands, contexts[1].commands)
        for runtime in runtimes:
            runtime.stop()

    def test_reused_extension_and_missing_transport_are_rejected(self):
        p = Plugin()
        DWhoRuntime(plugins={'p': p}).initialize({'general': {}})
        with self.assertRaises(ValueError):
            DWhoRuntime(plugins={'p': p}).initialize({'general': {}})
        with self.assertRaises(ValueError):
            DWhoRuntime(modules={'sample': Module()}).initialize({'general': {}})

    def test_init_failure_stops_partially_initialized_plugin(self):
        p = Plugin(fail=True)
        runtime = DWhoRuntime(plugins={'p': p})
        with self.assertRaises(ValueError):
            runtime.initialize({'general': {}})
        self.assertEqual(p.events, ['init', 'safe_init', 'stop'])
        runtime.stop()
        self.assertEqual(p.events.count('stop'), 1)
        with self.assertRaises(RuntimeError):
            runtime.initialize({'general': {}})

    def test_start_failure_and_stop_failure_do_not_skip_cleanup(self):
        p1, p2 = Plugin(), Plugin()
        p1.at_start = mock.Mock(side_effect=ValueError('start'))
        p1.at_stop = mock.Mock(side_effect=ValueError('stop'))
        runtime = DWhoRuntime(plugins={'first': p1, 'second': p2})
        runtime.initialize({'general': {}})
        with self.assertRaises(ValueError) as error:
            runtime.start()
        self.assertEqual(str(error.exception), 'start')
        self.assertIn('stop', p2.events)
        runtime.stop()
        self.assertEqual(p1.at_stop.call_count, 1)

    def test_legacy_route_registration_still_uses_global_facade(self):
        module = Module()
        with mock.patch('dwho.classes.modules.httpdis.register') as register:
            module.init({'general': {'server_id': 'localhost'}, 'modules': {
                'sample': {'routes': {'x': {'handler': 'handle', 'name': '/legacy'}}}}})
        self.assertEqual(register.call_count, 1)

    def test_inotify_queues_and_plugin_resolution_are_isolated(self):
        first, second = DWhoInotifyContext(), DWhoInotifyContext()
        a, b = object(), object()
        for watcher, plugin in ((first, a), (second, b)):
            conf = {'plugins': {'p': True}, 'paths': {tempfile.gettempdir(): {}}}
            DWhoInotifyConfig({'p': plugin})(watcher, conf)
            mode, path = watcher.command_queue.get_nowait()
            self.assertEqual(mode, MODE_ADD)
            self.assertEqual(path.plugins, [plugin])
        first.add('first')
        self.assertTrue(second.command_queue.empty())
        self.assertEqual(first.command_queue.get_nowait(), (MODE_ADD, 'first'))
        legacy = DWhoInotify()
        self.assertIs(legacy.command_queue, DWHO_INOQ)
        DWhoInotify.add('legacy')
        self.assertEqual(DWHO_INOQ.get_nowait(), (MODE_ADD, 'legacy'))

    def test_runtime_inotify_factories_receive_local_registry(self):
        watcher, parser = mock.Mock(), mock.Mock()
        parser.return_value.return_value = {'paths': {}}
        plugin = Plugin()
        runtime = DWhoRuntime(inoplugs={'p': plugin},
            inotify_factory=lambda: watcher, inotify_config_factory=parser)
        runtime.initialize({'general': {}, 'inotify': {'paths': {}}}).start()
        parser.assert_called_once_with(plugins=runtime.inoplugs)
        self.assertEqual(watcher.start.call_count, 1)
        runtime.stop(); runtime.stop()
        self.assertEqual(watcher.stop.call_count, 1)
        self.assertEqual(plugin.events, ['init', 'safe_init', 'start', 'stop'])


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.filename = os.path.join(self.directory, 'config.yml')
        with open(self.filename, 'w') as stream:
            stream.write('general:\n  server_id: localhost\nimport_modules: modules.yml\ninotify:\n  paths: {}\n')
        with open(os.path.join(self.directory, 'modules.yml'), 'w') as stream:
            stream.write('sample:\n  value: original\n')

    def test_read_in_worker_preserves_signals_and_global_registries(self):
        results = []
        def read():
            results.append(configuration.read_conf(self.filename))
        with mock.patch.object(config.signal, 'signal') as signals, \
             mock.patch.object(config, 'init_modules') as modules, \
             mock.patch.object(config, 'init_plugins') as plugins:
            thread = threading.Thread(target=read)
            thread.start(); thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['modules']['sample']['value'], 'original')
        self.assertEqual(results[0]['inotify'], {'paths': {}})
        self.assertEqual(signals.call_count + modules.call_count + plugins.call_count, 0)

    def test_legacy_loader_retains_signals_and_hooks(self):
        with mock.patch.object(config.signal, 'signal') as signals, \
             mock.patch.object(config, 'init_modules') as modules, \
             mock.patch.object(config, 'init_plugins') as plugins, \
             mock.patch.object(config, '_INOTIFY', None):
            result = config.load_conf(self.filename, parse_conf_func=lambda c: c)
        self.assertEqual(signals.call_count, 2)
        modules.assert_called_once_with(result)
        plugins.assert_called_once_with(result)

    def test_environment_custom_file_credentials_and_error_identity(self):
        from dwho.errors import DWhoConfigurationError
        from dwho.classes.errors import DWhoConfigurationError as LegacyError
        self.assertIs(DWhoConfigurationError, LegacyError)
        with mock.patch.dict(os.environ, {'DWHO_TEST_CONFIG': 'general: {server_id: localhost}'}):
            result = configuration.read_conf(os.path.join(self.directory, 'missing'),
                                             envvar='DWHO_TEST_CONFIG')
        self.assertIsNone(result['_config_directory'])
        with open(os.path.join(self.directory, 'custom.yml'), 'w') as stream:
            stream.write('general: {max_requests: 12}\ncredentials: creds.yml\n')
        with open(os.path.join(self.directory, 'creds.yml'), 'w') as stream:
            stream.write('account: {user: test}\n')
        result = configuration.read_conf(self.filename, custom_file='custom.yml', load_creds=True)
        self.assertEqual(result['general']['max_requests'], 12)
        self.assertEqual(result['credentials']['account']['user'], 'test')
        with self.assertRaises(LegacyError):
            configuration.parse_conf({})

    def test_data_and_runtime_import_without_interfaces(self):
        script = '''
import sys
try:
    import builtins
except ImportError:
    import __builtin__ as builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    blocked = ('httpdis', 'mako', 'argparse', 'curses', 'pyinotify',
               'dwho.config', 'dwho.classes.modules', 'dwho.classes.plugins')
    if any(name == item or name.startswith(item + '.') for item in blocked):
        raise AssertionError('Forbidden import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from dwho.configuration import read_conf
from dwho.runtime import DWhoRuntime
runtime = DWhoRuntime().initialize(read_conf(sys.argv[1],
    parse_conf_func=lambda conf: {'general': conf['general']}))
runtime.start()
runtime.stop()
'''
        subprocess.check_call([sys.executable, '-c', script, self.filename])


if __name__ == '__main__':
    unittest.main()
