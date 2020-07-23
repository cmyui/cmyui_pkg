# -*- coding: utf-8 -*-

from socket import socket

from .types import Address

__all__ = (
    'Connection',
)

class Connection:
    __slots__ = ('sock', 'addr', '_raw', 'request', 'headers', 'body')

    def __init__(self, sock: socket, addr: Address) -> None:
        self.sock = sock
        self.addr = addr

        self.read_data()
        self.parse_http_request()

    def read_data(self) -> None:
        self._raw = self.sock.recv(1024)
        if len(self._raw) % 1024 == 0:
            self._raw += self.sock.recv(1024)

    def parse_http_request(self) -> None:
        s = self._raw.split(b'\r\n\r\n')

        # Split all headers up by newline.
        # This includes the HTTP request line.
        _headers = s[0].decode('utf-8', 'strict').split('\r\n')

        # Split request line into (command, uri, version)
        self.request = _headers[0].split(' ')

        # Split headers into key: value pairs.
        self.headers = {k: v.lstrip() for k, v in (h.split(':') for h in _headers[1:])}

        # Keep the body as bytes.
        self.body = s[1]
