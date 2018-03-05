# -*- coding: utf-8 -*-
"""DWho modules"""

__author__  = "Adrien DELLE CAVE <adc@doowan.net>"
__license__ = """
    Copyright (C) 2015  doowan

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
import re

from dwho.classes.abstract import DWhoAbstractDB
from mako.lookup import TemplateLookup
from mako.template import Template
from sonicprobe.libs import http_json_server
from sonicprobe.libs.http_json_server import HttpResponse

LOG     = logging.getLogger('dwho.modules')


class DWhoModules(dict):
    def register(self, module):
        if not isinstance(module, DWhoModuleBase):
            raise TypeError("Invalid Module class. (class: %r)" % module)
        return dict.__setitem__(self, module.MODULE_NAME, module)

MODULES = DWhoModules()


class DWhoModuleBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def MODULE_NAME(self):
        return

    def __init__(self):
        self.config         = None
        self.charset        = 'utf-8'
        self.content_type   = 'application/json'
        self.initialized    = False
        self.options        = None

    def _anonymous(self, request):
        return

    def at_start(self, options):
        self.options        = options

    def safe_init(self, options):
        return

    def at_stop(self):
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

        ref_general      = config['general']
        routes_list      = []

        if ref_general.has_key('charset'):
            self.set_charset(ref_general['charset'])

        if ref_general.has_key('content_type'):
            self.set_content_type(ref_general['content_type'])

        if config.has_key('modules') \
           and config['modules'].has_key(self.MODULE_NAME):
            ref_module      = config['modules'][self.MODULE_NAME]

            if ref_module.has_key('charset'):
                self.set_charset(ref_module['charset'])

            if ref_module.has_key('content_type'):
                self.set_content_type(ref_module['content_type'])

            if ref_module.has_key('routes') and isinstance(ref_module['routes'], dict):
                routes_list.append(ref_module['routes'])

        for routes in routes_list:
            self._register_commands(routes)

        return self

    def _register_commands(self, routes):
        for value in routes.itervalues():
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
                           'to_auth':       bool(value.get('auth')),
                           'to_log':        bool(value.get('log', True))}

            if value.has_key('regexp'):
                try:
                    cmd_args['name']    = re.compile(value['regexp'])
                except Exception, e:
                    LOG.exception("Unable to compile regexp. (regexp: %r, error: %r)", value['regexp'], e)
                    raise

            if value.get('static'):
                cmd_args['static']  = True
                cmd_args['op']      = 'GET'

                if not value.get('root'):
                    LOG.error("Missing root for static route")
                else:
                    cmd_args['root']    = value['root']

            for x in ('safe_init', 'at_start', 'at_stop'):
                if value.get(x):
                    if value[x] is True:
                        cmd_args[x] = getattr(self, x)
                    else:
                        cmd_args[x] = getattr(self, value[x])

            http_json_server.register(**cmd_args)


class DWhoModuleSQLBase(DWhoModuleBase, DWhoAbstractDB):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        DWhoModuleBase.__init__(self)
        DWhoAbstractDB.__init__(self)

    def init(self, config):
        DWhoModuleBase.init(self, config)

        for key in config['general'].iterkeys():
            if not key.startswith('db_uri_'):
                continue
            name = key[7:]
            if not self.db.has_key(name):
                self.db[name] = {'conn': None, 'cursor': None}

        return self


class DWhoModuleWebBase(DWhoModuleBase):
    __metaclass__ = abc.ABCMeta

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

        if config.has_key('modules') \
           and config['modules'].has_key(self.MODULE_NAME):
            ref_module      = config['modules'][self.MODULE_NAME]

            if ref_module.has_key('web_directories'):
                if isinstance(ref_module['web_directories'], basestring):
                    ref_module['web_directories'] = [ref_module['web_directories']]
                elif not isinstance(ref_module['web_directories'], list):
                    LOG.error('Invalid web_directories type. (web_directories: %r, module: %r)',
                              ref_module['web_directories'],
                              self.MODULE_NAME)
                    ref_module['web_directories'] = []
            else:
                ref_module['web_directories'] = []

            if ref_module['web_directories']:
                web_directories = ref_module['web_directories']

        self.templates  = TemplateLookup(directories        = web_directories,
                                         output_encoding    = self.get_charset())

        return self
