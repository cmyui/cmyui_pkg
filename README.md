# Generic multipurpose library for the average cmyui (and alike)

## The good stuff

- Async multi-domain http server & sql wrapper
- Simple logging utilities, for printing in colour w/ timestamps.
- osu! tools, such as replay and beatmap parsers, and more.
- Simple discord webhook wrapper, likely going to grow into more.

```py
# Example of how to use some of the stuff.

import asyncio
import time
import re
from typing import NoReturn
from typing import Optional

from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import Rainbow
from cmyui.logging import RGB
from cmyui.mysql import AsyncSQLPool
from cmyui.version import Version
from cmyui.utils import rstring
from cmyui.web import Connection
from cmyui.web import Domain
from cmyui.web import Server
from pathlib import Path

version = Version(1, 0, 3)
debug = True

sql: Optional[AsyncSQLPool] = None
players = [just imagine this is a list with
           player objects on a game server]

# server has built-in gzip compression support,
# simply pass the level you'd like to use (1-9).
app = Server(name=f'Gameserver v{version}',
             gzip=4, verbose=debug)

# usually, domains are defined externally in
# other files, generally in a 'domains' folder.
domain1 = Domain('osu.ppy.sh')
domain2 = Domain('cmyui.codes')

# domains can then have their routes defined
# in similar syntax to many other popular web
# frameworks. these domains can be defined
# either with a plaintext url route, or using
# regular expressions, allowing for much
# greater complexity.
@domain1.route('/ingame/getfriends.php')
async def ingame_getfriends(conn: Connection) -> Optional[bytes]:
    if 'token' not in conn.headers:
        # returning a tuple of (int, bytes) allows
        # for customization of the return code.
        return (400, b'Bad Request')

    token = conn.headers['token']

    global players
    if not token in conn.headers:
        return (401, b'Unauthorized')

    # returning bytes alone will simply use 200.
    return '\n'.join(players[token].friends).encode()

# methods can be specified as a list in the route definition
@domain1.route('/ingame/screenshot.php', methods=['POST'])
async def ingame_screenshot(conn: Connection) -> Optional[bytes]:
    if 'token' not in conn.headers or 'ss' not in conn.files:
        return (400, b'Bad Request')

    token = conn.headers['token']

    global players
    if not token in conn.headers:
        return (401, b'Unauthorized')

    p = players[token]
    ss_file = Path.cwd() / 'ss' / rstring(8)

    with open(ss_file, 'wb') as f:
        f.write(conn.files['ss'])

    # there are three colour options available,
    log(f'{p!r} uploaded {ss_file}.', Ansi.LBLUE)
    log(f'{p!r} uploaded {ss_file}.', RGB(0x77ffdd))
    log(f'{p!r} uploaded {ss_file}.', Rainbow)

    return b'Uploaded'

@domain2.route(re.compile('^/u/(?P<id>\d{1,10}$'))
async def user_profile(conn: Connection) -> Optional[bytes]:
    ... # TODO: templates implementation?

# finally, the domains themselves
# can be added to the server object.
app.add_domains({domain1, domain2})

# and the server allows for any number
# of async callables to be enqueued as
# tasks once the server is started up.
async def on_start():
    # this should probably be
    # in a config somewhere lol
    sql_info = {
        'db': 'cmyui',
        'host': 'localhost',
        'password': 'lol123',
        'user': 'cmyui'
    }

    global sql
    sql = AsyncSQLPool()
    await sql.connect(sql_info)

async def disconnect_inactive_players() -> NoReturn:
    ping_timeout = 120
    global players

    while True:
        for p in players:
            if time.time() - p.last_recv_time > ping_timeout:
                await p.logout()

        await asyncio.sleep(ping_timeout)

app.add_task(on_start())
app.add_tasks({on_start(), disconnect_inactive_players()})

# both inet & unix sockets are supported.
server_addr = ('127.0.0.1', 5001)  # inet4
server_addr = '/tmp/myserver.sock' # unix

# then, the server can be run; this is a blocking
# call after which the server will indefinitely
# continue to listen for and handle connections.
app.run(server_addr)

# and voila, you have an async server. the server
# will use uvloop if you have it installed; if you
# don't know about the project, consider checking
# out https://github.com/MagicStack/uvloop.

# cheers B)
