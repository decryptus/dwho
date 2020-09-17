# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.inoplugs"""

import abc
import logging
import os

from socket import getfqdn

from six import iterkeys

from dwho.classes.abstract import DWhoAbstractDB

CACHE_EXPIRE    = -1
LOCK_TIMEOUT    = 60
LOG             = logging.getLogger('dwho.inoplugs')


class DWhoInoPlugs(dict):
    def register(self, plugin):
        if not isinstance(plugin, DWhoInoPlugBase):
            raise TypeError("Invalid Inotify Plugin class. (class: %r)" % plugin)
        return dict.__setitem__(self, plugin.PLUGIN_NAME, plugin)

    def unregister(self, plugin):
        if not isinstance(plugin, DWhoInoPlugBase):
            raise TypeError("Invalid Inotify Plugin class. (class: %r)" % plugin)
        return dict.__delitem__(self, plugin.PLUGIN_NAME)

INOPLUGS = DWhoInoPlugs()


class DWhoInotifyEventBase(object): # pylint: disable=useless-object-inheritance
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


class DWhoInoPlugBase(object): # pylint: disable=useless-object-inheritance
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

        if not isinstance(self.plugconf, dict):
            self.enabled    = False
            return self

        if 'autostart' in self.plugconf:
            self.autostart  = bool(self.plugconf['autostart'])

        if 'enabled' in self.plugconf:
            self.enabled    = bool(self.plugconf['enabled'])

        return self

    def at_start(self): # pylint: disable=no-self-use
        return

    def at_stop(self): # pylint: disable=no-self-use
        return

    def safe_init(self): # pylint: disable=no-self-use
        return


class DWhoInoPluginSQLBase(DWhoInoPlugBase, DWhoAbstractDB):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def PLUGIN_NAME(self):
        return

    def __init__(self):
        DWhoInoPlugBase.__init__(self)
        DWhoAbstractDB.__init__(self)

    def init(self, config):
        DWhoInoPlugBase.init(self, config)

        for key in iterkeys(config['general']):
            if not key.startswith('db_uri_'):
                continue
            name = key[7:]
            if name not in self.db:
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

    def get_event_params(self):
        if hasattr(self.event, 'plugins') \
           and isinstance(self.event.plugins, dict) \
           and self.PLUGIN_NAME in self.event.plugins:
            return self.event.plugins[self.PLUGIN_NAME].copy()

        return {}

    def _get_path_all_options(self):
        if not self.cfg_path \
           or self.cfg_path.path not in self.inopaths \
           or not isinstance(self.inopaths[self.cfg_path.path], dict):
            return None

        return self.inopaths[self.cfg_path.path]

    def _get_path_options(self):
        path_all_options = self._get_path_all_options()

        if not path_all_options \
           or 'plugins' not in path_all_options \
           or self.PLUGIN_NAME not in path_all_options['plugins'] \
           or not isinstance(path_all_options['plugins'][self.PLUGIN_NAME], dict):
            return None

        return path_all_options['plugins'][self.PLUGIN_NAME]

    @abc.abstractmethod
    def run(self, cfg_path, event, filepath):
        """Do the action."""

    def realdstpath(self, event, filepath, prefix = None): # pylint: disable=unused-argument
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
