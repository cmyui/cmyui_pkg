# -*- coding: utf-8 -*-

import uvloop
from collections import defaultdict
from enum import IntEnum, unique
from socket import socket, AF_INET, AF_UNIX, SOCK_STREAM, socket
from typing import AsyncGenerator, Final, Dict, Generator, Optional, Tuple, Union, DefaultDict
from os import path, remove, chmod

__all__ = (
    # Information
    'HTTPStatus',
    'Address',

    # Synchronous
    'Connection',
    'Request',
    'Response',
    'TCPServer',

    # Asynchronous
    'AsyncConnection',
    'AsyncRequest',
    'AsyncResponse',
    'AsyncTCPServer'
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

""" Synchronous stuff """

class Request:
    __slots__ = ('headers', 'body', 'cmd', 'path',
                 'httpver', 'args', 'files')

    def __init__(self):
        self.headers: DefaultDict[str, str] = defaultdict(lambda: None)
        self.body = b''
        self.cmd = ''
        self.path = ''
        self.httpver = 0.0

        self.args: DefaultDict[str, str] = defaultdict(lambda: None)
        self.files: DefaultDict[str, str] = defaultdict(lambda: None)

    def startswith(self, s: str) -> bool:
        return self.path.startswith(s)

    def parse(self, req_content: bytes) -> None:
        """ HTTP Request format:
        # {cmd} /{path} HTTP/{httpver} ; HTTP Request Line
        # {key}: {value}               ; Header (indefinite amount)
        #                              ; Header/body separating line
        # {body}                       ; Body (for the rest of the req)
        """

        # TODO: move contants out of the function.

        # NOTE: the excessive logging on failure will be
        # removed after more extensive testing is done :)

        # Retrieve the http request line.
        req_line, after_req_line = req_content.split(b'\r\n', 1)

        # Decode and split into (cmd, path, httpver).
        req_line_split = req_line.decode().split(' ')

        # TODO: cmyui.utils this
        isfloat = lambda s: s.replace('.', '', 1).isnumeric()

        valid_req_line = (
            len(req_line_split) == 3 and # split must be (cmd, path, ver)
            len(req_line_split[2]) == 8 and # ver string must be 8 chars
            isfloat(req_line_split[2][5:]) # ver string must be float
        )

        # Ensure the split format is valid.
        if not valid_req_line:
            raise Exception(f'Invalid http request line "{req_line}"')

        cmd, path, ver = req_line_split

        # Ensure all pieces of the split are valid.
        if cmd not in ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'):
            raise Exception(f'Invalid http command "{cmd}"')
        # TODO: path regex match?
        if ver[5:] not in ('1.0', '1.1', '2.0', '3.0'):
            raise Exception(f'Invalid http version "{ver[5:]}"')

        # Store our cmd & http ver. The path may still
        # contain arguments if it is a get request.
        self.cmd = cmd
        self.httpver = float(ver[5:])

        # Split the rest of the request into headers & body.
        header_lines, self.body = after_req_line.split(b'\r\n\r\n', 1)

        # Parse the headers into our class.
        for header_line in header_lines.decode().split('\r\n'):
            # Split header into k: v pair.
            header = header_line.split(':', 1)

            if len(header) != 2: # Only key received.
                raise Exception(f'Invalid header "{header}"')

            self.headers.update({header[0]: header[1].lstrip()})

        if self.cmd in ('GET', 'HEAD'): # Args may be in the path
            # Find the ? in the path.
            p_start = path.find('?')
            if p_start != -1: # Has params
                # Path will simply be until the params.
                self.path = path[:p_start]

                # Parse params into our class arguments.
                for param_line in path[p_start + 1:].split('&'):
                    # Split param into k: v pair.
                    param = param_line.split('=', 1)

                    if len(param) != 2: # Only key received.
                        raise Exception(f'Invalid GET parameter "{param}"')

                    # If the param is an int or float, cast it.
                    if param[1].isnumeric():
                        param[1] = int(param[1])
                    elif isfloat(param[1]):
                        param[1] = float(param[1])

                    self.args.update({param[0]: param[1]})

            else: # No params
                # Path will be our full path.
                self.path = path

        elif self.cmd == 'POST': # Args may be in the body (multipart)
            self.path = path

            # XXX: may redesign so we don't have to return
            # here, that way timing will be easier..

            if 'Content-Type' not in self.headers:
                return

            if not self.headers['Content-Type'].startswith('multipart/form-data'):
                return

            # Retrieve the multipart boundary from the headers.
            # It will need to be encoded, since the body is as well.
            boundary = self.headers['Content-Type'].split('=', 1)[1].encode()

            # Ignore the first and last parts of the multipart,
            # since the boundary is always sent at the start/end.
            for part in self.body.split(b'--' + boundary)[1:-1]:
                # Split each part by CRLF, this should give use the
                # content-disposition on index 1, possibly the
                # content-type on index 2, and the data 2 indices later.
                s = part[2:].split(b'\r\n')

                # Ensure content disposition is correct.
                if not s[0].startswith(b'Content-Disposition: form-data;'):
                    raise Exception(f'Invalid multipart param "{part}"')

                # Used to store attributes passed
                # in the content-disposition line.
                attrs = {}

                # Split attributes from the content-disposition line.
                for attr_line in s[0].decode().split(';')[1:]:
                    # Split attr into k: v pair.
                    attr = attr_line.split('=', 1)

                    if len(attr) != 2: # Only key received.
                        raise Exception(f'Invalid multipart attribute "{attr}"')

                    # Values are inside of quotation marks "",
                    # so we simply use [1:-1] to remove them.
                    attrs.update({attr[0].lstrip(): attr[1][1:-1]})

                # Make sure either 'name' or 'filename' was in
                # the attributes, so we know where to store it.
                if not any(i in attrs for i in ('name', 'filename')):
                    raise Exception('Neither name nor filename passed in multipart attributes')

                # Check if content-type has been included.
                if s[1].startswith(b'Content-Type'):
                    # Since we have content-type, push
                    # the data line idx back one more.
                    data_line_idx = 3

                    # TODO: perhaps use the content-type?
                    # At the moment, it's not very useful to me.
                else:
                    # No content-type provided, index
                    # will be two indices after disposition.
                    data_line_idx = 2

                data = s[data_line_idx]

                if 'filename' in attrs:
                    # Save to files as bytes
                    self.files.update({attrs['filename']: data})
                else:
                    # Save to args as string
                    self.args.update({attrs['name']: data.decode()})

                # Save any non-related attributes
                # into our request's arguments.
                for k, v in attrs.items():
                    if k not in ('name', 'filename'):
                        self.args.update({k: v})

        else:
            # Currently unhandled method,
            # no further parsing required.
            pass

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

""" Asynchronous stuff """

class AsyncRequest:
    __slots__ = ('headers', 'body', 'cmd', 'path',
                 'httpver', 'args', 'files')

    def __init__(self) -> None:
        self.headers: DefaultDict[str, str] = defaultdict(lambda: None)
        self.body = b''
        self.cmd = ''
        self.path = ''
        self.httpver = 0.0

        self.args: DefaultDict[str, str] = defaultdict(lambda: None)
        self.files: DefaultDict[str, str] = defaultdict(lambda: None)

    def startswith(self, s: str) -> bool:
        return self.path.startswith(s)

    async def parse(self, req_content: bytes) -> None:
        """ HTTP Request format:
        # {cmd} /{path} HTTP/{httpver} ; HTTP Request Line
        # {key}: {value}               ; Header (indefinite amount)
        #                              ; Header/body separating line
        # {body}                       ; Body (for the rest of the req)
        """

        # TODO: move contants out of the function.

        # NOTE: the excessive logging on failure will be
        # removed after more extensive testing is done :)

        # Retrieve the http request line.
        req_line, after_req_line = req_content.split(b'\r\n', 1)

        # Decode and split into (cmd, path, httpver).
        req_line_split = req_line.decode().split(' ')

        # TODO: cmyui.utils this
        isfloat = lambda s: s.replace('.', '', 1).isnumeric()

        valid_req_line = (
            len(req_line_split) == 3 and # split must be (cmd, path, ver)
            len(req_line_split[2]) == 8 and # ver string must be 8 chars
            isfloat(req_line_split[2][5:]) # ver string must be float
        )

        # Ensure the split format is valid.
        if not valid_req_line:
            raise Exception(f'Invalid http request line "{req_line}"')

        cmd, path, ver = req_line_split

        # Ensure all pieces of the split are valid.
        if cmd not in ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'):
            raise Exception(f'Invalid http command "{cmd}"')
        # TODO: path regex match?
        if ver[5:] not in ('1.0', '1.1', '2.0', '3.0'):
            raise Exception(f'Invalid http version "{ver[5:]}"')

        # Store our cmd & http ver. The path may still
        # contain arguments if it is a get request.
        self.cmd = cmd
        self.httpver = float(ver[5:])

        # Split the rest of the request into headers & body.
        header_lines, self.body = after_req_line.split(b'\r\n\r\n', 1)

        # Parse the headers into our class.
        for header_line in header_lines.decode().split('\r\n'):
            # Split header into k: v pair.
            header = header_line.split(':', 1)

            if len(header) != 2: # Only key received.
                raise Exception(f'Invalid header "{header}"')

            self.headers.update({header[0]: header[1].lstrip()})

        if self.cmd in ('GET', 'HEAD'): # Args may be in the path
            # Find the ? in the path.
            p_start = path.find('?')
            if p_start != -1: # Has params
                # Path will simply be until the params.
                self.path = path[:p_start]

                # Parse params into our class arguments.
                for param_line in path[p_start + 1:].split('&'):
                    # Split param into k: v pair.
                    param = param_line.split('=', 1)

                    if len(param) != 2: # Only key received.
                        raise Exception(f'Invalid GET parameter "{param}"')

                    # If the param is an int or float, cast it.
                    if param[1].isnumeric():
                        param[1] = int(param[1])
                    elif isfloat(param[1]):
                        param[1] = float(param[1])

                    self.args.update({param[0]: param[1]})

            else: # No params
                # Path will be our full path.
                self.path = path

        elif self.cmd == 'POST': # Args may be in the body (multipart)
            self.path = path

            # XXX: may redesign so we don't have to return
            # here, that way timing will be easier..

            if 'Content-Type' not in self.headers:
                return

            if not self.headers['Content-Type'].startswith('multipart/form-data'):
                return

            # Retrieve the multipart boundary from the headers.
            # It will need to be encoded, since the body is as well.
            boundary = self.headers['Content-Type'].split('=', 1)[1].encode()

            # Ignore the first and last parts of the multipart,
            # since the boundary is always sent at the start/end.
            for part in self.body.split(b'--' + boundary)[1:-1]:
                # Split each part by CRLF, this should give use the
                # content-disposition on index 1, possibly the
                # content-type on index 2, and the data 2 indices later.
                s = part[2:].split(b'\r\n')

                # Ensure content disposition is correct.
                if not s[0].startswith(b'Content-Disposition: form-data;'):
                    raise Exception(f'Invalid multipart param "{part}"')

                # Used to store attributes passed
                # in the content-disposition line.
                attrs = {}

                # Split attributes from the content-disposition line.
                for attr_line in s[0].decode().split(';')[1:]:
                    # Split attr into k: v pair.
                    attr = attr_line.split('=', 1)

                    if len(attr) != 2: # Only key received.
                        raise Exception(f'Invalid multipart attribute "{attr}"')

                    # Values are inside of quotation marks "",
                    # so we simply use [1:-1] to remove them.
                    attrs.update({attr[0].lstrip(): attr[1][1:-1]})

                # Make sure either 'name' or 'filename' was in
                # the attributes, so we know where to store it.
                if not any(i in attrs for i in ('name', 'filename')):
                    raise Exception('Neither name nor filename passed in multipart attributes')

                # Check if content-type has been included.
                if s[1].startswith(b'Content-Type'):
                    # Since we have content-type, push
                    # the data line idx back one more.
                    data_line_idx = 3

                    # TODO: perhaps use the content-type?
                    # At the moment, it's not very useful to me.
                else:
                    # No content-type provided, index
                    # will be two indices after disposition.
                    data_line_idx = 2

                data = s[data_line_idx]

                if 'filename' in attrs:
                    # Save to files as bytes
                    self.files.update({attrs['filename']: data})
                else:
                    # Save to args as string
                    self.args.update({attrs['name']: data.decode()})

                # Save any non-related attributes
                # into our request's arguments.
                for k, v in attrs.items():
                    if k not in ('name', 'filename'):
                        self.args.update({k: v})

        else:
            # Currently unhandled method,
            # no further parsing required.
            pass

class AsyncResponse:
    __slots__ = ('loop', 'client', 'headers')

    def __init__(self, loop: uvloop.Loop, client: socket) -> None:
        self.loop = loop
        self.client = client
        self.headers = []

    async def add_header(self, header: str, index: int = -1) -> None:
        if index > -1: # Insert
            self.headers.insert(index, header)
        else: # Append
            self.headers.append(header)

    async def send(self, data: bytes, status: HTTPStatus = HTTPStatus.Ok) -> None:
        # Insert HTTP response line & content at the beginning of headers.
        await self.add_header(f'HTTP/1.1 {repr(HTTPStatus(status)).upper()}', 0)
        await self.add_header(f'Content-Length: {len(data)}', 1)

        # Concat all data together for sending to the client.
        ret = '\r\n'.join(self.headers).encode() + b'\r\n\r\n' + data

        try: # Send all data to client.
            await self.loop.sock_sendall(self.client, ret)
        except BrokenPipeError:
            print('\x1b[1;91mWARN: Connection pipe broken.\x1b[0m')

class AsyncConnection:
    __slots__ = ('req', 'resp', 'addr')

    def __init__(self, addr: Address) -> None:
        # Request & Response setup in self.read()
        self.req: Optional[AsyncRequest] = None
        self.resp: Optional[AsyncResponse] = None
        self.addr = addr

    async def read(self, loop: uvloop.Loop, client: socket,
                   ch_size: int = 1024) -> bytes:
        data = await loop.sock_recv(client, ch_size)

        # Read in `ch_size` byte chunks until there
        # was no change in size between reads.
        while (l := len(data)) % ch_size == 0:
            data += await loop.sock_recv(client, ch_size)
            if l == len(data):
                break

        # Parse our data into an HTTP request.
        self.req = AsyncRequest()
        await self.req.parse(data)

        # Prepare response obj aswell.
        self.resp = AsyncResponse(loop, client)

class AsyncTCPServer:
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

    async def __aenter__(self) -> None:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def listen(self, loop: uvloop.Loop, max_conns: int = 5
                    ) -> AsyncGenerator[AsyncConnection, None]:
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
            sock.setblocking(False)

            while self.listening:
                client, addr = await loop.sock_accept(sock)
                conn = AsyncConnection(addr)
                await conn.read(loop, client, 1024)
                yield conn
