"""Regression coverage for dynamic plugin loading (no external services)."""
import os
import shutil
import sys
import tempfile
import types
import unittest
import uuid

from dwho.classes.libloader import DwhoLibLoader


class LibLoaderTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.namespace = 'dwho_test_' + uuid.uuid4().hex
        self.addCleanup(shutil.rmtree, self.root)
        self.addCleanup(self.clear_modules)

    def clear_modules(self):
        for name in list(sys.modules):
            if name == self.namespace or name.startswith(self.namespace + '.'):
                del sys.modules[name]

    def write(self, filename, source):
        path = os.path.join(self.root, filename)
        with open(path, 'w') as stream:
            stream.write(source)
        return path

    def load(self):
        return DwhoLibLoader.load_dir(self.namespace, self.root)

    def test_loads_source_with_module_metadata_and_registration(self):
        path = self.write('plugin.py', 'import sys\nSELF = sys.modules[__name__]\nVALUE = 42\n')
        name = self.namespace + '.plugin'
        module = self.load()[name]
        self.assertEqual(module.VALUE, 42)
        self.assertEqual(module.__name__, name)
        self.assertEqual(module.__file__, path)
        self.assertIs(module.SELF, module)
        self.assertIs(sys.modules[name], module)

    def test_cached_plugin_is_not_executed_again(self):
        self.write('plugin.py', 'VALUE = 42\n')
        first = self.load()
        self.write('plugin.py', 'raise RuntimeError("must not execute twice")\n')
        self.assertIs(self.load()[self.namespace + '.plugin'], first[self.namespace + '.plugin'])

    def test_ignores_hidden_init_and_non_python_files(self):
        for filename in ('.hidden.py', '__init__.py', 'notes.txt'):
            self.write(filename, 'raise RuntimeError("must be ignored")\n')
        self.assertEqual(self.load(), {})

    def test_failed_load_cleans_cache_and_can_retry(self):
        self.write('broken.py', 'PARTIAL = True\nraise RuntimeError("broken plugin")\n')
        with self.assertRaises(RuntimeError):
            self.load()
        self.assertNotIn(self.namespace + '.broken', sys.modules)
        self.write('broken.py', 'VALUE = "repaired"\n')
        self.assertEqual(self.load()[self.namespace + '.broken'].VALUE, 'repaired')

    def test_syntax_error_cleans_cache(self):
        self.write('broken.py', 'def broken(:\n')
        with self.assertRaises(SyntaxError):
            self.load()
        self.assertNotIn(self.namespace + '.broken', sys.modules)

    def test_system_exit_is_propagated_and_cleans_cache(self):
        self.write('broken.py', 'raise SystemExit(7)\n')
        with self.assertRaises(SystemExit) as caught:
            self.load()
        self.assertEqual(caught.exception.code, 7)
        self.assertNotIn(self.namespace + '.broken', sys.modules)

    def test_relative_import_and_plugin_registration(self):
        package = types.ModuleType(self.namespace)
        package.__path__ = [self.root]
        package.registry = []
        sys.modules[self.namespace] = package
        self.write('plugin.py',
                   'from . import registry\n'
                   'class Plugin(object):\n'
                   '    pass\n'
                   'registry.append(Plugin)\n')
        module = self.load()[self.namespace + '.plugin']
        self.assertEqual(package.registry, [module.Plugin])
        self.load()
        self.assertEqual(package.registry, [module.Plugin])

    def test_source_encoding_is_honoured(self):
        with open(os.path.join(self.root, 'plugin.py'), 'wb') as stream:
            stream.write(b'# coding: latin-1\nVALUE = u"caf\xe9"\n')
        self.assertEqual(self.load()[self.namespace + '.plugin'].VALUE,
                         u'caf\u00e9')

    def test_relative_directory_produces_absolute_module_path(self):
        path = self.write('plugin.py', 'VALUE = 42\n')
        modules = DwhoLibLoader.load_dir(self.namespace, os.path.relpath(self.root))
        self.assertEqual(modules[self.namespace + '.plugin'].__file__, path)

    def test_missing_directory_propagates_error(self):
        with self.assertRaises(OSError):
            DwhoLibLoader.load_dir(self.namespace, os.path.join(self.root, 'missing'))


if __name__ == '__main__':
    unittest.main()
