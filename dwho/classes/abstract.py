# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.abstract"""

import abc

try:
    from threading import _get_ident as thread_get_ident
except ImportError:
    from threading import get_ident as thread_get_ident

import six

from sonicprobe.libs import anysql


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
           or isinstance(res, six.string_types):
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
