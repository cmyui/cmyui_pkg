# -*- coding: utf-8 -*-

# NOTE: this package used to include a
# synchronous server implementation,
# though it was removed as the async
# one far surpassed it in development.

# Perhaps at some point, it will be re-added,
# though it doesn't sound too useful atm. :P

import asyncio
import socket
import signal
import os
import re
import time
import gzip
from enum import IntEnum, unique
from typing import Callable, Coroutine, Optional, Union

from .logging import log, Ansi, AnsiRGB

__all__ = (
    # Informational
    'HTTPStatus',
    'Address',

    # Functional
    'Connection',
    'RouteMap',
    'Domain',
    'Server'
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

class Connection:
    __slots__ = (
        'client',

        # Request params
        'headers', 'body', 'cmd',
        'path', 'httpver',

        'args', 'multipart_args', 'files',

        # Response params
        'resp_code', 'resp_headers',

    )

    # TODO: probably cut back on the defaultdicts
    def __init__(self, client: socket.socket) -> None:
        self.client = client

        # Request params
        self.headers = {}
        self.body: Optional[bytearray] = None
        self.cmd = ''
        self.path = ''
        self.httpver = 0.0

        self.args = {}
        self.multipart_args = {}

        self.files = {}

        # Response params
        self.resp_code = 200
        self.resp_headers: list[str] = []

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
                    log(f'Invalid url path argument', Ansi.LRED)
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

        # get the length of the body, and check whether we've
        # already have the entirety within in our temp buffer.
        content_length = int(self.headers['Content-Length'])

        if already_read != content_length:
            # there is still data to read; now that we know
            # the length remaining, we can allocate a static
            # buffer and read into a view for high efficiency.
            to_read = content_length - already_read
            buf = bytearray(to_read)
            view = memoryview(buf)

            while to_read:
                nbytes = await loop.sock_recv_into(self.client, view)
                view = view[nbytes:]
                to_read -= nbytes

            # save data to our connection object as immutable bytes.
            self.body = temp_buf + bytes(buf)
        else:
            # we already have all the data.
            self.body = temp_buf

        if self.cmd == 'POST':
            # if we're parsing a POST request, there may
            # still be arguments passed as multipart/form-data.

            if 'Content-Type' in self.headers:
                ct = self.headers['Content-Type']
                if ct and ct.startswith('multipart/form-data'):
                    await self.parse_multipart()

    """ Response methods """

    def add_resp_header(self, header: str, index: int = -1) -> None:
        if index > -1:
            self.resp_headers.insert(index, header)
        else:
            self.resp_headers.append(header)

    async def send(self, status: Union[HTTPStatus, int], body: bytes = b'') -> None:
        """Attach appropriate headers and send data back to the client."""
        # Insert HTTP response line & content at the beginning of headers.
        self.add_resp_header(f'HTTP/1.1 {HTTPStatus(status)!r}'.upper(), 0)

        if body: # Add content-length header if we are sending a body.
            self.add_resp_header(f'Content-Length: {len(body)}', 1)

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

class Route:
    """A single endpoint within of domain."""
    __slots__ = ('key', 'methods', 'handler')
    def __init__(self, key: Union[str, re.Pattern],
                 methods: list[str], handler: Callable) -> None:
        self.key = key
        self.methods = methods
        self.handler = handler

    def matches(self, key: Union[str, re.Pattern], method: str) -> bool:
        # Check if a given `key` matches our internal `self.key`.
        if method not in self.methods:
            return False

        if isinstance(self.key, str):
            return self.key == key
        elif isinstance(self.key, re.Pattern):
            return self.key.match(key)
        else:
            raise TypeError('Key should be str or re.Pattern object.')

class RouteMap:
    """A collection of endpoints of a domain."""
    __slots__ = ('routes',)
    def __init__(self) -> None:
        self.routes = set() # {Route(), ...}

    def route(self, path: Union[str, re.Pattern],
              methods: list[str] = ['GET']) -> Callable:
        """Add a possible route to the server."""
        if type(path) not in (str, re.Pattern):
            raise TypeError('Route path must be str or regex pattern.')

        def wrapper(f: Coroutine) -> Coroutine:
            self.routes.add(Route(path, methods, f))
            return f
        return wrapper

    def find_route(self, path: str, method: str):
        for route in self.routes:
            if route.matches(path, method):
                return route

class Domain(RouteMap):
    """The main routemap, with a hostname.
       Allows for merging of additional routemaps."""
    __slots__ = ('hostname',)
    def __init__(self, hostname: Union[str, re.Pattern]) -> None:
        super().__init__()
        self.hostname = hostname

    def matches(self, hostname: Union[str, re.Pattern]) -> bool:
        # Check if a given `hostname` matches stored value.
        if isinstance(self.hostname, str):
            return self.hostname == hostname
        elif isinstance(self.hostname, re.Pattern):
            return self.hostname.match(hostname)
        else:
            raise TypeError('Key should be str or re.Pattern object.')

    def add_map(rmap: RouteMap) -> None:
        self.routes |= rmap.routes

# TODO: perhaps implement Server, or refactor
# both into one with a kwarg for async? moyai
class Server:
    """An asynchronous multi-domain server."""
    __slots__ = ('name', 'max_conns', 'gzip',
                 'verbose', 'domains', 'tasks')
    def __init__(self, **kwargs) -> None:
        self.name = kwargs.pop('name', 'Server')
        self.max_conns = kwargs.pop('max_conns', 5)
        self.gzip = kwargs.pop('gzip', 0) # 0-9 valid levels
        self.verbose = kwargs.pop('verbose', False)

        self.domains = set()
        self.tasks = set()

    # Domain management

    def add_domain(self, domain: Domain) -> None:
        self.domains.add(domain)

    def add_domains(self, domains: set[Domain]) -> None:
        self.domains |= domains

    def remove_domain(self, domain: Domain) -> None:
        self.domains.remove(domain)

    def remove_domains(self, domains: set[Domain]) -> None:
        self.domains -= domains

    def find_domain(self, host_header: str):
        for domain in self.domains:
            if domain.matches(host_header):
                return domain

    # Task management

    def add_task(self, task: asyncio.Task) -> None:
        self.tasks.add(task)

    def remove_task(self, task: asyncio.Task) -> None:
        self.tasks.remove(task)

    def add_tasks(self, tasks: set[asyncio.Task]) -> None:
        self.tasks |= tasks

    def remove_tasks(self, tasks: set[asyncio.Task]) -> None:
        self.tasks -= tasks

    # True Internals

    async def dispatch(self, conn: Connection) -> int:
        """Dispatch the connection to any matching routes."""
        host = conn.headers['Host']
        path = conn.path

        resp = None

        if domain := self.find_domain(host):
            if route := domain.find_route(path, conn.cmd):
                resp = await route.handler(conn) or b''

        if resp is not None:
            code, resp = resp if isinstance(resp, tuple) else (200, resp)

            if self.gzip > 0:
                resp = gzip.compress(resp, self.gzip)
                conn.add_resp_header('Content-Encoding: gzip')
        else:
            code, resp = (404, b'Not Found.')

        await conn.send(code, resp)
        return code

    def run(self, addr: Address) -> None:
        is_inet = type(addr) is tuple and len(addr) == 2 and \
                  type(addr[0]) is str and type(addr[1]) is int

        if is_inet:
            sock_family = socket.AF_INET
            using_unix = False
        elif isinstance(addr, str):
            sock_family = socket.AF_UNIX
            using_unix = True
        else:
            raise ValueError('Invalid address.')

        """Run the server indefinitely."""
        async def runner() -> None:
            loop = asyncio.get_event_loop()

            try:
                loop.add_signal_handler(signal.SIGINT, loop.stop)
                loop.add_signal_handler(signal.SIGTERM, loop.stop)
            except NotImplementedError:
                pass

            # Start up any tasks
            for task in self.tasks:
                loop.create_task(task)

            # Setup socket & begin listening

            if using_unix:
                if os.path.exists(addr):
                    os.remove(addr)

            with socket.socket(sock_family) as sock:
                sock.bind(addr)

                if using_unix:
                    os.chmod(addr, 0o777)

                sock.listen(self.max_conns)
                sock.setblocking(False)

                log(f'{self.name} listening @ {addr}', AnsiRGB(0x00ff7f))

                async def handle(client: socket.socket) -> None:
                    """Handle a single client socket from the server."""
                    start_time = time.time_ns()

                    # Read & parse connection.
                    await (conn := Connection(client)).read()

                    if 'Host' not in conn.headers:
                        # This should never happen?
                        client.shutdown(socket.SHUT_RDWR)
                        client.close()
                        return

                    # Dispatch the handler.
                    code = await self.dispatch(conn)

                    # Event complete, stop timing, log result and cleanup.
                    time_taken = (time.time_ns() - start_time) / 1e6

                    colour = (Ansi.LGREEN if 200 <= code < 300 else
                              Ansi.LYELLOW if 300 <= code < 400 else
                              Ansi.LRED)

                    uri = f'{conn.headers["Host"]}{conn.path}'

                    log(f'[{conn.cmd}] {code} {uri}', colour)

                    if self.verbose:
                        log(f'Request took {time_taken:.2f}ms', Ansi.LBLUE)

                    client.shutdown(socket.SHUT_RDWR)
                    client.close()

                while True:
                    client, _ = await loop.sock_accept(sock)
                    loop.create_task(handle(client))

        asyncio.run(runner())
