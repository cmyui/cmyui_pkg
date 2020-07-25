# -*- coding: utf-8 -*-

from os import path, remove, chmod, name as _name
from socket import socket, AF_INET, AF_UNIX, SOCK_STREAM
from collections import defaultdict
from typing import Final, Dict, Generator, Tuple, Union

__all__ = (
    'http_statuses',
    'Address',
    'Connection',
    'Request',
    'Response',
    'TCPServer'
)

http_statuses: Final[Dict[int, str]] = {
    # Informational
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',

    # Success
    200: 'Ok',

    # Redirection
    307: 'Temporary Redirect',
    308: 'Permanent Redirect',

    # Client Error
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',

    # Server Error
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout'
}

# Will be (host: str, port: int) if INET,
# or (sock_dir: str) if UNIX.
Address = Union[Tuple[str, int], str]

class Request:
    __slots__ = ('headers', 'body', 'data', 'cmd',
                 'uri', 'httpver', 'args', 'files')

    def __init__(self, data: bytes):
        self.data = data

        self.headers = []
        self.body = b''
        self.cmd = ''
        self.uri = ''
        self.httpver = 0.0

        self.args = defaultdict(lambda: None)
        self.files = defaultdict(lambda: None)

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
                for k, v in (i.split('=') for i in full_uri[p_start + 1:].split('&')):
                    self.args.update({k: v})
            else:
                self.uri = full_uri
        elif self.cmd == 'POST':
            self.uri = full_uri

            if not (ct := self.headers['Content-Type']) \
            or not ct.startswith('multipart/form-data'):
                return # Non-multipart POST

            # Parse multipartform data into args.
            # Very sketch method, i'm not a fan of multipart forms..
            boundary = ct.split('=')[1].encode()

            for form_part in self.body.split(b'--' + boundary)[1:]:
                # TODO len checks? will think abt it
                if form_part[:2] != b'\r\n':
                    continue

                param_lines = form_part[2:].split(b'\r\n', 3)
                if len(param_lines) < 1:
                    raise Exception('Malformed line in multipart form-data.')
                    #continue

                # Find idx manually
                data_line_idx = 0
                for idx, l in enumerate(param_lines):
                    if not l:
                        data_line_idx = idx + 1
                        break

                if data_line_idx == 0:
                    continue

                # XXX: type_line is currently unused, but it
                # can contain the content-type of the param,
                # such as `Content-Type: image/png`.
                attrs_line, type_line = (s.decode() for s in param_lines[:2])

                if not attrs_line.startswith('Content-Disposition: form-data'):
                    continue

                if ';' not in attrs_line:
                    continue

                # Line has attributes in `k="v"` fmt, each
                # delimited by ` ;`. We split by `;` and
                # lstrip the key to allow for a `;` delimiter.
                attrs = {k.lstrip(): v[1:-1] for k, v in (
                    a.split('=', 1) for a in attrs_line.split(';')[1:]
                )}

                if 'filename' in attrs:
                    self.files.update({attrs['filename']: param_lines[data_line_idx]})
                elif 'name' in attrs:
                    self.args.update({attrs['name']: param_lines[data_line_idx]})
                else:
                    continue

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
        self.headers.insert(0, f'HTTP/1.1 {code} {http_statuses[code].upper()}')
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

class TCPServer:
    __slots__ = ('addr', 'sock_family', 'listening')
    def __init__(self, addr: Address) -> None:
        if isinstance(addr, str):
            if _name == 'nt':
                raise ValueError('UNIX sockets are not available on Windows.')
            self.sock_family = AF_UNIX
        elif isinstance(addr, tuple) and len(addr) == 2 and all(
        isinstance(i, t) for i, t in zip(addr, (str, int))):
            self.sock_family = AF_INET
        else:
            raise Exception('Invalid address.')

        self.addr = addr
        self.listening = False

    def __enter__(self) -> None:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def listen(self, max_conns: int = 5
              ) -> Generator[Connection, None, None]:
        if using_unix := self.sock_family == AF_UNIX:
            # Remove unix socket if it already exists.
            if path.exists(self.addr):
                remove(self.addr)

        with socket(self.sock_family, SOCK_STREAM) as s:
            s.bind(self.addr)

            if using_unix:
                chmod(self.addr, 0o777)

            self.listening = True
            s.listen(max_conns)

            while self.listening:
                yield Connection(*s.accept())
