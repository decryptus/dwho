import unittest
from dwho.classes.objects import DWhoObjectSQLBase as SQL

class SQLTests(unittest.TestCase):
    def test_values_are_bound_and_empty_list_matches_nothing(self):
        query, values = SQL._prepare_condition({'name': "x' OR 1=1 --"})
        self.assertEqual(query, 'name = ?')
        self.assertEqual(values, ["x' OR 1=1 --"])
        self.assertEqual(SQL._prepare_condition({'id': []}), ('1 = 0', []))

    def test_rejects_sql_fragments_in_identifiers_and_order(self):
        for identifier in ('name; DROP TABLE test', 'id OR 1=1', 'id\n'):
            with self.assertRaises(ValueError):
                SQL._prepare_condition({identifier: 1})
            with self.assertRaises(ValueError):
                SQL._prepare_cond_like([identifier], 'value')
            with self.assertRaises(ValueError):
                SQL._validate_columns_values([identifier], [1])
        with self.assertRaises(ValueError):
            SQL._prepare_order([('name', 'DESC; DROP TABLE test')])
        self.assertEqual(SQL._prepare_order([('table.name', 'desc')]), ' ORDER BY table.name DESC')

    def test_limit_and_offset(self):
        self.assertEqual(SQL._prepare_limit(0), ' LIMIT 0')
        for value in (-1, True, '1'):
            with self.assertRaises(ValueError):
                SQL._prepare_limit(value)
            with self.assertRaises(ValueError):
                SQL._prepare_offset(value)
