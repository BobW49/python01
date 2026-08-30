#!/usr/bin/env python3
# vi:nu:et:sts=4 ts=4 sw=4

"""Live tests for rw_rpg.RPG — control-break headers/trailers.
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.abspath('.'))

import rw_rpg


EXPECTED = """\
========== RPG II REPORT ==========
========== L1 - A Header Break  ==========
========== L2 - X Header Break  ==========
  → ('A', 'X', 10)
  → ('A', 'X', 20)
  → ('A', 'X', 30)
---------- L2 - X Trailer Count: 3 Total: 60 ----------
========== L2 - Y Header Break  ==========
  → ('A', 'Y', 30)
  → ('A', 'Y', 35)
---------- L2 - Y Trailer Count: 2 Total: 65 ----------
========== L2 - Z Header Break  ==========
  → ('A', 'Z', 55)
---------- L2 - Z Trailer Count: 1 Total: 55 ----------
---------- L1 - A Trailer Count: 6 Total: 180 ----------
========== L1 - B Header Break  ==========
========== L2 - X Header Break  ==========
  → ('B', 'X', 40)
  → ('B', 'X', 50)
  → ('B', 'X', 60)
  → ('B', 'X', 70)
---------- L2 - X Trailer Count: 4 Total: 220 ----------
========== L2 - Y Header Break  ==========
  → ('B', 'Y', 50)
---------- L2 - Y Trailer Count: 1 Total: 50 ----------
========== L2 - Z Header Break  ==========
  → ('B', 'Z', 50)
---------- L2 - Z Trailer Count: 1 Total: 50 ----------
---------- L1 - B Trailer Count: 6 Total: 320 ----------
---------- LR - None Grand Count: 12 Total: 500 ----------
"""


class Report(rw_rpg.RPG):
    """Same sample used by rw_rpg_test2.py."""

    def __init__(self):
        super().__init__()
        self.data = [
            ("A", "X", 10), ("A", "X", 20), ("A", "X", 30),
            ("A", "Y", 30), ("A", "Y", 35),
            ("A", "Z", 55),
            ("B", "X", 40), ("B", "X", 50), ("B", "X", 60), ("B", "X", 70),
            ("B", "Y", 50),
            ("B", "Z", 50),
        ]
        self.i = 0
        self.setup_level(1, 1, None, self.header, self.trailer)
        self.setup_level(2, 2, None, self.header, self.trailer)
        self.levels[self.lvl_lr]['trailer'] = self.lr_trailer
        self.tindex = 2

    def header(self, ld):
        print(f"========== {ld['name']} - {ld['data']} Header Break  ==========")

    def lr_trailer(self, ld, prevs):
        print(
            f"---------- {ld['name']} - {ld['prev']} "
            f"Grand Count: {ld['count']} Total: {ld['total']} ----------"
        )

    def read_next_record(self):
        if self.i >= len(self.data):
            return None
        rec = self.data[self.i]
        self.i += 1
        return rec

    def p1_output(self):
        print("========== RPG II REPORT ==========")

    def trailer(self, ld, prevs):
        print(
            f"---------- {ld['name']} - {ld['prev']} "
            f"Trailer Count: {ld['count']} Total: {ld['total']} ----------"
        )

    def detail_output(self, record):
        print(f"  → {record}")


class Test_Rpg_ControlBreaks(unittest.TestCase):

    def test_two_level_report_matches_golden(self):
        rw_rpg.flg_debug = False
        rpt = Report()
        rpt.loop_max = 150
        buf = io.StringIO()
        with redirect_stdout(buf):
            rpt.run()
        got = buf.getvalue()
        self.assertEqual(got, EXPECTED)

    def test_setup_level_rejects_bad_level(self):
        rpt = rw_rpg.RPG()
        with self.assertRaises(ValueError):
            rpt.setup_level(0, 1)
        with self.assertRaises(ValueError):
            rpt.setup_level(9, 1)

    def test_run_requires_an_active_level(self):
        class Empty(rw_rpg.RPG):
            def read_next_record(self):
                return None
        with self.assertRaises(ValueError):
            Empty().run()


if __name__ == '__main__':
    unittest.main()
