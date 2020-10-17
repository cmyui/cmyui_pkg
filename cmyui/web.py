# -*- coding: utf-8 -*-

# NOTE: this package used to include a
# synchronous server implementation,
# though it was removed as the async
# one far surpassed it in development.

# Perhaps at some point, it will be re-added,
# though it doesn't sound too useful atm. :P

import asyncio
import socket
import os
import re
from collections import defaultdict
from enum import IntEnum, unique
from typing import AsyncGenerator, Optional, Union

from .logging import log, Ansi

__all__ = (
    # Information
    'HTTPStatus',
    'Address',

    # Asynchronous
    'AsyncConnection',
    'AsyncTCPServer'
)

_httpstatus_str = {
    # Informational
    100: "Continue",
    101: "Switching Protocols",
    102: "Processing",

    # Success
    200: "Ok",
    201: "Created",
    202: "Accepted",
    203: "Non-authoritative Information",
    204: "No Content",
    205: "Reset Content",
    206: "Partial Content",
    207: "Multi-Status",
    208: "Already Reported",
    226: "IM Used",

    # Redirection
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    305: "Use Proxy",
    307: "Temporary Redirect",
    308: "Permanent Redirect",

    # Client Error
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    412: "Precondition Failed",
    413: "Payload Too Large",
    414: "Request-URI Too Long",
    415: "Unsupported Media Type",
    416: "Requested Range Not Satisfiable",
    417: "Expectation Failed",
    418: "I'm a teapot",
    421: "Misdirected Request",
    422: "Unprocessable Entity",
    423: "Locked",
    424: "Failed Dependency",
    426: "Upgrade Required",
    428: "Precondition Required",
    429: "Too Many Requests",
    431: "Request Header Fields Too Large",
    444: "Connection Closed Without Response",
    451: "Unavailable For Legal Reasons",
    499: "Client Closed Request",

    # Server Error
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
    505: "HTTP Version Not Supported",
    506: "Variant Also Negotiates",
    507: "Insufficient Storage",
    508: "Loop Detected",
    510: "Not Extended",
    511: "Network Authentication Required",
    599: "Network Connect Timeout Error"
}

@unique
class HTTPStatus(IntEnum):
    # Informational
    Continue = 100
    SwitchingProtocols = 101
    Processing = 102

    # Success
    Ok = 200
    Created = 201
    Accepted = 202
    NonAuthoritativeInformation = 203
    NoContent = 204
    ResetContent = 205
    PartialContent = 206
    MultiStatus = 207
    AlreadyReported = 208
    IMUsed = 226

    # Redirection
    MultipleChoices = 300
    MovedPermanently = 301
    Found = 302
    SeeOther = 303
    NotModified = 304
    UseProxy = 305
    TemporaryRedirect = 307
    PermanentRedirect = 308

    # Client Error
    BadRequest = 400
    Unauthorized = 401
    PaymentRequired = 402
    Forbidden = 403
    NotFound = 404
    MethodNotAllowed = 405
    NotAcceptable = 406
    ProxyAuthenticationRequired = 407
    RequestTimeout = 408
    Conflict = 409
    Gone = 410
    LengthRequired = 411
    PreconditionFailed = 412
    PayloadTooLarge = 413
    RequestURITooLong = 414
    UnsupportedMediaType = 415
    RequestedRangeNotSatisfiable = 416
    ExpectationFailed = 417
    ImATeapot = 418
    MisdirectedRequest = 421
    UnprocessableEntity = 422
    Locked = 423
    FailedDependency = 424
    UpgradeRequired = 426
    PreconditionRequired = 428
    TooManyRequests = 429
    RequestHeaderFieldsTooLarge = 431
    ConnectionClosedWithoutResponse = 444
    UnavailableForLegalReasons = 451
    ClientClosedRequest = 499

    # Server Error
    InternalServerError = 500
    NotImplemented = 501
    BadGateway = 502
    ServiceUnavailable = 503
    GatewayTimeout = 504
    HTTPVersionNotSupported = 505
    VariantAlsoNegotiates = 506
    InsufficientStorage = 507
    LoopDetected = 508
    NotExtended = 510
    NetworkAuthenticationRequired = 511
    NetworkConnectTimeoutError = 599

    def __repr__(self) -> str:
        return f'{self.value} {_httpstatus_str[self.value]}'

# Will be (host: str, port: int) if INET,
# or (sock_dir: str) if UNIX.
Address = Union[tuple[str, int], str]

req_line_re = re.compile(
    r'^(?P<cmd>GET|HEAD|POST|PUT|DELETE|PATCH|OPTIONS) '
    r'(?P<path>/[^? ]*)(?P<args>\?[^ ]+)? ' # cursed?
    r'HTTP/(?P<httpver>1\.0|1\.1|2\.0|3\.0)$'
)

class AsyncConnection:
    __slots__ = (
        'client',

        # Request params
        'headers', 'body', 'cmd',
        'path', 'httpver', 'args', 'files',

        # Response params
        'resp_headers', 'multipart_args'
    )

    # TODO: probably cut back on the defaultdicts
    def __init__(self, client: socket.socket) -> None:
        self.client = client

        # Request params
        self.headers: defaultdict[str, str] = defaultdict(lambda: None)
        self.body: Optional[bytearray] = None
        self.cmd: Optional[str] = None
        self.path: Optional[str] = None
        self.httpver: Optional[float] = None

        self.args: defaultdict[str, str] = defaultdict(lambda: None)
        self.files: defaultdict[str, bytes] = defaultdict(lambda: None)

        # Response params
        self.resp_headers: list[str] = []
        self.multipart_args: defaultdict[str, str] = defaultdict(lambda: None)

    """ Request methods """

    async def parse_headers(self, data: str) -> None:
        # Retrieve the http request line.
        delim = data.find('\r\n')

        # Make sure request line is properly formatted.
        if not (m := req_line_re.match(data[:delim])):
            log('Invalid request line', Ansi.LRED)
            return

        # cmd & httpver are fine as-is
        self.cmd = m['cmd']
        self.httpver = float(m['httpver'])

        # There may be params in the path, they
        # will be removed once the body is read.
        self.path = m['path']

        # Parse the headers into our class.
        for header_line in data[delim + 2:].split('\r\n'):
            # Split header into k: v pair.
            header = header_line.split(':', 1)

            if len(header) != 2: # Only key received.
                log('Invalid header', Ansi.LRED)
                return

            self.headers.update({header[0]: header[1].lstrip()})

        if m['args']: # parse args from url path
            for param_line in m['args'][1:].split('&'):
                param = param_line.split('=', 1)

                if len(param) != 2: # Only key received.
                    log(f'Invalid url path argument', Ansi.RED)
                    return

                self.args.update({param[0]: param[1]})

    async def parse_multipart(self) -> None:
        # retrieve the multipart boundary from the headers.
        # It will need to be encoded, since the body is as well.
        boundary = self.headers['Content-Type'].split('=', 1)[1].encode()

        params = self.body.split(b'--' + boundary)[1:]

        # perhaps `if b'\r\n\r\n` in p` would be better?
        for param in (p for p in params if p != b'--\r\n'):
            _headers, _body = param.split(b'\r\n\r\n', 1)

            headers = {}
            for header in _headers.decode().split('\r\n')[1:]:
                if len(split := header.split(':', 1)) != 2:
                    breakpoint()

                headers.update({split[0]: split[1].lstrip()})

            if 'Content-Disposition' not in headers:
                breakpoint()

            attrs = {}
            for attr in headers['Content-Disposition'].split(';')[1:]:
                if len(split := attr.split('=', 1)) != 2:
                    breakpoint()

                attrs.update({split[0].lstrip(): split[1][1:-1]})

            body = _body[:-2]

            # multipart args should be decoded,
            # but files should stay as bytes.
            if 'filename' in attrs:
                self.files.update({attrs['filename']: body})
            else:
                self.multipart_args.update({attrs['name']: body.decode()})

    async def read(self) -> bytes:
        loop = asyncio.get_event_loop()

        # create a temp buffer, and read until we find
        # b'\r\n\r\n', meaning we've read all the headers.
        temp_buf = b''

        while b'\r\n\r\n' not in temp_buf:
            # read for headers in 512 byte chunks, this will
            # usually only have to read once, sometimes twice.
            temp_buf += await loop.sock_recv(self.client, 512)

        delim = temp_buf.find(b'\r\n\r\n')

        # we've read all the headers, parse them
        await self.parse_headers(temp_buf[:delim].decode())

        if 'Content-Length' not in self.headers:
            # there was either a problem parsing,
            # or the request only contains headers
            return

        # advance our temp buffer to the beginning of the body.
        temp_buf = temp_buf[delim + 4:]

        # since we were reading from the socket in chunks, we
        # almost definitely overshot and have some of the body
        # in our temp buffer. calculate how much we have.
        already_read = len(temp_buf)

        # now that we have our headers, we can allocate our 'real'
        # buffer with the content length included in the headers.
        content_length = int(self.headers['Content-Length'])
        buf = bytearray(content_length)

        # add the data we've already read to our
        # real buffer, and advance the reader.
        buf[:already_read] = temp_buf
        view = memoryview(buf)[already_read:]
        toread = content_length - already_read

        # continue reading from the socket until we've read the
        # entirety of the data described with the content length.
        # TODO: implement some sort of timeout system..
        while toread:
            nbytes = await loop.sock_recv_into(self.client, view)
            view = view[nbytes:]
            toread -= nbytes

        # save data to our connection object as immutable bytes.
        self.body = bytes(buf)

        if self.cmd == 'POST':
            # if we're parsing a POST request, there may
            # still be arguments passed as multipart/form-data.
            ct = self.headers['Content-Type']
            if ct and ct.startswith('multipart/form-data'):
                await self.parse_multipart()

    """ Response methods """

    async def add_resp_header(self, header: str, index: int = -1) -> None:
        if index > -1:
            self.resp_headers.insert(index, header)
        else:
            self.resp_headers.append(header)

    async def send(self, status: Union[HTTPStatus, int], body: bytes = b'') -> None:
        """Attach appropriate headers and send data back to the client."""
        # Insert HTTP response line & content at the beginning of headers.
        await self.add_resp_header(f'HTTP/1.1 {HTTPStatus(status)!r}'.upper(), 0)

        if body: # Add content-length header if we are sending a body.
            await self.add_resp_header(f'Content-Length: {len(body)}', 1)

        # Encode the headers.
        headers_str = '\r\n'.join(self.resp_headers)
        response = f'{headers_str}\r\n\r\n'.encode()

        if body:
            response += body

        loop = asyncio.get_event_loop()

        try: # Send all data to client.
            await loop.sock_sendall(self.client, response)
        except BrokenPipeError:
            log('Connection ended abruptly', Ansi.LRED)

class AsyncTCPServer:
    """\
    Create a TCP socket server which can asynchronously listen and yield connections.

    Simple usage:
    ```
    import asyncio
    import cmyui
    import time

    async def handle_conn(conn: cmyui.AsyncConnection) -> None:
        # see the AsyncConnection implementation for
        # details on it's use and methods/attributes.

        # i've provided a simple server example below.

        if 'Host' not in conn.headers:
            await conn.send(400, b'Missing required headers.')
            return

        st = time.time()

        if conn.cmd == 'GET':
            if conn.path == '/math/sum.php':
                if 'x' not in conn.args or 'y' not in conn.args:
                    await conn.send(400, b'Must supply x & y parameters.')
                    return

                x = conn.args['x']
                y = conn.args['y']

                if not x.isdecimal() or not y.isdecimal():
                    await conn.send(400, b'Must supply integral parameters.')
                    return

                await conn.send(200, f'Sum: {x + y}'.encode())
                return
            else:
                await conn.send(404, b'Handler not found.')
                return
        elif conn.cmd == 'POST':
            if conn.path.startswith('/ss/') and conn.path.endswith('.png'):
                # POSTing with screenshot in multipart data as a file.
                if 'screenshot' not in conn.files:
                    await conn.send(400, b'Missing screenshot data.')
                    return

                ss_id = conn.path[4:-4]

                if not ss_id.isdecimal():
                    await conn.send(400, b'Invalid screenshot id.')
                    return

                with open(f'ss/{ss_id}.png', 'wb') as f:
                    f.write(conn.files['screenshot'])

                log(f'Saved screenshot {ss_id}.png', Ansi.LGREEN)
                return
            else:
                await conn.send(404, b'Handler not found.')
                return
        else:
            await conn.send(400, b'Handler not found.')
            return

    async def run_server():
        loop = asyncio.get_event_loop()

        # support for both ipv4 and unix domain sockets
        addr = ('127.0.0.1', 5001) # ipv4
        addr = '/tmp/gulag.sock' # unix domain

        async with cmyui.AsyncTCPServer(addr) as serv:
            async for conn in serv.listen(max_conns=16):
                loop.create_task(handle_conn(conn))

    asyncio.run(run_server())
    ```
    """
    __slots__ = ('addr', 'sock_family', 'listening')
    def __init__(self, addr: Address) -> None:
        is_inet = isinstance(addr, tuple) \
              and len(addr) == 2 \
              and all(isinstance(i, t) for i, t in zip(addr, (str, int)))

        if is_inet:
            self.sock_family = socket.AF_INET
        elif isinstance(addr, str):
            self.sock_family = socket.AF_UNIX
        else:
            raise ValueError('Invalid address.')

        self.addr = addr
        self.listening = False

    async def __aenter__(self) -> None:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def listen(self, max_conns: int = 5
                    ) -> AsyncGenerator[AsyncConnection, None]:
        if using_unix := self.sock_family == socket.AF_UNIX:
            # Remove unix socket if it already exists.
            if os.path.exists(self.addr):
                os.remove(self.addr)

        loop = asyncio.get_event_loop()

        sock: socket.socket
        with socket.socket(self.sock_family, socket.SOCK_STREAM) as sock:
            sock.bind(self.addr)

            if using_unix:
                os.chmod(self.addr, 0o777)

            self.listening = True
            sock.listen(max_conns)
            sock.setblocking(False)

            while self.listening:
                client, _ = await loop.sock_accept(sock)
                conn = AsyncConnection(client)
                await conn.read()
                yield conn
