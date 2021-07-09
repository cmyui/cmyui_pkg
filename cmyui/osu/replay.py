# -*- coding: utf-8 -*-

import os
import lzma
import struct
from typing import Optional

from cmyui.osu.mods import Mods

__all__ = ('ReplayFrame', 'Replay',
           'KEYS_M1', 'KEYS_M2',
           'KEYS_K1', 'KEYS_K2',
           'KEYS_SMOKE')

"""\
a simple osu! replay parser, for all your replay parsing needs..

Basic usage:
```
  r = Replay.from_str('1234567.osr')
  if not r:
    # file not found
    ...

  # replay objects have pretty much everything
  # you can imagine for an osu! replay. :P

  print(r.player_name, r.mode, r.mods, r.osu_version, ...)

  for frame in r.frames:
    print(r.delta, r.x, r.y, r.keys)

  # etc
  ...
```

i'm sure it'll get cleaned up more over time, basically
wrote it with the same style as the beatmap parser.
"""

KEYS_M1 = 1 << 0
KEYS_M2 = 1 << 1
KEYS_K1 = 1 << 2
KEYS_K2 = 1 << 3
KEYS_SMOKE = 1 << 4

class ReplayFrame:
    __slots__ = ('delta', 'x', 'y', 'keys')

    def __init__(self, delta: int, x: float, y: float, keys: int) -> None:
        self.delta = delta
        self.x = x
        self.y = y
        self.keys = keys

    @property
    def as_bytes(self) -> bytes:
        buf = bytearray()
        buf.extend(self.delta.to_bytes(4, 'little', signed=True))
        buf.extend(struct.pack('<ff', self.x, self.y))
        buf.append(self.keys)

        return bytes(buf)

    @property
    def as_str(self) -> str:
        # we want to display the keys as an integer.
        return f'{self.delta}|{self.x}|{self.y}|{self.keys}'

class Replay:
    __slots__ = (
        'mode', 'osu_version', 'map_md5', 'player_name', 'replay_md5',
        'n300', 'n100', 'n50', 'ngeki', 'nkatu', 'nmiss',
        'score', 'max_combo', 'perfect', 'mods', 'life_graph',
        'timestamp', 'score_id', 'mod_extras', 'seed', 'frames',
        '_data', '_offset'
    )
    def __init__(self) -> None:
        """ replay headers"""
        self.mode: Optional[int] = None # gm
        self.osu_version: Optional[int] = None

        self.map_md5: Optional[str] = None
        self.player_name: Optional[str] = None
        self.replay_md5: Optional[str] = None

        self.n300: Optional[int] = None
        self.n100: Optional[int] = None
        self.n50: Optional[int] = None
        self.ngeki: Optional[int] = None
        self.nkatu: Optional[int] = None
        self.nmiss: Optional[int] = None

        self.score: Optional[int] = None
        self.max_combo: Optional[int] = None
        self.perfect: Optional[int] = None
        self.mods: Optional[Mods] = None

        """ additional info"""
        self.life_graph: Optional[list[tuple[int, float]]] = None # zz
        self.timestamp: Optional[int] = None
        self.score_id: Optional[int] = None
        self.mod_extras: Optional[float] = None
        self.seed: Optional[int] = None

        """ replay frames """
        self.frames: Optional[list[ReplayFrame]] = None

        """ internal reader use only """
        self._data: Optional[bytes] = None
        self._offset: Optional[int] = None

    @property
    def data(self) -> bytes:
        return self._data[self._offset:]

    @classmethod
    def from_file(cls, filename: str) -> 'Replay':
        if not os.path.exists(filename):
            return

        r = cls()

        with open(filename, 'rb') as f:
            r._data = f.read()
            r._offset = 0

        r._parse()
        return r

    def _parse(self) -> None:
        """ parse replay headers """
        self.mode = self._read_byte()
        self.osu_version = self._read_int()
        self.map_md5 = self._read_string()
        self.player_name = self._read_string()
        self.replay_md5 = self._read_string()
        self.n300 = self._read_short()
        self.n100 = self._read_short()
        self.n50 = self._read_short()
        self.ngeki = self._read_short()
        self.nkatu = self._read_short()
        self.nmiss = self._read_short()
        self.score = self._read_int()
        self.max_combo = self._read_short()
        self.perfect = self._read_byte()
        self.mods = Mods(self._read_int())

        self.life_graph = []
        if _life_graph_str := self._read_string():
            for entry in _life_graph_str[:-1].split(','):
                split = entry.split('|', maxsplit=1)
                self.life_graph.append((int(split[0]), float(split[1])))

        self.timestamp = self._read_long()

        """ parse lzma """
        self.frames = self._read_frames()

        """ parse additional info """
        self.score_id = self._read_long()

        if self.mods & Mods.TARGET:
            self.mod_extras = self._read_double()

    def _read_byte(self):
        val = self.data[0]
        self._offset += 1
        return val

    def _read_short(self):
        val, = struct.unpack('<h', self.data[:2])
        self._offset += 2
        return val

    def _read_int(self):
        val, = struct.unpack('<i', self.data[:4])
        self._offset += 4
        return val

    def _read_float(self):
        val, = struct.unpack('<f', self.data[:4])
        self._offset += 4
        return val

    def _read_long(self):
        val, = struct.unpack('<q', self.data[:8])
        self._offset += 8
        return val

    def _read_double(self):
        val, = struct.unpack('<d', self.data[:8])
        self._offset += 8
        return val

    def _read_uleb128(self):
        val = shift = 0

        while True:
            b = self._read_byte()

            val |= ((b & 0b01111111) << shift)
            if (b & 0b10000000) == 0x00:
                break

            shift += 7

        return val

    def _read_raw(self, length: int):
        val = self.data[:length]
        self._offset += length
        return val

    def _read_string(self):
        if self._read_byte() == 0x00:
            return ''

        uleb = self._read_uleb128()
        return self._read_raw(uleb).decode()

    def _read_frames(self):
        frames = []

        lzma_len = self._read_int()
        lzma_data = lzma.decompress(self._read_raw(lzma_len))

        actions = [x for x in lzma_data.decode().split(',') if x]

        for action in actions[:-1]:
            if len(split := action.split('|')) != 4:
                return

            try:
                frames.append(ReplayFrame(
                    delta=int(split[0]),
                    x=float(split[1]),
                    y=float(split[2]),
                    keys=int(split[3])
                ))
            except:
                continue

        if self.osu_version > 2013_03_19:
            self.seed = int(actions[-1].rsplit('|', 1)[1])

        return frames
