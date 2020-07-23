# -*- coding: utf-8 -*-

from socket import socket
from collections import defaultdict

from .types import Address

__all__ = (
    'Connection',
    'Request',
    'Response'
)

class Request:
    __slots__ = ('headers', 'body', 'data', 'cmd', 'uri', 'httpver', 'args')

    def __init__(self, data: bytes):
        self.data = data
        self.parse_http_request()

    def parse_http_request(self) -> None:
        # Retrieve http request line from content.
        req_line, after_req_line = self.data.split(b'\r\n', 1)

        self.cmd, full_uri, _httpver = req_line.decode().split(' ')

        if len(_httpver) != 8 \
        or not _httpver[5:].replace('.', '', 1).isnumeric():
            raise Exception('Invalid HTTP version.')

        self.httpver = float(_httpver[5:])

        # Split into headers & body
        s = after_req_line.split(b'\r\n\r\n', 1)
        self.headers = defaultdict(lambda: None, {
            k: v.lstrip() for k, v in (
                h.split(':') for h in s[0].decode().split('\r\n')
            )
        })
        self.body = s[1]
        del s

        # Parse our request for arguments.
        # Method varies on the http command.
        if self.cmd == 'GET':
            # If our request has arguments, parse them.
            if (p_start := full_uri.find('?')) != -1:
                self.uri = full_uri[:p_start]
                self.args = defaultdict(lambda: None, {k: v for k, v in (
                    i.split('=') for i in full_uri[p_start + 1:].split('&')
                )})
            else:
                self.uri, self.args = full_uri, {}
        elif self.cmd == 'POST':
            self.uri = full_uri

            if not (ct := self.headers['Content-Type']) \
            or not ct.startswith('multipart/form-data'):
                raise Exception('non-multipart POST')

            # Parse multipartform data into args.
            # Very sketch method, i'm not a fan of multipart forms..
            boundary = ct.split('=')[1].encode()
            self.args = {}

            for form_part in self.body.split(b'--' + boundary)[1:]:
                # TODO len checks? will think abt it
                if form_part[:2] != b'\r\n': # This shouldn't happen?
                    continue

                param_lines = form_part[2:].split(b'\r\n', 3)
                if len(param_lines) < 4:
                    continue

                if not param_lines[0].startswith(
                b'Content-Disposition: form-data'):
                    continue

                # XXX: unfinished

                #tags = {k: v.replace('"', '') for k, v in (x.split('=') for x in s[0].decode().split('; ')[1:])}
                #if 'name' not in tags:
                #    continue

                #if tags['name'] in self.args and tags['name'] == 'score':
                #    print(1)

                #self.args.update({tags['name']: s[2]})

                #if self.args:
                #    print(1)

                ...

                #_args = self.body.split(boundary + b'\r\nContent-Disposition: form-data; name="')
                #self.args = {k: v for k, v in (i[:-4].split(b'"\r\n\r\n') for i in _args[1:])}
                #print(1)
                #self.args = {k: v for k, v in (i[40:-4].split(b'"\r\n\r\n') for i in _args)}
                #if not self.args:
                #    print(1)
        else:
            raise Exception('invalid http cmd?')

class Response:
    __slots__ = ('sock', 'headers')

    def __init__(self, sock: socket) -> None:
        self.sock = sock
        self.headers = []

    def add_header(self, header: str) -> None:
        self.headers.append(header)

    def send(self, data: bytes, code: int = 200) -> None:
        # Insert HTTP response line & content
        # length at the beginning of the headers.
        self.headers.insert(
            0, 'HTTP/1.1 ' + {
                200: '200 OK',
                404: '404 NOT FOUND'
            }[code])
        self.headers.insert(1, f'Content-Length: {len(data)}')
        try:
            self.sock.send('\r\n'.join(self.headers).encode() + b'\r\n\r\n' + data)
        except BrokenPipeError:
            print('\x1b[1;91mConnection pipe broken.\x1b[0m')

class Connection: # will probably end up removing addr?
    __slots__ = ('request', 'response', 'addr')

    def __init__(self, sock: socket, addr: Address) -> None:
        self.request = Request(self.read_data(sock))
        self.response = Response(sock)
        self.addr = addr

    @staticmethod
    def read_data(sock: socket, ch_size: int = 1024) -> bytes:
        data = sock.recv(ch_size)

        while (l := len(data)) % ch_size == 0:
            data += sock.recv(ch_size)
            if l == len(data):
                # No growth
                break

        print(f'len: {len(data)}')
        return data
