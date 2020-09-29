# -*- coding: utf-8 -*-

import sys
from enum import IntEnum
from string import ascii_letters, digits
from random import choice
from datetime import (
    datetime as dt,
    timezone as tz,
    timedelta as td
)

__all__ = ('get_timestamp', 'isfloat', 'rstring', 'Ansi', 'printc')

ts_fmt = ('%I:%M:%S%p', '%d/%m/%Y %I:%M:%S%p')
tz_est = tz(td(hours = -4), 'EDT')
def get_timestamp(full: bool = False) -> str:
    return f'{dt.now(tz = tz_est):{ts_fmt[full]}}'

def isfloat(s: str) -> bool:
    return s.replace('.', '', 1).isdecimal()

__chars = ascii_letters + digits
def rstring(l: int, seq: str = __chars) -> str:
    return ''.join((choice(seq) for _ in range(l)))

class Ansi(IntEnum):
    # Default colours
    BLACK   = 30
    RED     = 31
    GREEN   = 32
    YELLOW  = 33
    BLUE    = 34
    MAGENTA = 35
    CYAN    = 36
    WHITE   = 37

    # Light colours
    GRAY          = 90
    LIGHT_RED     = 91
    LIGHT_GREEN   = 92
    LIGHT_YELLOW  = 93
    LIGHT_BLUE    = 94
    LIGHT_MAGENTA = 95
    LIGHT_CYAN    = 96
    LIGHT_WHITE   = 97

    RESET = 0

    def __repr__(self) -> str:
        return f'\x1b[{self.value}m'

def printc(s: str, col: Ansi) -> None:
    # abstract the ugliness of colour codes away a bit.
    sys.stdout.write(f'{col!r}{s}{Ansi.RESET!r}\n')
