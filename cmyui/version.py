# -*- coding: utf-8 -*-

__all__ = 'Version',

class Version:
    def __init__(self, major: int, minor: int, micro: int) -> None:
        self.major, self.minor, self.micro = major, minor, micro

    def __repr__(self) -> str:
        return '{major}.{minor}.{micro}'.format(**self.__dict__)
