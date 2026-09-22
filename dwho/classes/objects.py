# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.object"""

import abc
import logging
import re

from six import integer_types, iteritems, string_types

from dwho.classes.abstract import DWhoAbstractDB

LOG = logging.getLogger('dwho.objects')

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

        if self.CONNECTION_NAME not in self.db:
            self.db[self.CONNECTION_NAME] = {'conn':    None,
                                             'cursor':  None}

        return self

    def connect(self):
        return self.db_connect(self.CONNECTION_NAME)

    @staticmethod
    def _identifier(value):
        if not isinstance(value, string_types) or not re.match(
                r'^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z', value):
            raise ValueError('Expected an SQL column identifier')
        return value

    @classmethod
    def _prepare_condition(cls, elements):
        if not isinstance(elements, dict):
            raise ValueError("Invalid elements for condition. (elements: %r)" % elements)

        q   = []
        v   = []

        for key, value in iteritems(elements):
            cls._identifier(key)
            if isinstance(value, (list, tuple)):
                if not value:
                    q.append('1 = 0')
                    continue
                q.append(("%s IN(" + ", ".join(["?"] * len(value)) + ") ") % key)
                v.extend(value)
            else:
                if value is not None:
                    q.append("%s = ?" % key)
                    v.append(value)
                else:
                    q.append("%s IS NULL" % key)

        return (" AND ".join(q), v)

    @classmethod
    def _prepare_cond_like(cls, columns, value):
        if not isinstance(columns, (list, tuple)):
            raise ValueError("Invalid columns for LIKE condition. (columns: %r)" % columns)

        if not isinstance(value, string_types):
            raise ValueError("Invalid search value for LIKE condition. (value: %r)" % value)

        q   = []
        v   = []

        for column in columns:
            cls._identifier(column)
            q.append("%s LIKE ?" % column)
            v.append("%" + value.replace('%', r'\%').replace('_', r'\_') + "%")

        return (" OR ".join(q), v)

    @classmethod
    def _prepare_order(cls, clause):
        if isinstance(clause, string_types):
            clause = ((clause, 'ASC'),)

        if not isinstance(clause, (list, tuple)):
            raise ValueError("Invalid clause type. (clause: %r)" % clause)

        parts = []
        for key, direction in clause:
            cls._identifier(key)
            if not isinstance(direction, string_types) or direction.upper() not in ('ASC', 'DESC'):
                raise ValueError('SQL sort direction must be ASC or DESC')
            parts.append('%s %s' % (key, direction.upper()))
        return ' ORDER BY ' + ', '.join(parts)

    @staticmethod
    def _prepare_limit(row_count):
        if isinstance(row_count, bool) or not isinstance(row_count, integer_types) or row_count < 0:
            raise ValueError("Invalid row_count type. (row_count: %r)" % row_count)

        return " LIMIT %d" % row_count

    @staticmethod
    def _prepare_offset(offset):
        if isinstance(offset, bool) or not isinstance(offset, integer_types) or offset < 0:
            raise ValueError("Invalid offset type. (offset: %r)" % offset)

        return " OFFSET %d" % offset

    @classmethod
    def _validate_columns_values(cls, columns, values):
        if not isinstance(columns, (list, tuple)):
            raise ValueError("Invalid columns type. (columns: %r)" % columns)

        if not isinstance(values, (list, tuple)):
            raise ValueError("Invalid values type. (values: %r)" % values)

        columns_len = len(columns)
        values_len  = len(values)

        if columns_len != values_len or columns_len == 0:
            raise ValueError("Invalid length between columns and values. (columns length: %r, values length: %r)"
                             % (columns_len, values_len))

        for column in columns:
            cls._identifier(column)
        return columns_len

    @classmethod
    def get_columns(cls, *columns):
        if not columns:
            columns = cls.COLUMNS

        return ["%s.%s" % (cls.TABLE_NAME, c) for c in columns]

    def get(self, to_dict = False, order = None, columns = None, **conditions):
        db = self.connect()

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
        db = self.connect()

        if not column:
            column = '*'

        if column != '*':
            self._identifier(column)
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
        db = self.connect()

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

        if limit is not None:
            query          += self._prepare_limit(limit)

            if offset is not None:
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
        db = self.connect()

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

        if limit is not None:
            query          += self._prepare_limit(limit)

            if offset is not None:
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
        db = self.connect()

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
