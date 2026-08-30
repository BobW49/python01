#!python3
# vi:nu:et:sts=4 ts=4 sw=4

""" Field Definitions used for SQL, CSV and fixed record I/O

    Field_Defns is made up of Field_Defn(s) plus some controlling
    variables. Field_Defns should be defined for each SQL Table
    that is used with this system. Additionally, if an input or
    output source is different from the SQL data Field_Defns, 
    then a Field_Defns class should be defined for that input 
    or output.

    WARNING: If you define a CSV Field_Defns that you
                will want to output to a database Field_Defns,
                then you need to insure that the 'name'(s) 
                to be copied are the same in both Field_Defns.
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




import  os
import  sys
from dataclasses import dataclass, field, asdict, make_dataclass, fields
from enum import IntEnum
from typing import Optional, Type
from datetime import datetime

"""             *** Field Definitions ***

    {'name':'xyzzy', 'desc1':'top', 'desc2':'bottom', 'type':Col_Type.BIGINT,
            ['precision':10,] ['scale':2,] 
            ['length':10,]
           ['nullable':True | False,] ['default':"25",] ['auto':True | False,] ['check':"",] ['other':""]
           ['seqno': nnn,] ['col_name':'',]
     }
    'name' is field name used within the record and is required.
    'desc1' is top line for column description
    'desc2' is bottom line for column description
    If single line description (label), use f"{desc1} {desc2}".
    'type' is required as one of:
        BIGINT          # int64_t
        BLOB
        BOOL
        CHAR
        DATE
        DECIMAL
        FILLER
        INTEGER         # int32_t
        MONEY64         # int64_t
        NCHAR
        NUMBER
        NVARCHAR
        REAL
        SMALLINT        # int16_t
        TEXT
        TINYINT         # int8_t
        VARCHAR         # Same as TEXT
    'scale' are used with Decimal to specify the number of digits to the right of the decimal point.
    'length' is used with CHAR, NCHAR, VARCHAR to specify maximum length allowed. It is also used
            with Decimal, Money64 and Real to specify the total number of digits in the number.
    'key' provides the definition for key fields. Composite keys must be ordered in definition as
        how they are to be generated.
        True | ('ASC' | 'DESC'[, int])
    'null' set to False adds 'NOT NULL', True means nullable (ie a value is not required).
            If 'null' is missing, True is assumed.
    'default' sets a DEFAULT(value).
    'auto' if True sets 'AUTOINCREMENT'. If 'auto' is missing, False is assumed.
    'check' sets a CHECK(value).
    'other' can be used for foriegn definitions or whatever is needed.
    'seqno' can be used to define a column number for use with other interfaces
        such as CSV. It is a zero-based integer if present. If not present, then it is None.
    'fixed_start' is the zero-based integer that defines the offset of thestart of the 
        field in a fixed length record. If it is present, then 'fixed_end' must 
        be present as well.
    'fixed_end' is a zero-based integer that denotes the offset of the last character in a
        fixed length record. If this is present, then 'fixed_start' must be present as
        well.
    'conv_in' defines what conversions must be done on the field on input from CSV or Fixed
        records. Valid entries are:
            'lower' means to convert to lower case.
            'title' means to camelize each word of the field (ie First char is uppercase
                and remaining chars in word are lowercase.
            'upper' means to convert to uppercase.

"""

"""             *** Table_Definition ***
    {'name':'table_name', 'dataclass':'data_class_name', 'field_defns':[field_defn...] 
    }

    'name': is the name that will be used in SQL statements to create, delete, insert,
            update, ... the table within the database. It is normally plural of the
            @dataclass name.
    'dataclass': is the @dataclass name used to access one record in the table and
            is normally singular.
    'field_defns': is a list of field_defn as described above.
"""


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

def is_debug() -> bool:
    return flg_debug

def is_test() -> bool:
    return flg_test




#-------------------------------------------------------------------------------
#                           Field Type Definition Class
#-------------------------------------------------------------------------------
class SQL_Format(IntEnum):
    UNKNOWN = 0,
    CSV = 1,
    FIXED = 2,
    SQLITE = 3,
    POSTGRE = 4,
    MYSQL = 5,
    COUNT = 6

SQL_Format_Desc = ['UNKNOWN', 'CSV', 'FIXED', 'SQLITE', 'POSTGRE', 'MYSQL']


class Data_Type(IntEnum):
    UNKNOWN = 0,
    BIGINT = 1,         # int64_t
    BLOB = 2,
    BOOL = 3,
    CHAR = 4,
    DATE = 5,
    DATETIME = 6,
    DECIMAL = 7,
    FILLER = 8,         # Field is only used to mark a position in a CSV or fixed record
    #                   # which is not used in the SQL itself.
    INTEGER = 9,        # int32_t
    MONEY64 = 10,       # int64_t
    NCHAR = 11,
    NUMBER = 12,
    NVARCHAR = 13,
    REAL = 14,
    SMALLINT = 15,      # int16_t
    TEXT = 16,
    TINYINT = 17,       # int8_t
    VARCHAR = 18,
    COUNT = 19          # Number of Data_Type(s)

Data_Type_Desc = ['UNKNOWN', 'BIGINT', 'BLOB', 'BOOL', 'CHAR', 
                  'DATE', 'DATETIME', 'DECIMAL', 'FILLER', 'INTEGER', 
                  'MONEY64', 'NCHAR', 'NUMBER', 'NVARCHAR', 'REAL',
                  'SMALLINT', 'TEXT', 'TINYINT', 'VARCHAR',
                  ]



#======================================================================
#                           Field/Column Class
#======================================================================

class   Field_Defn:
    """ The class defines a field or column within a database row. It
        can be used with SQLite, PostgreSQL and MySQL as well as CSV
        files or any files where the field is indexed by a number
        (ie seqno).
    """
    
    def __init__(
            self, 
            defn: Optional[dict] = None     # See above
        ):
        # Set defaults 
        self._name:   str = ''
        self._desc1:  str = ''
        self._desc2:  str = ''
        self._type:   int = Data_Type.UNKNOWN
        self._prec:   int = 0
        self._scale:  int = 0
        self._length: int = 0
        self._auto:   bool = False
        self._key:    Optional[tuple[str,int]] = None
        self._null:   bool = True
        self._unique: bool = False
        self._default: Optional[str] = None
        self._check:  Optional[str] = None
        self._other:  Optional[str] = None
        self._seqno:  Optional[int] = None          # 0,1,2,...
        self._fixed_start: Optional[int] = None
        self._fixed_end: Optional[int] = None

        if defn:
            self._load_from_dict(defn)

    def _load_from_dict(self, defn: dict):
        """     Load the object from a dictionary.
        """
        if 'name' in defn:
            self._name = defn.get('name')
        else:
            raise ValueError(f"'name' is required")
        if 'desc1' in defn:
            self._desc1 = defn.get('desc1')
        if 'desc2' in defn:
            self._desc2 = defn.get('desc2')
        if 'type' in defn:
            self._type = defn.get('type')
        else:
            raise ValueError(f"'type' is required for {self._name}")
        if 'prec' in defn:
            self._prec = defn.get('prec')
        if 'scale' in defn:
            self._scale = defn.get('scale')
        if 'length' in defn:
            self._length = defn.get('length')
        if 'auto' in defn:
            self._auto = defn.get('auto')
        if 'key' in defn:
            self.key = defn.get('key')
        if 'null' in defn:
            self._null = defn.get('null')
        if 'unique' in defn:
            self._unique = defn.get('unique')
        if 'default' in defn:
            self._default = defn.get('default')
        if 'check' in defn:
            self._check = defn.get('check')
        if 'other' in defn:
            self._other = defn.get('other')
        if 'seqno' in defn:
            self._seqno = defn.get('seqno')
        if 'fixed_start' in defn:
            self._fixed_start = defn.get('fixed_start')
        if 'fixed_end' in defn:
            self._fixed_end = defn.get('fixed_end')
        if self._fixed_start or self._fixed_end:
            if not self._fixed_start and self._fixed_end:
                raise ValueError(f"fixed_start and fixed_end must both be present for {self._name}")
            if (self._fixed_end - self._fixed_start + 1) > 0:
                pass
            else:
                raise ValueError(f"(fixed_end - fixed_start + 1) must be > 0 for {self._name}")

    def __repr__(self) -> str:
        """ Return an expression string that can generally be used to
            recreate this object.
        """
        return f"Field_Defn({self._name})"

    def __str__(self) -> str:
        """ Return a simple string representation of an object.
        """
        return f"Field_Defn(name: {self._name} type: {self._type})"


    # --- Properties -------------------------------------------------

    @property
    def key(self) -> Optional[tuple[str,int]]:
        return self._key

    @key.setter
    def key(self, value):
        """ key may be True or a tuple of 'ASC' or 'DESC' optionally followed 
            by an integer relative to 1 to denote key placement in a composite key. 
            The integer may be 0 denoting the definition order defines the key placement.
        """
        if isinstance(value, bool):
            self._key = ('ASC',0)
            return
        if isinstance(value, (tuple, list)):
            if len(value) == 0:
                self._key = ('ASC',0)
                return
            else:
                ordering = 'ASC'
                if value[0] in ('ASC', 'DESC'):
                    ordering = value[0]
                else:
                    raise ValueError(
                        f"key must be 'True' or (['ASC' | 'DESC'] [, int]), not '{value[0]}'!"
                    )
            index = 0
            if len(value) > 1 and isinstance(value[1], int):
                index = value[1]
            self._key = (ordering, index)
            return
        raise TypeError(
               f"key must be 'True' or (['ASC' | 'DESC'] [, int]), not '{value}'!"
        )


    @property
    def name(self) -> str:
        return self._name

    @property
    def desc1(self) -> str:
        return self._desc1

    @property
    def desc2(self) -> str:
        return self._desc2

    @property
    def type(self) -> int:
        return self._type

    @property
    def auto(self) -> bool:
        return self._auto

    @property
    def nullable(self) -> bool:
        return self._null

    @property
    def unique(self) -> bool:
        return self._unique

    @property
    def default(self) -> Optional[str]:
        return self._default

    @property
    def seqno(self) -> int:
        return self._seqno

    @property
    def fixed_start(self) -> int:
        return self._fixed_start

    @property
    def fixed_end(self) -> int:
        return self._fixed_end



    # --- Class Methods  ----------------------------------------------


    # --- Conversion Methods  -----------------------------------------

    def from_csv(self, rcd: list[str], frmt: SQL_Format) -> int | float | bool | str | bytes:
        """ Convert data from a CSV or general list  to internal format
            according to the data type.
        """
        if self._seqno is None:
            raise ValueError(f"'seqno' is required for CSV conversion for {self._name}")
        data = rcd[self._seqno]

        match   self._type:
            case Data_Type.BIGINT:
                return int(data)
            case Data_Type.MONEY64:
                return int(data)
            case Data_Type.SMALLINT:
                return int(data)
            case Data_Type.TINYINT:
                return int(data)
            case Data_Type.INTEGER:
                return int(data)
            case Data_Type.BOOL:
                if not data:
                    return False
                first = data[0].lower()
                if first in ('t', 'y'):
                    return True
                if first in ('f', 'n'):
                    return False
                try:
                    return int(data) > 0
                except ValueError:
                    return False
            case Data_Type.REAL:
                return float(data)
            case Data_Type.DECIMAL | Data_Type.NUMBER:
                raise NotImplementedError
            case Data_Type.VARCHAR | Data_Type.NVARCHAR | Data_Type.TEXT:
                return data
            case Data_Type.CHAR | Data_Type.NCHAR:
                return data
            case Data_Type.DATE:
                match frmt:
                    case SQL_Format.SQLITE:
                        return data
                    case _:
                        raise NotImplementedError
            case Data_Type.DATETIME:
                match frmt:
                    case SQL_Format.SQLITE:
                        return data
                    case _:
                        raise NotImplementedError
            case Data_Type.BLOB:
                return data
            case _:
                raise ValueError(f"Invalid Field Type, {self._type}, for {self._name}")

    def from_fixed(self, rcd: bytes, frmt: SQL_Format) -> int | float | bool | str | bytes:
        """ Convert data from a fixed record to internal format
            according to the data type.
        """
        data = rcd[self._fixed_start:self._fixed_end]
        if self._type == Data_Type.BLOB:
            return data
        data_str = data.decode('utf-8', errors='replace').strip()

        match   self._type:
            case Data_Type.BIGINT:
                return int(data_str)
            case Data_Type.MONEY64:
                return int(data_str)
            case Data_Type.SMALLINT:
                return int(data_str)
            case Data_Type.TINYINT:
                return int(data_str)
            case Data_Type.INTEGER:
                return int(data_str)
            case Data_Type.BOOL:
                if not data_str:
                    return False
                first = data_str[0].lower()
                if first in ('t', 'y'):
                    return True
                if first in ('f', 'n'):
                    return False
                try:
                    return int(data_str) > 0
                except ValueError:
                    return False
            case Data_Type.REAL:
                return float(data_str)
            case Data_Type.DECIMAL | Data_Type.NUMBER:
                raise NotImplementedError
            case Data_Type.VARCHAR | Data_Type.NVARCHAR | Data_Type.TEXT:
                return data_str
            case Data_Type.CHAR | Data_Type.NCHAR:
                return data_str
            case Data_Type.DATE:
                match frmt:
                    case SQL_Format.SQLITE:
                        return data_str
                    case _:
                        raise NotImplementedError
            case Data_Type.DATETIME:
                match frmt:
                    case SQL_Format.SQLITE:
                        return data_str
                    case _:
                        raise NotImplementedError
            case Data_Type.BLOB:
                return data
            case _:
                raise ValueError(f"Invalid Field Type, {self._type}, for {self._name}")


    # --- Misc Methods  -----------------------------------------------

    def is_numeric(self, frmt: SQL_Format) -> bool:
        """ Indicate if a field is numeric or not.
        """
        flg: bool = False
        match self._type:
            case Data_Type.BIGINT:
                flg = True
            case Data_Type.MONEY64:
                flg = True
            case Data_Type.SMALLINT:
                flg = True
            case Data_Type.TINYINT:
                flg = True
            case Data_Type.INTEGER:
                flg = True
            case Data_Type.BOOL:
                match frmt:
                    case SQL_Format.SQLITE:
                        flg = True
                    case _:
                        pass
            case Data_Type.REAL:
                flg = True
            case Data_Type.DECIMAL | Data_Type.NUMBER:
                flg = True
            case Data_Type.VARCHAR | Data_Type.NVARCHAR | Data_Type.TEXT:
                pass
            case Data_Type.CHAR | Data_Type.NCHAR:
                pass
            case Data_Type.DATE:
                match frmt:
                    case SQL_Format.SQLITE:
                        pass
                    case SQL_Format.POSTGRE:
                        flg = True
                    case SQL_Format.MYSQL:
                        flg = True
                    case _:
                        flg = True
            case Data_Type.DATETIME:
                match frmt:
                    case SQL_Format.SQLITE:
                        pass
                    case SQL_Format.POSTGRE:
                        flg = True
                    case SQL_Format.MYSQL:
                        flg = True
                    case _:
                        flg = True
            case Data_Type.BLOB:
                pass
            case _:
                raise ValueError(f"Invalid Field Type, {self._type}, for {self._name}")
        return flg


    def to_sql_create(self, frmt: SQL_Format, single_pk: bool = False) -> str:
        """ Generate a column SQL partial statement from a column
            definition. The column definition is from a dict as
            defined above.
        """
        wrk_str = ""

        match frmt:
            case SQL_Format.SQLITE:
                wrk_str += f"\t`{self._name}`"
            case SQL_Format.POSTGRE:
                wrk_str += f"\t{self._name}"
            case SQL_Format.MYSQL:
                wrk_str += f"\t{self._name}"
            case _:
                wrk_str += f"\t{self._name}"

        text_type:  bool = False
        is_integer: bool = False
        match self._type:
            case Data_Type.BIGINT:
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' INTEGER'
                    case SQL_Format.POSTGRE:
                        wrk_str += ' BIGINT'
                    case SQL_Format.MYSQL:
                        wrk_str += ' BIGINT'
                    case _:
                        wrk_str += ' BIGINT'
            case Data_Type.MONEY64:
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' INTEGER'
                    case _:
                        wrk_str += ' DECIMAL(18,4)'
            case Data_Type.SMALLINT:
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' INTEGER'
                    case _:
                        wrk_str += ' SMALLINT'
            case Data_Type.TINYINT:
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' INTEGER'
                    case _:
                        wrk_str += ' TINYINT'
            case Data_Type.INTEGER:
                is_integer = True
                wrk_str += ' INTEGER'
            case Data_Type.BOOL:
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' INTEGER'
                    case _:
                        wrk_str += ' BOOLEAN'
            case Data_Type.REAL:
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' FLOAT'
                    case _:
                        wrk_str += ' REAL'
            case Data_Type.DECIMAL | Data_Type.NUMBER:
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' NUMERIC'
                    case _:
                        wrk_str += f' DECIMAL({self._prec},{self._scale})'
            case Data_Type.VARCHAR | Data_Type.NVARCHAR | Data_Type.TEXT:
                text_type = True
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' TEXT'
                    case _:
                        wrk_str += f' VARCHAR({self._length})'
            case Data_Type.CHAR | Data_Type.NCHAR:
                text_type = True
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' TEXT'
                    case _:
                        wrk_str += f' CHAR({self._length})'
            case Data_Type.DATE:
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' TEXT'
                    case SQL_Format.POSTGRE:
                        wrk_str += ' DATE'
                    case SQL_Format.MYSQL:
                        wrk_str += ' TIMESTAMP'
                    case _:
                        wrk_str += ' DATE'
            case Data_Type.DATETIME:
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' TEXT'
                    case SQL_Format.POSTGRE:
                        wrk_str += ' DATETIME'
                    case SQL_Format.MYSQL:
                        wrk_str += ' TIMESTAMP'
                    case _:
                        wrk_str += ' DATETIME'
            case Data_Type.BLOB:
                text_type = True
                match frmt:
                    case SQL_Format.SQLITE:
                        wrk_str += ' BLOB'
                    case _:
                        wrk_str += ' BLOB'
            case Data_Type.FILLER:
                return ''
            case _:
                raise ValueError(f"Invalid Field Type, {self._type}, for {self._name}")
          
        # Common attributes
        match frmt:
            case SQL_Format.SQLITE:
                if is_integer and self._key and single_pk:
                    wrk_str += ' PRIMARY KEY'
                    if self._auto:
                        wrk_str += ' AUTOINCREMENT'
            case SQL_Format.MYSQL:
                if self._auto:
                    wrk_str += ' AUTO_INCREMENT'
        if not self._null:
            wrk_str += ' NOT NULL'
        if self._unique:
            wrk_str += ' UNIQUE'
        if isinstance(self._default, str):
            wrk_str += f" DEFAULT( '{self._default}' )"       
        if isinstance(self._check, str):
            wrk_str += f" CHECK( {self._check} )"
        if isinstance(self._other, str):
            wrk_str += f" {self._other}"

        wrk_str += ',\n'

        return wrk_str


    def to_dc(self) -> list:
        """
        Return a make_dataclass field specification:
            (name, type)
            or
            (name, type, field(...))
        """
        if not self._name:
            return []

        # Map Data_Type → Python type
        match self._type:
            case (Data_Type.BIGINT | Data_Type.MONEY64 |
                  Data_Type.SMALLINT | Data_Type.TINYINT | Data_Type.INTEGER):
                py_type = int
                default = 0
            case Data_Type.BOOL:
                py_type = bool
                default = False
            case Data_Type.REAL | Data_Type.DECIMAL | Data_Type.NUMBER:
                py_type = float
                default = 0.0
            case (Data_Type.VARCHAR | Data_Type.NVARCHAR | Data_Type.TEXT |
                  Data_Type.CHAR | Data_Type.NCHAR | Data_Type.DATE |
                  Data_Type.DATETIME):
                py_type = str
                default = ''
            case Data_Type.BLOB:
                py_type = bytes
                default = b''
            case _:
                py_type = str
                default = ''

        # Honour an explicit default from the field definition
        if self._default is not None:
            default = self._default
            # Try to coerce string defaults to the right Python type
            if isinstance(default, str):
                if py_type is int:
                    try:
                        default = int(default)
                    except ValueError:
                        pass
                elif py_type is float:
                    try:
                        default = float(default)
                    except ValueError:
                        pass
                elif py_type is bool:
                    default = default.lower() in ('1', 'true', 't', 'yes', 'y')

        return [self._name, py_type, field(default=default)]




#======================================================================
#                   Field/Column List Class
#======================================================================

class Field_Defns(list):
    """ A list of Field_Defn objects with some helper methods.
    """

    def __init__(
                    self, 
                    items=None, 
                    allow_no_seqno: bool = False, 
                    frmt: SQL_Format = SQL_Format.UNKNOWN 
                ):
        if items is None:
            items = []
        super().__init__(self._convert(item) for item in items)
        self.allow_no_seqno = allow_no_seqno
        self._frmt = frmt

    def _convert(self, item):
        """
        """
        if isinstance(item, Field_Defn):
            return item
        elif isinstance(item, dict):
            return Field_Defn(item)
        else:
            raise TypeError(f"Cannot convert {type(item)} to Field_Defn")

    def append(self, item):
        super().append(self._convert(item))

    def extend(self, items):
        for item in items:
            self.append(item)


    # --- Properties -------------------------------------------------

    @property
    def frmt(self) -> Optional[SQL_Format]:
        return self._frmt

    @frmt.setter
    def frmt(self, value: SQL_Format):
        self._frmt = value


    # --- Misc Methods  -----------------------------------------------

    # Optional helper methods
    def find_name(self, name: str) -> Field_Defn | None:
        for f in self:
            if f.name == name:
                return f
        return None


    def to_names(self) -> list[str]:
        """ Return a list of field names ordered by seqno.

            Only fields that have a seqno are included.
            The list is dense from 0 .. max(seqno). Missing seqnos
            are filled with placeholder names UNK_0, UNK_1, ...
        """
        if not self:
            return []

        name_by_seq: dict[int, str] = {}
        for fd in self:
            if fd.seqno is not None:
                name_by_seq[fd.seqno] = fd.name

        if not name_by_seq:
            return []

        max_seq = max(name_by_seq.keys())
        result: list[str] = []
        unknown_counter = 0

        for i in range(max_seq + 1):
            name = name_by_seq.get(i)
            if name:
                result.append(name)
            else:
                result.append(f"UNK_{unknown_counter}")
                unknown_counter += 1

        return result    


    def to_sql_create(
            self,
            table_name: str,
            other: Optional[str] = None
        ) -> str:
        match self._frmt:
            case SQL_Format.SQLITE:
                sql = f"DROP TABLE IF EXISTS `{table_name}`;\nCREATE TABLE IF NOT EXISTS `{table_name}` (\n"
            case _:
                sql = f"DROP TABLE IF EXISTS {table_name};\nCREATE TABLE IF NOT EXISTS {table_name} (\n"
        sql_defns = ""
        # list of (position, ordering, name) for fields that participate in the PK
        single_pk: bool = False
        num_keys = 0
        for field_defn in self:
            if field_defn.key:
                num_keys += 1
        if num_keys == 1:
            single_pk = True
        pk_entries: list[tuple[int, str, str]] = []
        for field_defn in self:
            if field_defn.key:
                ordering, position = field_defn.key   # ('ASC'|'DESC', int)
                pk_entries.append((position, ordering, field_defn.name))
            wrk = field_defn.to_sql_create(self._frmt, single_pk)
            if wrk:
                sql_defns += wrk
        sql += sql_defns
        if other:
            sql += other
        # ----- Validate & order the primary-key columns -----
        keys: list[str] = []
        if pk_entries and not single_pk:
            positions = [p for p, _, _ in pk_entries]
            use_defn_order = any(p == 0 for p in positions)

            if use_defn_order:
                # Rule: if *any* position is 0 then *all* must be 0
                if not all(p == 0 for p in positions):
                    raise ValueError(
                        "Primary-key positions: if any key has position 0 "
                        "(definition order), then every key must have position 0. "
                        f"Got positions: {positions}"
                    )
                # Keep the order they appeared in the field list
                ordered = pk_entries
            else:
                # Explicit positions must be exactly 1..N with no gaps/duplicates
                n = len(pk_entries)
                expected = list(range(1, n + 1))
                if sorted(positions) != expected:
                    raise ValueError(
                        "Primary-key positions must be the contiguous sequence "
                        f"1..{n} with no duplicates. Got: {sorted(positions)}"
                    )
                # Sort by the explicit position
                ordered = sorted(pk_entries, key=lambda t: t[0])

            for _, ordering, name in ordered:
                if self.frmt == SQL_Format.SQLITE:
                    keys.append(f"`{name}` {ordering}")
                else:
                    keys.append(f"{name} {ordering}")

        # ----- Finish the statement -----
        # Ensure we have a trailing comma before PRIMARY KEY / closing paren
        # (column defs already end with ',\n')
        if sql.endswith(',\n'):
            pass
        else:
            sql = sql.removesuffix('\n') + ',\n'

        if keys and not single_pk:
            sql += f"\tPRIMARY KEY({', '.join(keys)})\n"

        if sql.endswith(',\n'):
            sql = sql.removesuffix(',\n') + '\n'
        sql += ');\n'

        return sql


    def to_sql_insert(
            self,
            table_name: str,
            other: Optional[str] = None
        ) -> str:
        """
        Return a parameterized INSERT statement.

        AUTOINCREMENT / serial primary-key columns are omitted from the
        column list (the database will supply the value).
        """
        match self._frmt:
            case SQL_Format.SQLITE:
                sql = f"INSERT INTO `{table_name}` ( "
                q = lambda n: f"`{n}`"
            case _:
                sql = f"INSERT INTO {table_name} ( "
                q = lambda n: n

        labels = []
        placeholders = []
        for fd in self:
            name = fd.name
            if not name:
                continue
            # Skip autoincrement primary-key columns
            if fd.key is not None and fd.auto:
                continue
            labels.append(q(name))
            placeholders.append('?')

        sql += ', '.join(labels)
        sql += f" )\n\tVALUES ( {', '.join(placeholders)} );\n"
        return sql


    def to_sql_update(
            self,
            table_name: str,
            other: Optional[str] = None
        ) -> str:
        """
        Return a parameterized UPDATE statement.

        SET clause contains every non-key column; WHERE uses the primary-key
        column(s) in definition / key-position order. Pair with
        field_defns_to_sql_params(..., for_update=True) which supplies
        non-key values first, then key values.
        """
        match self._frmt:
            case SQL_Format.SQLITE:
                sql = f"UPDATE `{table_name}` SET\n"
                q = lambda n: f"`{n}`"
            case _:
                sql = f"UPDATE {table_name} SET\n"
                q = lambda n: n

        set_parts = []
        where_parts = []
        for fd in self:
            name = fd.name
            if not name:
                continue
            if fd.key is not None:
                where_parts.append(f"{q(name)}=?")
            else:
                set_parts.append(f"\t{q(name)}=?")

        if not set_parts:
            raise ValueError("UPDATE needs at least one non-key column")
        if not where_parts:
            raise ValueError(
                "UPDATE needs at least one primary-key column for the WHERE clause"
            )

        sql += ',\n'.join(set_parts) + '\n'
        sql += '  WHERE ' + ' AND '.join(where_parts) + ';\n'
        return sql


    def to_dc(self) -> list[dict]:
        """ Convert Field Definitions to Data Class definitions
        """
        sql_defns = []
        for field_defn in self:
            wrk = field_defn.to_dc()
            if wrk:
                sql_defns.append(wrk)
        return sql_defns


    def generate_dataclass(self, cls_name: str = 'Record'):
        """
        Dynamically create a @dataclass from the field definitions.
        """
        dc_fields = []
        for fd in self:
            spec = fd.to_dc()
            if not spec:
                continue
            # spec is [name, type, field(...)]
            dc_fields.append((spec[0], spec[1], spec[2]))

        return make_dataclass(
            cls_name,
            dc_fields,
            repr=True,
            eq=True,
            order=False,
            frozen=False,
        )


    def validate(self) -> None:
        """ Validate that the field definitions are correct for the specified SQL format.
        """
        if not self:
            raise ValueError("Field_Defns is empty")

        seen_names: set[str] = set()
        seen_seqnos: set[int] = set()
        has_seqno = False
        pk_count = 0
        has_int_pk = False

        for i, fd in enumerate(self):          # explicit enumerate is clearer
            # --- basic required fields ---
            if not fd.name:
                raise ValueError(f"[{i}] Missing name")
            if fd.name.lower() == 'filler':
                pass
            elif fd.name in seen_names:
                raise ValueError(f"[{i}] Duplicate name: {fd.name!r}")
            seen_names.add(fd.name)

            if fd.type == Data_Type.UNKNOWN:
                raise ValueError(f"[{i}] ({fd.name}) Missing type")
            if fd.type >= Data_Type.COUNT:
                raise ValueError(f"[{i}] ({fd.name}) Invalid type: {fd.type}")

            # --- primary key tracking ---
            if fd.key:
                if fd.type == Data_Type.INTEGER and self.frmt == SQL_Format.SQLITE:
                    has_int_pk = True
                pk_count += 1

            # --- seqno / csv handling ---
            if fd.seqno is not None:           # allow seqno == 0
                has_seqno = True
                if fd.seqno in seen_seqnos:
                    raise ValueError(f"[{i}] ({fd.name}) Duplicate seqno: {fd.seqno}")
                seen_seqnos.add(fd.seqno)

                if not getattr(fd, "name", None):
                    raise ValueError(
                        f"[{i}] ({fd.name}) has seqno={fd.seqno} but is missing name"
                    )

            # --- Fixed Record Handling ---
            if fd.fixed_start or fd.fixed_end:
                if not (fd.fixed_start and fd.fixed_end):
                    raise ValueError(f"fixed_start and fixed_end must both be present for {fd.name}")
                if (fd.fixed_end - fd.fixed_start + 1) > 0:
                    pass
                else:
                    raise ValueError(f"(fixed_end - fixed_start + 1) must be > 0 for {fd.name}")


        # --- cross-field rules ---
        if has_seqno and not self.allow_no_seqno:
            for i, fd in enumerate(self):
                # SQLite INTEGER PRIMARY KEY is an alias for rowid — often has no CSV column
                if (fd.key and pk_count == 1 and has_int_pk):
                    continue

                if fd.seqno is None:
                    raise ValueError(f"[{i}] ({fd.name}) Missing seqno (other fields have them)")

        if pk_count == 0:
            # optional — only raise if you require a primary key
            # raise ValueError("No primary key defined")
            pass
        elif pk_count > 1 and self.frmt == SQL_Format.SQLITE:
            # SQLite allows composite keys, but your rowid helpers assume a single INTEGER PK
            pass  # or warn / raise depending on your design


#-------------------------------------------------------------------------------
#               Convert some Field Definitions to DataClass
#-------------------------------------------------------------------------------

# p = Property(...)                    # your dataclass instance
# data_dict = asdict(p)


def dict_to_dataclass(cls, data: dict):
    """ Convert dict to dataclass instance, ignoring extra keys.
        Usage:
            p = dict_to_dataclass(Property, data_dict)
    """
    from dataclasses import fields
    # Only pass fields that exist in the dataclass
    field_names = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in data.items() if k in field_names}
    return cls(**filtered)







