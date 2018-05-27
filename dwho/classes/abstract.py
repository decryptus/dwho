# -*- coding: utf-8 -*-
"""DWho abstract"""

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
import threading

from sonicprobe.libs import anysql


class DWhoAbstractDB(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.config = None
        self._db    = {}

    @property
    def db(self):
        thread_id = threading._get_ident()
        if thread_id not in self._db:
            self._db[thread_id] = {}

        return self._db[thread_id]

    @db.setter
    def db(self, value):
        thread_id = threading._get_ident()
        if thread_id not in self._db:
            self._db[thread_id] = {}

        self._db[thread_id] = value

    def db_connect(self, name):
        if not self.db:
            self.db = {name:
                        {'conn':    None,
                         'cursor':  None}}

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
           or isinstance(res, basestring):
            return res

        return "%s" % res

    def db_disconnect(self, name):
        if not self.db:
            self.db = {name:
                        {'conn':    None,
                         'cursor':  None}}

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
