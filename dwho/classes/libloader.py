# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.libloader"""

import imp
import logging
import os
import sys
import warnings

LOG = logging.getLogger('dwho.libloader')


class DwhoLibLoader(object):
    @classmethod
    def load_dir(cls, xtype, path):
        r = {}

        for xfile in os.listdir(path):
            if xfile.startswith('.') \
               or xfile.endswith('__init__.py') \
               or not xfile.endswith('.py'):
                continue

            filepath = os.path.join(path, xfile)

            name = '.'.join([xtype, os.path.splitext(xfile)[0]])
            if name in sys.modules:
                r[name] = sys.modules[name]
                continue

            with warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                with open(filepath, 'rb') as module_file:
                    module = imp.load_source(name,
                                             os.path.abspath(os.path.join(path, xfile)),
                                             module_file)

            r[name] = module

        return r
