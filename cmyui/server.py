# -*- coding: utf-8 -*-

import socket
from typing import Generator, Tuple, Any

from .types import Address
from .connection import Connection

__all__ = (
    'Server',
)

class Server:
    __slots__ = ('sock_family', 'sock_type', 'listening')

    def __init__(self, socket_family: int = socket.AF_INET,
                 socket_type: int = socket.SOCK_STREAM) -> None:
        if socket_family == socket.AF_UNIX:
            from os import name
            if name == 'nt': raise ValueError(
                'UNIX sockets can only be used on UNIX operating systems.')

        self.sock_family = socket_family
        self.sock_type = socket_type
        self.listening = False

    def __enter__(self) -> None:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def listen(self, addr: Address = ('127.0.0.1', 5001),
               max_conns: int = 5) -> Generator[Connection, None, None]:

        if using_unix := self.sock_family == socket.AF_UNIX:
            if not isinstance(addr, str):
                raise TypeError('Addr must be a string for UNIX sockets.')

            # Remove unix socket if it already exists.
            from os import path, remove
            if path.exists(addr):
                remove(addr)
        else:
            from itertools import izip
            if not isinstance(addr, tuple) or len(addr) != 2 \
            or not all(isinstance(i, t) for i, t in izip(addr, (str, int))):
                raise TypeError(
                    'Addr must be a tuple of (ip: str, port: int) for INET sockets.')

        with socket.socket(self.sock_family, self.sock_type) as s:
            s.bind(addr)

            if using_unix:
                from os import chmod
                chmod(addr, 0o777)

            self.listening = True
            s.listen(max_conns)

            while self.listening:
                yield Connection(*s.accept())

# Simple example usage.
if __name__ == '__main__':
    from socket import AF_UNIX, SOCK_STREAM
    with Server(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        for conn in s.listen('/tmp/gulag.sock', 5):
            print(conn)
