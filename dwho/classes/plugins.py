# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.plugins"""

import abc
import logging
import re

from socket import getfqdn

import six

from dwho.classes.abstract import DWhoAbstractDB

LOG                          = logging.getLogger('dwho.plugins')

_RE_MATCH_OBJECT_FUNCS       = ('match', 'search')
_PARAMS_DICT_MODIFIERS_MATCH = re.compile(r'^(?:(?P<modifiers>[\+\-~=%]+)\s)?(?P<key>.+)$').match
_PARAM_REGEX_OPTS            = ('default', 'func', 'return', 'return_args')


class DWhoPlugins(dict):
    def register(self, plugin):
        if not isinstance(plugin, DWhoPluginBase):
            raise TypeError("Invalid Plugin class. (class: %r)" % plugin)
        return dict.__setitem__(self, plugin.PLUGIN_NAME, plugin)

PLUGINS = DWhoPlugins()


class DWhoPluginBase(object): # pylint: disable=useless-object-inheritance
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

    @classmethod
    def _parse_re_flags(cls, flags):
        if isinstance(flags, int):
            return flags

        if isinstance(flags, list):
            r = 0
            for x in flags:
                r |= cls._parse_re_flags(x)
            return r

        if isinstance(flags, six.string_types):
            if flags.isdigit():
                return int(flags)
            return getattr(re, flags)

        return 0

    def _param_regex(self, args, value):
        args         = args.copy()
        func         = args.get('func') or 'sub'
        rfunc        = args.get('return')
        rargs        = args.get('return_args')
        is_match_obj = func in _RE_MATCH_OBJECT_FUNCS

        if is_match_obj and not rfunc:
            rfunc = 'group'
            rargs = [1]

        if is_match_obj and not rargs:
            rargs = [1]

        for x in _PARAM_REGEX_OPTS:
            if x in args:
                del args[x]

        if 'pattern' in args:
            flags = 0
            if 'flags' in args:
                flags = self._parse_re_flags(args.pop('flags'))
            func = getattr(re.compile(pattern = args.pop('pattern'),
                                      flags = flags),
                           func)
        else:
            func = getattr(re, func)

        args['string'] = value
        ret            = func(**args)

        if ret is None:
            return ''

        if not rfunc:
            return ret

        if rargs:
            return getattr(ret, rfunc)(*rargs)

        return getattr(ret, rfunc)()

    def _build_params_dict(self, name, cfg, values = None, xvars = None, r = None):
        if not isinstance(values, dict):
            values = {}

        if not isinstance(r, dict):
            r = {}

        if not cfg or not isinstance(cfg, list):
            return r

        fkwargs = {name: values.copy()}

        if isinstance(xvars, dict):
            fkwargs.update(xvars)

        for elt in cfg:
            ename = list(elt.keys())[0]
            m = _PARAMS_DICT_MODIFIERS_MATCH(ename)
            if m:
                modifiers = m.group('modifiers') or '+'
                key       = m.group('key')
            else:
                modifiers = '+'
                key       = ename

            if '+' in modifiers:
                r[key] = elt[ename]
            elif '-' in modifiers:
                if key not in r:
                    continue
                elif elt[ename] in (None, r[key]):
                    del r[key]
            elif '~' in modifiers:
                args = elt[ename]

                if key not in r:
                    r[key] = args.get('default') or ''
                else:
                    r[key] = self._param_regex(args, r[key])
            elif '=' in modifiers:
                if key in r:
                    r[elt[ename]] = r[key]

            if '%' in modifiers:
                r[key] = r[key].format(**fkwargs)

        return r

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

        for key in six.iterkeys(config['general']):
            if not key.startswith('db_uri_'):
                continue
            name = key[7:]
            if name not in self.db:
                self.db[name] = {'conn': None, 'cursor': None}

        return self

    @abc.abstractmethod
    def at_start(self):
        return
