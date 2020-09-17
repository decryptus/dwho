# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.modules"""

import abc
import logging
import re

from socket import getfqdn

from six import iterkeys, itervalues, string_types

from httpdis import httpdis
from httpdis.httpdis import HttpResponse
from mako.lookup import TemplateLookup
from mako.template import Template

from dwho.classes.abstract import DWhoAbstractDB

LOG     = logging.getLogger('dwho.modules')


class DWhoModules(dict):
    def register(self, module):
        if not isinstance(module, DWhoModuleBase):
            raise TypeError("Invalid Module class. (class: %r)" % module)
        return dict.__setitem__(self, module.MODULE_NAME, module)

MODULES = DWhoModules()


class DWhoModuleBase(object): # pylint: disable=useless-object-inheritance
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def MODULE_NAME(self):
        return

    def __init__(self):
        self.config         = None
        self.charset        = 'utf-8'
        self.content_type   = 'application/json'
        self.initialized    = False
        self.modconf        = None
        self.options        = None
        self.server_id      = getfqdn()

    def _anonymous(self, request): # pylint: disable=unused-argument,no-self-use
        return

    def at_start(self, options):
        self.options        = options

    def safe_init(self, options): # pylint: disable=no-self-use,unused-argument
        return

    def at_stop(self): # pylint: disable=no-self-use
        return

    def set_charset(self, charset):
        self.charset        = charset
        return self

    def get_charset(self):
        return self.charset

    def set_content_type(self, content_type):
        self.content_type   = content_type
        return self

    def get_content_type(self):
        return self.content_type

    def init(self, config):
        if self.initialized:
            return self

        self.initialized = True
        self.config      = config
        self.server_id   = config['general']['server_id']

        ref_general      = config['general']
        routes_list      = []

        if 'charset' in ref_general:
            self.set_charset(ref_general['charset'])

        if 'content_type' in ref_general:
            self.set_content_type(ref_general['content_type'])

        if 'modules' in config \
           and self.MODULE_NAME in config['modules']:
            self.modconf = config['modules'][self.MODULE_NAME]

            if 'charset' in self.modconf:
                self.set_charset(self.modconf['charset'])

            if 'content_type' in self.modconf:
                self.set_content_type(self.modconf['content_type'])

            if 'routes' in self.modconf and isinstance(self.modconf['routes'], dict):
                routes_list.append(self.modconf['routes'])

        for routes in routes_list:
            self._register_commands(routes)

        return self

    def _register_commands(self, routes):
        for value in itervalues(routes):
            LOG.debug("Route: %r", value)
            cmd_args    = {'op':            value.get('op') or 'GET',
                           'safe_init':     None,
                           'at_start':      None,
                           'name':          value.get('name') or None,
                           'handler':       getattr(self, value['handler']),
                           'at_stop':       None,
                           'static':        False,
                           'root':          value.get('root') or None,
                           'replacement':   value.get('replacement') or None,
                           'charset':       value.get('charset') or self.get_charset(),
                           'content_type':  value.get('content_type') or self.get_content_type(),
                           'to_auth':       value.get('auth'),
                           'to_log':        bool(value.get('log', True))}

            if 'regexp' in value:
                try:
                    cmd_args['name'] = re.compile(value['regexp'])
                except Exception as e:
                    LOG.exception("Unable to compile regexp. (regexp: %r, error: %r)", value['regexp'], e)
                    raise

            if value.get('static'):
                cmd_args['static']  = True
                cmd_args['op']      = 'GET'

                if not value.get('root'):
                    LOG.error("Missing root for static route")
                else:
                    cmd_args['root'] = value['root']

            if isinstance(cmd_args['op'], string_types):
                cmd_args['op'] = [cmd_args['op']]

            for i, op in enumerate(cmd_args['op']):
                cmd       = cmd_args.copy()
                cmd['op'] = op

                for x in ('safe_init', 'at_start', 'at_stop'):
                    if i != 0:
                        cmd[x] = None
                    elif value.get(x):
                        if value[x] is True:
                            cmd[x] = getattr(self, x)
                        else:
                            cmd[x] = getattr(self, value[x])

                httpdis.register(**cmd)


class DWhoModuleSQLBase(DWhoModuleBase, DWhoAbstractDB):
    __metaclass__ = abc.ABCMeta


    @abc.abstractproperty
    def MODULE_NAME(self):
        return

    def __init__(self):
        DWhoModuleBase.__init__(self)
        DWhoAbstractDB.__init__(self)

    def init(self, config):
        DWhoModuleBase.init(self, config)

        for key in iterkeys(config['general']):
            if not key.startswith('db_uri_'):
                continue
            name = key[7:]
            if name not in self.db:
                self.db[name] = {'conn': None, 'cursor': None}

        return self


class DWhoModuleWebBase(DWhoModuleBase):
    __metaclass__ = abc.ABCMeta


    @abc.abstractproperty
    def MODULE_NAME(self):
        return

    def __init__(self):
        DWhoModuleBase.__init__(self)

        self.content_type   = "text/html; charset=%s" % self.get_charset()
        self.templates      = None

    def render(self, template_name, **kwargs):
        return HttpResponse(data    = self.templates.get_template(template_name).render(**kwargs),
                            headers = {'Content-type': self.get_content_type()})

    def frender(self, filename, **kwargs):
        return HttpResponse(data    = Template(filename = filename,
                                               lookup   = TemplateLookup(directories = ['/'])).render(**kwargs),
                            headers = {'Content-type': self.get_content_type()})

    def init(self, config):
        DWhoModuleBase.init(self, config)

        web_directories = config['general']['web_directories']

        if self.modconf:
            if 'web_directories' in self.modconf:
                if isinstance(self.modconf['web_directories'], string_types):
                    self.modconf['web_directories'] = [self.modconf['web_directories']]
                elif not isinstance(self.modconf['web_directories'], list):
                    LOG.error('Invalid web_directories type. (web_directories: %r, module: %r)',
                              self.modconf['web_directories'],
                              self.MODULE_NAME)
                    self.modconf['web_directories'] = []
            else:
                self.modconf['web_directories'] = []

            if self.modconf['web_directories']:
                web_directories = self.modconf['web_directories']

        self.templates  = TemplateLookup(directories        = web_directories,
                                         output_encoding    = self.get_charset())

        return self
