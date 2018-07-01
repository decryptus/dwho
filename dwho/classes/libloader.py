# -*- coding: utf-8 -*-
"""dwho libloader"""

__author__  = "Adrien DELLE CAVE <adc@doowan.net>"
__license__ = """
    Copyright (C) 2018  doowan

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA..
"""

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
