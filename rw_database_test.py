#!/usr/bin/env python3
# vi:nu:et:sts=4 ts=4 sw=4

""" Tests for rw_database.py (Database, Table, Row)

Covers the Field_Defns-driven Table API:
  - construction from field_defns / table_defn
  - column metadata
  - sql_create / sql_insert / sql_update generation
  - create / insert / update / drop / count against an in-process SQLite DB
  - Row helpers

Run from the directory that contains rw_database.py and rw_field_defn.py:

    python3 rw_database_test.py
    python3 -m unittest rw_database_test -v
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

from rw_field_defn import SQL_Format, Data_Type, Field_Defn, Field_Defns
from rw_database import Database, Table, Row
import rw_database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Ledger-style table with autoincrement PK
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

# Composite PK, no autoincrement
INVENTORY_FIELDS = [
    {'name': 'tenant_id', 'type': Data_Type.INTEGER, 'key': ('ASC', 1), 'null': False},
    {'name': 'sku',       'type': Data_Type.VARCHAR, 'length': 32, 'key': ('ASC', 2), 'null': False},
    {'name': 'qty',       'type': Data_Type.INTEGER, 'default': '0'},
    {'name': 'note',      'type': Data_Type.TEXT},
]


# ===========================================================================
# Minimal SQLite Database subclass for integration tests
# ===========================================================================

class SqliteDB(Database):
    """Concrete Database for tests — wraps sqlite3."""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = pathlib.Path(':memory:')
        elif not isinstance(db_path, pathlib.Path):
            db_path = pathlib.Path(db_path)
        super().__init__(db_path=db_path, frmt=SQL_Format.SQLITE)

    def connection_create(self, db_path):
        path = str(db_path) if db_path is not None else ':memory:'
        if path.endswith(':memory:') or path == ':memory:':
            path = ':memory:'
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, sql: str, params=None):
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        return cur


# ===========================================================================
# Lightweight fake DB (no real connection) for pure unit tests
# ===========================================================================

class FakeCursor:
    def __init__(self, rows=None, lastrowid=None):
        self._rows = list(rows or [])
        self.lastrowid = lastrowid
        self.closed = False

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        self.closed = True


class FakeDB(Database):
    """
    Database stand-in that records execute() calls and never touches disk.
    Suitable for testing Table SQL generation and argument plumbing.
    """

    def __init__(self, path='fake.db', frmt=SQL_Format.SQLITE):
        super().__init__(db_path=pathlib.Path(path), frmt=frmt)
        self.executed = []          # list of (sql, params)
        self._next_rows = []
        self._next_lastrowid = 1
        self._conn = object()       # pretend connected

    def connection_create(self, db_path):
        return object()

    def connection_close(self):
        pass

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        rows = self._next_rows
        self._next_rows = []
        rid = self._next_lastrowid
        self._next_lastrowid += 1
        return FakeCursor(rows=rows, lastrowid=rid)

    def commit(self):
        pass

    def queue_fetch(self, rows):
        """Preset rows for the next execute().fetchone/fetchall()."""
        self._next_rows = list(rows)


# ===========================================================================
# Database unit tests (base class behaviour)
# ===========================================================================

class Test_Database_Base(unittest.TestCase):

    def test_init_defaults(self):
        db = FakeDB()
        self.assertEqual(db._frmt, SQL_Format.SQLITE)
        self.assertIsNotNone(db.path)

    def test_connect_disconnect(self):
        db = SqliteDB(':memory:')
        conn = db.connect()
        self.assertIsNotNone(conn)
        self.assertIs(db.conn, conn)
        db.disconnect()
        self.assertIsNone(db.conn)

    def test_connect_missing_path_raises(self):
        db = Database(db_path=None, frmt=SQL_Format.SQLITE)
        with self.assertRaises(ValueError):
            db.connect()

    def test_double_connect_raises(self):
        db = SqliteDB(':memory:')
        db.connect()
        with self.assertRaises(ValueError):
            db.connect()
        db.disconnect()

    def test_context_manager(self):
        db = SqliteDB(':memory:')
        with db:
            self.assertIsNotNone(db.conn)
        self.assertIsNone(db.conn)

    def test_commit_safe_when_connected(self):
        db = SqliteDB(':memory:')
        db.connect()
        db.commit()  # should not raise
        db.disconnect()

    def test_delete_file(self):
        fd, path = tempfile.mkstemp(suffix='.sqlite')
        os.close(fd)
        try:
            db = SqliteDB(path)
            db.connect()
            db.disconnect()
            self.assertTrue(os.path.isfile(path))
            db.delete()
            self.assertFalse(os.path.isfile(path))
        finally:
            if os.path.isfile(path):
                os.unlink(path)


# ===========================================================================
# Table — construction & Field_Defns wiring
# ===========================================================================

class Test_Table_Construction(unittest.TestCase):

    def test_from_field_defns_list(self):
        db = FakeDB()
        t = Table(db, name='items', field_defns=LEDGER_FIELDS)
        self.assertEqual(t.name, 'items')
        self.assertIsInstance(t.field_defns, Field_Defns)
        self.assertEqual(len(t.field_defns), len(LEDGER_FIELDS))
        self.assertEqual(t.col_names[0], 'id')
        self.assertEqual(t.col_names[-1], 'amt')

    def test_from_field_defns_object(self):
        db = FakeDB()
        fds = Field_Defns(LEDGER_FIELDS)
        t = Table(db, name='items', field_defns=fds)
        self.assertIs(t.field_defns, fds)

    def test_from_table_defn(self):
        db = FakeDB()
        t = Table.from_table_defn(db, LEDGER_TABLE_DEFN)
        self.assertEqual(t.name, 'items')
        self.assertEqual(t.dataclass_name, 'Item')
        self.assertEqual(len(t.field_defns), len(LEDGER_FIELDS))

    def test_from_defns_classmethod(self):
        db = FakeDB()
        t = Table.from_defns(db, 'items', LEDGER_FIELDS)
        self.assertEqual(t.name, 'items')
        self.assertEqual(len(t.field_defns), len(LEDGER_FIELDS))

    def test_name_override_table_defn(self):
        db = FakeDB()
        t = Table(db, name='other', table_defn=LEDGER_TABLE_DEFN)
        self.assertEqual(t.name, 'other')

    def test_field_defns_setter_refreshes_cols(self):
        db = FakeDB()
        t = Table(db, name='t', field_defns=LEDGER_FIELDS)
        t.field_defns = INVENTORY_FIELDS
        self.assertEqual(t.col_names[0], 'tenant_id')
        self.assertEqual(len(t.col_names), 4)

    def test_repr_str(self):
        db = FakeDB('xyzzy.db')
        t = Table(db, name='items', field_defns=LEDGER_FIELDS)
        self.assertIn('items', repr(t))
        self.assertIn('items', str(t))

    def test_frmt_from_db(self):
        db = FakeDB(frmt=SQL_Format.POSTGRE)
        t = Table(db, name='items', field_defns=LEDGER_FIELDS)
        self.assertEqual(t.frmt, SQL_Format.POSTGRE)


# ===========================================================================
# Table — column metadata
# ===========================================================================

class Test_Table_Columns(unittest.TestCase):

    def setUp(self):
        self.db = FakeDB()
        self.t = Table(self.db, name='items', field_defns=LEDGER_FIELDS)

    def test_col_names(self):
        self.assertEqual(
            self.t.col_names,
            ['id', 'date', 'typ', 'cat', 'merch', 'desc', 'amt'],
        )

    def test_col_name_list_is_copy(self):
        names = self.t.col_name_list()
        names.append('hacked')
        self.assertNotIn('hacked', self.t.col_names)

    def test_col_comma_list(self):
        s = self.t.col_comma_list()
        self.assertEqual(s, 'id,date,typ,cat,merch,desc,amt')

    def test_col_ques_list(self):
        s = self.t.col_ques_list()
        self.assertEqual(s, '?, ?, ?, ?, ?, ?, ?')

    def test_col_comma_skip_rowid(self):
        fields = [{'name': 'rowid', 'type': Data_Type.INTEGER, 'key': True, 'auto': True}]
        fields += LEDGER_FIELDS[1:]
        t = Table(self.db, name='x', field_defns=fields)
        self.assertEqual(t.col_comma_list(skip_first=True), 'date,typ,cat,merch,desc,amt')

    def test_find_name_on_field_defns(self):
        fd = self.t.field_defns.find_name('amt')
        self.assertIsNotNone(fd)
        self.assertEqual(fd.type, Data_Type.MONEY64)
        self.assertIsNone(self.t.field_defns.find_name('nope'))


# ===========================================================================
# Table — SQL generation (no DB I/O)
# ===========================================================================

class Test_Table_SqlGeneration(unittest.TestCase):

    def setUp(self):
        self.db = FakeDB(frmt=SQL_Format.SQLITE)
        self.ledger = Table(self.db, name='items', field_defns=LEDGER_FIELDS)
        self.inv = Table(self.db, name='inventory', field_defns=INVENTORY_FIELDS)

    def test_sql_create_ledger(self):
        sql = self.ledger.sql_create()
        self.assertIn('CREATE TABLE IF NOT EXISTS `items`', sql)
        self.assertIn('`id`', sql)
        self.assertIn('PRIMARY KEY', sql)
        self.assertIn('AUTOINCREMENT', sql)
        self.assertIn('NOT NULL', sql)
        self.assertIn('`amt`', sql)

    def test_sql_create_with_other(self):
        sql = self.ledger.sql_create(other='\t-- extra\n')
        self.assertIn('-- extra', sql)

    def test_sql_create_composite_pk(self):
        sql = self.inv.sql_create()
        self.assertIn('PRIMARY KEY(`tenant_id` ASC, `sku` ASC)', sql)

    def test_sql_create_requires_name(self):
        t = Table(self.db, field_defns=LEDGER_FIELDS)
        with self.assertRaises(ValueError):
            t.sql_create()

    def test_sql_create_requires_fields(self):
        t = Table(self.db, name='empty')
        with self.assertRaises(ValueError):
            t.sql_create()

    def test_sql_create_postgre_no_backticks(self):
        db = FakeDB(frmt=SQL_Format.POSTGRE)
        t = Table(db, name='items', field_defns=LEDGER_FIELDS)
        sql = t.sql_create()
        self.assertIn('CREATE TABLE IF NOT EXISTS items', sql)
        self.assertNotIn('`items`', sql)
        self.assertIn('NOT NULL', sql)

    def test_sql_insert_skips_auto_pk(self):
        sql = self.ledger.sql_insert()
        self.assertTrue(sql.startswith('INSERT INTO `items`'))
        self.assertNotIn('`id`', sql)
        for col in ('date', 'typ', 'cat', 'merch', 'desc', 'amt'):
            self.assertIn(f'`{col}`', sql)
        self.assertEqual(sql.count('?'), 6)

    def test_sql_insert_exact(self):
        sql = self.ledger.sql_insert()
        expected = (
            "INSERT INTO `items` ( `date`, `typ`, `cat`, `merch`, `desc`, `amt` )\n"
            "\tVALUES ( ?, ?, ?, ?, ?, ? );\n"
        )
        self.assertEqual(sql, expected)

    def test_sql_insert_composite_includes_keys(self):
        sql = self.inv.sql_insert()
        self.assertIn('`tenant_id`', sql)
        self.assertIn('`sku`', sql)
        self.assertEqual(sql.count('?'), 4)

    def test_sql_update_single_pk(self):
        sql = self.ledger.sql_update()
        self.assertTrue(sql.startswith('UPDATE `items` SET'))
        self.assertIn('WHERE `id`=?', sql)
        set_part = sql.split('WHERE')[0]
        self.assertNotIn('`id`=?', set_part)
        for col in ('date', 'typ', 'cat', 'merch', 'desc', 'amt'):
            self.assertIn(f'`{col}`=?', sql)

    def test_sql_update_composite_where(self):
        sql = self.inv.sql_update()
        self.assertIn('WHERE `tenant_id`=? AND `sku`=?', sql)
        set_part = sql.split('WHERE')[0]
        self.assertIn('`qty`=?', set_part)
        self.assertIn('`note`=?', set_part)
        self.assertNotIn('`tenant_id`=?', set_part)


# ===========================================================================
# Table — CRUD against real SQLite (:memory:)
# ===========================================================================

class Test_Table_SqliteCrud(unittest.TestCase):

    def setUp(self):
        rw_database.flg_debug = True
        self.db = SqliteDB(':memory:')
        self.db.connect()
        self.t = Table(self.db, name='items', field_defns=LEDGER_FIELDS)
        self.t.table_name_to_sql = lambda: '`items`'  # type: ignore
        self.t.create()

    def tearDown(self):
        self.db.disconnect()

    def test_create_and_count_zero(self):
        self.assertEqual(self.t.count(), 0)

    def test_insert_dict_and_count(self):
        rid = self.t.insert({
            'date': '2021-05-19', 'typ': 'debit', 'cat': 'food',
            'merch': 'Publix', 'desc': 'Groceries', 'amt': 10001,
        })
        self.assertIsNotNone(rid)
        self.assertEqual(self.t.count(), 1)

    def test_insert_sequence_full_width_drops_auto_pk(self):
        rid = self.t.insert((None, '2021-05-20', 'debit', 'food', 'Publix', 'Milk', 500))
        self.assertIsNotNone(rid)
        self.assertEqual(self.t.count(), 1)

    def test_insert_sequence_non_auto_only(self):
        rid = self.t.insert(('2021-05-21', 'debit', 'food', 'Publix', 'Bread', 300))
        self.assertIsNotNone(rid)
        self.assertEqual(self.t.count(), 1)

    def test_multiple_inserts(self):
        self.t.insert(('2021-05-19', 'debit', 'food', 'Publix', 'A', 10001))
        self.t.insert(('2021-05-23', 'debit', 'food', 'Publix', 'B', 10101))
        self.t.insert(('2021-05-29', 'debit', 'food', 'Publix', 'C', 7923))
        self.assertEqual(self.t.count(), 3)

    def test_update_by_dict(self):
        rid = self.t.insert(('2021-05-19', 'debit', 'food', 'Publix', 'A', 10001))
        self.t.update({
            'id': rid,
            'date': '2021-05-19',
            'typ': 'debit',
            'cat': 'food',
            'merch': 'Publix',
            'desc': 'Updated',
            'amt': 999,
        })
        cur = self.db.execute('SELECT `desc`, `amt` FROM `items` WHERE `id`=?', (rid,))
        row = cur.fetchone()
        cur.close()
        self.assertEqual(row[0], 'Updated')
        self.assertEqual(row[1], 999)

    def test_drop(self):
        self.t.drop()
        cur = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='items'"
        )
        row = cur.fetchone()
        cur.close()
        self.assertIsNone(row)

    def test_gen_dict_tuple(self):
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

    def test_col_names_from_field_defns(self):
        self.assertEqual(self.t.col_names[0], 'id')
        self.assertIn('amt', self.t.col_names)


# ===========================================================================
# Table — composite PK CRUD
# ===========================================================================

class Test_Table_CompositePk(unittest.TestCase):

    def setUp(self):
        self.db = SqliteDB(':memory:')
        self.db.connect()
        self.t = Table(self.db, name='inventory', field_defns=INVENTORY_FIELDS)
        self.t.table_name_to_sql = lambda: '`inventory`'  # type: ignore
        self.t.create()

    def tearDown(self):
        self.db.disconnect()

    def test_create_composite_pk(self):
        cur = self.db.execute("PRAGMA TABLE_INFO(inventory)")
        cols = cur.fetchall()
        cur.close()
        names = [c[1] for c in cols]
        self.assertEqual(names, ['tenant_id', 'sku', 'qty', 'note'])

    def test_insert_and_update(self):
        self.t.insert({'tenant_id': 1, 'sku': 'ABC', 'qty': 10, 'note': 'first'})
        self.assertEqual(self.t.count(), 1)
        self.t.update({'tenant_id': 1, 'sku': 'ABC', 'qty': 20, 'note': 'restocked'})
        cur = self.db.execute(
            'SELECT `qty`, `note` FROM `inventory` WHERE `tenant_id`=? AND `sku`=?',
            (1, 'ABC'),
        )
        row = cur.fetchone()
        cur.close()
        self.assertEqual(row[0], 20)
        self.assertEqual(row[1], 'restocked')


# ===========================================================================
# Table.insert / update plumbing with FakeDB
# ===========================================================================

class Test_Table_InsertUpdatePlumbing(unittest.TestCase):

    def setUp(self):
        self.db = FakeDB()
        self.t = Table(self.db, name='items', field_defns=LEDGER_FIELDS)

    def test_insert_dict_params_order(self):
        self.t.insert({
            'date': '2021-05-19', 'typ': 'debit', 'cat': 'food',
            'merch': 'Publix', 'desc': 'A', 'amt': 100,
        })
        sql, params = self.db.executed[-1]
        self.assertIn('INSERT INTO', sql)
        self.assertEqual(params, ('2021-05-19', 'debit', 'food', 'Publix', 'A', 100))

    def test_insert_full_tuple_strips_auto_pk(self):
        self.t.insert((None, '2021-05-19', 'debit', 'food', 'Publix', 'A', 100))
        _, params = self.db.executed[-1]
        self.assertEqual(params, ('2021-05-19', 'debit', 'food', 'Publix', 'A', 100))

    def test_update_dict_params_order(self):
        self.t.update({
            'id': 7,
            'date': '2021-05-19', 'typ': 'debit', 'cat': 'food',
            'merch': 'Publix', 'desc': 'A', 'amt': 100,
        })
        sql, params = self.db.executed[-1]
        self.assertIn('UPDATE', sql)
        self.assertEqual(params[-1], 7)
        self.assertEqual(params[:-1], ('2021-05-19', 'debit', 'food', 'Publix', 'A', 100))


# ===========================================================================
# Row
# ===========================================================================

class Test_Row(unittest.TestCase):

    def setUp(self):
        self.db = FakeDB()
        self.t = Table(self.db, name='items', field_defns=LEDGER_FIELDS)

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

    def test_to_tuple_include_all(self):
        tup = (1, '2021-05-19', 'debit', 'food', 'Publix', 'A', 100)
        row = Row.from_tuple(self.t, tup)
        full = row.to_tuple(include_rowid=True)
        self.assertEqual(len(full), 7)

    def test_setitem(self):
        row = Row.from_dict(self.t, {'id': 1, 'amt': 10})
        row['amt'] = 20
        self.assertEqual(row['amt'], 20)

    def test_repr(self):
        row = Row.from_dict(self.t, {'id': 1})
        self.assertIn('Row', repr(row))


# ===========================================================================
# Integration: SQL shapes align across create/insert/update
# ===========================================================================

class Test_Integration_SqlAlignment(unittest.TestCase):

    def test_ledger_shapes(self):
        db = FakeDB()
        t = Table(db, name='items', field_defns=LEDGER_FIELDS)
        create = t.sql_create()
        insert = t.sql_insert()
        update = t.sql_update()

        self.assertIn('PRIMARY KEY', create)
        self.assertNotIn('`id`', insert)
        self.assertIn('WHERE `id`=?', update)
        for col in ('date', 'typ', 'cat', 'merch', 'desc', 'amt'):
            self.assertIn(f'`{col}`', insert)
            self.assertIn(f'`{col}`=?', update)


################################################################################
#                           Command-line interface
################################################################################

if __name__ == '__main__':
    unittest.main()
