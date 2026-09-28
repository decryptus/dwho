# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional curses presentation. Importing this package does not import curses.

Widgets require Python 3 with get_wch support. The application owns curses
lifecycle, translations, selection, authorization and all business operations.
"""
from __future__ import absolute_import

import textwrap

MAX_INPUT_LENGTH = 1024
DEFAULT_INPUT_HELP = 'Enter to accept; Escape to cancel'
DEFAULT_SCROLL_HELP = 'Up/Down to scroll; q or Escape to return'
DEFAULT_CONFIRM_HELP = 'Up/Down to scroll'
CONFIRM_KEYS = ('y',)
CANCEL_KEYS = ('\x1b', 'q', 'n')
RETURN_KEYS = ('q', '\x1b')


def put(screen, row, text, style=0):
    import curses
    height, width = screen.getmaxyx()
    if 0 <= row < height and width > 1:
        try:
            screen.addnstr(row, 0, str(text).replace('\n', ' '), width - 1, style)
        except curses.error:
            # The terminal may resize between getmaxyx and addnstr.
            pass


def prompt(screen, title, initial='', help_text=DEFAULT_INPUT_HELP,
           max_length=MAX_INPUT_LENGTH):
    """Resize-safe input editor; Escape returns None, Enter accepts even empty."""
    import curses
    value = initial
    while True:
        screen.erase()
        put(screen, 1, title)
        put(screen, 3, value)
        put(screen, 5, help_text)
        screen.refresh()
        key = screen.get_wch()
        if key == '\x1b':
            return None
        if key in ('\n', '\r', curses.KEY_ENTER):
            return value
        if key in ('\b', '\x7f', curses.KEY_BACKSPACE):
            value = value[:-1]
        elif isinstance(key, str) and key.isprintable() and len(value) < max_length:
            value += key


def _scroll(screen, title, source, help_text, accept_keys, cancel_keys):
    import curses
    # Materialize once so generators also survive redraws and resizing.
    source = tuple(source)
    offset = 0
    while True:
        height, width = screen.getmaxyx()
        lines = [part for line in source
                 for part in (textwrap.wrap(str(line), max(1, width - 1)) or [''])]
        count = max(1, height - 2)
        offset = min(offset, max(0, len(lines) - count))
        screen.erase()
        put(screen, 0, title)
        for row, line in enumerate(lines[offset:offset + count], 1):
            put(screen, row, line)
        put(screen, height - 1, help_text)
        screen.refresh()
        key = screen.get_wch()
        if key in accept_keys:
            return True
        if key in cancel_keys:
            return False
        if key == curses.KEY_DOWN:
            offset = min(max(0, len(lines) - count), offset + 1)
        elif key == curses.KEY_UP:
            offset = max(0, offset - 1)


def view_details(screen, title, source, help_text=DEFAULT_SCROLL_HELP):
    _scroll(screen, title, source, help_text, (), RETURN_KEYS)


def confirm(screen, title, source, help_text=DEFAULT_CONFIRM_HELP,
            accept_keys=CONFIRM_KEYS, cancel_keys=CANCEL_KEYS):
    """Return user intent only; this is never authorization or a service call."""
    return _scroll(screen, title, source, help_text, accept_keys, cancel_keys)
