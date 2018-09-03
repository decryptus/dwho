# -*- coding: utf-8 -*-
"""DWho plugins"""

__author__  = "Adrien DELLE CAVE <adc@doowan.net>"
__license__ = """
    Copyright (C) 2016-2018  doowan

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
import os

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
        self.plugconf    = None

    def init(self, config):
        if self.initialized:
            return self

        self.initialized    = True
        self.config         = config

        if 'inotify' not in config \
           or 'plugins' not in config['inotify'] \
           or self.PLUGIN_NAME not in config['inotify']['plugins']:
            return self

        self.plugconf       = config['inotify']['plugins'][self.PLUGIN_NAME]

        if isinstance(self.plugconf, bool):
            self.enabled    = self.plugconf
            return self
        elif not isinstance(self.plugconf, dict):
            self.enabled    = False
            return self

        if 'autostart' in self.plugconf:
            self.autostart  = bool(self.plugconf['autostart'])

        if 'enabled' in self.plugconf:
            self.enabled    = bool(self.plugconf['enabled'])

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
        self.cfg_path = None
        self.inoconf  = None
        self.inopaths = None

        DWhoInoPlugBase.__init__(self)
        DWhoInotifyEventBase.__init__(self)

    def init(self, config):
        DWhoInoPlugBase.init(self, config)
        DWhoInotifyEventBase.init(self, config)

        self.inoconf  = self.config['inotify']
        self.inopaths = self.config['inotify']['paths']

        return self

    def _get_path_all_options(self):
        if not self.cfg_path \
           or self.cfg_path.path not in self.inopaths \
           or not isinstance(self.inopaths[self.cfg_path.path], dict):
            return

        return self.inopaths[self.cfg_path.path]

    def _get_path_options(self):
        path_all_options = self._get_path_all_options()

        if not path_all_options \
           or 'plugins' not in path_all_options \
           or self.PLUGIN_NAME not in path_all_options['plugins'] \
           or not isinstance(path_all_options['plugins'][self.PLUGIN_NAME], dict):
            return

        return path_all_options['plugins'][self.PLUGIN_NAME]

    @abc.abstractmethod
    def run(self, cfg_path, event, filepath):
        """Do the action."""

    def realdstpath(self, event, filepath, prefix = None):
        r            = filepath
        path_options = self._get_path_options()

        if not path_options:
            path_options = self._get_path_all_options()
            if not path_options:
                return r

        if path_options.get('dest') and filepath.startswith(self.cfg_path.path):
            r = os.path.join(path_options['dest'], filepath[len(self.cfg_path.path):].lstrip(os.path.sep))

        if not prefix:
            return r

        return os.path.join(os.path.sep, prefix, r.lstrip(os.path.sep))

    def __call__(self, cfg_path, event, filepath):
        self.cfg_path = cfg_path
        return self.run(cfg_path, event, filepath)
