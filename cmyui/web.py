# -*- coding: utf-8 -*-

# Domain-based asynchronous server implementation, written from
# sockets, mostly with https://github.com/cmyui/gulag in mind.

import asyncio
import gzip
import http
import importlib
import inspect
import os
import re
import select
import signal
import socket
import sys
import time
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
    'Address',
    'STATUS_LINES',
    'ratelimit',
    'Connection',
    'RouteMap',
    'Domain',
    'Server'
)

STATUS_LINES = {
    c.value: f'HTTP/1.1 {c.value} {c.phrase.upper()}'
    for c in http.HTTPStatus
}

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
        self._keystore = {}
        d = dict(*args, **kwargs)
        for k in d.keys():
            self._keystore[k.lower()] = k
        return super().__init__(*args, **kwargs)

    def __setitem__(self, k, v) -> None:
        self._keystore[k.lower()] = k
        return super().__setitem__(k, v)

    def __getitem__(self, k) -> str:
        k_lower = k.lower()
        if k_lower in self._keystore:
            k = self._keystore[k_lower]
        return super().__getitem__(k)

    def __contains__(self, k: str) -> bool:
        k_lower = k.lower()
        if k_lower in self._keystore:
            k = self._keystore[k_lower]
        return super().__contains__(k)

    def get(self, k, failobj=None) -> Optional[str]:
        k_lower = k.lower()
        if k_lower in self._keystore:
            k = self._keystore[k_lower]
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
        self.resp_headers = {}

    """ Request methods """

    async def parse_headers(self, data: str) -> None:
        # Retrieve the http request line.
        delim = data.find('\r\n')

        req_line = data[:delim]

        # Make sure request line is properly formatted.
        if not (m := req_line_re.match(req_line)):
            log(f'Invalid request line ({req_line})', Ansi.LRED)
            return

        # cmd & httpver are fine as-is
        self.cmd = m['cmd']
        self.httpver = float(m['httpver'])

        # There may be params in the path, they
        # will be removed once the body is read.
        self.path = m['path']

        # Parse the headers into our class.
        for header_line in data[delim + 2:].split('\r\n'):
            if len(split := header_line.split(':', 1)) != 2:
                log(f'Invalid header ({header_line})', Ansi.LRED)
                continue

            # normalize header capitalization
            # https://github.com/cmyui/cmyui_pkg/issues/3
            self.headers[split[0].title()] = split[1].lstrip()

        if m['args']: # parse args from url path
            for param_line in m['args'][1:].split('&'):
                if len(param := param_line.split('=', 1)) != 2:
                    log(f'Invalid path arg ({param_line})', Ansi.LRED)
                    continue

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
                    log(f'Invalid multipart header ({header})', Ansi.LRED)
                    continue

                headers[split[0]] = split[1].lstrip()

            if 'Content-Disposition' not in headers:
                log('Invalid multipart headers (no content-disposition)', Ansi.LRED)
                continue

            attrs = {}
            for attr in headers['Content-Disposition'].split(';')[1:]:
                if len(split := attr.split('=', 1)) != 2:
                    log(f'Invalid multipart attr ({attr})', Ansi.LRED)
                    continue

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
                content_type = self.headers['Content-Type']
                if content_type.startswith('multipart/form-data'):
                    await self.parse_multipart()

    """ Response methods """

    async def send(self, status: int, body: bytes = b'') -> None:
        """Attach appropriate headers and send data back to the client."""
        # Insert HTTP response line & content at the beginning of headers.
        header_lines = [STATUS_LINES[status]]

        if body: # Add content-length header if we are sending a body.
            header_lines.append(f'Content-Length: {len(body)}')

        # Add all user-specified response headers.
        header_lines.extend(map(': '.join, self.resp_headers.items()))

        # Create an encoded response from the headers.
        resp = ('\r\n'.join(header_lines) + '\r\n\r\n').encode()

        # Add body to response if we have one to send.
        if body:
            resp += body

        # Send all data to the client.
        loop = asyncio.get_running_loop()
        try:
            await loop.sock_sendall(self.client, resp)
        except BrokenPipeError: # TODO: detect this earlier?
            log('Connection closed by client.', Ansi.LRED)

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
        """Check if a given path & method match internals."""
        return method in self.methods and self.cond(path)

class RouteMap:
    """A collection of endpoints of a domain."""
    __slots__ = ('routes',)
    def __init__(self) -> None:
        self.routes = set() # {Route(), ...}

    def route(self, path: Hostname_Types,
              methods: list[str] = ['GET']) -> Callable:
        """Add a given route to the routemap."""
        if not isinstance(path, (str, Iterable, re.Pattern)):
            raise TypeError('Route should be str | Iterable[str] | re.Pattern')

        def wrapper(handler: Coroutine) -> Coroutine:
            self.routes.add(Route(path, methods, handler))
            return handler

        return wrapper

    def find_route(self, path: str, method: str) -> Optional[Route]:
        """Find the first route matching a given path & method."""
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
        """Check if a given hostname matches our condition."""
        return self.cond(hostname)

    def add_map(self, rmap: RouteMap) -> None:
        """Add an existing routemap to our domain."""
        self.routes |= rmap.routes

class Server:
    """An asynchronous multi-domain server."""
    __slots__ = (
        'name', 'max_conns', 'gzip', 'debug',
        'sock_family', 'before_serving', 'after_serving',
        'domains', 'exceptions',
        'tasks', '_task_coros'
    )
    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get('name', 'Server')
        self.max_conns = kwargs.get('max_conns', 5)
        self.gzip = kwargs.get('gzip', 0) # 0-9 valid levels
        self.debug = kwargs.get('debug', False)
        self.sock_family: Optional[socket.AddressFamily] = None

        self.before_serving: Optional[Callable] = None
        self.after_serving: Optional[Callable] = None

        self.domains = kwargs.get('domains', set())
        self.exceptions = 0 # num of exceptions handled

        self.tasks = kwargs.get('tasks', set())
        self._task_coros = kwargs.get('pending_tasks', set()) # coros not yet run

    def set_sock_mode(self, addr: Address) -> None:
        """Determine the type of socket from the address given."""
        is_inet = type(addr) is tuple and len(addr) == 2 and \
                  type(addr[0]) is str and type(addr[1]) is int

        if is_inet:
            self.sock_family = socket.AF_INET
        elif isinstance(addr, str):
            self.sock_family = socket.AF_UNIX
        else:
            raise ValueError('Invalid address.')

    @property
    def using_unix_socket(self) -> bool:
        return self.sock_family is socket.AF_UNIX

    # Domain management

    def add_domain(self, domain: Domain) -> None:
        """Add a domain to the server."""
        self.domains.add(domain)

    def add_domains(self, domains: set[Domain]) -> None:
        """Add multiple domains to the server."""
        self.domains |= domains

    def remove_domain(self, domain: Domain) -> None:
        """Remove a domain from the server."""
        self.domains.remove(domain)

    def remove_domains(self, domains: set[Domain]) -> None:
        """Remove multiple domains from the server."""
        self.domains -= domains

    def find_domain(self, hostname: str):
        """Find the first domain matching a given hostname."""
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
            if isinstance(resp, tuple):
                # code explicitly given
                code, resp = resp
            else:
                # use 200 as default
                code, resp = (200, resp)

            # gzip responses larger than a single ethernet frame
            # if it's enabled server-side and client supports it
            if (
                self.gzip > 0 and
                'Accept-Encoding' in conn.headers and
                'gzip' in conn.headers['Accept-Encoding'] and
                len(resp) > 1500 # eth frame size (minus headers)
            ):
                # ignore files that're already compressed heavily
                if not (
                    'Content-Type' in conn.resp_headers and
                    conn.resp_headers['Content-Type'] in (
                        # TODO: surely there's more i should be ignoring
                        'image/png', 'image/jpeg'
                    )
                ):
                    resp = gzip.compress(resp, self.gzip)
                    conn.resp_headers['Content-Encoding'] = 'gzip'
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
            log('Connection missing Host header.', Ansi.LRED)
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

    def _default_cb(self, t: asyncio.Task) -> None:
        """A simple callback for tasks to log & call exc handler."""
        if not t.cancelled():
            exc = t.exception()
            if exc and not isinstance(exc, (SystemExit, KeyboardInterrupt)):
                self.exceptions += 1

                loop = asyncio.get_running_loop()
                loop.default_exception_handler({
                    'exception': exc
                })

    def run(
        self, addr: Address,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        handle_restart: bool = True, # using USR1 signal
    ) -> None:
        """Run the server indefinitely."""
        if not loop:
            # no event loop given, check if one's running
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
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

        self.set_sock_mode(addr) # figure out family (INET4/UNIX)

        async def runner() -> None:
            log(f'=== Starting up {self.name} ===', Ansi.LMAGENTA)
            loop = asyncio.get_running_loop()

            # Call our before_serving coroutine,
            # if theres one specified.
            if self.before_serving:
                await self.before_serving()

            # Start pending coroutine tasks.
            if self.debug:
                log(f'-> Starting {len(self._task_coros)} tasks.', Ansi.LMAGENTA)

            for coro in self._task_coros:
                task = loop.create_task(coro)
                task.add_done_callback(self._default_cb) # XXX: never removed?
                self.tasks.add(task)

            self._task_coros.clear()

            # Setup socket & begin listening

            if self.using_unix_socket:
                if os.path.exists(addr):
                    os.remove(addr)

            # read/write signal listening socks
            sig_rsock, sig_wsock = os.pipe()
            os.set_blocking(sig_wsock, False)
            signal.set_wakeup_fd(sig_wsock)

            # connection listening sock
            lsock = socket.socket(self.sock_family)
            lsock.setblocking(False)

            lsock.bind(addr)
            if self.using_unix_socket:
                os.chmod(addr, 0o777)

            lsock.listen(self.max_conns)
            log(f'-> Listening @ {addr}', AnsiRGB(0x00ff7f))

            # TODO: terminal input support (tty, termios fuckery)
            # though, tbh this should be moved into gulag as it's
            # mostly a gulag-specific thing, and it'll be easier
            # to manage all the printing stuff that way.

            should_close = False
            should_restart = False

            while True:
                await asyncio.sleep(0.01) # skip loop iteration
                rlist, _, _ = select.select([lsock, sig_rsock], [], [], 0)

                for reader in rlist:
                    if reader is lsock:
                        # new connection received for server
                        client, _ = await loop.sock_accept(lsock)
                        task = loop.create_task(self.handle(client))
                        task.add_done_callback(self._default_cb)
                    elif reader is sig_rsock:
                        # received a blocked signal, shutdown
                        sig_received = signal.Signals(os.read(sig_rsock, 1)[0])
                        if sig_received is signal.SIGINT:
                            print('\x1b[2K', end='\r') # clear ^C from console
                        elif sig_received is signal.SIGUSR1:
                            should_restart = True
                        log(f'Received {signal.strsignal(sig_received)}', Ansi.LRED)
                        should_close = True
                    else:
                        raise RuntimeError(f'Unknown reader {reader}')

                if should_close:
                    break

            # server closed, clean things up.
            for sock_fd in {lsock.fileno(), sig_rsock, sig_wsock}:
                os.close(sock_fd)

            signal.set_wakeup_fd(-1)

            if self.using_unix_socket:
                os.remove(addr)

            log('-> Cancelling tasks', Ansi.LMAGENTA)
            for task in self.tasks:
                task.cancel()

            await asyncio.gather(*self.tasks, return_exceptions=True)

            if in_progress := [t for t in asyncio.all_tasks()
                               if t is not asyncio.current_task()]:
                try:
                    # allow up to 5 seconds for in-progress handlers
                    # to finish their execution, just incase they're
                    # in a half-complete state. we wouldn't want to
                    # get any sql tables into a weird state, or alike.
                    log(f'-> Awaiting {len(in_progress)} '
                        'in-progress handler(s).', Ansi.LMAGENTA)
                    await asyncio.wait(in_progress, loop=loop, timeout=5.0)
                except asyncio.TimeoutError:
                    log('-> Timed out awaiting handlers, cancelling them.', Ansi.LMAGENTA)
                    to_await = []
                    for task in in_progress:
                        if not task.cancelled():
                            task.cancel()
                            to_await.append(task)
                    await asyncio.gather(*to_await, return_exceptions=True)

            if self.after_serving:
                await self.after_serving()

            return should_restart

        # ignore any signal events in the code, the selector loop will
        # pick up on signals from the fd being awoken from set_wakeup_fd.
        def _sighandler_noop(signum, frame):
            pass

        signals = {signal.SIGINT, signal.SIGTERM, signal.SIGHUP}

        if handle_restart:
            signals.add(signal.SIGUSR1)

        for sig in signals:
            signal.signal(sig, _sighandler_noop)

        def _runner_cb(fut: asyncio.Future) -> None:
            if not fut.cancelled():
                exc = fut.exception()
                if exc and not isinstance(exc, (SystemExit, KeyboardInterrupt)):
                    loop.default_exception_handler({
                        'exception': exc
                    })

            loop.stop()

        """ run the event loop """
        future = asyncio.ensure_future(runner(), loop=loop)
        future.add_done_callback(_runner_cb)

        try:
            loop.run_forever()
        finally:
            future.remove_done_callback(_runner_cb)
            loop.close()

            log(f'=== Shut down {self.name} ===', Ansi.LMAGENTA)

            should_restart = future.result()

            if should_restart:
                log('=== Server restarting ===', Ansi.LMAGENTA)
                os.execv(sys.executable, [sys.executable] + sys.argv)
