# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.abstract"""

import abc
import re

try:
    from threading import _get_ident as thread_get_ident
except ImportError:
    from threading import get_ident as thread_get_ident

from six import string_types

from sonicprobe.libs import anysql

_RE_MATCH_OBJECT_FUNCS       = ('match', 'search')
_PARAMS_DICT_MODIFIERS_MATCH = re.compile(r'^(?:(?P<modifiers>[\+\-~=%]+)\s)?(?P<key>.+)$').match
_PARAM_REGEX_OPTS            = ('default', 'func', 'return', 'return_args')


class DWhoAbstractHelper(object): # pylint: disable=useless-object-inheritance
    __metaclass__ = abc.ABCMeta

    @classmethod
    def _parse_re_flags(cls, flags):
        if isinstance(flags, int):
            return flags

        if isinstance(flags, list):
            r = 0
            for x in flags:
                r |= cls._parse_re_flags(x)
            return r

        if isinstance(flags, string_types):
            if flags.isdigit():
                return int(flags)
            return getattr(re, flags)

        return 0

    @classmethod
    def _param_regex(cls, args, value):
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
                flags = cls._parse_re_flags(args.pop('flags'))
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

    @classmethod
    def _build_params_dict(cls, name, cfg, values = None, xvars = None, r = None):
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
                    r[key] = cls._param_regex(args, r[key])
            elif '=' in modifiers:
                if key in r:
                    r[elt[ename]] = r[key]

            if '{' in modifiers and '}' in modifiers:
                r[key] = r[key].format(**fkwargs)

        return r


class DWhoAbstractDB(object): # pylint: disable=useless-object-inheritance
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.config = {}
        self._db    = {}

    @property
    def db(self):
        thread_id = thread_get_ident()
        if thread_id not in self._db:
            self._db[thread_id] = {}

        return self._db[thread_id]

    @db.setter
    def db(self, value):
        thread_id = thread_get_ident()
        if thread_id not in self._db:
            self._db[thread_id] = {}

        self._db[thread_id] = value

    def db_connect(self, name):
        if not self.db:
            self.db = {name: {'conn':   None,
                              'cursor': None}}

        if not self.db[name]['conn'] or not self.db[name]['conn'].is_connected(self.db[name]['cursor']):
            if self.db[name]['cursor']:
                try:
                    self.db[name]['cursor'].close()
                except Exception:
                    pass
                self.db[name]['cursor'] = None

            if self.db[name]['conn']:
                try:
                    self.db[name]['conn'].close()
                except Exception:
                    pass

            self.db[name]['conn'] = anysql.connect_by_uri(self.config['general']["db_uri_%s" % name])

        if not self.db[name]['cursor']:
            self.db[name]['cursor'] = self.db[name]['conn'].cursor()

        return self.db[name]

    @staticmethod
    def get_column_name(column):
        return (".%s" % column).split('.', 2)[-1]

    def db_prepare_column(self, res, column = None):
        if column:
            prep_method = "_prepcol_%s" % self.get_column_name(column)
            if hasattr(self, prep_method):
                return getattr(self, prep_method)(column, res)

        if not isinstance(res, object) \
           or res is None \
           or isinstance(res, string_types):
            return res

        return "%s" % res

    def db_disconnect(self, name):
        if not self.db:
            self.db = {name: {'conn':   None,
                              'cursor': None}}

        if self.db[name]['cursor']:
            try:
                self.db[name]['cursor'].close()
            except Exception:
                pass

        self.db[name]['cursor'] = None

        if self.db[name]['conn']:
            try:
                self.db[name]['conn'].close()
            except Exception:
                pass

        self.db[name]['conn']   = None

        return self
