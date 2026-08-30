#!/usr/bin/env python3
# vi:nu:et:sts=4 ts=4 sw=4

"""
TODO:
    *   When Database receives a list of dict in defn, have it build
        the tables from that.



This object supports an SQL Databases including Tables and Rows in con-
junction with rw_field_defns. It is designed to be inherited by classes
that support a specific database format such as SQLite, PostgreSQL,
MySQL, etc. This was designed after reviewing at SQLite's and PostgreSQL's
implementation in python.

Notes:
    1.  Certain operations such as next() and prev() require a rowid
        such as defined in SQLite.



"""

import  datetime
import  os
import  pathlib
import  sqlite3
import  sys
from    typing import List, Tuple, Type, Dict, Optional, Any
from enum import IntEnum

from    rw_field_defn import SQL_Format, Data_Type, Field_Defn, Field_Defns
import  rw_field_defn


flg_debug = False
flg_test  = False



#---------------------------------------------------------------------
#                           F l a g s
#---------------------------------------------------------------------

def set_flags(fdebug=False, ftest=False):
    global  flg_debug
    global  flg_test
    flg_debug = fdebug
    flg_test  = ftest
    rw_field_defn.set_flags(fdebug, ftest)

def is_debug() -> bool:
    return flg_debug

def is_test() -> bool:
    return flg_test



#======================================================================
#                           Database Class
#======================================================================

class Database:
    """
        Args:
            path (str): is normally the path to the database.
        Usage:
            db = Database("xyzzy.sqlite3")
            db.delete()
            db.connect()
            ...
            db.disconnect()
    """

    def __init__(
            self, 
            db_path: Optional[pathlib.Path] = None,
            frmt: SQL_Format = SQL_Format.UNKNOWN
        ):
        self._path = db_path
        self._frmt = frmt
        self._conn = None

    def __del__(self):
        """ Object Instance Destruction
            Called when an instance is being destroyed.
        """
        if self._conn is not None:
            self.connection_close()
            self._conn = None

    # ---- class methods -----------------------------------------------


    # ---- property methods --------------------------------------------

    @property
    def conn(self):
        return self._conn

    @property
    def frmt(self) -> SQL_Format:
        return self._frmt

    @property
    def path(self) -> Optional[str]:
        return self._path


    # ---- context manager ---------------------------------------------

    def __enter__(self)  -> "Database":
        """
        This function is entered when a 'with' statement is used
        with the Sql_Database object.  It connects the database
        handler to its file.
        :return: the connection object if successful
        """
        if self._path is not None:
            return self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb)  -> bool:
        """
        This function is entered when a 'with' statement terminates.
        If an exception occurred while processing the statements in
        the 'with' then exc_type, exec_val and exc_tb will have values
        other than None.
        :param exc_type: Exception Type
        :param exc_val: Exception Value
        :param exc_tb:  Exception Traceback
        :return:
        """
        self.disconnect()
        return False

    # ---- connection handling -----------------------------------------

    def connect(self, path: Optional[pathlib.Path] = None) -> Optional[object]:
        """ Open a connection to the database file.
            :return sqlite connection or None:
        """
        if self._path is None and path is not None:
            self._path = path
        if path is None and self._path is not None:
            path = self._path
        if path is None:
            raise ValueError('Database::connect - Missing database file path!')
        if self._conn:
            raise ValueError('Database::connect - Connection is already established!')
            return

        self._conn = self.connection_create(path)

        return self._conn

    def connection_close(self):
        """ Close an open connection.
        """
        if hasattr(self._conn, 'close'):
            self._conn.close()
        else:
            raise NotImplementedError

    def connection_create(self, db_path: pathlib.Path):
        """ Create the table if it does not exist.
        """
        raise NotImplementedError

    def disconnect(self) -> None:
        """ Disconnect a database connection.
        """
        if self._conn is not None:
            if hasattr(self._conn, 'close'):
                self.connection_close()
            self._conn = None

    # ---- convenience -------------------------------------------------
    
    def cursor(self) -> Optional[object]:
        """ Create a cursor from the current connection.
            :return: SQL Cursor from the current connection or None
        """
        if not self._conn:
            self.connect()
        if self._conn is not None and hasattr(self._conn, 'cursor'):
            return self._conn.cursor()
        return None

    def delete(self):
        """ Delete a closed database file.
        :return:
        """
        self.disconnect()           # IE Close the database if still open
        if self._path is not None and pathlib.Path(self._path).exists():
            pathlib.Path(self._path).unlink()

    def commit(self):
        """
        :return: SQL Connection
        """
        if self._conn is not None:
            if hasattr(self._conn, 'commit'):            
                self._conn.commit()

    def drop_table(self, name: str) -> None:
        """ Drop the table, completely deleting it and its data.
        """
        # self.execute(f"DROP TABLE IF EXISTS {name}").close()
        raise NotImplementedError

    def execute(self, sql: str, params: Optional[tuple] = None) -> object:
        """ Execute an sql statement with optional data.
            :param sql: required sql statement
            :param data: data tuple used with the sql statement
            :return: a cursor object that needs to be closed
        """
        if self._conn is None:
            return None
        raise NotImplementedError




#======================================================================
#                           Table Class
#======================================================================

class Table:
    """
    A helper class for dealing with SQL Tables, driven by Field_Defns.

    Table definition dict (optional) shape — see rw_field_defn:
        {
            'name':       'table_name',          # SQL table name (plural)
            'dataclass':  'Record',              # optional dataclass name
            'field_defns': [ field_defn, ... ],  # list of dicts or Field_Defn
        }

    You may also pass field_defns= directly (list of dicts / Field_Defn /
    Field_Defns) without a full table_defn.

    Notes:
      1. create() uses Field_Defns.to_sql_create().
      2. insert() uses Field_Defns.to_sql_insert() and skips AUTOINCREMENT PKs.
      3. If you alter the table outside this object, rebuild the Table so
         Field_Defns stays in sync.
    """

    def __init__(
            self,
            db: Database,
            name: Optional[str] = None,
            field_defns: Optional[Any] = None,
            table_defn: Optional[Dict[str, Any]] = None
        ):
        """
        Args:
            db:           Database this table belongs to
            name:         SQL table name (overrides table_defn['name'])
            field_defns:  optional Field_Defns | list[dict|Field_Defn]
                          (overrides table_defn['field_defns'])
            table_defn:   optional dict with name / dataclass / field_defns
        """
        self.db = db
        self._name: Optional[str] = name
        self._dataclass_name: Optional[str] = name
        self._field_defns: Field_Defns = Field_Defns()
        self._col_info: Optional[List[Tuple]] = None
        self._col_names: Optional[List[str]] = None
        self._num_keys: int = 0
        self._primary_key: Optional[Field_Defn] = None
        self._cur: int = 0          # current rowid for First/Last/Next/Prev

        if table_defn:
            if self._name is None:
                self._name = table_defn.get('name')
            self._dataclass_name = table_defn.get('dataclass') or self._name
            if field_defns is None:
                field_defns = table_defn.get('field_defns')

        if field_defns is not None:
            if isinstance(field_defns, Field_Defns):
                self._field_defns = field_defns
            else:
                self._field_defns = Field_Defns(field_defns)
            if db is not None:
                self._field_defns.frmt = db.frmt
            self._field_defns.validate()

        self._refresh_cols()

    def _refresh_cols(self) -> None:
        """Cache column names and single INTEGER primary key, if any."""
        self._col_names = []
        self._num_keys = 0
        self._primary_key = None
        for fd in self._field_defns:
            self._col_names.append(fd.name)
            if fd.key:
                self._num_keys += 1
                if fd.type == Data_Type.INTEGER:
                    self._primary_key = fd
        if not (self._primary_key and self._num_keys == 1):
            self._primary_key = None
        self._col_num = len(self._col_names)

    def __repr__(self) -> str:
        return f"Table({self.db.path}, {self.name})"

    def __str__(self) -> str:
        return f"Table({self.db.path}, {self.name})"


    # --- Class Methods  ----------------------------------------------

    @classmethod
    def from_defns(
            cls,
            db: Database,
            name: str,
            field_defns: Any,
        ) -> "Table":
        """Construct a Table from a name + field definitions."""
        return cls(db=db, name=name, field_defns=field_defns)

    @classmethod
    def from_table_defn(
            cls,
            db: Database,
            table_defn: Dict[str, Any],
        ) -> "Table":
        """Construct a Table from a full table-definition dict."""
        return cls(db=db, table_defn=table_defn)


    # ---- property methods --------------------------------------------

    @property
    def name(self) -> Optional[str]:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def field_defns(self) -> Field_Defns:
        """The Field_Defns that describe this table's columns."""
        return self._field_defns

    @field_defns.setter
    def field_defns(self, value: Any) -> None:
        if isinstance(value, Field_Defns):
            self._field_defns = value
        else:
            self._field_defns = Field_Defns(value or [])
        if self.db is not None:
            self._field_defns.frmt = self.db.frmt
        self._refresh_cols()

    @property
    def dataclass_name(self) -> Optional[str]:
        return self._dataclass_name

    @property
    def frmt(self) -> SQL_Format:
        """ SQL dialect from the owning Database.
        """
        return self.db.frmt


    # ---- column metadata --------------------------------------------

    def col_name_list(self) -> list[str]:
        """Return column names (copy). Prefer Field_Defns; else live metadata."""
        if self._col_names:
            return self._col_names[:]
        if len(self._field_defns):
            self._col_names = [fd.name for fd in self._field_defns]
            return self._col_names[:]
        self._col_names = self._load_metadata()
        return (self._col_names or [])[:]

    @property
    def col_names(self) -> list[str]:
        """List of column names for this table."""
        return self.col_name_list()

    def col_comma_list(self, skip_first: bool = False) -> str:
        """Column names joined by commas. Optionally skip a leading rowid."""
        names = self.col_name_list()
        if skip_first and names and names[0].lower() == "rowid":
            names = names[1:]
        return ",".join(names)

    def col_ques_list(self, skip_first: bool = False) -> str:
        """'?, ?, ?' placeholders matching col_comma_list()."""
        names = self.col_name_list()
        if skip_first and names and names[0].lower() == "rowid":
            names = names[1:]
        return ", ".join("?" for _ in names)

    def col_name_to_sql(self, col_name: str) -> str:
        """Override in dialect subclass if quoting is needed (e.g. SQLite `name`)."""
        return col_name

    def table_name_to_sql(self) -> str:
        """Quote the table name when the dialect needs it (SQLite)."""
        name = self._name or ''
        if self.frmt == SQL_Format.SQLITE and name:
            return f'`{name}`'
        return name


    # --- Row Factory ----------------------------------------------------

    def _row_from_dict(self, data: dict) -> Optional["Row"]:
        if data:
            return Row.from_dict(self, data)
        return None

    def _row_from_tuple(self, data: tuple) -> Optional["Row"]:
        if data:
            return Row.from_tuple(self, data)
        return None


    # ---- SQL generation via Field_Defns --------------------------------

    def sql_create(self, other: Optional[str] = None) -> str:
        """ Full CREATE TABLE statement from Field_Defns.
        """
        if not len(self._field_defns):
            raise ValueError(f"Table({self.name}): no field_defns for create")
        if not self._name:
            raise ValueError("Table: name is required for create")
        return self._field_defns.to_sql_create(self._name, other)

    def sql_insert(self, other: Optional[str] = None) -> str:
        """ Parameterized INSERT (skips AUTOINCREMENT PK columns).
        """
        if not len(self._field_defns):
            raise ValueError(f"Table({self.name}): no field_defns for insert")
        if not self._name:
            raise ValueError("Table: name is required for insert")
        return self._field_defns.to_sql_insert(self._name, other)

    def sql_update(self, other: Optional[str] = None) -> str:
        """ Parameterized UPDATE (SET non-keys, WHERE keys).
        """
        if not len(self._field_defns):
            raise ValueError(f"Table({self.name}): no field_defns for update")
        if not self._name:
            raise ValueError("Table: name is required for update")
        return self._field_defns.to_sql_update(self._name, other)


    # ---- basic CRUD ----------------------------------------------------

    def count(self) -> int:
        """ Return the number of rows in the table.
        """
        cur = self.db.execute(f"SELECT COUNT(*) FROM {self.table_name_to_sql()}")
        cnt = cur.fetchone()[0]
        cur.close()
        return cnt

    def create(self, other: Optional[str] = None):
        """ Create the table from Field_Defns.
            Uses to_sql_create(); subclass may override for 
            dialect specifics.
        """
        sql = self.sql_create(other)
        if flg_debug:
            print(f'\tTable::create sql:\n{sql}', file=sys.stderr)
        # to_sql_create may emit multiple statements (DROP + CREATE)
        for stmt in filter(None, (s.strip() for s in sql.split(';'))):
            if flg_debug:
                print(f"Table:create stmt: '{stmt}'", file=sys.stderr)
            cur = self.db.execute(stmt)
            if cur is not None and hasattr(cur, 'close'):
                cur.close()
        self.db.commit()

    def drop(self) -> None:
        """ Drop the table and all of its data.
        """
        sql = f"DROP TABLE IF EXISTS {self.table_name_to_sql()}"
        cur = self.execute(sql)
        if cur is not None and hasattr(cur, 'close'):
            cur.close()
        self.db.commit()

    def execute(self, sql, data=None):
        """
        Execute SQL with optional bind params.
        Use '{tn}' in sql where the table name should be substituted.
        Returns a cursor that the caller should close.
        """
        sql = sql.format(tn=self.name)
        return self.db.execute(sql, data)

    def fetch_one(self, cur) -> Optional["Row"]:
        if flg_debug:
            print(f"\n  fetch_one:", file=sys.stderr)
        row_data = cur.fetchone()
        if flg_debug:
            print(f"\t  row_data: {row_data}", file=sys.stderr)
        if row_data is None:
            return None
        if isinstance(row_data, tuple):
            row = self._row_from_tuple(row_data)
        elif isinstance(row_data, dict):
            row = self._row_from_dict(row_data)
        elif isinstance(row_data, sqlite3.Row):
            row = self._row_from_dict(dict(row_data))
        else:
            raise TypeError(f"row_data is invalid type of {type(row_data)}!")
        if flg_debug:
            print(f"\t row: {row}", file=sys.stderr)
        return row

    def gen_dict(self, row) -> Optional[dict]:
        """Convert a row tuple/list to a dict keyed by column name."""
        if not row:
            return None
        return dict(zip(self.col_names, row))

    def gen_tuple(self, row: dict) -> tuple:
        """Convert a dict to a tuple in column-name order."""
        return tuple(row.get(name) for name in self.col_names)

    def insert(self, data) -> Optional[int]:
        """
        Insert a row.

        data may be:
          - a sequence matching *all* Field_ columns (legacy; includes
            autoincrement PK — value is typically None), or
          - a sequence matching the non-auto columns only (preferred;
            same order as sql_insert placeholders), or
          - a dict keyed by column name.

        Returns lastrowid when available.
        """
        if flg_debug:
            print(f'\tTable::insert data: {data!r}', file=sys.stderr)

        sql = self.sql_insert()

        # Build bind values in the order to_sql_insert expects:
        # all columns except autoincrement primary keys.
        if isinstance(data, dict):
            params = []
            for fd in self._field_defns:
                if fd.key is not None and fd.auto:
                    continue
                params.append(data.get(fd.name))
            params = tuple(params)
        else:
            data = tuple(data)
            # If caller passed a full-width tuple (including auto PK), drop
            # autoincrement key positions so it matches sql_insert.
            auto_idxs = [
                i for i, fd in enumerate(self._field_defns)
                if fd.key is not None and fd.auto
            ]
            if auto_idxs and len(data) == len(self._field_defns):
                params = tuple(v for i, v in enumerate(data) if i not in auto_idxs)
            else:
                params = data

        if flg_debug:
            print(f'\tTable::insert sql: {sql!r} params: {params!r}', file=sys.stderr)

        cur = self.db.execute(sql, params)
        self.db.commit()
        rowid = getattr(cur, 'lastrowid', None)
        if cur is not None and hasattr(cur, 'close'):
            cur.close()
        return rowid

    def insert_from_dict(self, row_dict: dict) -> Optional[int]:
        """ Insert from a dict keyed by column name (auto PK columns ignored).
        """
        return self.insert(row_dict)

    def update(self, data) -> None:
        """ Update a row using sql_update().

        data may be a dict keyed by column name, or a sequence ordered as:
          non-key columns (SET) followed by key columns (WHERE)
        — the same order Field_Defns.to_sql_update / params expect.
        """
        sql = self.sql_update()

        if isinstance(data, dict):
            non_key = []
            key_vals = []
            for fd in self._field_defns:
                if fd.key is not None:
                    key_vals.append(data.get(fd.name))
                else:
                    non_key.append(data.get(fd.name))
            params = tuple(non_key + key_vals)
        else:
            params = tuple(data)

        if flg_debug:
            print(f'\tTable::update sql: {sql!r} params: {params!r}', file=sys.stderr)

        cur = self.db.execute(sql, params)
        self.db.commit()
        if cur is not None and hasattr(cur, 'close'):
            cur.close()

    def generate_dataclass(self, cls_name: Optional[str] = None):
        """
        Build a dynamic dataclass from this table's Field_Defns.
        cls_name defaults to table_defn['dataclass'] or the table name.
        """
        name = cls_name or self._dataclass_name or (self._name or 'Record')
        return self._field_defns.generate_dataclass(name)


    # ---- Miscellaneous -------------------------------------------------

    def to_csv_enum(self, name: str = "col_name") -> Type[IntEnum] | None:
        if self._field_defns:
            members = {}
            for fd in self._field_defns:
                csv_name = getattr(fd, "col_name", None)
                seqno    = getattr(fd, "seqno", None)

                if not csv_name:          # skip missing / empty csv_name
                    continue
                if seqno is None:         # skip if no sequence number
                    continue
                if csv_name in members:   # optional: guard against duplicates
                    raise ValueError(f"Duplicate col_name: {csv_name}")

                members[csv_name] = seqno

            return IntEnum(name, members)
        return None


#======================================================================
#                           Row Class
#======================================================================

class Row:
    """ A helper class for dealing with SQL Rows.
    """
    __slots__ = ("_data", "_table")

    def __init__(self, table: Table, data: Optional[Dict[str, Any]] = None) -> None:
        self._table = table
        self._data = data or {}

    def __repr__(self) -> str:
        return f"Row({self._table.__repr__()},{self._data})"

    @classmethod
    def from_dict(cls, table: Table, data: Dict) -> "Row":
        """ Create a row given the table and data dictionary.

            Args:
                table (Table): the table that this row is associated with.
                data (dict): column name → value

            Returns:
                Row  Row class instance
        """
        names = table.col_names
        d = {n: data.get(n) for n in names}
        return cls(table, d)

    @classmethod
    def from_tuple(cls, table: Table, tup: Tuple) -> "Row":
        """ Create a row given the table and data tuple. The
            tuple must have the same number of columns as the
            table including rowid if present.

            Args:
                table (Table): the table that this row is associated with.
                data (tuple): a tuple which is the column names of the Row.

            Returns:
                Row class instance

            Raises:
                none
        """
        names = table.col_names
        d = dict(zip(names, tup))
        return cls(table, d)

    def to_dict(self) -> Dict[str, Any]:
        return self._data.copy()

    def to_tuple(self, include_rowid: bool = True) -> Tuple:
        names = self._table.col_names
        if not include_rowid and names and names[0].lower() == "rowid":
            names = names[1:]
        return tuple(self._data.get(n) for n in names)

    def __getitem__(self, col) -> Optional[Any]:
        if isinstance(col, int):
            names = list(self._data.keys())
            if 0 <= col < len(names):
                return self._data.get(names[col])
            return None
        if isinstance(col, str):
            return self._data.get(col)
        return None

    def __setitem__(self, col: str, value: Any) -> None:
        self._data[col] = value

    def rowid(self) -> Optional[int]:
        if self._data.get('rowid') is not None:
            return self._data.get('rowid')
        pk = getattr(self._table, '_primary_key', None)
        if pk is not None:
            return self._data.get(pk.name)
        return None

    

#-------------------------------------------------------------------------------
#                           Column Definition Class
#-------------------------------------------------------------------------------

class Col_Def:
    """ A helper class for dealing with SQL Columns.
        We assume that the primary key for the table is an integer as in
        "`rowid` INTEGER PRIMARY KEY,". SQLite will automatically increase
        this number when doing inserts if a NULL is passed for that column.
    """
    __slots__ = ("_data", "_table")

    def __init__(self, table: Table, data: Optional[Dict[str, Any]] = None):
        self._table = table
        self._data = data or {}

    def __repr__(self) -> str:
        return f"Row({self._table.__repr__()},{self._data})"



################################################################################
#                           Command-line interface
################################################################################

if __name__ == '__main__':
    print("Error: Sorry, rw_database.py provides classes and functions for"
            + " use by other scripts.")
    print("\tIt is not meant to be run by itself.")
    sys.exit(4)
