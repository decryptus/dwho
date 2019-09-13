# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.errors"""

from pyinotify import PyinotifyError


class DWhoError(Exception):
    pass

class DWhoConfigurationError(DWhoError):
    pass

class DWhoInotifyError(PyinotifyError):
    pass
