# -*- coding: utf-8 -*-

from typing import Any
from collections.abc import Callable
from time import time

__all__ = (
    'for_all_methods',
    'log_performance'
)

def log_performance(func, min_time: float = 0.0) -> Any:
    def _decorate(*m_args, **m_kwargs):
        st, ret = time(), func(*m_args, **m_kwargs)
        if (taken := 1000 * (time() - st)) >= min_time:
            print(f'{func.__name__}: {taken:,.2f}ms')
        return ret
    return _decorate

def for_all_methods(func, *args, **kwargs):
    def decorate(cls):
        for k in cls.__dict__:
            attr = getattr(cls, k)
            if isinstance(attr, Callable):
                setattr(cls, k, func(attr, *args, **kwargs))
        return cls
    return decorate
