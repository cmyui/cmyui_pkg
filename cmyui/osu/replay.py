""" Tools for working with osu!'s .osr file format """
# -*- coding: utf-8 -*-

import os
import lzma
import struct
from typing import Optional
from typing import Union

from cmyui.osu.mods import Mods

__all__ = ('Replay', 'ReplayFrame', 'Keys')

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

StrOrBytesPath = Union[str, bytes, os.PathLike[str], os.PathLike[bytes]]

class Keys:
    M1 = 1 << 0
    M2 = 1 << 1
    K1 = 1 << 2
    K2 = 1 << 3
    SMOKE = 1 << 4

class ReplayFrame:
    __slots__ = ('delta', 'x', 'y', 'keys', 'time')

    def __init__(self, delta: int, time: int,
                 x: float, y: float, keys: int) -> None:
        self.delta = delta
        self.x = x
        self.y = y
        self.keys = keys

        self.time = time

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
        'timestamp', 'score_id', 'mod_extras', 'seed',
        'skip_offset', 'frames', 'new_keypresses',
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
        self.skip_offset: Optional[int] = None
        self.frames: Optional[list[ReplayFrame]] = None
        self.new_keypresses: Optional[list[ReplayFrame]] = None

        """ internal reader use only """
        self._data: Optional[bytes] = None
        self._offset: Optional[int] = None

    @property
    def data(self) -> bytes:
        return self._data[self._offset:]

    @classmethod
    def from_data(cls, data: bytes, lzma_only: bool = False) -> 'Replay':
        r = cls()

        r._data = data
        r._offset = 0

        if not lzma_only:
            # parse full replay
            r._parse_full()
        else:
            # only parse replay frames
            r._read_frames(r._data)

        return r

    @classmethod
    def from_file(
        cls, path: StrOrBytesPath,
        lzma_only: bool = False
    ) -> Optional['Replay']:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                return cls.from_data(f.read(), lzma_only)

    """Read sections from the data."""

    def _parse_headers(self) -> None:
        """Parse replay headers."""
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

        self.life_graph = self._read_life_graph()
        self.timestamp = self._read_long()

    def _parse_frames(self) -> None:
        """Parse (lzma'd) replay frames."""
        lzma_length = self._read_int()
        if lzma_length:
            lzma_data = self._read_raw(lzma_length)
            self._read_frames(lzma_data)
        else:
            self.frames = []

    def _parse_trailers(self) -> None:
        """Parse replay trailers."""
        if self.osu_version >= 2014_07_21:
            self.score_id = self._read_long()
        elif self.osu_version >= 2012_10_08:
            self.score_id = self._read_int()

        if self.mods & Mods.TARGET:
            self.mod_extras = self._read_double()

    def _parse_full(self) -> None:
        """Parse a full replay file."""
        self._parse_headers()
        self._parse_frames()
        self._parse_trailers()

    """Read individual elements from the data."""

    def _read_byte(self) -> int:
        val = self.data[0]
        self._offset += 1
        return val

    def _read_short(self) -> int:
        val, = struct.unpack('<h', self.data[:2])
        self._offset += 2
        return val

    def _read_int(self) -> int:
        val, = struct.unpack('<i', self.data[:4])
        self._offset += 4
        return val

    def _read_long(self) -> int:
        val, = struct.unpack('<q', self.data[:8])
        self._offset += 8
        return val

    def _read_float(self) -> float:
        val, = struct.unpack('<f', self.data[:4])
        self._offset += 4
        return val

    def _read_double(self) -> float:
        val, = struct.unpack('<d', self.data[:8])
        self._offset += 8
        return val

    def _read_uleb128(self) -> int:
        val = shift = 0

        while True:
            b = self._read_byte()

            val |= ((b & 127) << shift)
            if (b & 128) == 0:
                break

            shift += 7

        return val

    def _read_raw(self, length: int) -> bytes:
        val = self.data[:length]
        self._offset += length
        return val

    def _read_string(self) -> str:
        if self._read_byte() == 0x00:
            return ''

        uleb = self._read_uleb128()
        return self._read_raw(uleb).decode()

    def _read_life_graph(self) -> None:
        life_graph = []
        if _life_graph_str := self._read_string():
            if _life_graph_str[-1] == ',':
                _life_graph_str = _life_graph_str[:-1]

            for entry in _life_graph_str.split(','):
                split = entry.split('|', maxsplit=1)
                life_graph.append((int(split[0]), float(split[1])))
        return life_graph

    def _read_frames(self, data: bytes) -> None:
        lzma_data = lzma.decompress(data)
        self.frames = []
        self.new_keypresses = []

        actions = [x for x in lzma_data.decode().split(',') if x]

        # stable adds two extra frames at the beginning, the first being
        # useless and the second containing the skip offset (if any)
        skip_offs = actions[1].split('|', maxsplit=1)[0]
        if skip_offs != '-1':
            self.skip_offset = int(skip_offs)

            if self.mods & Mods.AUTOPLAY:
                self.skip_offset -= 100000

        prev_keys = 0
        total_delta = self.skip_offset or 0

        for action in actions[2:-1]:
            if len(split := action.split('|')) != 4:
                return

            try:
                delta = int(split[0])
                total_delta += delta
                #if delta < 0:
                #    continue

                keys = int(split[3])

                frame = ReplayFrame(
                    delta=delta,
                    time=total_delta,
                    x=float(split[1]),
                    y=float(split[2]),
                    keys=keys
                )
                if (
                    (keys & Keys.M1 and not prev_keys & Keys.M1) or
                    (keys & Keys.M2 and not prev_keys & Keys.M2)
                ):
                    self.new_keypresses.append(frame)

                self.frames.append(frame)
                prev_keys = keys
            except ValueError:
                continue

        if actions[-1].startswith('-12345'): # >(=?)2013/03/19
            # last replay frame contains the seed
            self.seed = int(actions[-1].rsplit('|', maxsplit=1)[1])
        else:
            # treat last replay frame as a normal frame
            if len(split := action.split('|')) != 4:
                return

            try:
                self.frames.append(ReplayFrame(
                    delta=int(split[0]),
                    x=float(split[1]),
                    y=float(split[2]),
                    keys=int(split[3])
                ))
            except ValueError:
                pass
