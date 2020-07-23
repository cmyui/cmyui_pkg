# -*- coding: utf-8 -*-

from struct import (
    pack as st_pack,
    unpack as st_unpack
)
from typing import Any, Tuple

from .types import DataType

__all__ = (
    'PacketStream',
    #'BanchoPacketStream'
)

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

#class BanchoPacketStream(PacketStream):
#    pass
