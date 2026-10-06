# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared blue terminal appearance and explicitly labelled semantic states."""

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
SHELL_CSS = '''
Screen { background: #0a1220; color: #d6e2f3; }
.dw-top { height: 3; background: #101f34; padding: 1 2; }
.dw-brand { width: 25; color: #83cfff; text-style: bold; }
.dw-location { width: 1fr; color: #b5cbe4; }
.dw-mode { width: 18; color: #afd6ff; text-align: right; text-style: bold; }
.dw-notice { height: auto; min-height: 1; max-height: 3; padding: 0 2; background: #16334a; }
.dw-workspace { height: 1fr; }
.dw-sidebar { width: 23; background: #0e1b2c; border-right: solid #21354f; padding: 1; }
.dw-sidebar-title { height: 3; color: #718eaf; padding: 1; }
.dw-nav { width: 100%; min-width: 0; height: 3; border: none; background: #0e1b2c; color: #b3c7df; text-align: left; }
.dw-nav:hover { background: #18314e; }
.dw-nav.dw-active { background: #173e62; color: #b7e2ff; border-left: thick #69bafa; text-style: bold; }
.dw-main { width: 1fr; padding: 1 2; }
.dw-heading { height: auto; max-height: 2; margin-bottom: 1; text-style: bold; color: #eef6ff; }
.dw-metrics { height: 5; margin-bottom: 1; }
.dw-metric { width: 1fr; margin-right: 1; padding: 0 2; background: #102137; border-top: solid #315675; }
.dw-metric-label { height: 1; color: #95b2d1; }
.dw-metric-value { height: 1; text-style: bold; color: #e4f2ff; }
.dw-metric-note { height: 1; color: #86a1c0; }
.dw-body { height: 1fr; }
.dw-inventory { width: 1fr; margin-right: 2; }
.dw-search { height: 3; margin-bottom: 1; background: #102137; border: tall #294866; }
.dw-search:focus { border: tall #72bdff; }
.dw-table { height: 1fr; background: #0d192a; }
.dw-table > .datatable--header { background: #182c44; color: #aec5e0; text-style: none; }
.dw-table > .datatable--odd-row { background: #101f32; }
.dw-table > .datatable--even-row { background: #0d192a; }
.dw-table > .datatable--cursor { background: #204c73; color: #ffffff; text-style: bold; }
.dw-table > .datatable--hover { background: #193a59; }
.dw-empty { height: auto; padding: 1; color: #a6bed8; background: #102137; }
.dw-detail { width: 39; background: #102137; border: round #305778; padding: 1 2; }
.dw-detail-title { height: auto; margin-bottom: 1; color: #e6f3ff; text-style: bold; }
.dw-detail-text { height: auto; color: #a9c2df; }
.dw-activity { height: 7; margin-top: 1; padding-top: 1; border-top: solid #29425e; }
.dw-activity-title { height: 1; color: #badbfa; text-style: bold; }
.dw-activity-text { height: 1fr; color: #a6bed9; }
.dw-small { display: none; height: 1fr; content-align: center middle; padding: 2; color: #efc586; }
.dw-compact .dw-sidebar { width: 18; }
.dw-compact .dw-detail { width: 29; }
.dw-compact .dw-main { padding: 1; }
.dw-compact .dw-metric { padding: 0 1; }
.dw-too-small .dw-workspace { display: none; }
.dw-too-small .dw-small { display: block; }
Footer { background: #13273f; color: #a9c5e4; }
Footer > .footer--key { background: #244566; color: #cbeaff; }
Confirmation { align: center middle; background: #000000 60%; }
.dw-confirm { width: 76; max-width: 95%; height: auto; max-height: 90%; padding: 1 2; background: #14253b; border: round #638fb4; }
.dw-confirm-title { height: auto; text-style: bold; color: #e3f2ff; margin-bottom: 1; }
.dw-confirm-details { height: 10; max-height: 50%; }
.dw-confirm-hint { height: auto; margin: 1 0; color: #efc586; }
.dw-confirm-buttons { height: 3; align: right middle; }
.dw-confirm-buttons Button { margin-left: 1; }
'''
