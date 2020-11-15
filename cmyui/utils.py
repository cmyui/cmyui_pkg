# -*- coding: utf-8 -*-

from collections import namedtuple
from functools import update_wrapper
from string import ascii_letters, digits
from random import choice
from datetime import (
    datetime as dt,
    timezone as tz,
    timedelta as td
)

__all__ = ('get_timestamp', '_isdecimal', 'rstring', 'async_cache')

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
    return update_wrapper(wrapper, f)
