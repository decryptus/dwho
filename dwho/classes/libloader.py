# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.libloader"""

import logging
import os
import sys
import warnings

try:
    from importlib.util import module_from_spec, spec_from_file_location
except ImportError:  # Preserve the declared Python 2.7 compatibility.
    module_from_spec = spec_from_file_location = None

LOG = logging.getLogger('dwho.libloader')


class DwhoLibLoader(object):
    @staticmethod
    def _load_source(name, filepath):
        if spec_from_file_location is None:
            import imp  # Only used on interpreters without importlib's spec API.
            with open(filepath, 'rb') as module_file:
                return imp.load_source(name, filepath, module_file)

        spec = spec_from_file_location(name, filepath)
        if spec is None or spec.loader is None:
            raise ImportError("Unable to load module %r from %r" % (name, filepath))
        module = module_from_spec(spec)
        # Plugins may look themselves up while executing registration code.
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
        return sys.modules[name]

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
                module = cls._load_source(name, os.path.abspath(filepath))

            r[name] = module

        return r
