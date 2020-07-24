# -*- coding: utf-8 -*-

from socket import socket
from collections import defaultdict
from typing import Final, Dict

from .types import Address

__all__ = (
    'http_statuses',
    'Connection',
    'Request',
    'Response'
)

http_statuses: Final[Dict[int, str]] = {
    # Informational
    100: 'CONTINUE',
    101: 'SWITCHING PROTOCOLS',
    102: 'PROCESSING',

    # Success
    200: 'OK',

    # Redirection
    307: 'TEMPORARY REDIRECT',
    308: 'PERMANENT REDIRECT',

    # Client Error
    400: 'BAD REQUEST',
    401: 'UNAUTHORIZED',
    402: 'PAYMENT REQUIRED',
    403: 'FORBIDDEN',
    404: 'NOT FOUND',

    # Server Error
    500: 'INTERNAL SERVER ERROR',
    501: 'NOT IMPLEMENTED',
    502: 'BAD GATEWAY',
    503: 'SERVICE UNAVAILABLE',
    504: 'GATEWAY TIMEOUT'
}

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
                self.args = {}
                return # Non-multipart POST

            # Parse multipartform data into args.
            # Very sketch method, i'm not a fan of multipart forms..
            boundary = ct.split('=')[1].encode()
            self.args = {}

            for form_part in self.body.split(b'--' + boundary)[1:]:
                # TODO len checks? will think abt it
                if form_part[:2] != b'\r\n':
                    continue

                param_lines = form_part[2:].split(b'\r\n', 3)
                if (data_line_idx := len(param_lines) - 1) < 3:
                    raise Exception('Malformed line in multipart form-data.')
                    #continue

                # XXX: type_line is currently unused, but it
                # can contain the content-type of the param,
                # such as `Content-Type: image/png`.
                attrs_line, type_line = (s.decode() for s in param_lines[:2])

                if not attrs_line.startswith('Content-Disposition: form-data'):
                    raise Exception('What?') # XXX: temporary

                if ';' in attrs_line:
                    # Line has attributes in `k="v"` fmt,
                    # each delimited by ` ;`.
                    # We split by `;` and lstrip the key
                    # to allow for a `;` delimiter.
                    attrs = {k.lstrip(): v[1:-1] for k, v in (
                        a.split('=', 1) for a in attrs_line.split(';')[1:]
                    )}
                else:
                    attrs = {}

                if 'name' not in attrs:
                    # Can't really make a k:v pair out of this?
                    print(param_lines)
                    continue

                # Link attrs.name to the actual form part's data.
                self.args.update({attrs['name']: param_lines[data_line_idx]})

                # Link all other attrs to their respective values.
                for k, v in attrs.items():
                    if k != 'name':
                        self.args.update({k: v})
        else:
            raise Exception(f'Unsupported HTTP command: {self.cmd}')

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
        self.headers.insert(0, f'HTTP/1.1 {code} {http_statuses[code]}')
        self.headers.insert(1, f'Content-Length: {len(data)}')
        try:
            self.sock.send('\r\n'.join(self.headers).encode() + b'\r\n\r\n' + data)
        except BrokenPipeError:
            print('\x1b[1;91mWARN: Connection pipe broken.\x1b[0m')

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

        return data
