# -*- coding: utf-8 -*-

__all__ = ('Version',)

class Version: # TODO: why fixed length? also could maybe inherit comp ops
    __slots__ = ('major', 'minor', 'micro')
    def __init__(self, major: int, minor: int, micro: int) -> None:
        self.major = major
        self.minor = minor
        self.micro = micro

    def __repr__(self) -> str:
        return '{0}.{1}.{2}'.format(*self.as_tuple)

    def __hash__(self) -> int:
        return self.as_tuple.__hash__()

    def __eq__(self, other: 'Version') -> bool:
        return self.as_tuple == other.as_tuple

    def __ne__(self, other: 'Version') -> bool:
        return self.as_tuple != other.as_tuple

    def __lt__(self, other: 'Version') -> bool:
        return self.as_tuple < other.as_tuple

    def __le__(self, other: 'Version') -> bool:
        return self.as_tuple <= other.as_tuple

    def __gt__(self, other: 'Version') -> bool:
        return self.as_tuple > other.as_tuple

    def __ge__(self, other: 'Version') -> bool:
        return self.as_tuple >= other.as_tuple

    @property
    def as_tuple(self) -> tuple[int]:
        return (self.major, self.minor, self.micro)

    @classmethod
    def from_str(cls, s: str):
        if len(split := s.split('.')) != 3:
            return

        return cls(*map(int, split))
