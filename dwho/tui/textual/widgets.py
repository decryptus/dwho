# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Presentation only. Remote values are plain text, never terminal commands."""
from rich.text import Text
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from .theme import SHELL_CSS, STATE_COLORS, STATE_LABELS

MAX_TEXT_LENGTH = 65536


def plain_text(value, multiline=False, limit=MAX_TEXT_LENGTH):
    value = str(value)[:limit]
    return ''.join(char if char.isprintable() or (multiline and char == '\n')
                   else ' ' for char in value)


class StatusLine(Static):
    def __init__(self, state='info', text='', **kwargs):
        self.state = state if state in STATE_LABELS else 'unknown'
        super(StatusLine, self).__init__(self._text(text), markup=False, **kwargs)

    def _text(self, text):
        rendered = Text(STATE_LABELS[self.state] + '  ', style=STATE_COLORS[self.state])
        rendered.append(plain_text(text))
        return rendered

    def set_status(self, state, text):
        self.state = state if state in STATE_LABELS else 'unknown'
        self.update(self._text(text))


class MetricCard(Vertical):
    def __init__(self, label, value, note='', state='info', **kwargs):
        super(MetricCard, self).__init__(**kwargs)
        self.add_class('dw-metric')
        self._values = label, value, note, state

    def compose(self):
        label, value, note, state = self._values
        yield Static(plain_text(label), markup=False, classes='dw-metric-label')
        yield Static(Text(plain_text(value), style=STATE_COLORS.get(state, STATE_COLORS['unknown'])), classes='dw-metric-value')
        yield Static(plain_text(note), markup=False, classes='dw-metric-note')


class DetailPanel(VerticalScroll):
    def __init__(self, **kwargs):
        super(DetailPanel, self).__init__(**kwargs)
        self.add_class('dw-detail')

    def compose(self):
        yield Static('Details', markup=False, classes='dw-detail-title')
        yield Static('Select a row to view its details.', markup=False, classes='dw-detail-text')

    def show_details(self, title, text):
        self.query_one('.dw-detail-title', Static).update(plain_text(title))
        self.query_one('.dw-detail-text', Static).update(plain_text(text, multiline=True))
        self.scroll_home(animate=False)


class Confirmation(ModalScreen):
    """Return a boolean intent only; callers must authorize and act separately."""
    DEFAULT_CSS = SHELL_CSS[SHELL_CSS.index('Confirmation {'):]
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, title, details, confirm_label='Confirm', cancel_label='Cancel',
                 hint='Review the selection before confirming.'):
        super(Confirmation, self).__init__()
        self.title_text, self.details = title, details
        self.confirm_label, self.cancel_label, self.hint = confirm_label, cancel_label, hint

    def compose(self):
        with Vertical(classes='dw-confirm'):
            yield Static(plain_text(self.title_text), markup=False, classes='dw-confirm-title')
            with VerticalScroll(classes='dw-confirm-details'):
                yield Static(plain_text(self.details, multiline=True), markup=False)
            yield Static(plain_text(self.hint), markup=False, classes='dw-confirm-hint')
            with Horizontal(classes='dw-confirm-buttons'):
                yield Button(Text(plain_text(self.cancel_label)), id='dw-cancel')
                yield Button(Text(plain_text(self.confirm_label)), id='dw-confirm', variant='primary')

    def on_mount(self):
        self.query_one('#dw-cancel', Button).focus()

    def action_cancel(self):
        self.dismiss(False)

    def on_button_pressed(self, event):
        event.stop()
        self.dismiss(event.button.id == 'dw-confirm')
