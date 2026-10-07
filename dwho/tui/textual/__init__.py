# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional Textual presentation; importing dwho.tui never loads this module.

Applications own authentication, data collection, refresh and every operation.
This module requires Python 3.9+ and the dwho[textual] optional dependency.
"""
from __future__ import absolute_import

import sys

if sys.version_info < (3, 9):
    raise ImportError('dwho.tui.textual requires Python 3.9 or newer')

try:
    import textual as _textual
except ImportError:
    raise ImportError('Install dwho[textual] to use dwho.tui.textual')

from .widgets import Confirmation, DetailPanel, MetricCard, StatusLine, plain_text
from .dashboard import DashboardApp, TableRow
from .forms import InputForm
from .service import ServiceDashboard

__all__ = ['ServiceDashboard', 'InputForm', 'Confirmation', 'DashboardApp', 'DetailPanel', 'MetricCard',
           'StatusLine', 'TableRow', 'plain_text']
