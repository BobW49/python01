#!/usr/bin/env python3
# vi:nu:et:sts=4 ts=4 sw=4

""" Tests for rw_sqlite.py (Database, Table, Row)

Uses in-memory SQLite databases exclusively — no on-disk test files.

Run from the directory that contains rw_sqlite.py / rw_database.py /
rw_field_defn.py:

    python3 rw_sqlite_test.py
    python3 -m unittest rw_sqlite_test -v
"""


"""
    This is free and unencumbered software released into the public domain.

    Anyone is free to copy, modify, publish, use, compile, sell, or
    distribute this software, either in source code form or as a compiled
    binary, for any purpose, commercial or non-commercial, and by any
    means.

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
import pathlib
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath('.'))

from rw_field_defn import SQL_Format, Data_Type, Field_Defns
from rw_sqlite import Database, Table, Row, set_flags, is_debug, is_test


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Ledger-style: single autoincrement integer PK
LEDGER_FIELDS = [
    {'name': 'id',    'type': Data_Type.INTEGER, 'key': True, 'auto': True, 'null': False},
    {'name': 'date',  'type': Data_Type.DATE},
    {'name': 'typ',   'type': Data_Type.TEXT,    'default': ''},
    {'name': 'cat',   'type': Data_Type.TEXT,    'default': ''},
    {'name': 'merch', 'type': Data_Type.TEXT,    'default': ''},
    {'name': 'desc',  'type': Data_Type.TEXT,    'default': ''},
    {'name': 'amt',   'type': Data_Type.MONEY64, 'default': '0'},
]

LEDGER_TABLE_DEFN = {
    'name': 'items',
    'dataclass': 'Item',
    'field_defns': LEDGER_FIELDS,
}

# Composite PK (no autoincrement)
INVENTORY_FIELDS = [
    {'name': 'tenant_id', 'type': Data_Type.INTEGER, 'key': ('ASC', 1), 'null': False},
    {'name': 'sku',       'type': Data_Type.VARCHAR, 'length': 32,
     'key': ('ASC', 2), 'null': False},
    {'name': 'qty',       'type': Data_Type.INTEGER, 'default': '0'},
    {'name': 'note',      'type': Data_Type.TEXT},
]


def _mem_db() -> Database:
    """Fresh connected in-memory Database."""
    db = Database(':memory:')
    db.connect()
    return db


def _ledger_table(db: Database) -> Table:
    t = Table(db, name='items', field_defns=LEDGER_FIELDS)
    t.create()
    return t


def _inventory_table(db: Database) -> Table:
    t = Table(db, name='inventory', field_defns=INVENTORY_FIELDS)
    t.create()
    return t


# ===========================================================================
# Flags
# ===========================================================================

class Test_Flags(unittest.TestCase):

    def test_set_and_read(self):
        set_flags(True, True)
        self.assertTrue(is_debug())
        self.assertTrue(is_test())
        set_flags(False, False)
        self.assertFalse(is_debug())
        self.assertFalse(is_test())


# ===========================================================================
# Database — connection / lifecycle
# ===========================================================================

class Test_Database_Connection(unittest.TestCase):

    def test_memory_connect_disconnect(self):
        db = Database(':memory:')
        self.assertIsNone(db.conn)
        conn = db.connect()
        self.assertIsNotNone(conn)
        self.assertIs(db.conn, conn)
        self.assertEqual(db._frmt, SQL_Format.SQLITE)
        db.disconnect()
        self.assertIsNone(db.conn)

    def test_double_connect_raises(self):
        db = _mem_db()
        with self.assertRaises(ValueError):
            db.connect()
        db.disconnect()

    def test_context_manager(self):
        db = Database(':memory:')
        with db:
            self.assertIsNotNone(db.conn)
        self.assertIsNone(db.conn)

    def test_commit_safe(self):
        db = _mem_db()
        db.commit()  # no-op / no raise
        db.disconnect()

    def test_execute_simple(self):
        db = _mem_db()
        cur = db.execute('SELECT 1 AS n')
        row = cur.fetchone()
        cur.close()
        self.assertEqual(row[0], 1)
        db.disconnect()

    def test_execute_params(self):
        db = _mem_db()
        cur = db.execute('SELECT ? AS n', (42,))
        self.assertEqual(cur.fetchone()[0], 42)
        cur.close()
        db.disconnect()

    def test_delete_file(self):
        fd, path = tempfile.mkstemp(suffix='.sqlite')
        os.close(fd)
        try:
            db = Database(path)
            db.connect()
            db.disconnect()
            self.assertTrue(os.path.isfile(path))
            db.delete()
            self.assertFalse(os.path.isfile(path))
        finally:
            if os.path.isfile(path):
                os.unlink(path)


# ===========================================================================
# Table — construction & Field_Defns
# ===========================================================================

class Test_Table_Construction(unittest.TestCase):

    def test_from_field_list(self):
        db = _mem_db()
        t = Table(db, name='items', field_defns=LEDGER_FIELDS)
        self.assertEqual(t.name, 'items')
        self.assertIsInstance(t.field_defns, Field_Defns)
        self.assertEqual(len(t.field_defns), len(LEDGER_FIELDS))
        self.assertEqual(t.col_names[0], 'id')
        self.assertEqual(t.frmt, SQL_Format.SQLITE)
        db.disconnect()

    def test_from_defns_classmethod(self):
        db = _mem_db()
        t = Table.from_defns(db, 'items', LEDGER_FIELDS)
        self.assertEqual(t.name, 'items')
        db.disconnect()

    def test_quoting(self):
        db = _mem_db()
        t = Table(db, name='items', field_defns=LEDGER_FIELDS)
        self.assertEqual(t.table_name_to_sql(), '`items`')
        self.assertEqual(t.col_name_to_sql('amt'), '`amt`')
        db.disconnect()


# ===========================================================================
# Table — SQL generation (via Field_Defns)
# ===========================================================================

class Test_Table_SqlGeneration(unittest.TestCase):

    def setUp(self):
        self.db = _mem_db()
        self.ledger = Table(self.db, name='items', field_defns=LEDGER_FIELDS)
        self.inv = Table(self.db, name='inventory', field_defns=INVENTORY_FIELDS)

    def tearDown(self):
        self.db.disconnect()

    def test_sql_create_auto_pk(self):
        sql = self.ledger.sql_create()
        self.assertIn('CREATE TABLE IF NOT EXISTS `items`', sql)
        # sole auto integer PK → column-level PRIMARY KEY AUTOINCREMENT
        self.assertIn('PRIMARY KEY AUTOINCREMENT', sql)
        # no table-level PRIMARY KEY for that case
        self.assertNotIn('PRIMARY KEY(`id`', sql)

    def test_sql_create_composite(self):
        sql = self.inv.sql_create()
        self.assertIn('PRIMARY KEY(`tenant_id` ASC, `sku` ASC)', sql)
        self.assertNotIn('AUTOINCREMENT', sql)

    def test_sql_insert_skips_auto(self):
        sql = self.ledger.sql_insert()
        self.assertTrue(sql.startswith('INSERT INTO `items`'))
        self.assertNotIn('`id`', sql)
        self.assertEqual(sql.count('?'), 6)

    def test_sql_insert_composite_includes_keys(self):
        sql = self.inv.sql_insert()
        self.assertIn('`tenant_id`', sql)
        self.assertIn('`sku`', sql)
        self.assertEqual(sql.count('?'), 4)

    def test_sql_update_single_pk(self):
        sql = self.ledger.sql_update()
        self.assertIn('WHERE `id`=?', sql)
        set_part = sql.split('WHERE')[0]
        self.assertNotIn('`id`=?', set_part)

    def test_sql_update_composite(self):
        sql = self.inv.sql_update()
        self.assertIn('WHERE `tenant_id`=? AND `sku`=?', sql)


# ===========================================================================
# Table — CRUD against :memory:
# ===========================================================================

class Test_Table_Crud(unittest.TestCase):

    def setUp(self):
        self.db = _mem_db()
        self.t = _ledger_table(self.db)

    def tearDown(self):
        self.db.disconnect()

    def test_create_and_count_zero(self):
        self.assertEqual(self.t.count(), 0)

    def test_insert_dict(self):
        rid = self.t.insert({
            'date': '2021-05-19', 'typ': 'debit', 'cat': 'food',
            'merch': 'Publix', 'desc': 'Groceries', 'amt': 10001,
        })
        self.assertIsNotNone(rid)
        self.assertEqual(self.t.count(), 1)

    def test_insert_sequence_non_auto(self):
        rid = self.t.insert(
            ('2021-05-21', 'debit', 'food', 'Publix', 'Bread', 300)
        )
        self.assertIsNotNone(rid)
        self.assertEqual(self.t.count(), 1)

    def test_insert_full_width_strips_auto(self):
        rid = self.t.insert(
            (None, '2021-05-20', 'debit', 'food', 'Publix', 'Milk', 500)
        )
        self.assertIsNotNone(rid)
        self.assertEqual(self.t.count(), 1)

    def test_multiple_inserts_and_count(self):
        self.t.insert(('2021-05-19', 'debit', 'food', 'Publix', 'A', 10001))
        self.t.insert(('2021-05-23', 'debit', 'food', 'Publix', 'B', 10101))
        self.t.insert(('2021-05-29', 'debit', 'food', 'Publix', 'C', 7923))
        self.assertEqual(self.t.count(), 3)

    def test_update_by_dict(self):
        rid = self.t.insert(
            ('2021-05-19', 'debit', 'food', 'Publix', 'A', 10001)
        )
        self.t.update({
            'id': rid,
            'date': '2021-05-19',
            'typ': 'debit',
            'cat': 'food',
            'merch': 'Publix',
            'desc': 'Updated',
            'amt': 999,
        })
        cur = self.db.execute(
            'SELECT `desc`, `amt` FROM `items` WHERE `id`=?', (rid,)
        )
        row = cur.fetchone()
        cur.close()
        self.assertEqual(row[0], 'Updated')
        self.assertEqual(row[1], 999)

    def test_drop(self):
        self.t.drop()
        self.assertNotIn('items', self.db.table_names())

    def test_gen_dict_and_tuple(self):
        self.t.insert(('2021-05-19', 'debit', 'food', 'Publix', 'A', 10001))
        cur = self.db.execute(
            'SELECT `id`,`date`,`typ`,`cat`,`merch`,`desc`,`amt` FROM `items`'
        )
        tup = tuple(cur.fetchone())
        cur.close()
        d = self.t.gen_dict(tup)
        self.assertEqual(d['typ'], 'debit')
        self.assertEqual(d['amt'], 10001)
        back = self.t.gen_tuple(d)
        self.assertEqual(back[1], '2021-05-19')

    def test_col_names(self):
        self.assertEqual(
            self.t.col_names,
            ['id', 'date', 'typ', 'cat', 'merch', 'desc', 'amt'],
        )

    def test_col_comma_and_ques(self):
        self.assertEqual(
            self.t.col_comma_list(),
            'id,date,typ,cat,merch,desc,amt',
        )
        self.assertEqual(self.t.col_ques_list().count('?'), 7)


# ===========================================================================
# Table — composite PK CRUD
# ===========================================================================

class Test_Table_CompositePk(unittest.TestCase):

    def setUp(self):
        self.db = _mem_db()
        self.t = _inventory_table(self.db)

    def tearDown(self):
        self.db.disconnect()

    def test_create_columns(self):
        cur = self.db.execute('PRAGMA TABLE_INFO(inventory)')
        cols = cur.fetchall()
        cur.close()
        names = [c[1] for c in cols]
        self.assertEqual(names, ['tenant_id', 'sku', 'qty', 'note'])

    def test_insert_and_update(self):
        self.t.insert(
            {'tenant_id': 1, 'sku': 'ABC', 'qty': 10, 'note': 'first'}
        )
        self.assertEqual(self.t.count(), 1)
        self.t.update(
            {'tenant_id': 1, 'sku': 'ABC', 'qty': 20, 'note': 'restocked'}
        )
        cur = self.db.execute(
            'SELECT `qty`, `note` FROM `inventory` '
            'WHERE `tenant_id`=? AND `sku`=?',
            (1, 'ABC'),
        )
        row = cur.fetchone()
        cur.close()
        self.assertEqual(row[0], 20)
        self.assertEqual(row[1], 'restocked')

    def test_composite_pk_uniqueness(self):
        self.t.insert(
            {'tenant_id': 1, 'sku': 'ABC', 'qty': 1, 'note': 'a'}
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.t.insert(
                {'tenant_id': 1, 'sku': 'ABC', 'qty': 2, 'note': 'dup'}
            )


# ===========================================================================
# Table — rowid navigation
# ===========================================================================

class Test_Table_RowidNav(unittest.TestCase):

    def setUp(self):
        self.db = _mem_db()
        self.t = _ledger_table(self.db)
        self.t.insert(('2021-05-19', 'debit', 'food', 'Publix', 'A', 100))
        self.t.insert(('2021-05-20', 'debit', 'food', 'Publix', 'B', 200))
        self.t.insert(('2021-05-21', 'debit', 'food', 'Publix', 'C', 300))

    def tearDown(self):
        self.db.disconnect()

    def test_first_last(self):
        set_flags(True, False)
        first = self.t.rowid_first()
        self.assertIsNotNone(first)
        self.assertEqual(first['desc'], 'A')
        last = self.t.rowid_last()
        self.assertIsNotNone(last)
        self.assertEqual(last['desc'], 'C')
        set_flags(False, False)

    def test_next_prev(self):
        set_flags(True, False)
        first = self.t.rowid_first()
        print(f"\ntest_next_prev: first: {first}", file=sys.stderr)
        self.assertEqual(first['desc'], 'A')
        second = self.t.rowid_next()
        print(f"test_next_prev: second: {second}", file=sys.stderr)
        self.assertIsNotNone(second)
        self.assertEqual(second['desc'], 'B')
        third = self.t.rowid_next()
        print(f"test_next_prev: third: {third}", file=sys.stderr)
        self.assertEqual(third['desc'], 'C')
        self.assertIsNone(self.t.rowid_next())  # past end
        back = self.t.rowid_prev()
        print(f"test_next_prev: back: {back}", file=sys.stderr)
        self.assertEqual(back['desc'], 'C')
        back = self.t.rowid_prev()
        print(f"test_next_prev: back: {back}", file=sys.stderr)
        self.assertEqual(back['desc'], 'B')
        set_flags(False, False)

    def test_find(self):
        set_flags(True, False)
        first = self.t.rowid_first()
        rid = self.t.rowid_current()
        found = self.t.rowid_find(rid)
        self.assertIsNotNone(found)
        self.assertEqual(found['desc'], 'A')
        self.assertIsNone(self.t.rowid_find(99999))
        set_flags(False, False)

    def test_delete(self):
        first = self.t.rowid_first()
        rid = self.t.rowid_current()
        self.assertEqual(self.t.count(), 3)
        self.t.rowid_delete(rid)
        self.assertEqual(self.t.count(), 2)
        self.assertIsNone(self.t.rowid_find(rid))


# ===========================================================================
# Row
# ===========================================================================

class Test_Row(unittest.TestCase):

    def setUp(self):
        self.db = _mem_db()
        self.t = Table(self.db, name='items', field_defns=LEDGER_FIELDS)

    def tearDown(self):
        self.db.disconnect()

    def test_from_tuple(self):
        tup = (1, '2021-05-19', 'debit', 'food', 'Publix', 'A', 10001)
        row = Row.from_tuple(self.t, tup)
        self.assertEqual(row['id'], 1)
        self.assertEqual(row['amt'], 10001)
        self.assertEqual(row[0], 1)
        self.assertEqual(row.to_dict()['cat'], 'food')

    def test_from_dict(self):
        d = {
            'id': 2, 'date': '2021-06-01', 'typ': 'credit', 'cat': 'pay',
            'merch': 'Boss', 'desc': 'Salary', 'amt': 500000,
        }
        row = Row.from_dict(self.t, d)
        self.assertEqual(row['typ'], 'credit')
        self.assertEqual(row.to_tuple()[0], 2)

    def test_setitem(self):
        row = Row.from_dict(self.t, {'id': 1, 'amt': 10})
        row['amt'] = 20
        self.assertEqual(row['amt'], 20)

    def test_repr(self):
        row = Row.from_dict(self.t, {'id': 1})
        self.assertIn('Row', repr(row))


# ===========================================================================
# Integration — end-to-end shapes
# ===========================================================================

class Test_Integration(unittest.TestCase):

    def test_create_insert_update_select_roundtrip(self):
        db = _mem_db()
        t = _ledger_table(db)

        rid = t.insert({
            'date': '2021-05-19', 'typ': 'debit', 'cat': 'food',
            'merch': 'Publix', 'desc': 'Groceries', 'amt': 10001,
        })
        self.assertEqual(t.count(), 1)

        t.update({
            'id': rid, 'date': '2021-05-19', 'typ': 'debit', 'cat': 'food',
            'merch': 'Publix', 'desc': 'Fixed', 'amt': 9999,
        })

        row = t.rowid_find(rid)
        self.assertIsNotNone(row)
        self.assertEqual(row['desc'], 'Fixed')
        self.assertEqual(row['amt'], 9999)

        t.drop()
        self.assertEqual(db.table_names(), [])
        db.disconnect()

    def test_two_tables_same_db(self):
        db = _mem_db()
        ledger = _ledger_table(db)
        inv = _inventory_table(db)
        ledger.insert(('2021-05-19', 'debit', 'food', 'Publix', 'A', 100))
        inv.insert({'tenant_id': 1, 'sku': 'X', 'qty': 5, 'note': 'n'})
        self.assertEqual(ledger.count(), 1)
        self.assertEqual(inv.count(), 1)
        names = sorted(db.table_names())
        self.assertEqual(names, ['inventory', 'items'])
        db.disconnect()


################################################################################
#                           Command-line interface
################################################################################

if __name__ == '__main__':
    unittest.main()

