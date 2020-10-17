# -*- coding: utf-8 -*-

from string import ascii_letters, digits
from random import choice
from datetime import (
    datetime as dt,
    timezone as tz,
    timedelta as td
)

__all__ = ('get_timestamp', '_isdecimal', 'rstring')

ts_fmt = ('%I:%M:%S%p', '%d/%m/%Y %I:%M:%S%p')
tz_est = tz(td(hours = -4), 'EDT')
def get_timestamp(full: bool = False) -> str:
    return f'{dt.now(tz = tz_est):{ts_fmt[full]}}'

def _isdecimal(s: str, _float: bool = False,
               _negative: bool = False) -> None:
    if _float:
        s = s.replace('.', '', 1)

    if _negative:
        s = s.replace('-', '', 1)

    return s.isdecimal()

__chars = ascii_letters + digits
def rstring(l: int, seq: str = __chars) -> str:
    return ''.join((choice(seq) for _ in range(l)))
