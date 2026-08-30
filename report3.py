#!/usr/bin/env python3
# vi:nu:et:sts=4 ts=4 sw=4


"""
Merchant -> Category -> Subcategory -> Date Report with Subtotals
Uses rw_rpg.py + rw_sqlite.py

Notes:
    *   Input consists of an SQLite csv that was output as a temporary file.
"""

import os
import sys
from decimal import Decimal
from datetime import date

import cmnUtil
import rw_rpg 
from   rw_sqlite import Database, Table

scripts = cmnUtil.absolute_path('./scripts')
if os.path.exists(scripts):
    sys.path.insert(0, scripts)
else:
    print("FATAL: Did not find './scripts' which is needed!")
    sys.exit(16)
#print(f"PythonPath: {sys.path}")
import  db_defs


db_path = './db.sqlite3'
table_name = 'items'
records = None
num_records: int = 0
cur_record:  int = 0




class Report(rw_rpg.RPG):
    def __init__(self):
        super().__init__()

        def header(r, ld):
            print(f"\n========== {ld['name']} - {ld['data']} HEADER BREAK  ==========")

        def trailer1(r, ld):
            print(f"---------- {ld['name']} - {ld['prev']} Merchant Total: {ld['total']/100} Count: {ld['count']} ----------\n")

        def trailer2(r, ld):
            print(f"---------- {ld['name']} - {ld['prev']} Category Total: {ld['total']/100} Count: {ld['count']} ----------\n")

        def trailer3(r, ld):
            print(f"---------- {ld['name']} - {ld['prev']} Subcategory Total: {ld['total']/100} Count: {ld['count']} ----------\n")

        def lr_trailer(r, ld):
            print(f"---------- {ld['name']} - {ld['prev']} GRAND TOTAL: {ld['total']/100} Count: {ld['count']} ----------\n")
        #              level,      index,           calc, header, trailer
        self.setup_level(1, db_defs.csv_items.MERCH+1, None, None,  trailer1)
        self.setup_level(2, db_defs.csv_items.CAT+1, None, None,  trailer2)
        self.setup_level(3, db_defs.csv_items.SUB+1, None, None,  trailer3)
        #self.setup_level(3, db_defs.csv_items.DATE+1, None, None, trailer)
        self.levels[self.lvl_lr]['trailer'] = lr_trailer
        self.tindex = db_defs.csv_items.AMT
        self.flg_detail = True
        # setup the SQLite3 Interface
        self.db = Database(db_path)
        if self.db:
            self.tbl = Table(self.db, table_name)
            self._iter = None                     # will hold a cursor for sequential read

    def read_next_record(self):
        row = None
        if self.db and self.tbl:
            if self._iter is None:
                cur = self.db.execute(f"SELECT * FROM {self.tbl.name} ORDER BY merch,cat,sub,date")
                self._iter = cur
            row = self._iter.fetchone()
            if row is None:
                self._iter.close()
                self._iter = None
        return row

    def p1_output(self): 
        print("========= Category, Subcategory Report =========\n")

    def detail_output(self, record):
        if self.flg_detail:
            print(f"  → {record[db_defs.csv_items.DATE]} {record[db_defs.csv_items.CAT]} {record[db_defs.csv_items.SUB]} {record[db_defs.csv_items.AMT]/100} {record[db_defs.csv_items.DESC]}")





################################################################################
#                           Command-line interface
################################################################################

if __name__ == '__main__':
    rpt = Report()
    if rpt:
        #rw_rpg.flg_debug = True
        #rpt.flg_detail = False
        rpt.run()
        sys.exit(0)
    sys.exit(4)


