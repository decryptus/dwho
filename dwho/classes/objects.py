# -*- coding: utf-8 -*-
"""DWho object"""

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

from dwho.classes.abstract import DWhoAbstractDB

LOG             = logging.getLogger('dwho.objects')

class DWhoObjectSQLBase(DWhoAbstractDB):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def CONNECTION_NAME(self):
        return

    @abc.abstractproperty
    def TABLE_NAME(self):
        return

    @abc.abstractproperty
    def COLUMNS(self):
        return

    def __init__(self):
        self.config = None
        DWhoAbstractDB.__init__(self)

    def init(self, config):
        self.config = config

        if not self.db.has_key(self.CONNECTION_NAME):
            self.db[self.CONNECTION_NAME] = {'conn':    None,
                                             'cursor':  None}

        return self

    def connect(self):
        return self.db_connect(self.CONNECTION_NAME)

    @staticmethod
    def _prepare_condition(elements):
        if not isinstance(elements, dict):
            raise ValueError("Invalid elements for condition. (elements: %r)" % elements)

        q   = []
        v   = []

        for key, value in elements.iteritems():
            if isinstance(value, (list, tuple)):
                q.append(("%s IN(" + ", ".join(["?"] * len(value)) + ") ") % key)
                v.extend(value)
            else:
                if value is not None:
                    q.append("%s = ?" % key)
                    v.append(value)
                else:
                    q.append("%s IS NULL" % key)

        return (" AND ".join(q), v)

    @staticmethod
    def _prepare_cond_like(columns, value):
        if not isinstance(columns, (list, tuple)):
            raise ValueError("Invalid columns for LIKE condition. (columns: %r)" % columns)

        if not isinstance(value, basestring):
            raise ValueError("Invalid search value for LIKE condition. (value: %r)" % value)

        q   = []
        v   = []

        for column in columns:
            q.append("%s LIKE ?" % column)
            v.append("%" + value.replace('%', '\%').replace('_', '\_') + "%")

        return (" OR ".join(q), v)

    @staticmethod
    def _prepare_order(clause):
        if isinstance(clause, basestring):
            clause = ((clause, 'ASC'),)

        if not isinstance(clause, (list, tuple)):
            raise ValueError("Invalid clause type. (clause: %r)" % clause)

        return " ORDER BY " + ", ".join(["%s %s" % (k, v) for k, v in clause])

    @staticmethod
    def _prepare_limit(row_count):
        if not isinstance(row_count, (int, long)):
            raise ValueError("Invalid row_count type. (row_count: %r)" % row_count)

        return " LIMIT %d" % row_count

    @staticmethod
    def _prepare_offset(offset):
        if not isinstance(offset, (int, long)):
            raise ValueError("Invalid offset type. (offset: %r)" % offset)

        return " OFFSET %d" % offset

    @staticmethod
    def _validate_columns_values(columns, values):
        if not isinstance(columns, (list, tuple)):
            raise ValueError("Invalid columns type. (columns: %r)" % columns)

        if not isinstance(values, (list, tuple)):
            raise ValueError("Invalid values type. (values: %r)" % values)

        columns_len = len(columns)
        values_len  = len(values)

        if columns_len != values_len or columns_len == 0:
            raise ValueError("Invalid length between columns and values. (columns length: %r, values length: %r)"
                             % (columns_len, values_len))

        return columns_len

    @classmethod
    def get_columns(cls, *columns):
        if not columns:
            columns = cls.COLUMNS

        return ["%s.%s" % (cls.TABLE_NAME, c) for c in columns]

    def get(self, to_dict = False, order = None, columns = None, **conditions):
        db          = self.connect()
        db['conn'].commit()

        if not columns:
            columns = self.COLUMNS

        query       = "SELECT ${columns} FROM " + db['cursor'].escape(self.TABLE_NAME)
        cond_values = None

        if conditions:
            cond            = self._prepare_condition(conditions)
            query          += " WHERE " + cond[0]
            cond_values     = cond[1]

        if order:
            query          += self._prepare_order(order)

        query      += " LIMIT 1"

        db['cursor'].query(query,
                           columns,
                           cond_values)
        row         = db['cursor'].fetchone()

        if not row:
            return False

        if not to_dict:
            return row

        r           = {}

        for column in columns:
            r[column] = self.db_prepare_column(row[column], column)

        return r

    def get_count(self, column = None, **conditions):
        db          = self.connect()
        db['conn'].commit()

        if not column:
            column = '*'

        query       = "SELECT COUNT(" + column + ") FROM " + db['cursor'].escape(self.TABLE_NAME)
        cond_values = None

        if conditions:
            cond            = self._prepare_condition(conditions)
            query          += " WHERE " + cond[0]
            cond_values     = cond[1]

        query      += " LIMIT 1"

        db['cursor'].query(query,
                           None,
                           cond_values)
        res         = db['cursor'].fetchone()
        if not res:
            return 0

        return res[0]

    def get_all(self, to_dict = False, order = None, limit = None, offset = None, columns = None, **conditions):
        db          = self.connect()
        db['conn'].commit()

        if not columns:
            columns = self.COLUMNS

        query       = "SELECT ${columns} FROM " + db['cursor'].escape(self.TABLE_NAME)
        cond_values = None

        if conditions:
            cond            = self._prepare_condition(conditions)
            query          += " WHERE " + cond[0]
            cond_values     = cond[1]

        if order:
            query          += self._prepare_order(order)

        if limit:
            query          += self._prepare_limit(limit)

            if offset:
                query      += self._prepare_offset(offset)

        db['cursor'].query(query,
                           columns,
                           cond_values)
        res         = db['cursor'].fetchall()

        if not res:
            return False

        if not to_dict:
            return res

        r           = []

        for row in res:
            xobject = {}

            for column in columns:
                xobject[column] = self.db_prepare_column(row[column], column)

            r.append(xobject)

        return r

    def search(self, scolumns, svalue, to_dict = False, order = None, limit = None, offset = None, columns = None, **conditions):
        db          = self.connect()
        db['conn'].commit()

        if not columns:
            columns = self.COLUMNS

        query       = "SELECT ${columns} FROM " + db['cursor'].escape(self.TABLE_NAME)

        cond        = self._prepare_cond_like(scolumns, svalue)
        query      += " WHERE (" + cond[0] + ")"
        cond_values = cond[1]

        if conditions:
            cond            = self._prepare_condition(conditions)
            query          += " AND (" + cond[0] + ")"
            cond_values    += cond[1]

        if order:
            query          += self._prepare_order(order)

        if limit:
            query          += self._prepare_limit(limit)

            if offset:
                query      += self._prepare_offset(offset)

        db['cursor'].query(query,
                           columns,
                           cond_values)
        res         = db['cursor'].fetchall()

        if not res:
            return False

        if not to_dict:
            return res

        r           = []

        for row in res:
            xobject = {}

            for column in columns:
                xobject[column] = self.db_prepare_column(row[column], column)

            r.append(xobject)

        return r

    def exists(self, **conditions):
        db          = self.connect()
        db['conn'].commit()

        query       = "SELECT 1 FROM " + db['cursor'].escape(self.TABLE_NAME)
        cond_values = None

        if conditions:
            cond            = self._prepare_condition(conditions)
            query          += " WHERE " + cond[0]
            cond_values     = cond[1]

        query      += " LIMIT 1"
        db['cursor'].query(query,
                           None,
                           cond_values)

        res         = db['cursor'].fetchone()
        if not res:
            return False

        return True

    def create(self, columns, values):
        db          = self.connect()

        columns_len = self._validate_columns_values(columns, values)

        db['cursor'].query("INSERT INTO " + db['cursor'].escape(self.TABLE_NAME) + " "
                           "(${columns}) "
                           "VALUES (" + ", ".join(["?"] * columns_len) + ")",
                           columns,
                           values)
        db['conn'].commit()

        return db['cursor'].lastrowid

    def update(self, columns, values, **conditions):
        db          = self.connect()

        self._validate_columns_values(columns, values)

        query       = ("UPDATE " + db['cursor'].escape(self.TABLE_NAME) + " "
                       "SET " + ", ".join(["%s = ?" % x for x in columns]))
        cond_values = []

        if conditions:
            cond            = self._prepare_condition(conditions)
            query          += " WHERE " + cond[0]
            cond_values     = cond[1]

        db['cursor'].query(query,
                           None,
                           list(values) + cond_values)
        db['conn'].commit()

        return db['cursor'].rowcount

    def delete(self, **conditions):
        db          = self.connect()

        query       = "DELETE FROM " + db['cursor'].escape(self.TABLE_NAME)
        cond_values = None

        if conditions:
            cond            = self._prepare_condition(conditions)
            query          += " WHERE " + cond[0]
            cond_values     = cond[1]

        db['cursor'].query(query,
                           None,
                           cond_values)
        db['conn'].commit()

        return db['cursor'].rowcount
