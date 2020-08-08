# -*- coding: utf-8 -*-

from collections import defaultdict
from enum import IntEnum, unique, auto
from socket import (AF_INET, AF_UNIX, SOCK_STREAM,
                    socket, SOL_SOCKET, SO_REUSEADDR)
from typing import Final, Dict, Generator, Tuple, Union
from os import path, remove, chmod, name as _name

__all__ = (
    'HTTPStatus',
    'Address',
    'Connection',
    'Request',
    'Response',
    'TCPServer'
)

_httpstatus_str: Final[Dict[int, str]] = {
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

@unique
class HTTPStatus(IntEnum):
    # Informational
    Continue = 100
    SwitchingProtocols = 101
    Processing = 102

    # Success
    Ok = 200

    # Redirection
    TemporaryRedirect = 307
    PermanentRedirect = 308

    # Client Error
    BadRequest = 400
    Unauthorized = 401
    PaymentRequired = 402
    Forbidden = 403
    NotFound = 404

    # Server Error
    InternalServerError = 500
    NotImplemented = 501
    BadGateway = 502
    ServiceUnavailable = 503
    GatewayTimeout = 504

    def __repr__(self) -> str:
        return f'{self.value} {_httpstatus_str[self.value]}'

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

    def startswith(self, s: str) -> bool:
        return self.uri.startswith(s)

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
                h.split(':', 1) for h in s[0].decode().split('\r\n')
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
                for k, v in (i.split('=', 1) for i in full_uri[p_start + 1:].split('&')):
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
                         a.split('=', 1) for a in attrs_line.split(';')[1:])}

                if 'filename' in attrs:
                    self.files.update({attrs['filename']: param_lines[data_line_idx]})
                elif 'name' in attrs:
                    self.args.update({attrs['name']: param_lines[data_line_idx].decode()})
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

    def send(self, data: bytes, status: Union[HTTPStatus, int] = 200) -> None:
        # Insert HTTP response line & content
        # length at the beginning of the headers.
        self.headers.insert(0, f'HTTP/1.1 {repr(HTTPStatus(status)).upper()}') # suboptimal
        self.headers.insert(1, f'Content-Length: {len(data)}')

        try:
            self.sock.send('\r\n'.join(self.headers).encode() + b'\r\n\r\n' + data)
        except BrokenPipeError:
            print('\x1b[1;91mWARN: Connection pipe broken.\x1b[0m')

class Connection: # will probably end up removing addr?
    __slots__ = ('req', 'resp', 'addr')

    def __init__(self, sock: socket, addr: Address) -> None:
        self.req = Request(self.read(sock))
        self.resp = Response(sock)
        self.addr = addr

    @staticmethod
    def read(sock: socket, ch_size: int = 1024) -> bytes:
        data = sock.recv(ch_size)

        # Read in `ch_size` byte chunks until there
        # was no change in size between reads.
        while (l := len(data)) % ch_size == 0:
            data += sock.recv(ch_size)
            if l == len(data):
                break

        return data

class TCPServer:
    __slots__ = ('addr', 'sock_family', 'listening')
    def __init__(self, addr: Address) -> None:
        is_inet = isinstance(addr, tuple) \
              and len(addr) == 2 \
              and all(isinstance(i, t) for i, t in zip(addr, (str, int)))

        if is_inet:
            self.sock_family = AF_INET
        elif isinstance(addr, str):
            self.sock_family = AF_UNIX
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

        sock: socket
        with socket(self.sock_family, SOCK_STREAM) as sock:
            sock.bind(self.addr)

            if using_unix:
                chmod(self.addr, 0o777)

            self.listening = True
            sock.listen(max_conns)

            while self.listening:
                yield Connection(*sock.accept())
