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


CACHE_EXPIRE    = -1
LOCK_TIMEOUT    = 60
LOG             = logging.getLogger('dwho.inoplugs')


class DWhoInoPlugs(dict):
    def register(self, plugin):
        if not isinstance(plugin, DWhoInoPlugBase):
            raise TypeError("Invalid Inotify Plugin class. (class: %r)" % plugin)
        return dict.__setitem__(self, plugin.PLUGIN_NAME, plugin)

INOPLUGS = DWhoInoPlugs()


class DWhoInotifyEventBase(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.cache_expire   = CACHE_EXPIRE
        self.config         = None
        self.cfg_path       = None
        self.event          = None
        self.filepath       = None
        self.lock_timeout   = LOCK_TIMEOUT
        self.server_id      = getfqdn()

    def init(self, config):
        self.cache_expire   = config['inotify'].get('cache_expire', CACHE_EXPIRE)
        self.config         = config
        self.lock_timeout   = config['inotify'].get('lock_timeout', LOCK_TIMEOUT)
        self.server_id      = config['general']['server_id']

        return self


class DWhoInoPlugBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def PLUGIN_NAME(self):
        return

    def __init__(self):
        self.autostart   = False
        self.config      = None
        self.enabled     = False
        self.initialized = False

    def init(self, config):
        if self.initialized:
            return self

        self.initialized    = True
        self.config         = config

        if 'inotify' not in config \
           or 'plugins' not in config['inotify'] \
           or self.PLUGIN_NAME not in config['inotify']['plugins']:
            return self

        ref_plugin          = config['inotify']['plugins'][self.PLUGIN_NAME]

        if isinstance(ref_plugin, bool):
            self.enabled    = ref_plugin
            return self
        elif not isinstance(ref_plugin, dict):
            self.enabled    = False
            return self

        if 'autostart' in ref_plugin:
            self.autostart  = bool(ref_plugin['autostart'])

        if 'enabled' in ref_plugin:
            self.enabled    = bool(ref_plugin['enabled'])

        return self

    def at_start(self):
        return

    def at_stop(self):
        return

    def safe_init(self):
        return


class DWhoInoPluginSQLBase(DWhoInoPlugBase, DWhoAbstractDB):
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


class DWhoInoEventPlugBase(DWhoInoPlugBase, DWhoInotifyEventBase):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        DWhoInoPlugBase.__init__(self)
        DWhoInotifyEventBase.__init__(self)

    def init(self, config):
        DWhoInoPlugBase.init(self, config)
        DWhoInotifyEventBase.init(self, config)

        return self

    @abc.abstractmethod
    def __call__(self, event, filepath):
        """Do the action."""
        return
