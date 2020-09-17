# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.plugins"""

import abc
import logging

from socket import getfqdn

from six import iterkeys

from dwho.classes.abstract import DWhoAbstractHelper, DWhoAbstractDB

LOG                          = logging.getLogger('dwho.plugins')


class DWhoPlugins(dict):
    def register(self, plugin):
        if not isinstance(plugin, DWhoPluginBase):
            raise TypeError("Invalid Plugin class. (class: %r)" % plugin)
        return dict.__setitem__(self, plugin.PLUGIN_NAME, plugin)

PLUGINS = DWhoPlugins()


class DWhoPluginBase(DWhoAbstractHelper): # pylint: disable=useless-object-inheritance
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def PLUGIN_NAME(self):
        return

    def __init__(self):
        self.autostart   = True
        self.config      = None
        self.enabled     = True
        self.initialized = False
        self.plugconf    = None
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

        self.plugconf       = config['plugins'][self.PLUGIN_NAME]

        if 'autostart' in self.plugconf:
            self.autostart  = bool(self.plugconf['autostart'])

        if 'enabled' in self.plugconf:
            self.enabled    = bool(self.plugconf['enabled'])

        return self

    @abc.abstractmethod
    def at_start(self):
        return

    def at_stop(self): # pylint: disable=no-self-use
        return

    def safe_init(self): # pylint: disable=no-self-use
        return


class DWhoPluginSQLBase(DWhoPluginBase, DWhoAbstractDB):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def PLUGIN_NAME(self):
        return

    def __init__(self):
        DWhoPluginBase.__init__(self)
        DWhoAbstractDB.__init__(self)

    def init(self, config):
        DWhoPluginBase.init(self, config)

        for key in iterkeys(config['general']):
            if not key.startswith('db_uri_'):
                continue
            name = key[7:]
            if name not in self.db:
                self.db[name] = {'conn': None, 'cursor': None}

        return self

    @abc.abstractmethod
    def at_start(self):
        return
