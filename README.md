# Generic multipurpose library for the average cmyui (and alike)

## The good stuff

- Asynchronous TCP server (parses ur headers and args and multipart and stuff)
- (A)synchronous mysql wrapper (fetch(all), execute, iterall, more if anyone cares enough to ask?)
- Fully 2020-november-1st-esque osu! beatmap and replay parsers with super hot context managers (osuapiv2 wrapper coming soon)
- Really simple logging setup with ansi/rgb color support, probably going to get more control in future
- Lots of misc utility functions and classes, mostly for my specific need but seemed pretty generic
- More to come, again, if anyone cares enough to ask?

```py
""" AsyncTCPServer (relatively for the project you're probably taking on if you care about this example) basic example"""

import asyncio
import cmyui

async def handle_conn(conn: cmyui.AsyncConnection) -> None:
    # see the AsyncConnection implementation for
    # details on it's use and methods/attributes.

    # i've provided a simple server example below.

    if 'Host' not in conn.headers:
        await conn.send(400, b'Missing required headers.')
        return

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

"""More docs coming soon?™️"""
```
