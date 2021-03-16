# -*- coding: utf-8 -*-

# NOTE: this package used to include a
# synchronous server implementation,
# though it was removed as the async
# one far surpassed it in development.

# Perhaps at some point, it will be re-added,
# though it doesn't sound too useful atm. :P

import asyncio
import gzip
import importlib
import inspect
import os
import re
import signal
import socket
import sys
import time
from enum import IntEnum
from enum import unique
from functools import wraps
from time import perf_counter as clock
from typing import Any
from typing import Callable
from typing import Coroutine
from typing import Iterable
from typing import Optional
from typing import Union

from .logging import Ansi
from .logging import AnsiRGB
from .logging import log
from .logging import printc

__all__ = (
    # Informational
    'HTTPStatus',
    'Address',

    # Functional
    'ratelimit',
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

def ratelimit(period: int, max_count: int,
              default_return: Optional[Any] = None
             ) -> Callable:
    """Utility decorator for global ratelimiting."""
    period = period
    max_count = max_count
    default_return = default_return

    last_reset = 0
    num_calls = 0

    def decorate(f: Callable) -> Callable:
        # TODO: not an extra 18 lines for 6 char change
        if inspect.iscoroutinefunction(f):
            async def wrapper(*args, **kwargs) -> Optional[Any]:
                nonlocal period, max_count, last_reset, num_calls

                elapsed = clock() - last_reset
                period_remaining = period - elapsed

                if period_remaining <= 0:
                    num_calls = 0
                    last_reset = clock()

                num_calls += 1

                if num_calls > max_count:
                    # call ratelimited.
                    return default_return

                return await f(*args, **kwargs)
        else:
            def wrapper(*args, **kwargs) -> Optional[Any]:
                nonlocal period, max_count, last_reset, num_calls

                elapsed = clock() - last_reset
                period_remaining = period - elapsed

                if period_remaining <= 0:
                    num_calls = 0
                    last_reset = clock()

                num_calls += 1

                if num_calls > max_count:
                    # call ratelimited.
                    return default_return

                return f(*args, **kwargs)

        return wraps(f)(wrapper)
    return decorate

# Will be (host: str, port: int) if INET,
# or (sock_dir: str) if UNIX.
Address = Union[tuple[str, int], str]
Hostname_Types = Union[str, Iterable[str], re.Pattern]

req_line_re = re.compile(
    r'^(?P<cmd>GET|HEAD|POST|PUT|DELETE|PATCH|OPTIONS) '
    r'(?P<path>/[^? ]*)(?P<args>\?[^ ]+)? ' # cursed?
    r'HTTP/(?P<httpver>1\.0|1\.1|2\.0|3\.0)$'
)

class CaseInsensitiveDict(dict):
    """A dictionary with case insensitive keys."""
    def __init__(self, *args, **kwargs) -> None:
        self.keystore = {}
        d = dict(*args, **kwargs)
        for k in d.keys():
            self.keystore[k.lower()] = k
        return super().__init__(*args, **kwargs)

    def __setitem__(self, k, v) -> None:
        self.keystore[k.lower()] = k
        return super().__setitem__(k, v)

    def __getitem__(self, k) -> str:
        k_lower = k.lower()
        if k_lower in self.keystore:
            k = self.keystore[k_lower]
        return super().__getitem__(k)

    def __contains__(self, k: str) -> bool:
        k_lower = k.lower()
        if k_lower in self.keystore:
            k = self.keystore[k_lower]
        return super().__contains__(k)

    def get(self, k, failobj=None) -> Optional[str]:
        k_lower = k.lower()
        if k_lower in self.keystore:
            k = self.keystore[k_lower]
        return super().get(k, failobj)

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
        self.headers = CaseInsensitiveDict()
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

            # normalize header capitalization
            # https://github.com/cmyui/cmyui_pkg/issues/3
            self.headers[header[0].title()] = header[1].lstrip()

        if m['args']: # parse args from url path
            for param_line in m['args'][1:].split('&'):
                param = param_line.split('=', 1)

                if len(param) != 2: # Only key received.
                    log('Invalid url path argument.', Ansi.LRED)
                    return

                self.args[param[0]] = param[1]

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

                headers[split[0]] = split[1].lstrip()

            if 'Content-Disposition' not in headers:
                breakpoint()

            attrs = {}
            for attr in headers['Content-Disposition'].split(';')[1:]:
                if len(split := attr.split('=', 1)) != 2:
                    breakpoint()

                attrs[split[0].lstrip()] = split[1][1:-1]

            body = _body[:-2]

            # multipart args should be decoded,
            # but files should stay as bytes.
            if 'filename' in attrs:
                self.files[attrs['filename']] = body
            else:
                self.multipart_args[attrs['name']] = body.decode()

    async def read(self) -> bytes:
        loop = asyncio.get_running_loop()

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
                if self.headers['Content-Type'].startswith('multipart/form-data'):
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

        loop = asyncio.get_running_loop()

        try: # Send all data to client.
            await loop.sock_sendall(self.client, response)
        except BrokenPipeError:
            # TODO: perhaps a way to detect this before
            # constructing the whole response? lol..
            #log('Connection ended abruptly', Ansi.LRED)
            pass

class Route:
    """A single endpoint within of domain."""
    __slots__ = ('path', 'methods', 'handler', 'cond')
    def __init__(self, path: Union[str, Iterable, re.Pattern],
                 methods: list[str], handler: Callable) -> None:
        self.path = path # for __repr__
        self.methods = methods
        self.handler = handler

        # do these checks once rather
        # than for every conn.. lol
        if isinstance(path, str):
            self.cond = lambda k: k == path
        elif isinstance(path, Iterable):
            self.cond = lambda k: k in path
            self.path = str(path)
        elif isinstance(path, re.Pattern):
            self.cond = lambda k: path.match(k)
            self.path = f'~{self.path.pattern}' # ~ for rgx

    def __repr__(self) -> str:
        return f'{"/".join(self.methods)} {self.path}'

    def matches(self, path: str, method: str) -> bool:
        """Check if a given `path` matches our method & condition."""
        return method in self.methods and self.cond(path)

class RouteMap:
    """A collection of endpoints of a domain."""
    __slots__ = ('routes',)
    def __init__(self) -> None:
        self.routes = set() # {Route(), ...}

    def route(self, path: Hostname_Types,
              methods: list[str] = ['GET']) -> Callable:
        """Add a possible route to the server."""
        if not isinstance(path, (str, Iterable, re.Pattern)):
            raise TypeError('Route should be str | Iterable[str] | re.Pattern')

        def wrapper(handler: Coroutine) -> Coroutine:
            self.routes.add(Route(path, methods, handler))
            return handler

        return wrapper

    def find_route(self, path: str, method: str) -> Optional[Route]:
        for route in self.routes:
            if route.matches(path, method):
                return route

class Domain(RouteMap):
    """The main routemap, with a hostname.
       Allows for merging of additional routemaps."""
    __slots__ = ('hostname', 'cond',)
    def __init__(self, hostname: Hostname_Types) -> None:
        super().__init__()
        self.hostname = hostname # for __repr__

        if isinstance(hostname, str):
            self.cond = lambda hn: hn == hostname
        elif isinstance(hostname, Iterable):
            self.cond = lambda hn: hn in hostname
            self.hostname = str(hostname)
        elif isinstance(hostname, re.Pattern):
            self.cond = lambda hn: hostname.match(hn) is not None
            self.hostname = f'~{hostname.pattern}' # ~ for rgx
        else:
            raise TypeError('Key should be str | Iterable[str] | re.Pattern')

    def __repr__(self) -> str:
        return self.hostname

    def matches(self, hostname: str) -> bool:
        """Check if a hostname matches our condition."""
        return self.cond(hostname)

    def add_map(self, rmap: RouteMap) -> None:
        self.routes |= rmap.routes

# TODO: perhaps implement Server, or refactor
# both into one with a kwarg for async? moyai
class Server:
    """An asynchronous multi-domain server."""
    __slots__ = (
        'name', 'max_conns', 'gzip',
        'debug', 'sock_family',
        'before_serving', 'after_serving',
        'domains',
        'tasks', '_task_coros',
        '_runner_task', '_shutdown_reqs'
    )
    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get('name', 'Server')
        self.max_conns = kwargs.get('max_conns', 5)
        self.gzip = kwargs.get('gzip', 0) # 0-9 valid levels
        self.debug = kwargs.get('debug', False)
        self.sock_family: Optional[socket.AddressFamily] = None

        self.before_serving: Optional[Callable] = None
        self.after_serving: Optional[Callable] = None

        self.domains = set()

        self.tasks = set()
        self._task_coros = set() # coros not yet run

        self._runner_task: Optional[Coroutine] = None
        self._shutdown_reqs: int = 0

    def set_sock_mode(self, addr: Address) -> None:
        is_inet = type(addr) is tuple and len(addr) == 2 and \
                  type(addr[0]) is str and type(addr[1]) is int

        if is_inet:
            self.sock_family = socket.AF_INET
        elif isinstance(addr, str):
            self.sock_family = socket.AF_UNIX
        else:
            raise ValueError('Invalid address.')

    # Domain management

    def add_domain(self, domain: Domain) -> None:
        self.domains.add(domain)

    def add_domains(self, domains: set[Domain]) -> None:
        self.domains |= domains

    def remove_domain(self, domain: Domain) -> None:
        self.domains.remove(domain)

    def remove_domains(self, domains: set[Domain]) -> None:
        self.domains -= domains

    def find_domain(self, hostname: str):
        for domain in self.domains:
            if domain.matches(hostname):
                return domain

    # Task management

    def add_pending_task(self, coro: Coroutine) -> None:
        """Add a coroutine to be launched as a task at
           startup & shutdown cleanly on shutdown."""
        self._task_coros.add(coro)

    def remove_pending_task(self, coro: Coroutine) -> None:
        """Remove a pending coroutine awaiting server launch."""
        self._task_coros.remove(coro)

    def add_task(self, task: asyncio.Task) -> None:
        """Add an existing task to be cleaned
           up on shutdown."""
        self.tasks.add(task)

    def remove_task(self, task: asyncio.Task) -> None:
        """Remove an existing task from being
           cleaned up on shutdown."""
        self.tasks.remove(task)

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

    async def handle(self, client: socket.socket) -> None:
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

        if self.debug:
            # Event complete, stop timing, log result and cleanup.
            time_taken = (time.time_ns() - start_time) / 1e6

            col = (Ansi.LGREEN  if 200 <= code < 300 else
                   Ansi.LYELLOW if 300 <= code < 400 else
                   Ansi.LRED)

            uri = f'{conn.headers["Host"]}{conn.path}'

            log(f'[{conn.cmd}] {code} {uri}', col, end=' | ')
            printc(f'Elapsed: {time_taken:.2f}ms', Ansi.LBLUE)

        try:
            client.shutdown(socket.SHUT_RDWR)
            client.close()
        except socket.error:
            pass

    def run(
        self, addr: Address,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        handle_signals: bool = True,
        # use signal.SIGUSR1 for restarts.
        # note this is only used with handle_signals enabled.
        sigusr1_restart: bool = False # signal.SIGUSR1 for restart
    ) -> None:
        """Run the server indefinitely."""
        if not loop:
            # no event loop given, check if one's running
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

        if not loop:
            self.set_sock_mode(addr)

            async def runner() -> None:
                log(f'=== Starting up {self.name} ===', Ansi.LMAGENTA)
                loop = asyncio.get_running_loop()

                # Call our before_serving coroutine,
                # if theres one specified.
                if self.before_serving:
                    await self.before_serving()

                # Start pending coroutine tasks.
                log(f'-> Starting {len(self._task_coros)} tasks.', Ansi.LMAGENTA)
                for coro in self._task_coros:
                    self.tasks.add(loop.create_task(coro))

                self._task_coros.clear()

                # Setup socket & begin listening

                if self.sock_family == socket.AF_UNIX:
                    if os.path.exists(addr):
                        os.remove(addr)

                with socket.socket(self.sock_family) as sock:
                    sock.bind(addr)

                    if self.sock_family == socket.AF_UNIX:
                        os.chmod(addr, 0o777)

                    sock.listen(self.max_conns)
                    sock.setblocking(False)

                    log(f'-> Listening @ {addr}', AnsiRGB(0x00ff7f))

                    while True:
                        client, _ = await loop.sock_accept(sock)
                        loop.create_task(self.handle(client))

            # no event loop running, we need to make our own
            if spec := importlib.util.find_spec('uvloop'):
                # use uvloop if it's already installed
                # TODO: could make this configurable
                # incase people want to disable it
                # for their own use-cases?
                uvloop = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(uvloop)

                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

            loop = asyncio.new_event_loop()

        if handle_signals:
            # attach a shutdown handler to SIGHUP, SIGTERM,
            # and SIGINT. if you'd like to clean up your own
            # stuff, attach your code to `self.after_serving`.
            # if `sigusr1_restart` is enabled, also attach
            # SIGUSR1 and run execv to reboot before shutdown.
            __should_restart = False

            async def shutdown(sig, loop):
                self._shutdown_reqs += 1

                if self._shutdown_reqs != 1:
                    if self._shutdown_reqs == 2:
                        log('Only one shutdown request is required. '
                            'Please be patient!', Ansi.LRED)
                    return

                if sig is signal.SIGINT:
                    print('\33[2K', end='\r') # Remove '^C' from console

                log(f'-> Received {sig.name} signal, shutting down.', Ansi.LRED)

                cancelled = []

                # No longer accept any new connections
                log('-> Closing socket listener.', Ansi.LMAGENTA)
                self._runner_task.cancel()
                cancelled.append(self._runner_task)

                # Shut down all running tasks
                if self.tasks:
                    log(f'-> Cancelling {len(self.tasks)} tasks.', Ansi.LMAGENTA)
                    for task in self.tasks:
                        task.cancel()
                        cancelled.append(task)

                await asyncio.gather(*cancelled, return_exceptions=True)

                to_await = [t for t in asyncio.all_tasks()
                            if t is not asyncio.current_task()]
                timeout = 5.0

                if to_await:
                    log(f'-> Awaiting {len(to_await)} pending handlers', Ansi.LMAGENTA)
                    for task in to_await:
                        try:
                            asyncio.wait_for(task, timeout=timeout)
                        except asyncio.TimeoutError:
                            qualname = task.get_coro().__qualname__
                            log(f'-> {qualname} timed out ({timeout}s)', Ansi.LRED)

                # run `after_serving` if it's set.
                if self.after_serving:
                    await self.after_serving()

                nonlocal __should_restart
                __should_restart = sig is signal.SIGUSR1

                loop.stop()

            signals = [signal.SIGHUP, signal.SIGTERM, signal.SIGINT]

            if sigusr1_restart:
                # use SIGUSR1 to restart the script.
                signals.append(signal.SIGUSR1)

            for s in signals:
                loop.add_signal_handler(
                    sig = s,
                    callback = lambda s = s: asyncio.create_task(shutdown(s, loop))
                )
        else:
            # not handling signals
            __should_restart = False

        try:
            self._runner_task = loop.create_task(runner())
            loop.run_forever()
        except: # exception raised in the users code?
            # I'm not sure what I should do here; probably shutdown,
            # but I'm going to think about it a bit more lol.
            #loop.run_until_complete(shutdown(signal.SIGTERM, loop))
            pass
        finally:
            log(f'=== Shut down {self.name} ===', Ansi.LMAGENTA)
            loop.close()

            if __should_restart:
                log('=== Server restarting ===', Ansi.LMAGENTA)
                os.execv(sys.executable, [sys.executable] + sys.argv)
