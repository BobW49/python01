#!python3
# vi:nu:et:sts=4 ts=4 sw=4

""" Test rw_field_defn.py

This module tests the rw_field_defn.py classes:
    Field_Defn, Field_Defns
plus helpers: dict_to_dataclass, set_flags.

Execute from the directory that contains rw_field_defn.py:

    python3 rw_field_defn_test.py
    python3 -m unittest rw_field_defn_test -v
"""

"""
    This is free and unencumbered software released into the public domain.

    Anyone is free to copy, modify, publish, use, compile, sell, or
    distribute this software, either in source code form or as a compiled
    binary, for any purpose, commercial or non-commercial, and by any
    means.

    In jurisdictions that recognize copyright laws, the author or authors
    of this software dedicate any and all copyright interest in the
    software to the public domain. We make this dedication for the benefit
    of the public at large and to the detriment of our heirs and
    successors. We intend this dedication to be an overt act of
    relinquishment in perpetuity of all present and future rights to this
    software under copyright law.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
    OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
    OR OTHER DEALINGS IN THE SOFTWARE.

    For more information, please refer to <http://unlicense.org/>
"""

import os
import sys
import unittest

from rw_field_defn import (
    SQL_Format, Data_Type, Field_Defn, Field_Defns,
    dict_to_dataclass, set_flags
)


# ---------------------------------------------------------------------------
# Sample field-definition fixtures
# ---------------------------------------------------------------------------

# Single autoincrement PK + common column types (SQLite-oriented ledger)
LEDGER_FIELDS = [
    {'name': 'id',       'type': Data_Type.INTEGER,  'key': True, 'auto': True, 'null': False},
    {'name': 'date',     'type': Data_Type.DATE},
    {'name': 'typ',      'type': Data_Type.CHAR,     'length': 2,  'default': ''},
    {'name': 'cat',      'type': Data_Type.VARCHAR,  'length': 16, 'default': ''},
    {'name': 'merch_id', 'type': Data_Type.BIGINT,   'default': '0'},
    {'name': 'desc',     'type': Data_Type.TEXT,     'default': ''},
    {'name': 'amt',      'type': Data_Type.MONEY64,  'default': '0'},
]

# Composite PK with explicit positions 1, 2
COMPOSITE_PK_FIELDS = [
    {'name': 'tenant_id', 'type': Data_Type.INTEGER, 'key': ('ASC', 1), 'null': False},
    {'name': 'sku',       'type': Data_Type.VARCHAR, 'length': 32, 'key': ('ASC', 2), 'null': False},
    {'name': 'qty',       'type': Data_Type.INTEGER, 'default': '0'},
    {'name': 'note',      'type': Data_Type.TEXT},
]

# Composite PK using definition order (all positions 0 / True)
DEFN_ORDER_PK_FIELDS = [
    {'name': 'a', 'type': Data_Type.INTEGER, 'key': ('DESC', 0), 'null': False},
    {'name': 'b', 'type': Data_Type.INTEGER, 'key': True,        'null': False},  # → ('ASC', 0)
    {'name': 'c', 'type': Data_Type.TEXT},
]

# Mixed / invalid PK positions (for error tests)
MIXED_PK_FIELDS = [
    {'name': 'a', 'type': Data_Type.INTEGER, 'key': ('ASC', 0)},
    {'name': 'b', 'type': Data_Type.INTEGER, 'key': ('ASC', 1)},
]

DUP_PK_FIELDS = [
    {'name': 'a', 'type': Data_Type.INTEGER, 'key': ('ASC', 1)},
    {'name': 'b', 'type': Data_Type.INTEGER, 'key': ('ASC', 1)},
]

GAP_PK_FIELDS = [
    {'name': 'a', 'type': Data_Type.INTEGER, 'key': ('ASC', 1)},
    {'name': 'b', 'type': Data_Type.INTEGER, 'key': ('ASC', 3)},
]


# ===========================================================================
# Field_Defn — construction & properties
# ===========================================================================

class Test_Field_Defn_Basic(unittest.TestCase):

    def test_empty(self):
        f = Field_Defn()
        self.assertEqual(f.name, '')
        self.assertEqual(f.type, Data_Type.UNKNOWN)
        self.assertIsNone(f.key)
        self.assertTrue(f.nullable)          # default null=True
        self.assertFalse(f.auto)
        self.assertFalse(f.unique)
        self.assertIsNone(f.default)
        self.assertIsNone(f.seqno)

    def test_from_dict_core(self):
        f = Field_Defn({
            'name': 'amt',
            'desc1': 'Amount',
            'desc2': 'cents',
            'type': Data_Type.MONEY64,
            'null': False,
            'default': '0',
            'seqno': 7,
        })
        self.assertEqual(f.name, 'amt')
        self.assertEqual(f.desc1, 'Amount')
        self.assertEqual(f.desc2, 'cents')
        self.assertEqual(f.type, Data_Type.MONEY64)
        self.assertFalse(f.nullable)
        self.assertEqual(f.default, '0')
        self.assertEqual(f.seqno, 7)

    def test_repr_str(self):
        f = Field_Defn({'name': 'id', 'type': Data_Type.INTEGER})
        self.assertIn('id', repr(f))
        self.assertIn('id', str(f))

    def test_auto_unique(self):
        f = Field_Defn({'name': 'id', 'type': Data_Type.INTEGER, 'auto': True, 'unique': True})
        self.assertTrue(f.auto)
        self.assertTrue(f.unique)


# ===========================================================================
# Field_Defn — key setter
# ===========================================================================

class Test_Field_Defn_Key(unittest.TestCase):

    def test_key_true(self):
        f = Field_Defn({'name': 'id', 'type': Data_Type.INTEGER, 'key': True})
        self.assertEqual(f.key, ('ASC', 0))

    def test_key_tuple_asc(self):
        f = Field_Defn({'name': 'a', 'type': Data_Type.INTEGER, 'key': ('ASC', 1)})
        self.assertEqual(f.key, ('ASC', 1))

    def test_key_tuple_desc(self):
        f = Field_Defn({'name': 'a', 'type': Data_Type.INTEGER, 'key': ('DESC', 2)})
        self.assertEqual(f.key, ('DESC', 2))

    def test_key_list(self):
        f = Field_Defn({'name': 'a', 'type': Data_Type.INTEGER, 'key': ['ASC', 3]})
        self.assertEqual(f.key, ('ASC', 3))

    def test_key_ordering_only(self):
        f = Field_Defn({'name': 'a', 'type': Data_Type.INTEGER, 'key': ('DESC',)})
        self.assertEqual(f.key, ('DESC', 0))

    def test_key_empty_tuple(self):
        f = Field_Defn({'name': 'a', 'type': Data_Type.INTEGER})
        f.key = ()
        self.assertEqual(f.key, ('ASC', 0))

    def test_key_invalid_ordering(self):
        with self.assertRaises(ValueError):
            Field_Defn({'name': 'a', 'type': Data_Type.INTEGER, 'key': ('UP', 1)})

    def test_key_invalid_type(self):
        f = Field_Defn({'name': 'a', 'type': Data_Type.INTEGER})
        with self.assertRaises(TypeError):
            f.key = 42

    def test_key_assign_after(self):
        f = Field_Defn({'name': 'a', 'type': Data_Type.INTEGER})
        self.assertIsNone(f.key)
        f.key = True
        self.assertEqual(f.key, ('ASC', 0))
        f.key = ('DESC', 2)
        self.assertEqual(f.key, ('DESC', 2))


# ===========================================================================
# Field_Defn — to_sql_create (per-column fragment)
# ===========================================================================

class Test_Field_Defn_ToSqlCreate(unittest.TestCase):

    def test_sqlite_integer_pk_auto(self):
        sql = Field_Defn({
            'name': 'id', 'type': Data_Type.INTEGER, 'key': True, 'auto': True, 'null': False,
        }).to_sql_create(SQL_Format.SQLITE, True)
        self.assertIn('`id`', sql)
        self.assertIn('INTEGER', sql)
        self.assertIn('PRIMARY KEY', sql)
        self.assertIn('AUTOINCREMENT', sql)
        self.assertIn('NOT NULL', sql)
        self.assertTrue(sql.endswith(',\n'))

        sql = Field_Defn({
            'name': 'id', 'type': Data_Type.INTEGER, 'key': True, 'auto': True, 'null': False,
        }).to_sql_create(SQL_Format.SQLITE, False)
        self.assertIn('`id`', sql)
        self.assertIn('INTEGER', sql)
        self.assertNotIn('PRIMARY KEY', sql)
        self.assertNotIn('AUTOINCREMENT', sql)
        self.assertIn('NOT NULL', sql)
        self.assertTrue(sql.endswith(',\n'))

    def test_sqlite_text_types(self):
        for dt in (
            Data_Type.VARCHAR,
            Data_Type.TEXT,
            Data_Type.CHAR,
            Data_Type.DATE,
            Data_Type.DATETIME,
        ):
            sql = Field_Defn({'name': 'x', 'type': dt, 'length': 10}).to_sql_create(SQL_Format.SQLITE)
            self.assertIn('TEXT', sql, msg=f'failed for {dt}')

    def test_sqlite_money_bigint_bool(self):
        self.assertIn('INTEGER', Field_Defn({'name': 'a', 'type': Data_Type.MONEY64}).to_sql_create(SQL_Format.SQLITE))
        self.assertIn('INTEGER', Field_Defn({'name': 'a', 'type': Data_Type.BIGINT}).to_sql_create(SQL_Format.SQLITE))
        self.assertIn('INTEGER', Field_Defn({'name': 'a', 'type': Data_Type.BOOL}).to_sql_create(SQL_Format.SQLITE))
        self.assertIn('INTEGER', Field_Defn({'name': 'a', 'type': Data_Type.SMALLINT}).to_sql_create(SQL_Format.SQLITE))
        self.assertIn('FLOAT',   Field_Defn({'name': 'a', 'type': Data_Type.REAL}).to_sql_create(SQL_Format.SQLITE))
        self.assertIn('BLOB',    Field_Defn({'name': 'a', 'type': Data_Type.BLOB}).to_sql_create(SQL_Format.SQLITE))

    def test_sqlite_default_and_check(self):
        sql = Field_Defn({
            'name': 'typ', 'type': Data_Type.CHAR, 'length': 2,
            'default': '', 'check': "typ IN ('A','B')",
        }).to_sql_create(SQL_Format.SQLITE)
        self.assertIn("DEFAULT( '' )", sql)
        self.assertIn("CHECK( typ IN ('A','B') )", sql)

    def test_sqlite_unique(self):
        sql = Field_Defn({
            'name': 'email', 'type': Data_Type.VARCHAR, 'length': 80, 'unique': True,
        }).to_sql_create(SQL_Format.SQLITE)
        self.assertIn('UNIQUE', sql)

    def test_sqlite_nullable_true_no_not_null(self):
        sql = Field_Defn({'name': 'x', 'type': Data_Type.INTEGER, 'null': True}).to_sql_create(SQL_Format.SQLITE)
        self.assertNotIn('NOT NULL', sql)

    def test_sqlite_nullable_false_has_not_null(self):
        sql = Field_Defn({'name': 'x', 'type': Data_Type.INTEGER, 'null': False}).to_sql_create(SQL_Format.SQLITE)
        self.assertIn('NOT NULL', sql)

    def test_postgre_types(self):
        cases = [
            (Data_Type.BIGINT,   'BIGINT'),
            (Data_Type.MONEY64,  'DECIMAL(18,4)'),
            (Data_Type.SMALLINT, 'SMALLINT'),
            (Data_Type.TINYINT,  'TINYINT'),
            (Data_Type.INTEGER,  'INTEGER'),
            (Data_Type.BOOL,     'BOOLEAN'),
            (Data_Type.REAL,     'REAL'),
            (Data_Type.DATE,     'DATE'),
            (Data_Type.DATETIME, 'DATETIME'),
            (Data_Type.BLOB,     'BLOB'),
        ]
        for dt, expected in cases:
            sql = Field_Defn({
                'name': 'x', 'type': dt, 'length': 10, 'prec': 10, 'scale': 2,
            }).to_sql_create(SQL_Format.POSTGRE)
            self.assertIn(expected, sql, msg=f'POSTGRE {dt}')

    def test_postgre_varchar_char_decimal(self):
        sql = Field_Defn({'name': 'v', 'type': Data_Type.VARCHAR, 'length': 32}).to_sql_create(SQL_Format.POSTGRE)
        self.assertIn('VARCHAR(32)', sql)
        sql = Field_Defn({'name': 'c', 'type': Data_Type.CHAR, 'length': 2}).to_sql_create(SQL_Format.POSTGRE)
        self.assertIn('CHAR(2)', sql)
        sql = Field_Defn({
            'name': 'd', 'type': Data_Type.DECIMAL, 'prec': 12, 'scale': 4,
        }).to_sql_create(SQL_Format.POSTGRE)
        self.assertIn('DECIMAL(12,4)', sql)

    def test_mysql_datetime_is_timestamp(self):
        sql = Field_Defn({'name': 'ts', 'type': Data_Type.DATETIME}).to_sql_create(SQL_Format.MYSQL)
        self.assertIn('TIMESTAMP', sql)

    def test_mysql_no_backticks_on_name(self):
        sql = Field_Defn({'name': 'id', 'type': Data_Type.INTEGER}).to_sql_create(SQL_Format.MYSQL)
        self.assertNotIn('`id`', sql)
        self.assertIn('\tid', sql)

    def test_invalid_type_raises(self):
        f = Field_Defn({'name': 'x', 'type': Data_Type.UNKNOWN})
        with self.assertRaises(ValueError):
            f.to_sql_create(SQL_Format.SQLITE)

    def test_other_clause(self):
        sql = Field_Defn({
            'name': 'parent_id', 'type': Data_Type.INTEGER,
            'other': 'REFERENCES parents(id)',
        }).to_sql_create(SQL_Format.SQLITE)
        self.assertIn('REFERENCES parents(id)', sql)


# ===========================================================================
# Field_Defn — to_dc
# ===========================================================================

class Test_Field_Defn_ToDc(unittest.TestCase):

    def test_empty_name_returns_empty(self):
        self.assertEqual(Field_Defn().to_dc(), [])

    def test_int_types(self):
        for dt in (
            Data_Type.INTEGER, Data_Type.BIGINT, Data_Type.SMALLINT,
            Data_Type.TINYINT, Data_Type.MONEY64,
        ):
            spec = Field_Defn({'name': 'n', 'type': dt}).to_dc()
            self.assertEqual(spec[0], 'n')
            self.assertIs(spec[1], int)          # real type, not the string 'int'

    def test_bool_float_str_bytes(self):
        self.assertIs(Field_Defn({'name': 'b', 'type': Data_Type.BOOL}).to_dc()[1], bool)
        self.assertIs(Field_Defn({'name': 'r', 'type': Data_Type.REAL}).to_dc()[1], float)
        self.assertIs(Field_Defn({'name': 'd', 'type': Data_Type.DECIMAL}).to_dc()[1], float)
        self.assertIs(Field_Defn({'name': 's', 'type': Data_Type.TEXT}).to_dc()[1], str)
        self.assertIs(
            Field_Defn({'name': 's', 'type': Data_Type.VARCHAR, 'length': 10}).to_dc()[1], str
        )
        self.assertIs(Field_Defn({'name': 's', 'type': Data_Type.DATE}).to_dc()[1], str)
        self.assertIs(Field_Defn({'name': 'x', 'type': Data_Type.BLOB}).to_dc()[1], bytes)


# ===========================================================================
# Field_Defns — list behaviour
# ===========================================================================

class Test_Field_Defns_List(unittest.TestCase):

    def test_init_empty(self):
        fds = Field_Defns()
        self.assertEqual(len(fds), 0)

    def test_init_from_dicts(self):
        fds = Field_Defns(LEDGER_FIELDS)
        self.assertEqual(len(fds), len(LEDGER_FIELDS))
        self.assertIsInstance(fds[0], Field_Defn)
        self.assertEqual(fds[0].name, 'id')

    def test_init_from_field_defns(self):
        items = [Field_Defn(d) for d in LEDGER_FIELDS]
        fds = Field_Defns(items)
        self.assertEqual(len(fds), len(items))
        self.assertIs(fds[0], items[0])

    def test_init_bad_type_raises(self):
        with self.assertRaises(TypeError):
            Field_Defns([42])

    def test_append_dict_and_obj(self):
        fds = Field_Defns()
        fds.append({'name': 'a', 'type': Data_Type.INTEGER})
        fds.append(Field_Defn({'name': 'b', 'type': Data_Type.TEXT}))
        self.assertEqual(len(fds), 2)
        self.assertEqual(fds[0].name, 'a')
        self.assertEqual(fds[1].name, 'b')

    def test_extend(self):
        fds = Field_Defns([{'name': 'a', 'type': Data_Type.INTEGER}])
        fds.extend([
            {'name': 'b', 'type': Data_Type.TEXT},
            Field_Defn({'name': 'c', 'type': Data_Type.BOOL}),
        ])
        self.assertEqual([f.name for f in fds], ['a', 'b', 'c'])

    def test_find_name(self):
        fds = Field_Defns(LEDGER_FIELDS)
        self.assertIsNotNone(fds.find_name('amt'))
        self.assertEqual(fds.find_name('amt').type, Data_Type.MONEY64)
        self.assertIsNone(fds.find_name('nope'))


# ===========================================================================
# Field_Defns — to_sql_create (full CREATE TABLE)
# ===========================================================================

class Test_Field_Defns_ToSqlCreate(unittest.TestCase):

    def test_sqlite_ledger_smoke(self):
        fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_create('ledger')
        self.assertIn('DROP TABLE IF EXISTS `ledger`', sql)
        self.assertIn('CREATE TABLE IF NOT EXISTS `ledger`', sql)
        self.assertIn('`id`', sql)
        self.assertIn('PRIMARY KEY', sql)
        self.assertIn('AUTOINCREMENT', sql)
        self.assertIn('NOT NULL', sql)
        self.assertTrue(sql.rstrip().endswith(');'))

    def test_sqlite_with_other(self):
        fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_create('ledger', other='\tOTHER_DATA\n')
        self.assertIn('OTHER_DATA', sql)

    def test_postgre_no_backticks(self):
        fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.POSTGRE)
        sql = fds.to_sql_create('ledger')
        self.assertIn('DROP TABLE IF EXISTS ledger', sql)
        self.assertNotIn('`ledger`', sql)

    def test_composite_pk_explicit_positions(self):
        fds = Field_Defns(COMPOSITE_PK_FIELDS, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_create('inventory')
        self.assertIn('PRIMARY KEY(`tenant_id` ASC, `sku` ASC)', sql)

    def test_composite_pk_definition_order(self):
        fds = Field_Defns(DEFN_ORDER_PK_FIELDS, frmt=SQL_Format.POSTGRE)
        sql = fds.to_sql_create('t')
        self.assertIn('PRIMARY KEY(a DESC, b ASC)', sql)

    def test_pk_position_order_not_defn_order(self):
        fields = [
            {'name': 'a', 'type': Data_Type.INTEGER, 'key': ('ASC', 2)},
            {'name': 'b', 'type': Data_Type.INTEGER, 'key': ('DESC', 1)},
            {'name': 'c', 'type': Data_Type.TEXT},
        ]
        fds = Field_Defns(fields, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_create('t')
        self.assertIn('PRIMARY KEY(`b` DESC, `a` ASC)', sql)

    def test_mixed_zero_and_nonzero_raises(self):
        with self.assertRaises(ValueError) as cm:
            Field_Defns(MIXED_PK_FIELDS, frmt=SQL_Format.SQLITE).to_sql_create('bad')
        self.assertIn('position 0', str(cm.exception))

    def test_duplicate_positions_raises(self):
        with self.assertRaises(ValueError) as cm:
            Field_Defns(DUP_PK_FIELDS, frmt=SQL_Format.SQLITE).to_sql_create('bad')
        self.assertIn('contiguous', str(cm.exception).lower())

    def test_gap_positions_raises(self):
        with self.assertRaises(ValueError):
            Field_Defns(GAP_PK_FIELDS, frmt=SQL_Format.SQLITE).to_sql_create('bad')

    def test_no_pk(self):
        fields = [
            {'name': 'x', 'type': Data_Type.INTEGER},
            {'name': 'y', 'type': Data_Type.TEXT},
        ]
        fds = Field_Defns(fields, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_create('nopk')
        self.assertNotIn('PRIMARY KEY', sql)
        self.assertIn('`x`', sql)
        self.assertIn('`y`', sql)


# ===========================================================================
# Field_Defns — to_sql_insert
# ===========================================================================

class Test_Field_Defns_ToSqlInsert(unittest.TestCase):

    def test_sqlite_skips_auto_pk(self):
        fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_insert('ledger')
        self.assertTrue(sql.startswith('INSERT INTO `ledger`'))
        self.assertNotIn('`id`', sql)          # autoincrement PK omitted
        for col in ('date', 'typ', 'cat', 'merch_id', 'desc', 'amt'):
            self.assertIn(f'`{col}`', sql)
        self.assertEqual(sql.count('?'), 6)
        self.assertIn('VALUES', sql)

    def test_sqlite_exact(self):
        fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_insert('ledger')
        expected = (
            "INSERT INTO `ledger` ( `date`, `typ`, `cat`, `merch_id`, `desc`, `amt` )\n"
            "\tVALUES ( ?, ?, ?, ?, ?, ? );\n"
        )
        self.assertEqual(sql, expected)

    def test_composite_no_auto_includes_keys(self):
        fds = Field_Defns(COMPOSITE_PK_FIELDS, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_insert('inventory')
        self.assertIn('`tenant_id`', sql)
        self.assertIn('`sku`', sql)
        self.assertIn('`qty`', sql)
        self.assertIn('`note`', sql)
        self.assertEqual(sql.count('?'), 4)

    def test_postgre_no_backticks(self):
        fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.POSTGRE)
        sql = fds.to_sql_insert('ledger')
        self.assertTrue(sql.startswith('INSERT INTO ledger'))
        self.assertNotIn('`', sql)


# ===========================================================================
# Field_Defns — to_sql_update
# ===========================================================================

class Test_Field_Defns_ToSqlUpdate(unittest.TestCase):

    def test_sqlite_single_pk(self):
        fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_update('ledger')
        self.assertTrue(sql.startswith('UPDATE `ledger` SET'))
        self.assertIn('WHERE `id`=?', sql)
        self.assertNotIn('`id`=?', sql.split('WHERE')[0])  # id not in SET
        for col in ('date', 'typ', 'cat', 'merch_id', 'desc', 'amt'):
            self.assertIn(f'`{col}`=?', sql)

    def test_sqlite_exact_single_pk(self):
        fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_update('ledger')
        self.assertIn('`date`=?', sql)
        self.assertIn('`amt`=?', sql)
        self.assertTrue(sql.rstrip().endswith('WHERE `id`=?;'))

    def test_composite_pk_where(self):
        fds = Field_Defns(COMPOSITE_PK_FIELDS, frmt=SQL_Format.SQLITE)
        sql = fds.to_sql_update('inventory')
        self.assertIn('WHERE `tenant_id`=? AND `sku`=?', sql)
        self.assertIn('`qty`=?', sql)
        self.assertIn('`note`=?', sql)
        set_clause = sql.split('WHERE')[0]
        self.assertNotIn('`tenant_id`=?', set_clause)
        self.assertNotIn('`sku`=?', set_clause)

    def test_postgre_no_backticks(self):
        fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.POSTGRE)
        sql = fds.to_sql_update('ledger')
        self.assertTrue(sql.startswith('UPDATE ledger SET'))
        self.assertNotIn('`', sql)
        self.assertIn('WHERE id=?', sql)

    def test_no_non_key_raises(self):
        fields = [
            {'name': 'id', 'type': Data_Type.INTEGER, 'key': True},
        ]
        with self.assertRaises(ValueError) as cm:
            Field_Defns(fields, frmt=SQL_Format.SQLITE).to_sql_update('t')
        self.assertIn('non-key', str(cm.exception))

    def test_no_pk_raises(self):
        fields = [
            {'name': 'x', 'type': Data_Type.INTEGER},
            {'name': 'y', 'type': Data_Type.TEXT},
        ]
        with self.assertRaises(ValueError) as cm:
            Field_Defns(fields, frmt=SQL_Format.SQLITE).to_sql_update('t')
        self.assertIn('primary-key', str(cm.exception).lower())


# ===========================================================================
# Field_Defns — to_dc
# ===========================================================================

class Test_Field_Defns_DataClass(unittest.TestCase):

    def test_to_dc_list(self):
        fds = Field_Defns(LEDGER_FIELDS)
        specs = fds.to_dc()
        self.assertEqual(len(specs), len(LEDGER_FIELDS))
        names = [s[0] for s in specs]
        self.assertEqual(names[0], 'id')
        self.assertIn('amt', names)


# ===========================================================================
# dict_to_dataclass helper
# ===========================================================================

class Test_DictToDataClass(unittest.TestCase):

    def test_filters_extra_keys(self):
        from dataclasses import dataclass

        @dataclass
        class Sample:
            a: int = 0
            b: str = ''

        obj = dict_to_dataclass(Sample, {'a': 1, 'b': 'x', 'extra': 99})
        self.assertEqual(obj.a, 1)
        self.assertEqual(obj.b, 'x')
        self.assertFalse(hasattr(obj, 'extra'))


# ===========================================================================
# Integration-style: full round-trip shapes
# ===========================================================================

class Test_Integration(unittest.TestCase):
    """End-to-end SQL shape checks against the ledger fixture."""

    def setUp(self):
        self.fds = Field_Defns(LEDGER_FIELDS, frmt=SQL_Format.SQLITE)

    def test_create_insert_update_column_sets_align(self):
        create_sql = self.fds.to_sql_create('ledger')
        insert_sql = self.fds.to_sql_insert('ledger')
        update_sql = self.fds.to_sql_update('ledger')

        for name in ('date', 'typ', 'cat', 'merch_id', 'desc', 'amt'):
            self.assertIn(f'`{name}`', insert_sql)
            self.assertIn(f'`{name}`=?', update_sql)

        self.assertIn('PRIMARY KEY', create_sql)
        self.assertIn('AUTOINCREMENT', create_sql)
        self.assertNotIn('`id`', insert_sql)
        self.assertIn('WHERE `id`=?', update_sql)

    def test_column_fragments_embedded_in_create(self):
        create = self.fds.to_sql_create('ledger')
        for fd in self.fds:
            frag = fd.to_sql_create(SQL_Format.SQLITE, True).rstrip(',\n')
            self.assertIn(frag.strip(), create)


class Test_GenerateDataClass(unittest.TestCase):
    def test_basic(self):
        fds = Field_Defns([
            {'name': 'id',   'type': Data_Type.INTEGER, 'key': True, 'auto': True},
            {'name': 'addr', 'type': Data_Type.VARCHAR, 'length': 100, 'default': ''},
            {'name': 'beds', 'type': Data_Type.SMALLINT, 'default': '3'},
        ])
        Cls = fds.generate_dataclass('Property')
        self.assertEqual(Cls.__name__, 'Property')
        inst = Cls(addr='123 Main')
        self.assertEqual(inst.addr, '123 Main')
        self.assertEqual(inst.beds, 3)
        self.assertEqual(inst.id, 0)





################################################################################
#                           Command-line interface
################################################################################

if __name__ == '__main__':
    unittest.main()
