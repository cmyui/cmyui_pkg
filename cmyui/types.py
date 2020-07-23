# -*- coding: utf-8 -*-

from enum import IntEnum, unique, auto
from typing import Any, Dict, Tuple, Union

__all__ = (
    'Address',
    'DataType',
    'SQLParams',
    'SQLResult'
)

@unique
class DataType(IntEnum):
    pad = 0
    i8 = auto()
    u8 = auto()
    i16 = auto()
    u16 = auto()
    i32 = auto()
    u32 = auto()
    i64 = auto()
    u64 = auto()
    f32 = auto()
    f64 = auto()

    # 'advanced' types
    ''' TODO
    i16_list = auto()
    u16_list = auto()
    i32_list = auto()
    u32_list = auto()
    i64_list = auto()
    u64_list = auto()
    f32_list = auto()
    f64_list = auto()
    string = auto()
    '''

    def __str__(self) -> str:
        if self.value > self.f64:
            raise Exception(
                'Tried to use an advanced type with __str__.')

        return 'xbBhHiIqQfd'[self.value]

# Will be (host: str, port: int) if INET,
# or (sock_dir: str) if UNIX.
Address = Union[Tuple[str, int], str]

SQLParams = Tuple[Union[int, float, str]]
SQLResult = Dict[str, Union[int, float, str]]
