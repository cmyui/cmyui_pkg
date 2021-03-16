# -*- coding: utf-8 -*-

__all__ = ('Ansi', 'AnsiRGB', 'printc', 'log')

import sys
from typing import Union, Optional, overload
from enum import IntEnum

from .utils import get_timestamp

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
    GRAY     = 90
    LRED     = 91
    LGREEN   = 92
    LYELLOW  = 93
    LBLUE    = 94
    LMAGENTA = 95
    LCYAN    = 96
    LWHITE   = 97

    RESET = 0

    def __repr__(self) -> str:
        return f'\x1b[{self.value}m'

class AnsiRGB:
    @overload
    def __init__(self, rgb: int) -> None: ...
    @overload
    def __init__(self, r: int, g: int, b: int) -> None: ...

    def __init__(self, *args) -> None:
        largs = len(args)

        if largs == 3:
            # r, g, b passed.
            self.r, self.g, self.b = args
        elif largs == 1:
            # passed as single argument
            rgb = args[0]
            self.b = rgb & 0xff
            self.g = (rgb >> 8) & 0xff
            self.r = (rgb >> 16) & 0xff
        else:
            raise ValueError('Incorrect params for AnsiRGB.')

    def __repr__(self) -> str:
        return f'\x1b[38;2;{self.r};{self.g};{self.b}m'

Ansi_T = Union[Ansi, AnsiRGB]

stdout_write = sys.stdout.write
stdout_flush = sys.stdout.flush
_gray = repr(Ansi.GRAY)
_reset = repr(Ansi.RESET)

def printc(s: str, col: Ansi_T, end: str = '\n') -> None:
    """Print a string, in a specified ansi colour."""
    stdout_write(f'{col!r}{s}{Ansi.RESET!r}{end}')
    stdout_flush()

def log(msg: str, col: Optional[Ansi_T] = None,
        fd: Optional[str] = None, end: str = '\n') -> None:
    """\
    Print a string, in a specified ansi colour with timestamp.

    Allows for the functionality to write to a file as
    well by passing the filepath with the `fd` parameter.
    """

    ts_short = get_timestamp(full=False)

    if col:
        stdout_write(f'{_gray}[{ts_short}] {col!r}{msg}{_reset}{end}')
    else:
        stdout_write(f'{_gray}[{ts_short}]{_reset} {msg}{end}')

    stdout_flush()

    if fd:
        # log simple ascii output to fd.
        with open(fd, 'a+') as f:
            f.write(f'[{get_timestamp(full=True)}] {msg}\n')
