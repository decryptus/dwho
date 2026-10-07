# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Product terminal palettes and explicitly labelled semantic states."""

from types import MappingProxyType

from textual.theme import Theme

STATE_LABELS = {
    'info': 'INFO', 'accepted': 'ACCEPTED', 'queued': 'QUEUED',
    'running': 'IN PROGRESS', 'success': 'SUCCESS', 'warning': 'WARNING',
    'unknown': 'UNKNOWN', 'failure': 'FAILED', 'denied': 'DENIED',
}
STATE_COLORS = {
    'info': '#85bfff', 'accepted': '#85bfff', 'queued': '#85bfff',
    'running': '#b6adff', 'success': '#88d4bd', 'warning': '#efc586',
    'unknown': '#efc586', 'failure': '#ff9a9e', 'denied': '#ff9a9e',
}
MODE_LABELS = {'read_only': 'READ ONLY', 'test': 'TEST MODE', 'interactive': 'INTERACTIVE'}
# Immutable specifications; each application receives its own Theme instance.
# background, surface, panel, foreground, primary, secondary, selection
PALETTES = MappingProxyType({
    'default': ('#0a1220', '#101f34', '#102137', '#d6e2f3', '#83cfff', '#afd6ff', '#204c73'),
    'atraxis': ('#080f20', '#0e1b32', '#10233a', '#dcecf5', '#64d9f5', '#a6cfff', '#16435c'),
    'auton': ('#081b1c', '#0d292b', '#103336', '#def1ee', '#60d5c6', '#ffb173', '#1b504c'),
    'monit-docker': ('#111922', '#1a2734', '#203140', '#e0e8ef', '#92bad6', '#bdd0e0', '#354f65'),
    'galliflow': ('#161022', '#241a35', '#2b2040', '#eee5f7', '#c1a0ef', '#dac3f5', '#503770'),
    'certlord': ('#191816', '#282620', '#333026', '#f0eadb', '#e2c16d', '#f0d9a0', '#51462b'),
})


def product_theme(product, palette=None):
    """Build an isolated native theme; unknown products retain the default blue.

    An explicit palette is useful when the displayed product name is customized.
    Invalid explicit choices fail instead of silently selecting another identity.
    """
    key = str(product).casefold() if palette is None else palette
    if palette is None and key not in PALETTES:
        key = 'default'
    if key not in PALETTES:
        raise ValueError('invalid_dashboard_palette')
    background, surface, panel, foreground, primary, secondary, selection = PALETTES[key]
    return Theme(name='dwho-' + key, primary=primary, secondary=secondary,
                 accent=secondary, background=background, surface=surface,
                 panel=panel, foreground=foreground, dark=True,
                 success=STATE_COLORS['success'], warning=STATE_COLORS['warning'],
                 error=STATE_COLORS['failure'], variables={
                     'primary-muted': selection,
                     'block-cursor-background': selection,
                     'block-cursor-foreground': foreground,
                     'block-cursor-blurred-background': selection,
                     'block-cursor-blurred-foreground': foreground,
                     'button-color-foreground': background,
                 })


SHELL_CSS = '''
Screen { background: $background; color: $foreground; }
.dw-top { height: 3; background: $surface; padding: 1 2; }
.dw-brand { width: 25; color: $primary; text-style: bold; }
.dw-location { width: 1fr; color: $foreground; }
.dw-mode { width: 18; color: $secondary; text-align: right; text-style: bold; }
.dw-notice { height: auto; min-height: 1; max-height: 3; padding: 0 2; background: $panel; }
.dw-workspace { height: 1fr; }
.dw-sidebar { width: 23; background: $surface; border-right: solid $panel-lighten-2; padding: 1; }
.dw-sidebar-title { height: 3; color: $foreground-muted; padding: 1; }
.dw-nav { width: 100%; min-width: 0; height: 3; border: none; background: $surface; color: $foreground; text-align: left; }
.dw-nav:hover { background: $surface-lighten-1; }
.dw-nav.dw-active { background: $primary-muted; color: $foreground; border-left: thick $primary; text-style: bold; }
.dw-main { width: 1fr; padding: 1 2; }
.dw-heading { height: auto; max-height: 2; margin-bottom: 1; text-style: bold; color: $foreground; }
.dw-metrics { height: 5; margin-bottom: 1; }
.dw-metric { width: 1fr; margin-right: 1; padding: 0 2; background: $panel; border-top: solid $panel-lighten-2; }
.dw-metric-label { height: 1; color: $foreground; }
.dw-metric-value { height: 1; text-style: bold; color: $foreground; }
.dw-metric-note { height: 1; color: $foreground-muted; }
.dw-body { height: 1fr; }
.dw-inventory { width: 1fr; margin-right: 2; }
.dw-search { height: 3; margin-bottom: 1; background: $panel; border: tall $panel-lighten-2; }
.dw-search:focus { border: tall $primary; }
.dw-table { height: 1fr; background: $background; }
.dw-table > .datatable--header { background: $panel; color: $foreground; text-style: none; }
.dw-table > .datatable--odd-row { background: $surface; }
.dw-table > .datatable--even-row { background: $background; }
.dw-table > .datatable--cursor { background: $primary-muted; color: $foreground; text-style: bold; }
.dw-table > .datatable--hover { background: $surface-lighten-1; }
.dw-empty { height: auto; padding: 1; color: $foreground; background: $panel; }
.dw-detail { width: 39; background: $panel; border: round $panel-lighten-2; padding: 1 2; }
.dw-detail-title { height: auto; margin-bottom: 1; color: $foreground; text-style: bold; }
.dw-detail-text { height: auto; color: $foreground; }
.dw-activity { height: 7; margin-top: 1; padding-top: 1; border-top: solid $panel-lighten-2; }
.dw-activity-title { height: 1; color: $secondary; text-style: bold; }
.dw-activity-text { height: 1fr; color: $foreground; }
.dw-small { display: none; height: 1fr; content-align: center middle; padding: 2; color: #efc586; }
.dw-compact .dw-sidebar { width: 18; }
.dw-compact .dw-detail { width: 29; }
.dw-compact .dw-main { padding: 1; }
.dw-compact .dw-metric { padding: 0 1; }
.dw-too-small .dw-workspace { display: none; }
.dw-too-small .dw-small { display: block; }
Footer { background: $surface; color: $foreground; }
Footer > .footer--key { background: $primary-muted; color: $secondary; }
Confirmation { align: center middle; background: #000000 60%; }
.dw-confirm { width: 76; max-width: 95%; height: auto; max-height: 90%; padding: 1 2; background: $panel; border: round $primary; }
.dw-confirm-title { height: auto; text-style: bold; color: $foreground; margin-bottom: 1; }
.dw-confirm-details { height: 10; max-height: 50%; }
.dw-confirm-hint { height: auto; margin: 1 0; color: #efc586; }
.dw-confirm-buttons { height: 3; align: right middle; }
.dw-confirm-buttons Button { margin-left: 1; }
'''
