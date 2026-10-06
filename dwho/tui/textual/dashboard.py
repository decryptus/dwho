# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reusable shell for product-owned tables; no collector, client or operations."""
from collections import namedtuple

from rich.text import Text
from textual.app import App
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, DataTable, Footer, Input, Static

from .theme import MODE_LABELS, SHELL_CSS
from .widgets import DetailPanel, MetricCard, StatusLine, plain_text

TableRow = namedtuple('TableRow', 'key cells title details')
MAX_ROWS = 10000
MAX_COLUMNS = 20
MAX_NAVIGATION_ITEMS = 20
MAX_METRICS = 4
MAX_SEARCH = 128
MAX_CELL_LENGTH = 1024
MAX_TITLE_LENGTH = 256
MIN_WIDTH, MIN_HEIGHT = 80, 24
COMPACT_WIDTH = 120


class DashboardApp(App):
    """Products supply presentation rows and handle the emitted messages.

    No operation is implied by a row selection, navigation request or mode label.
    Call display_rows from the app thread (call_from_thread for worker results).
    """
    CSS = SHELL_CSS
    BINDINGS = [('slash', 'search', 'Search'), ('escape', 'clear_search', 'Clear'),
                ('q', 'quit', 'Quit')]

    class NavigationRequested(Message):
        def __init__(self, key):
            super(DashboardApp.NavigationRequested, self).__init__()
            self.key = key

    class SelectionChanged(Message):
        def __init__(self, key):
            super(DashboardApp.SelectionChanged, self).__init__()
            self.key = key

    def __init__(self, product, heading, columns, navigation=(), mode='read_only',
                 subtitle='', metrics=(), **kwargs):
        if mode not in MODE_LABELS:
            raise ValueError('invalid_dashboard_mode')
        if not 1 <= len(columns) <= MAX_COLUMNS:
            raise ValueError('invalid_dashboard_columns')
        nav = tuple(navigation)
        if len(nav) > MAX_NAVIGATION_ITEMS or len(set(key for key, label in nav)) != len(nav):
            raise ValueError('invalid_dashboard_navigation')
        if len(metrics) > MAX_METRICS:
            raise ValueError('too_many_dashboard_metrics')
        super(DashboardApp, self).__init__(**kwargs)
        self.product, self.heading, self.subtitle = product, heading, subtitle
        self.columns, self.navigation, self.mode = tuple(columns), nav, mode
        self.metrics = tuple(metrics)
        self._rows, self._visible_keys = {}, []
        self._updating_rows = False

    def compose(self):
        with Horizontal(classes='dw-top'):
            yield Static(plain_text(self.product), markup=False, classes='dw-brand')
            yield Static(plain_text(self.subtitle), markup=False, classes='dw-location')
            yield Static(MODE_LABELS[self.mode], markup=False, classes='dw-mode')
        yield StatusLine('info', 'Waiting for data.', classes='dw-notice', id='dw-notice')
        yield Static('Terminal too small. Resize to at least 80 x 24. Press q to quit.',
                     markup=False, classes='dw-small')
        with Horizontal(classes='dw-workspace'):
            with VerticalScroll(classes='dw-sidebar'):
                yield Static('NAVIGATION', classes='dw-sidebar-title')
                for index, (key, label) in enumerate(self.navigation):
                    yield Button(Text(plain_text(label)), id='dw-nav-%s' % index,
                                 classes='dw-nav' + (' dw-active' if index == 0 else ''))
            with Vertical(classes='dw-main'):
                yield Static(plain_text(self.heading), markup=False, classes='dw-heading')
                with Horizontal(classes='dw-metrics'):
                    for metric in self.metrics:
                        yield MetricCard(*metric)
                with Horizontal(classes='dw-body'):
                    with Vertical(classes='dw-inventory'):
                        yield Input(placeholder='Search this view...', max_length=MAX_SEARCH, classes='dw-search')
                        yield Static('No entries in this view.', markup=False, classes='dw-empty')
                        table = DataTable(zebra_stripes=True, cursor_type='row', classes='dw-table')
                        for label in self.columns:
                            table.add_column(Text(plain_text(label)))
                        yield table
                    yield DetailPanel(id='dw-details')
                with Vertical(classes='dw-activity'):
                    yield Static('RECENT ACTIVITY', classes='dw-activity-title')
                    with VerticalScroll():
                        yield Static('', markup=False, classes='dw-activity-text', id='dw-activity')
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.focus()
        self.query_one('.dw-metrics').display = bool(self.metrics)

    def on_resize(self, event):
        self.screen.set_class(event.size.width < COMPACT_WIDTH, 'dw-compact')
        self.screen.set_class(event.size.width < MIN_WIDTH or event.size.height < MIN_HEIGHT, 'dw-too-small')

    def display_rows(self, rows):
        prepared = {}
        for index, row in enumerate(rows):
            if (index >= MAX_ROWS or not isinstance(row, TableRow) or not isinstance(row.key, str)
                    or not 1 <= len(row.key) <= MAX_TITLE_LENGTH or row.key in prepared or len(row.cells) != len(self.columns)):
                raise ValueError('invalid_dashboard_rows')
            prepared[row.key] = TableRow(row.key, tuple(plain_text(cell, limit=MAX_CELL_LENGTH) for cell in row.cells),
                                         plain_text(row.title, limit=MAX_TITLE_LENGTH), plain_text(row.details, multiline=True))
        self._rows = prepared
        self._render_rows()

    def _render_rows(self):
        table = self.query_one(DataTable)
        selected = (self._visible_keys[table.cursor_row]
                    if table.cursor_row < len(self._visible_keys) else None)
        term = self.query_one(Input).value.casefold()
        visible = [row for row in self._rows.values() if term in ' '.join(row.cells).casefold()]
        self._visible_keys = [row.key for row in visible]
        self._updating_rows = True
        try:
            table.clear()
            for row in visible:
                table.add_row(*(Text(cell) for cell in row.cells), key=row.key)
            if visible:
                table.move_cursor(row=self._visible_keys.index(selected) if selected in self._visible_keys else 0)
        finally:
            self._updating_rows = False
        self.query_one('.dw-empty').display = not visible
        if visible:
            self._show_row(visible[table.cursor_row].key)
        else:
            self.query_one(DetailPanel).show_details('No selection', 'No matching entries in this view.')

    def _show_row(self, key):
        if key not in self._visible_keys:
            return
        row = self._rows[key]
        self.query_one(DetailPanel).show_details(row.title, row.details)

    def on_data_table_row_highlighted(self, event):
        cursor = self.query_one(DataTable).cursor_row
        if (not self._updating_rows and cursor < len(self._visible_keys)
                and event.row_key.value == self._visible_keys[cursor]):
            self._show_row(event.row_key.value)
            self.post_message(self.SelectionChanged(event.row_key.value))

    def on_input_changed(self, event):
        self._render_rows()

    def on_button_pressed(self, event):
        if not event.button.has_class('dw-nav'):
            return
        index = int(event.button.id.rsplit('-', 1)[1])
        # The owning application decides whether/how to change the visible view.
        self.post_message(self.NavigationRequested(self.navigation[index][0]))

    def select_navigation(self, key):
        keys = [item[0] for item in self.navigation]
        if key not in keys:
            raise ValueError('unknown_navigation_key')
        for index, button in enumerate(self.query('.dw-nav')):
            button.set_class(index == keys.index(key), 'dw-active')

    def set_notice(self, state, text):
        self.query_one('#dw-notice', StatusLine).set_status(state, text)

    def set_activity(self, lines):
        self.query_one('#dw-activity', Static).update(plain_text(lines, multiline=True))

    def action_search(self):
        self.query_one(Input).focus()

    def action_clear_search(self):
        self.query_one(Input).value = ''
        self.query_one(DataTable).focus()
