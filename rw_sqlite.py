#!/usr/bin/env python3
# vi:nu:et:sts=4 ts=4 sw=4

"""
SQLite-specific Database / Table / Row subclasses.

Notes:
    *   This uses rw_database + Field_Defns for column definitions, SQL generation, etc.
        Keeps SQLite-specific quoting, rowid helpers, and WITHOUT ROWID support.
    *   If just one field has Data_Type.Integer and a key present which equates to 
        "INTEGER PRIMARY KEY" is internally a alias internally for "rowid". So, first(), 
        last(), next() and prev() must have this to operate correctly.
"""

import datetime
import os
import pathlib
import sqlite3
import sys
from typing import List, Tuple, Dict, Optional, Any

from rw_field_defn import SQL_Format, Data_Type, Field_Defns
import rw_database


flg_debug = False
flg_test  = False


#---------------------------------------------------------------------
#                           F l a g s
#---------------------------------------------------------------------

def set_flags(fdebug=False, ftest=False):
    global flg_debug, flg_test
    flg_debug = fdebug
    flg_test = ftest
    rw_database.set_flags(fdebug, ftest)

def is_debug() -> bool:
    return flg_debug

def is_test() -> bool:
    return flg_test


#======================================================================
#                   SQLite Data Conversion
#======================================================================

def adapt_date(d: datetime.date) -> str:
    return d.isoformat()

def convert_date(val: bytes) -> Optional[datetime.date]:
    if not val:
        return None
    return datetime.date.fromisoformat(val.decode())

def adapt_datetime(dt: datetime.datetime) -> str:
    return dt.isoformat()

def convert_datetime(val: bytes) -> Optional[datetime.datetime]:
    if not val:
        return None
    s = val.decode()
    try:
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        return datetime.datetime.fromisoformat(s + "+00:00")

def register_converters():
    """Register custom adapters and converters for sqlite3."""
    sqlite3.register_adapter(datetime.date, adapt_date)
    sqlite3.register_adapter(datetime.datetime, adapt_datetime)
    sqlite3.register_converter("DATE", convert_date)
    sqlite3.register_converter("DATETIME", convert_datetime)


#======================================================================
#                           Database Class
#======================================================================

def dict_factory(cursor, row):
    """ Convert SQLite3 data from tuple to dictionary.
    """
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


class Database(rw_database.Database):
    """
    SQLite-specific Database.

    Usage:
        db = Database("xyzzy.sqlite3")
        db.connect()
        db.disconnect()
    """

    def __init__(self, db_path: Optional[str | pathlib.Path] = None):
        if isinstance(db_path, str):
            db_path = pathlib.Path(db_path)
        super().__init__(db_path=db_path, frmt=SQL_Format.SQLITE)
        register_converters()

    def connection_create(self, db_path: pathlib.Path):
        """Create sqlite3 connection (supports :memory:)."""
        path = str(db_path) if db_path is not None else ':memory:'
        if path.endswith(':memory:') or path == ':memory:':
            path = ':memory:'
        conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        #conn.row_factory = sqlite3.Row
        #conn.row_factory = dict_factory
        return conn

    def execute(self, sql: str, params: Optional[tuple] = None):
        """ Execute SQL (supports executescript for multi-statement CREATE).
        """
        if flg_debug:
            print(f"\n rw_sqlite3.Database.execute()", file=sys.stderr)
            print(f"\t sql:{sql} \n\t params:{params}", file=sys.stderr)
        if self._conn is None:
            self.connect()
        cur = self._conn.cursor()
        sql = sql.removesuffix(';').strip()
        try:
            if params is None and ';' in sql:
                cur.executescript(sql)
                # dummy cursor so caller can .close()
                class _Dummy:
                    def close(self): pass
                return _Dummy()
            sql = sql.removesuffix(';')
            if params is None:
                cur.execute(sql)
            else:
                cur.execute(sql, params)
            return cur
        except Exception:
            cur.close()
            raise

    def table_names(self) -> List[str]:
        """Return permanent table names (excludes sqlite_sequence)."""
        cur = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = [row[0] for row in cur.fetchall() if row[0] != "sqlite_sequence"]
        cur.close()
        return names

    def temp_table_names(self) -> List[str]:
        cur = self.execute(
            "SELECT name FROM sqlite_temp_master WHERE type='table' ORDER BY name"
        )
        names = [row[0] for row in cur.fetchall() if row[0] != "sqlite_sequence"]
        cur.close()
        return names


#======================================================================
#                           Table Class
#======================================================================

class Table(rw_database.Table):
    """
    SQLite-specific Table.

    Uses Field_Defns for column definitions and SQL generation.
    Adds SQLite-specific quoting and rowid helpers.
    """

    def __init__(
            self,
            db: Database,
            name: Optional[str] = None,
            field_defns: Optional[Any] = None,
            table_defn: Optional[Dict[str, Any]] = None,
            without_rowid: bool = False
        ):
        super().__init__(
            db=db, name=name, field_defns=field_defns, table_defn=table_defn
        )
        self.without_rowid = without_rowid

    def table_name_to_sql(self) -> str:
        """SQLite quoting: `table_name`"""
        return f'`{self._name}`' if self._name else ''

    def col_name_to_sql(self, col_name: str) -> str:
        """SQLite quoting: `col_name`"""
        return f'`{col_name}`'

    # ---- column metadata --------------------------------------------

    def _load_metadata(self) -> List[str]:
        """
        Load column names from the live database (PRAGMA TABLE_INFO).
        Returns [] if the table name is unknown or the table does not exist.
        Each PRAGMA row: (id, name, type, notnull, default_value, primary_key)
        """
        if self._name is None:
            return []
        if self._col_info is None:
            cur = self.db.execute(f"PRAGMA TABLE_INFO({self._name})")
            if cur is None:
                return []
            self._col_info = cur.fetchall()
            cur.close()
        return [row[1] for row in (self._col_info or [])]

    # ---- Rowid helpers -------------------------------------------------

    def rowid_current(self) -> int:
        """Current rowid (0 if none)."""
        return self._cur

    def rowid_first(self) -> Optional["Row"]:
        """ Return the first row.
        """
        if flg_debug:
            print(f"\n rowid_first:", file=sys.stderr)
        if self._primary_key:
            pk = self.col_name_to_sql(self._primary_key.name)
        else:
            return None
        sql = f"SELECT * FROM {self.table_name_to_sql()} ORDER BY {pk} ASC LIMIT 1"
        cur = self.db.execute(sql)
        row = self.fetch_one(cur)
        cur.close()
        self._cur = row[self._primary_key.name] if row else 0
        return row

    def rowid_last(self) -> Optional["Row"]:
        """Return the last row."""
        if flg_debug:
            print(f"\n rowid_last:", file=sys.stderr)
        if self._primary_key:
            pk = self.col_name_to_sql(self._primary_key.name)
        else:
            return None
        cur = self.db.execute(
            f"SELECT * FROM {self.table_name_to_sql()} ORDER BY {pk} DESC LIMIT 1"
        )
        row = self.fetch_one(cur)
        cur.close()
        self._cur = row[self._primary_key.name] if row else 0
        return row

    def rowid_next(self) -> Optional["Row"]:
        """Next row from current position."""
        if flg_debug:
            print(f"\n rowid_next:", file=sys.stderr)
        if self._primary_key:
            pk = self.col_name_to_sql(self._primary_key.name)
        else:
            return None
        if self._cur <= 0:
            return self.rowid_first()
        cur = self.db.execute(
            f"SELECT * FROM {self.table_name_to_sql()} "
            f"WHERE {pk} > ? ORDER BY {pk} ASC LIMIT 1",
            (self._cur,)
        )
        row = self.fetch_one(cur)
        cur.close()
        self._cur = row[self._primary_key.name] if row else 0
        return row

    def rowid_prev(self) -> Optional["Row"]:
        """ Previous row from current position.
        """
        if flg_debug:
            print(f"\n rowid_prev:", file=sys.stderr)
        if self._primary_key:
            pk = self.col_name_to_sql(self._primary_key.name)
        else:
            return None
        if self._cur <= 0:
            return self.rowid_last()
        sql  =  f"SELECT * FROM {self.table_name_to_sql()} " 
        sql +=  f"WHERE {pk} < ? ORDER BY {pk} DESC LIMIT 1"
        cur = self.db.execute(sql, (self._cur,))
        row = self.fetch_one(cur)
        cur.close()
        self._cur = row[self._primary_key.name] if row else 0
        return row

    def rowid_find(self, rowid: int) -> Optional["Row"]:
        """Find by rowid."""
        if flg_debug:
            print(f"\n rowid_find:", file=sys.stderr)
        if self._primary_key:
            pk = self.col_name_to_sql(self._primary_key.name)
        else:
            return None
        cur = self.db.execute(
            f"SELECT * FROM {self.table_name_to_sql()} WHERE {pk} = ?",
            (rowid,)
        )
        row = self.fetch_one(cur)
        cur.close()
        self._cur = row[self._primary_key.name] if row else 0
        return row

    def rowid_delete(self, rowid: int) -> None:
        """ Delete by rowid.
        """
        if flg_debug:
            print(f"\n rowid_delete({rowid}):", file=sys.stderr)
        if self._primary_key:
            pk = self.col_name_to_sql(self._primary_key.name)
        else:
            return
        sql = f"DELETE FROM {self.table_name_to_sql()} WHERE {pk} = ?"
        cur = self.db.execute(sql, (rowid,))
        cur.close()
        self.db.commit()


#======================================================================
#                           Row Class
#======================================================================

class Row(rw_database.Row):
    """ SQLite-specific Row (thin wrapper).
    """
    pass   # inherits everything needed from rw_database.Row


################################################################################
#                           Command-line interface
################################################################################

if __name__ == '__main__':
    print("rw_sqlite provides classes for use by other scripts.")
    print("It is not meant to be run by itself.")
    sys.exit(4)
