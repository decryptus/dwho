# -*- coding: utf-8 -*-
"""DWho plugins"""

__author__  = "Adrien DELLE CAVE <adc@doowan.net>"
__license__ = """
    Copyright (C) 2016  doowan

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

import abc
import logging

from dwho.classes.abstract import DWhoAbstractDB
from socket import getfqdn

LOG     = logging.getLogger('dwho.plugins')


class DWhoPlugins(dict):
    def register(self, plugin):
        if not isinstance(plugin, DWhoPluginBase):
            raise TypeError("Invalid Plugin class. (class: %r)" % plugin)
        return dict.__setitem__(self, plugin.PLUGIN_NAME, plugin)

PLUGINS = DWhoPlugins()


class DWhoPluginBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def PLUGIN_NAME(self):
        return

    def __init__(self):
        self.autostart   = True
        self.config      = None
        self.enabled     = True
        self.initialized = False
        self.server_id   = getfqdn()

    def init(self, config):
        if self.initialized:
            return self

        self.initialized    = True
        self.config         = config
        self.server_id      = config['general']['server_id']

        if 'plugins' not in config \
           or self.PLUGIN_NAME not in config['plugins']:
            return self

        ref_plugin          = config['plugins'][self.PLUGIN_NAME]

        if 'autostart' in ref_plugin:
            self.autostart  = bool(ref_plugin['autostart'])

        if 'enabled' in ref_plugin:
            self.enabled    = bool(ref_plugin['enabled'])

        return self

    @abc.abstractmethod
    def at_start(self):
        return

    def at_stop(self):
        return

    def safe_init(self):
        return


class DWhoPluginSQLBase(DWhoPluginBase, DWhoAbstractDB):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        DWhoPluginBase.__init__(self)
        DWhoAbstractDB.__init__(self)

    def init(self, config):
        DWhoPluginBase.init(self, config)

        for key in config['general'].iterkeys():
            if not key.startswith('db_uri_'):
                continue
            name = key[7:]
            if not self.db.has_key(name):
                self.db[name] = {'conn': None, 'cursor': None}

        return self
