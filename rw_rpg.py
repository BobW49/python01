#!/usr/bin/env python3
# vi:nu:et:sts=4 ts=4 sw=4

"""
This object supports generating an IBM System 3/Burroughs 1700 like RPG II 
program reports. We have slightly altered the algorithm to conform to RPG 
IV. When a 'step' is noted in the comments, it is from the RPG IV flowchart. 
See ILE RPG Reference.

Each level is self-contained in self.levels. The 'index' field indicates
if the level is active or not. Level 1, L1, is the highest level; Level
2, L2, is the second highest; ... If level breaks are used, you must start
at the highest and go down in priority. Otherwise, the algorithm will not
work properly. Any level indicator which is 0 or None means that a no
operation is use for that phase whatever that field controlled.

The main run-time has look-ahead for the input record. The current record
is in self.record and the next record is in self.next_record. If the next
record is None, the end-of-file has occurred (ie LR).

NOTES:
    *   This does NOT support multiple input files nor MR.
    *   This does NOT support Halt Indicators, Hn.
    *   This does NOT support Overflow and associated indicators.
    *   This does NOT support RT indicator.
    *   This does NOT support Execute Support.
    *   You must supply all file output including printing.

"""

from __future__ import annotations
from enum import IntEnum
from typing import Callable, ClassVar, List, Dict, Any, Optional, Sequence, Tuple



flg_debug = False



#=====================================================================
#               Report Program Generator (RPG) Class
#=====================================================================

class RPG:
    """
    """
    lvl_max: ClassVar[int] = 4          # Maximum number of Levels in the input
    lvl_lr:  ClassVar[int] = 0          # LR level in levels 
    lvl_1st: ClassVar[int] = 1          # L1 level index in levels
    # Forward Levels: range(self.lvl_1st, self.lvl_max+1, 1)    [1, 2, 3, 4]
    # Reverse Levels: range(self.lvl_max, self.lvl_lr, -1)      [4, 3, 2, 1]
    tindex:  ClassVar[Optional[int]] = None        
                                        # tindex to field in a record which is used
                                        # for constructing totals. 0 means no field
                                        # is to be used. This should be set before 
                                        # run().
    record_size: ClassVar[Optional[int]] = None   
                                        # Number of fields in the input records
                                        # If this is not set before run(), then
                                        # it will be taken from the first record
                                        # read.
    # The following Class Variables should not be written to by inheriting routines
    # since the internal logic depends on them.
    lindex: ClassVar[Optional[int]] = None
                                        # Lowest level active level break set and
                                        # used by run() (relative to 1)
    record: ClassVar[Optional[Sequence[Any]]] = None
                                        # Current Input Record (tuple or list)
    next_record: ClassVar[Optional[Sequence[Any]]] = None
                                        # Look Ahead Input Record
                                        # If None, indicates EOF (ie LR)
    first_page: ClassVar[bool] = True   # First Page Indicator
    first_time: ClassVar[bool] = True   # First time
    lr: ClassVar[bool] = False          # Last Record has been reached
    mr: ClassVar[bool] = False          # Matching Record when handling multiple files
    eof: ClassVar[bool] = False         # Last Record of all inputs marked with E
    #                                   # has been reached
    loop_max: ClassVar[int] = 50000     # Run Loop Maximum to control run-away loop
    
    def __init__(self, lvl_max: int = 4) -> None:
        self.lvl_max = lvl_max
        self.levels: List[Dict[str, Any]] = [
            {
                # LR is the highest priority level. Therefore, it is first in levels.
                # L1...L9 follow LR in that order. L9 being the lowest priority.
                #
                'level': idx,
                'name': f'L{idx}' if idx > self.lvl_lr else 'LR',
                'index': 0,             # Index into record for level break field
                                        # (relative to 1) 0 == level break is not
                                        # used
                'calc': None,
                'header': None,         # The header routine will receive one parm,
                                        # the level being printed. If it needs the
                                        # level data, it should use 'data'.
                'trailer': None,        # The trailer routine will receive one parm,
                                        # the level being printed. If it needs the
                                        # level data, it should use 'prev'.
                'data': None,           # Current Level Data (Lookahead - header)
                'prev': None,           # Previous Level Data (detail/trailer)
                'flag': False,          # True means Level Break
                'total': 0,             # Accumulator
                'count': 0,             # Record Count
            }
            for idx in range(self.lvl_max+1)      # '+ 1' accounts for LR
        ]
        self.flg_accum_all_levels = True


    # ------------------------------------------------------------------
    #               Public: Configure a level
    # ------------------------------------------------------------------
    def setup_level(
        self,
        level: int,
        index: int,
        calc: Optional[Callable[["RPG", Dict[str, Any]], None]] = None,
        header: Optional[Callable[["RPG", Dict[str, Any]], None]] = None,
        trailer: Optional[Callable[["RPG", Dict[str, Any]], None]] = None,
    ) -> None:
        if not 1 <= level <= self.lvl_max:
            raise ValueError(f"level must be 1 to {self.lvl_max}")
        if index < 0:
            raise ValueError("index >= 0")
        if self.record_size is not None and index > self.record_size:
            raise ValueError(f"index {index} exceeds record size {self.record_size}")   
        ld = self.levels[level]
        ld['index'] = index
        ld['calc'] = calc
        ld['header'] = header
        ld['trailer'] = trailer

    def setup_level_field( self, name: str = None, data = None) -> bool:
        """ Add a field to the level dictionary if it does not already
            exist.
            :return True if field was added
        """
        ld = self.levels[level - 1]
        if name in ld:
            return False
        ld[name] = data
        return True
    

    # ------------------------------------------------------------------
    #                           Core helpers
    # ------------------------------------------------------------------

    def _rpg_dump(self, hdr: str=None) -> None:
        """
        """
        if not flg_debug:
            return
        if hdr:
            print(hdr, file=sys.stderr)
        for i in range(0, self.lindex+1, 1):
            ld = self.levels[i]
            line1 = f"\t {ld['level']} {ld['name']} {ld['flag']} {ld['count']} {ld['total']}"
            line2 = f"{ld['level']} {ld['index']} {ld['prev']} {ld['data']}"
            print(f"{line1} {line2}", file=sys.stderr)
        print(f"\t lr: {self.lr}", file=sys.stderr)
        print(f"\t mr: {self.mr}", file=sys.stderr)
        print(f"\t eof: {self.eof}", file=sys.stderr)
        print(f"\t first_page: {self.first_page}", file=sys.stderr)
        print(f"\t first_time: {self.first_time}", file=sys.stderr)
        print(f"\t record: {self.record}", file=sys.stderr)
        print(f"\t next_record: {self.next_record}", file=sys.stderr)


    def _set_break_data(self, level: int):
        """ Set the data for a specific break level
        """
        if flg_debug:
            print(f"_set_break_data({level})", file=sys.stderr)
        ld = self.levels[level]
        idx = ld['index']
        if idx > 0:
            py_idx = idx - 1
        else:
            return False
        if py_idx >= len(self.next_record):
            return False
        if self.next_record is None: # or EOR
            new_val = None
        else:
            new_val = self.next_record[py_idx]
        ld['prev'] = ld['data']
        ld['data'] = new_val
        if flg_debug:
            print(f"\t break_data for {level}: {new_val}", file=sys.stderr)

    def _break_on(self, start_lvl: int) -> None:
        """ Set the break on for the specified level and every level
            below it in priority.
        """
        if flg_debug:
            print(f"_break_on({start_lvl})", file=sys.stderr)
        for i in range(start_lvl, self.lindex+1, 1):
            if flg_debug:
                print(f"\t Set break for {self.levels[i]['name']}", file=sys.stderr)
            self.levels[i]['flag'] = True
            self._set_break_data(i)

    def _is_eof(self) -> bool:
        """ Determine if EOF has been reached on all input files.
        """
        if flg_debug:
            print(f"_is_eof()", file=sys.stderr)
        # Right now, we only have one input file and EOF occurs
        # when self.next_record is None.
        if self.record is None:
            if flg_debug:
                print("\t Yes", file=sys.stderr)
            return True
        else:
            if flg_debug:
                print("\t No", file=sys.stderr)
            return False

    def _reset_level_breaks(self) -> None:
        """ Turn off all level breaks except LR, 
            but do not affect the level data nor
            the counts/totals.
        """
        if flg_debug:
            print("_reset_level_breaks()", file=sys.stderr)
        for i in range(self.lindex, self.lvl_lr, -1):
            ld = self.levels[i]
            ld['flag'] = False
            if flg_debug:
                print(f"\t reset break for {ld['name']}", file=sys.stderr)

    def _set_level_breaks(self) -> None:
        """ Turn on all level breaks except LR, 
            but do not affect the level data nor
            the counts/totals.
        """
        if flg_debug:
            print("_set_level_breaks()", file=sys.stderr)
        for i in range(self.lindex, self.lvl_lr, -1):
            ld = self.levels[i]
            ld['flag'] = True
            if ld['data'] is not None:
                ld['prev'] = ld['data']
                ld['data'] = None
            if flg_debug:
                print(f"\t set break for {ld['name']}", file=sys.stderr)

    def _build_level_data(self, level: int) -> list: 
        """ Given the current level, build a list of the
            data at the current level and above.
            This routines is normally called within the
            header or trailer methods within this class.
        """
        if flg_debug:
            print(f"_build_level_data({level})", file=sys.stderr)
        # Scan from lowest level to highest level.
        level_data = []
        for i in range(self.lvl_1st, level+1, 1):
            ld = self.levels[i]
            if ld['data']:
                if flg_debug:
                    print(f"\t adding {ld['data']} to level_data", file=sys.stderr)
                level_data.append(ld['data'])
        if flg_debug:
            print(f"\t level_data: {level_data}", file=sys.stderr)
        return level_data

    def _build_level_prev(self, level: int) -> list: 
        """ Given the current level, build a list of the
            previous data at the current level and above.
            This routine is normally called within the
            header or trailer methods within this class.
        """
        if flg_debug:
            print(f"_build_level_prev({level})", file=sys.stderr)
        # Scan from lowest level to highest level.
        level_prev = []
        for i in range(self.lvl_1st, level+1, 1):
            ld = self.levels[i]
            if ld['prev']:
                if flg_debug:
                    print(f"\t adding {ld['prev']} to level_prev", file=sys.stderr)
                level_prev.append(ld['prev'])
        if flg_debug:
            print(f"\t level_prev: {level_prev}", file=sys.stderr)
        return level_prev

    def _check_for_level_break(self, level: int, force=False) -> bool:
        """ 
        Check for a level break on the specified level.
        :parm   level is the level number relative to 1
        :return True if a level break occurred for this level
        """
        if flg_debug:
            print(f"_check_for_level_break({level})", file=sys.stderr)
        ld = self.levels[level]
        idx = ld['index']
        if idx == 0 or self.record is None: # EOF
            return False
        py_idx = idx - 1
        if py_idx >= len(self.record): # Index is out of range
            return False
        new_val = self.record[py_idx]
        if ld['data'] is None or ld['data'] != new_val or force:
            ld['prev'] = ld['data']
            ld['data'] = new_val
            ld['flag'] = True
            if flg_debug:
                print(f"Set level break for: {ld['name']}", file=sys.stderr)
            # Force lower priority level breaks as well.
            if self.lvl_lr < level+1 < self.lindex:
                self._check_for_level_break(level+1, True)
            return True
        return False

    def _detect_all_breaks(self) -> bool:
        """ Detect all level breaks and set
            flags appropriately.
            :return True if a level break occurred
        """ 
        if flg_debug:
            print("_detect_all_breaks()", file=sys.stderr)
        fRc = False
        for lvl in range(self.lindex, self.lvl_lr, -1):
            self._check_for_level_break(lvl)
            if flg_debug:
                print(f"\t break on for {lvl}", file=sys.stderr)
            fRc = True
        return fRc

    def _detail_read_next(self) -> None:
        """ Transfer the lookahead record to the
            current record position, read the next 
            record.
            :returns    True if EOF reached
        """
        self.record = self.next_record
        fRc = False
        if flg_debug:
            print("_detail_read_next()", file=sys.stderr)
        self.next_record = self.read_next_record()
        if self.record is None:        # EOF
            if flg_debug:
                print("\t EOF on current record", file=sys.stderr)
            fRc = True
        else:
            if not isinstance(self.record, (tuple, list)):
                raise TypeError("Record must be tuple or list")
            size = len(self.record)
            if self.record_size is None:
                self.record_size = size
            elif size != self.record_size:
                raise ValueError(
                    f"Record size mismatch: expected {self.record_size}, got {size}\n"
                    f"  Record: {self.record}"
                )
            if flg_debug:
                print(f"\t record: {self.record}", file=sys.stderr)
        return fRc

    def _run_level_calcs(self) -> None:
        """ Run all calculations for the levels starting at the 
            lowest priority level upward.
        """
        if flg_debug:
            print("_run_level_calcs()")
        for i in range(self.lindex, self.lvl_lr, -1):
            ld = self.levels[i]
            if ld['flag'] and ld['calc']:
                if flg_debug:
                    print(f"\t running calc() for {ld['name']}", file=sys.stderr)
                ld['calc'](self, ld, self.record)

    def _run_headers(self) -> None:
        """ Run all the headers from the highest priority
            level downward. Headers should use 'data' to
            identify what changed.
        """
        if flg_debug:
            print("_run_headers()", file=sys.stderr)
        for i in range(self.lvl_1st, self.lindex+1, 1):
            ld = self.levels[i]
            if ld['flag'] and ld['header']:
                if flg_debug:
                    print(f"\t running header() for {ld['name']}", file=sys.stderr)
                #ld['header'](self, ld)
                ld['header'](ld)

    def _run_trailers(self) -> None:
        """ Print trailers from lowest priority to highest
            upward whose levels are broken. Trailers use 
            'prev' for identifying what changed.
        """
        if flg_debug:
            print("_run_trailers()", file=sys.stderr)
        # L4 → L1
        if self.flg_accum_all_levels:
            for i in range(self.lindex, self.lvl_lr, -1):
                ld = self.levels[i]
                if not ld['flag']:
                    continue
                # Print trailer if present
                if ld['trailer']:
                    if flg_debug:
                        print(f"\t running trailer() for {ld}", file=sys.stderr)
                    prevs = self._build_level_prev(i)
                    ld['trailer'](ld, prevs)
                # Zero this level and below.
                for j in range(i, self.lindex+1, 1):
                    ld = self.levels[j]
                    ld['count'] = 0
                    ld['total'] = 0
        else:
            for i in range(self.lindex, self.lvl_lr, -1):
                ld = self.levels[i]
                if not ld['flag']:
                    continue
                # Print trailer if present
                if ld['trailer']:
                    if flg_debug:
                        print(f"\t running trailer() for {ld['name']}", file=sys.stderr)
                    prevs = self._build_level_prev(i)
                    ld['trailer'](ld, prevs)
                # Accumulate Totals in parent and zero in base level.
                ldp = self.levels[i-1]
                if flg_debug:
                    print(f"\t accum totals for {ld['name']} in {ldp['name']}", file=sys.stderr)
                    print(f"\t resut totals for {ld['name']}", file=sys.stderr)
                ldp['count'] += ld['count']
                ld['count'] = 0
                ldp['total'] += ld['total']
                ld['total'] = 0
        lr = self.levels[self.lvl_lr]
        if self.lr and lr['trailer']:
            if flg_debug:
                print(f"\trunning trailer() for LR", file=sys.stderr)
            lr['trailer'](lr, None)


    # ------------------------------------------------------------------
    #                           Hooks
    # ------------------------------------------------------------------

    def read_next_record(self) -> Optional[List,Tuple]:
        """ Read the next record from the Input File into self.next_record.
        """
        raise NotImplementedError("Subclass must implement read_next_record()")

    def detail_calc(self, record=None) -> None:
        """ Perform detail calculations accumulating to the lowest
            priority level. This can be over-ridden, but it is suggested
            to pass total up the level chain.
        """
        if flg_debug:
            print(f"detail_calc({record})", file=sys.stderr)
        amt = 0
        if self.tindex and record is not None:
            amt = int(record[self.tindex])
            if flg_debug:
                print(f"\t amt: {amt}", file=sys.stderr)
        if self.flg_accum_all_levels:
            for i in range(self.lindex, -1, -1):
                ld = self.levels[i]
                ld['count'] += 1
                ld['total'] += amt
        else:
            if self.lindex:
                ld = self.levels[self.lindex]
                ld['count'] += 1
                ld['total'] += amt
                if flg_debug:
                    print(f"\t count: {ld['count']} total: {ld['total']}", file=sys.stderr)

    def detail_output(self, record=None) -> None:
        """ Output the detail line given the data from the given record.
        """
        pass

    def p1_output(self) -> None:
        """ P1 time is for printing a separator page. If you are printing multiple
            reports, this can be handy to know where each report begins. It is
            optional. If present, a new page will be forced upon its return.
        """
        pass


    # ------------------------------------------------------------------
    #                       The Main RPG Cycle
    # ------------------------------------------------------------------


    def run(self) -> None:
        """ This is the main run loop. It is loosely based on RPG IV
            Program Cycle described in "ILE RPG Reference"
            All Class Variables should be set up by now except the ones 
            controlled by this method.
        """
        # This is used to control the run() state machine.
        # This is necessary because python does not support
        # a goto statement. However, it does support 
        # match/case which is ideal for state machines.
        class rpg_state(IntEnum):
            STEP04_STATE=1,
            STEP14_STATE=2,
            STEP24_STATE=3,
            STEP29_STATE=4,
            STEP30_STATE=5, 
            STEP31_STATE=6, 
            STEP32_STATE=7, 
            STEP33_STATE=8, 
            STEP41_STATE=9,

        current_state: int = rpg_state.STEP04_STATE
        loop_flag: bool = True
        loop_count: int = 0
        if flg_debug:
            print("Run()", file=sys.stderr)

        # Calculate lowest priority active level break to be used.
        self.lindex = 0
        for i in range(self.lvl_max, self.lvl_lr, -1):
            ld = self.levels[i]
            if ld['index']:
                self.lindex = i
                break
        if flg_debug:
            print(f"\tlindex: {self.lindex} - {self.levels[self.lindex]['name']}", file=sys.stderr)
        if self.lindex == 0:
            raise ValueError("lindex must be greater than 0!")

        if self.first_page and self.p1_output:
            self.p1_output()

        # Step 3 Addition - Ln and LR default to off.

        # Prime the lookahead input system.
        self.eof = self._detail_read_next()

        while loop_flag:
            # Note: First time through, there will be a look-ahead record,
            #       but there will NOT be a detail record.
            if self.loop_max > 0:
                loop_count += 1
                if flg_debug:
                    print(f"WHILE LOOP - {loop_count}", file=sys.stderr)
                if loop_count > self.loop_max:
                    raise RecursionError(f"loop_count, {loop_count}, exceeded maximum of {self.loop_max}!")

            # State Machine to simulate the Detailed RPG Cycle as defined
            # in the ILE RPG Reference
            match current_state:

                case rpg_state.STEP04_STATE:
                    # Step 4 - Header/Detail Output
                    # In the real RPG, headers and trailers can optionally be
                    # controlled by indicators optionally. If it is not con-
                    # trolled by indicators, then it is printed everytime in
                    # header/trailer time not just on control breaks.
                    if flg_debug:
                        self._rpg_dump('STEP04_STATE')
                    if any(ld['flag'] for ld in self.levels[:self.lvl_max]):
                        self._run_headers()
                    if self.record is None or self.first_time:
                        pass
                    else:
                        self.detail_output(self.record)
                    self.first_page = False

                    # Step 5 .. Step 7 - skipped

                    # Step 8 - Set off L1-L9.
                    self._reset_level_breaks()

                    # Step 9
                    if self.lr:
                        self._set_level_breaks()                # Step 10
                        current_state = rpg_state.STEP29_STATE
                        continue
                    current_state = rpg_state.STEP14_STATE
                    continue

                case rpg_state.STEP14_STATE:                    # Step 14
                    # If first time, read one record from the primary file
                    # and each secondary file. In other program cycles, a
                    # record is read from the last file processed. If this
                    # file processed by a record address file, the data in
                    # the record address file defines the record to be
                    # retrieved.
                    # Right now, all input is from the primary file and
                    # record address files are not supported.
                    if flg_debug:
                        self._rpg_dump('STEP14_STATE')
                    if self.first_time:
                        self._detail_read_next()
                    else:
                        self.eof = self._detail_read_next()
                    if self.next_record is None or self.eof:    # Step 16
                        pass                                    # Step 17
                    current_state = rpg_state.STEP24_STATE
                    continue

                case rpg_state.STEP24_STATE:                    # Step 24
                    if flg_debug:
                        self._rpg_dump('STEP24_STATE')
                    # Check to see if LR should be set.
                    if self._is_eof():
                        self.lr = True                          # Step 25
                        self.levels[self.lvl_lr]['flag'] = True
                        self._set_level_breaks()
                        current_state = rpg_state.STEP29_STATE
                        continue
                    # The record identifying indicator is       # Step 26
                    # set for the record being processed.
                    # Determine if the record selected          # Step 27
                    # caused a level break.
                    self._reset_level_breaks()                  # Step 28
                    self._detect_all_breaks()
                    #self._save_level_data()    # Included in _detect_all_breaks() 
                    current_state = rpg_state.STEP29_STATE
                    continue

                        
                case rpg_state.STEP29_STATE:                    # Step 29
                    if flg_debug:
                        self._rpg_dump('STEP29_STATE')
                    # Check if Total Processing should occur.
                    fRc = False
                    if self.record is not None or self.lr:
                        fLevels = any(ld['flag'] for ld in self.levels)
                        if self.lr:
                            fRc = True
                        if self.first_time and self.lindex == 0:
                            pass
                        else:
                            fRc = True
                    if fRc:
                        if flg_debug:
                            print('\t next: STEP30_STATE', file=sys.stderr)
                        current_state = rpg_state.STEP30_STATE
                    else:
                        if flg_debug:
                            print('\t next: STEP32_STATE', file=sys.stderr)
                        current_state = rpg_state.STEP32_STATE
                    continue

                case rpg_state.STEP30_STATE:                    # Step 30 - TOTC
                    if flg_debug:
                        self._rpg_dump('STEP30_STATE')
                    if not self.first_time:
                        self._run_level_calcs()
                    current_state = rpg_state.STEP31_STATE
                    continue

                case rpg_state.STEP31_STATE:                    # Step 31 - TOTL
                    if flg_debug:
                        self._rpg_dump('STEP31_STATE')
                    if not self.first_time:
                        self._run_trailers()
                    current_state = rpg_state.STEP32_STATE
                    continue

                case rpg_state.STEP32_STATE:                    # Step 32
                    if flg_debug:
                        self._rpg_dump('STEP32_STATE')
                    if self.lr:                                 # Step 32
                        # Handle EOJ processing                 # Step 33
                        loop_flag = False
                    current_state = rpg_state.STEP41_STATE
                    continue

                case rpg_state.STEP41_STATE:
                    if flg_debug:
                        self._rpg_dump('STEP41_STATE')
                    # Step 41 ignored for now
                    # Step 42 ignored for now
                    # Step 43 Set MR on or off according to input.
                    self.mr = False                             # Step 43 (limited)
                    # Step 44 ignored for now
                    # Step 45 ignored for now
                    # Step 46 ignored for now
                    self.detail_calc(self.record)               # Step 47 - DETC
                    self.first_time = False
                    current_state = rpg_state.STEP04_STATE
                    continue

        if flg_debug:
            print('***End of Loop ***')





#=====================================================================
#       Report Program Generator (RPG) Thread Class
#=====================================================================


import threading
import queue
import time



class RPG_Engine(RPG):
    """
        This class allows you to run the RPG process in the background. 
        This may be advantageous
        if it is a long running task with lots of input or output. 
        If you supply an on_output(), the background thread also can
        accumulate the output of the RPG so that it can be sent to a 
        file or whatever is needed. The RPG ouput in this situation
        would use emit() instead of print().

        Overview:

        [Main Thread]                       [RPG Thread]
        │                                   │
        ├─engine.thread_start()  ───▶       │   Creates Queue and sets up background thread
        │                                   │
        ├─thread_submit(rec)───▶            │   Queue ──▶ read_next_record() blocks
        │                                   │
        ├─submit_record(None)──▶            │   EOF ──▶ run() finishes
        │                                   │
        └─engine.thread_stop() ◀────────    │   joins thread
    """

    def __init__(self, lvl_max: int = 4):
        super().__init__(lvl_max)
        self.queue = queue.Queue()
        self.thread: Optional[threading.Thread] = None
        self.running = False
        # Optional: callback to send updates back to main thread (e.g. UI)
        self.on_update: Optional[Callable[[Dict], None]] = None
        self.on_complete: Optional[Callable[[], None]] = None
        self.on_output: Optional[Callable[[str], None]] = None

    def __del__(self):
        self.stop()

    def emit(self, line: str):
        """ Emit a line of ouput. Use of this method is optional.
            Using it allows one to control the output of the background
            thread so that it does not interfere with the foreground
            thread's output.
        """
        if self.on_output:
            self.on_output(line)
        else:
            print(line)

    def thread_start(self):
        """ Start the RPG worker thread.
            (Called from foreground thread)
        """
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def thread_stop(self):
        """ Gracefully stop the engine.
            (Called from foreground thread)
        """
        if not self.running:
            return
        self.running = False
        self.queue.put(None)  # Poison pill
        if self.thread:
            self.thread.join(timeout=2.0)

    def thread_submit(self, data: Any = None):
        """ Submit a command to the RPG engine.
            (Called from foreground thread)
        """
        if self.running:
            self.queue.put(data)

    def _worker(self):
        """ Internal worker loop — runs in background thread.
            Note: the notification methods, on_complete() and
                    on_output, also run in the background thread.
        """
        while self.running:
            try:
                self.run()
                if self.on_complete:
                    self.on_complete()
            except queue.Empty:
                # Allow idle processing (e.g. AI, timers)
                self._idle_update()
            except Exception as e:
                if self.on_output:
                    self.on_output(f"[ERROR] {e}")
                else:
                    print(f"[RPGEngine] Error: {e}")

    def _idle_update(self):
        """ Called every loop when no commands — for AI, timers, etc.
        """
        # Example: move enemies toward player
        for enemy in self.game_state["enemies"]:
            if enemy.get("ai") == "chase":
                px, py = self.game_state["player"]["x"], self.game_state["player"]["y"]
                ex, ey = enemy["x"], enemy["y"]
                if abs(px - ex) > abs(py - ey):
                    enemy["x"] += 1 if px > ex else -1
                else:
                    enemy["y"] += 1 if py > ey else -1
        time.sleep(0.01)  # Prevent busy-wait

    def read_next_record(self) -> Optional[Tuple]:
        """ Read the next record from the Input File into self.next_record.
        """
        next_record = None
        if self.running:
            try:
                record = self.input_queue.get(timeout=1.0)
                self.input_queue.task_done()
                return record
            except queue.Empty:
                return None  # Should not happen if managed properly        
        return next_record


''' Example 
def sample_report():
    engine = RPGEngine()

    # Optional: hook output
    def print_line(txt): print(txt)
    engine.on_output = print_line

    engine.on_complete = lambda: print_line("=== REPORT COMPLETE ===")

    # Start background processing
    engine.start()

    # Feed data (simulate file)
    records = [
        (1, "Alice", 100),
        (1, "Bob",   200),
        (2, "Carol", 150),
        (2, "Dave",  300),
        (3, "Eve",   400),
    ]

    for rec in records:
        engine.submit_record(rec)
        time.sleep(0.1)  # Simulate file I/O

    # Signal EOF
    engine.submit_record(None)
    engine.stop()  # Wait for finish
'''



################################################################################
#                           Command-line interface
################################################################################

if __name__ == '__main__':
    print("Error: Sorry, this module provides classes and functions for use by "
          "other scripts.")
    print("\tIt is not meant to be run by itself.")
    sys.exit(4)

