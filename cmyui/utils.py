# -*- coding: utf-8 -*-

from collections import namedtuple
from functools import wraps
from typing import Callable
from enum import IntEnum
from time import time_ns
from string import ascii_letters, digits
from random import choice
from datetime import (
    datetime as dt,
    timezone as tz,
    timedelta as td
)

__all__ = ('get_timestamp', '_isdecimal', 'rstring',
           'async_cache', 'TimeScale', 'timef')

ts_fmt = ('%I:%M:%S%p', '%d/%m/%Y %I:%M:%S%p')
tz_est = tz(td(hours = -5), 'EST') # TODO: fix for edt switch lol
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

_CacheStats = namedtuple('CacheStats', ['hits', 'misses'])

def _make_key(args, kwargs):
    """Get a hashed value out of args & kwargs."""
    key = args

    if kwargs:
        for item in kwargs.items():
            key += item

    return hash(key)

def async_cache(f):
    """Lightweight unbounded async function cache."""
    cache = {}
    hits = misses = 0

    @wraps(f)
    async def wrapper(*args, **kwargs):
        key = _make_key(args, kwargs)

        if key in cache:
            nonlocal hits
            hits += 1

            val = cache[key]
        else:
            nonlocal misses
            misses += 1

            val = await f(*args, **kwargs)
            cache[key] = val

        return val

    def cache_clear():
        nonlocal hits, misses
        hits = misses = 0
        cache.clear()

    def cache_stats():
        nonlocal hits, misses
        return _CacheStats(hits, misses)

    wrapper.cache_clear = cache_clear
    wrapper.cache_stats = cache_stats
    return wrapper

class TimeScale(IntEnum):
    Years = 0
    Months = 1
    Days = 2
    Hours = 3
    Minutes = 4
    Seconds = 5
    Milliseconds = 6
    Microseconds = 7
    Nanoseconds = 8

Call = namedtuple('CallEvent', ['duration', 'time',
                                'args', 'kwargs'])

timescale_divisor = lambda ts: { # lol
    TimeScale.Years: 1000 * 1000 * 1000 * 60 * 60 * 24 * 365,
    TimeScale.Months: 1000 * 1000 * 1000 * 60 * 60 * 24 * 30,
    TimeScale.Days: 1000 * 1000 * 1000 * 60 * 60 * 24,
    TimeScale.Hours: 1000 * 1000 * 1000 * 60 * 60,
    TimeScale.Minutes: 1000 * 1000 * 1000 * 60,
    TimeScale.Seconds: 1000 * 1000 * 1000,
    TimeScale.Milliseconds: 1000 * 1000,
    TimeScale.Microseconds: 1000,
    TimeScale.Nanoseconds: 1
}[ts]

def timef(f: Callable):
    calls: list[Call] = []

    @wraps(f)
    def wrapper(*args, **kwargs):
        # all timing is done in nanoseconds,
        # conversion will be done later when
        # displaying data.
        start = time_ns() # start clock
        result = f(*args, **kwargs) # run func
        end = time_ns() # stop clock

        duration = end - start

        # add to times log
        nonlocal calls
        calls.append(Call(duration, end, args, kwargs))

        return result

    def average(ts: TimeScale = TimeScale.Milliseconds):
        nonlocal calls
        total = sum([c.duration for c in calls])
        average = total / len(calls)
        return average / timescale_divisor(ts)

    wrapper.calls = calls # maybe temp?
    wrapper.average = average
    return wrapper
