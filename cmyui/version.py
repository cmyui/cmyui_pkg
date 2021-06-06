# -*- coding: utf-8 -*-

import functools

__all__ = ('Version',)

@functools.total_ordering
class Version:
    __slots__ = ('major', 'minor', 'micro')
    def __init__(self, major: int, minor: int, micro: int) -> None:
        self.major = major
        self.minor = minor
        self.micro = micro

    def __repr__(self) -> str:
        return f'{self.major}.{self.minor}.{self.micro}'

    def __hash__(self) -> int:
        return self.as_tuple.__hash__()

    def __eq__(self, other: 'Version') -> bool:
        return self.as_tuple == other.as_tuple

    def __lt__(self, other: 'Version') -> bool:
        return self.as_tuple < other.as_tuple

    @property
    def as_tuple(self) -> tuple[int]:
        return (self.major, self.minor, self.micro)

    @classmethod
    def from_str(cls, s: str) -> 'Version':
        if len(split := s.split('.')) != 3:
            return

        return cls(*map(int, split))
