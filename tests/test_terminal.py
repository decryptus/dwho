# -*- coding: utf-8 -*-
"""Terminal primitives work without HTTP, storage or a real terminal."""
import io
import json
import subprocess
import sys
import unittest
if sys.version_info < (3, 5):
    raise unittest.SkipTest('Curses widgets require Python 3.5+')

from unittest.mock import patch

from dwho.cli import write_json, require_terminal
from dwho import tui


class Screen:
    def __init__(self, keys, sizes=None):
        self.keys = iter(keys)
        self.size = (12, 60)
        self.sizes = iter(sizes or [])
        self.frames = []
        self.lines = []

    def getmaxyx(self):
        return self.size

    def erase(self):
        self.size = next(self.sizes, self.size)
        self.lines = []

    def addnstr(self, row, col, text, count, style):
        self.lines.append((row, text[:count]))

    def refresh(self):
        self.frames.append(list(self.lines))

    def get_wch(self):
        return next(self.keys)


class TerminalTests(unittest.TestCase):
    def test_imports_and_cli_work_with_optional_components_blocked(self):
        script = '''
import builtins, io, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('curses', 'httpdis', 'redis', 'sonicprobe'):
        raise AssertionError(name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from dwho.cli import write_json, require_terminal
from dwho import tui
output = io.StringIO()
write_json({'ok': True}, stream=output)
assert output.getvalue() == '{"ok": true}\\n'
assert 'curses' not in sys.modules
'''
        subprocess.run([sys.executable, '-c', script], check=True)

    def test_json_contract_and_dynamic_stdout(self):
        for options in ({}, {'indent': 2}, {'sort_keys': True, 'ensure_ascii': True}):
            value = {'z': 'é', 'a': [1, None]}
            output = io.StringIO()
            with patch('sys.stdout', output):
                write_json(value, **options)
            self.assertEqual(output.getvalue(), json.dumps(value, **options) + '\n')

    def test_json_serialization_failure_writes_nothing(self):
        output = io.StringIO()
        with self.assertRaises(TypeError):
            write_json(object(), stream=output)
        self.assertEqual(output.getvalue(), '')

    def test_terminal_requires_both_streams(self):
        class Stream:
            def __init__(self, tty): self.tty = tty
            def isatty(self): return self.tty
        for a, b in ((False, True), (True, False), (False, False)):
            with self.assertRaisesRegex(ValueError, 'terminal required'):
                require_terminal('terminal required', Stream(a), Stream(b))
        require_terminal('terminal required', Stream(True), Stream(True))

    def test_prompt_edit_cancel_and_limit(self):
        import curses
        screen = Screen(['a', 'b', curses.KEY_BACKSPACE, 'é', '\n'])
        self.assertEqual(tui.prompt(screen, 'Name'), 'aé')
        self.assertIsNone(tui.prompt(Screen(['\x1b']), 'Name', 'initial'))
        self.assertEqual(tui.prompt(Screen(['a', 'b', '\n']), 'Name', max_length=1), 'a')
        self.assertEqual(tui.prompt(Screen(['\n']), 'Name'), '')

    def test_confirmation_requires_configured_key(self):
        self.assertTrue(tui.confirm(Screen(['y', 'o']), 'Apply?', ['one'], accept_keys=('o',)))
        for key in ('q', '\x1b', 'n'):
            self.assertFalse(tui.confirm(Screen([key]), 'Apply?', ['one']))

    def test_details_scroll_generator_and_resize(self):
        import curses
        screen = Screen([curses.KEY_DOWN, curses.KEY_UP, 'q'])
        tui.view_details(screen, 'Details', (str(x) for x in range(20)))
        self.assertIn((1, '1'), screen.frames[1])
        self.assertIn((1, '0'), screen.frames[2])
        tui.view_details(Screen([curses.KEY_RESIZE, 'q'], [(1, 1), (12, 60)]), 'Details', [])

    def test_put_survives_resize_error(self):
        import curses
        screen = Screen([])
        with patch.object(screen, 'addnstr', side_effect=curses.error):
            tui.put(screen, 0, 'text')
        screen.size = (1, 1)
        tui.put(screen, 0, 'text')


if __name__ == '__main__':
    unittest.main()
