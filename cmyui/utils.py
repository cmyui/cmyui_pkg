# -*- coding: utf-8 -*-

from typing import Union, Final
from enum import IntEnum
from string import ascii_letters, digits
from random import choice
from datetime import (
    datetime as dt,
    timezone as tz,
    timedelta as td
)

__all__ = ('isnumeric_weak', 'rstring', 'Ansi', 'printc')

ts_fmt = ('%I:%M:%S%p', '%d/%m/%Y %I:%M:%S%p')
tz_est = tz(td(hours = -4), 'EDT')
def get_timestamp(full: bool = False) -> str:
    return f'{dt.now(tz = tz_est):{ts_fmt[full]}}'

def isnumeric_weak(s: str) -> bool:
    # isnumeric() which works with
    # negative numbers and floats.
    return s.replace('-', '', 1).replace('.', '', 1).isnumeric()

__chars = ascii_letters + digits
def rstring(l: int, seq: str = __chars) -> str:
    return ''.join((choice(seq) for _ in range(l)))

class Ansi(IntEnum):
    # Default colours
    BLACK: Final[int] = 30
    RED: Final[int] = 31
    GREEN: Final[int] = 32
    YELLOW: Final[int] = 33
    BLUE: Final[int] = 34
    MAGENTA: Final[int] = 35
    CYAN: Final[int] = 36
    WHITE: Final[int] = 37

    # Light colours
    GRAY: Final[int] = 90
    LIGHT_RED: Final[int] = 91
    LIGHT_GREEN: Final[int] = 92
    LIGHT_YELLOW: Final[int] = 93
    LIGHT_BLUE: Final[int] = 94
    LIGHT_MAGENTA: Final[int] = 95
    LIGHT_CYAN: Final[int] = 96
    LIGHT_WHITE: Final[int] = 97

    RESET: Final[int] = 0

    def __repr__(self) -> str:
        return f'\x1b[{self.value}m'

def printc(s: str, col: Ansi, *args, **kwargs) -> None:
    # abstract the ugliness of colour codes away a bit.
    print(f'{col!r}{s}{Ansi.RESET!r}', *args, **kwargs)
