# -*- coding: utf-8 -*-

from enum import IntEnum, unique, auto
from struct import (
    pack as st_pack,
    unpack as st_unpack
)
from typing import Any, Tuple, Final

__all__ = (
    'DataType',
    'PacketStream'
)

@unique
class DataType(IntEnum):
    pad: Final[int] = 0
    i8: Final[int] = auto()
    u8: Final[int] = auto()
    i16: Final[int] = auto()
    u16: Final[int] = auto()
    i32: Final[int] = auto()
    u32: Final[int] = auto()
    i64: Final[int] = auto()
    u64: Final[int] = auto()
    f32: Final[int] = auto()
    f64: Final[int] = auto()

    # 'advanced' types
    ''' TODO
    i16_list: Final[int] = auto()
    u16_list: Final[int] = auto()
    i32_list: Final[int] = auto()
    u32_list: Final[int] = auto()
    i64_list: Final[int] = auto()
    u64_list: Final[int] = auto()
    f32_list: Final[int] = auto()
    f64_list: Final[int] = auto()
    string: Final[int] = auto()
    '''

    def __str__(self) -> str:
        if self.value > self.f64:
            raise Exception('Tried to use an advanced type with __str__.')

        return 'xbBhHiIqQfd'[self.value]

class PacketStream:
    __slots__ = ('data',)

    def __init__(self, data: bytes = None) -> None:
        if data: # Reading
            self.data = data
        else: # Writing
            self.data = bytearray()

    @staticmethod
    def create_fmtstr(types: Tuple[DataType],
                      order: str = '<') -> str:
        return f"{order}{''.join(str(t) for t in types)}"

    def read(self, types: Tuple[DataType]) -> Tuple[Any]:
        return st_unpack(self.create_fmtstr(types, '<'), self.data)

    def write(self, params: Tuple[Tuple[Any, DataType]]) -> None:
        params, types = zip(*params)
        fmt = self.create_fmtstr(types, '<')
        self.data.extend(st_pack(fmt, *params))

# TODO: Some abstraction for osu!'s bancho protocol?
