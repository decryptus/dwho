# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Application errors without optional framework imports."""

class DWhoError(Exception):
    pass

class DWhoConfigurationError(DWhoError):
    pass

# Preserve the historical pickle/import identity.
DWhoError.__module__ = 'dwho.classes.errors'
DWhoConfigurationError.__module__ = 'dwho.classes.errors'
